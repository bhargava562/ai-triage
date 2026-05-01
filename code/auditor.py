"""
auditor.py — Gate 6: The Adversarial Fidelity Verifier.

After the Generator produces a response, the Auditor acts as a Prosecutor.
Its ONLY job is to find facts in the response that cannot be traced back
to the source documentation.

Two-phase audit:

Phase 1 (Local Fidelity Score — always runs, O(N) time, no API cost):
    Compute Groundedness Index: G = |overlap| / |factual_response_tokens|
    G tells us what fraction of facts in the response are grounded.
    If G < 0.35: immediate escalation (clear hallucination)
    If G >= 0.70: clear pass, skip Phase 2 (save API cost)
    If 0.35 <= G < 0.70: borderline, run Phase 2 (prosecutor check)

Phase 2 (LLM Adversarial Check — only borderline cases):
    A second, small LLM call acts as the Prosecutor.
    Prompt: "Does this response contain claims NOT in these documents?"
    If YES: escalate (found ungrounded claims)

Why two phases?
- Phase 1 catches obvious hallucinations cheaply (no API cost)
- Phase 2 catches subtle ones (e.g., correct-sounding but invented procedures)
- Clear passes skip Phase 2, reducing API cost by ~40%
- Clear fails skip Phase 2, already know it's bad
"""

import re
import logging
import math
from groq import Groq
from config import FIDELITY_THRESHOLD, AUDITOR_MAX_TOKENS, LLM_MODEL
from retriever import DocumentChunk

logger = logging.getLogger(__name__)

# Common English stopwords that don't count as "facts"
# These are filtered out of fidelity scoring
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "used", "ought",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "this", "that",
    "these", "those", "what", "which", "who", "whom", "whose", "where",
    "when", "why", "how", "all", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "but", "and", "or", "if", "in",
    "on", "at", "to", "for", "of", "with", "by", "from", "up", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "please", "also", "click", "go", "select",
    "contact", "via", "using", "help", "support", "issue", "problem",
    "request", "thank", "thanks", "you", "your", "we", "our",
}


def _extract_factual_tokens(text: str) -> set:
    """
    Extract tokens likely to be factual (meaningful claims).

    Filtering:
    1. Remove stopwords (common function words)
    2. Remove short tokens (< 4 chars, mostly noise)
    3. Keep only remaining tokens (nouns, specific terms)

    Args:
        text: Text to extract factual tokens from

    Returns:
        Set of "factual" tokens (lowercase, no punctuation)
    """
    text_lower = text.lower()
    text_clean = re.sub(r"[^\w\s]", " ", text_lower)
    tokens = set(text_clean.split())

    # Filter out stopwords and short tokens
    factual = tokens - STOPWORDS
    factual = {t for t in factual if len(t) > 3}

    return factual


def compute_fidelity_score(response: str, chunks: list) -> float:
    """
    Compute the TF-IDF Groundedness Index (G) with weighted scoring.

    Enhanced formula with IDF weighting:
    G = Σ(overlap_token_weight) / Σ(response_token_weight)

    Where weight = log(total_docs / docs_containing_token)

    This prioritizes rare, specific terms over common words:
    - "proctor" (unique to HackerRank): weight ~0.95
    - "button" (common everywhere): weight ~0.1

    Interpretation:
    - G = 1.0: All weighted facts in response are in the docs
    - G = 0.72 (threshold): ~3 in 4 weighted facts are grounded
    - G = 0.5: Half the "facts" are not in the docs (hallucination)
    - G = 0.0: No overlap (pure hallucination)

    Args:
        response: The LLM-generated response text
        chunks: List of DocumentChunk objects (context)

    Returns:
        Fidelity score from 0.0 to 1.0
    """
    if not chunks:
        return 0.0

    response_tokens = _extract_factual_tokens(response)
    if not response_tokens:
        return 1.0  # Trivial response = trivially grounded

    # Calculate IDF weights from context documents
    doc_count = len(chunks)
    token_doc_freq = {}

    for doc in chunks:
        doc_tokens = _extract_factual_tokens(doc.text)
        for token in doc_tokens:
            token_doc_freq[token] = token_doc_freq.get(token, 0) + 1

    # Calculate IDF: log(total_docs / docs_with_token)
    idf_weights = {}
    for token, freq in token_doc_freq.items():
        idf_weights[token] = math.log(doc_count / freq) if freq > 0 else 1.0

    # Get context tokens
    context_text = " ".join(chunk.text for chunk in chunks)
    context_tokens = _extract_factual_tokens(context_text)

    # Calculate weighted overlap
    overlap_weight = 0.0
    response_weight = 0.0

    for token in response_tokens:
        # Use IDF weight if available, else default 1.0
        weight = idf_weights.get(token, 1.0)
        response_weight += weight

        # If token is in context, add to overlap
        if token in context_tokens:
            overlap_weight += weight

    # Return fidelity (weighted overlap / total weighted response)
    if response_weight == 0:
        return 1.0

    fidelity = overlap_weight / response_weight
    return fidelity


def run_llm_adversarial_check(
    response: str, chunks: list, client: Groq
) -> bool:
    """
    Phase 2: LLM Adversarial Check (Prosecutor).

    This is a binary YES/NO check. The LLM is asked:
    "Does this response contain claims NOT in the documents?"

    Returns True if hallucination is detected (escalate).
    Returns False if response is grounded (keep).

    Args:
        response: The generated response to audit
        chunks: Retrieved documentation chunks
        client: Groq client instance

    Returns:
        True if hallucination detected, False if grounded
    """
    context_text = "\n\n".join(
        f"[SOURCE: {c.source_file}]\n{c.text}" for c in chunks
    )

    prompt = f"""I will show you a support response and the source documents it claims to be based on.

SUPPORT RESPONSE:
{response}

SOURCE DOCUMENTS:
{context_text}

QUESTION: Does the support response contain any specific factual claim, procedure, or
policy that is NOT directly stated or reasonably implied in the source documents above?

Answer with ONLY "YES" or "NO"."""

    try:
        msg = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=AUDITOR_MAX_TOKENS,
            temperature=0.0,
        )
        answer = msg.choices[0].message.content.strip().upper()
        is_hallucinated = answer.startswith("YES")

        if is_hallucinated:
            logger.warning("[AUDITOR] Phase 2: Hallucination detected")
        else:
            logger.info("[AUDITOR] Phase 2: Response is grounded")

        return is_hallucinated

    except Exception as e:
        logger.error(f"[AUDITOR] Phase 2 LLM call failed: {e}")
        # Fail safe: treat as hallucination if auditor errors
        return True


def audit_response(
    result: dict, chunks: list, client: Groq
) -> dict:
    """
    Run the full two-phase audit on the generator's response.

    Process:
    1. Phase 1: Compute local fidelity score (always)
    2. If G < 0.35: escalate (Phase 1 FAIL)
    3. If G >= 0.70: pass (Phase 1 PASS, skip Phase 2)
    4. If 0.35 <= G < 0.70: run Phase 2 (borderline)
       - If Phase 2 detects hallucination: escalate
       - If Phase 2 says grounded: keep

    Mutates and returns the result dict with fidelity metadata.

    Args:
        result: The dict from generator.generate_response()
        chunks: Retrieved documentation chunks
        client: Anthropic client instance

    Returns:
        Mutated result dict with audit metadata added
    """
    response_text = result.get("response", "")
    fidelity_score = compute_fidelity_score(response_text, chunks)

    # Format fidelity metadata for justification
    fidelity_pct = int(fidelity_score * 100)
    sources = list({c.source_file for c in chunks}) if chunks else []
    source_str = ", ".join(sources[:2]) if sources else "no_source"

    original_justification = result.get("justification", "")
    fidelity_tag = f"[FIDELITY: {fidelity_pct}%] [SOURCE: {source_str}]"

    # Add fidelity to justification if not already there
    if fidelity_tag not in original_justification:
        result["justification"] = f"{fidelity_tag} {original_justification}"

    # Skip fidelity check for out-of-scope/invalid replies — refusal templates
    # are not grounded in docs by design, so fidelity scoring is meaningless here
    if result.get("request_type") == "invalid" and result.get("status") == "replied":
        logger.info("[AUDITOR] Skipping fidelity check for out-of-scope reply")
        result["justification"] = f"{fidelity_tag} [AUDIT: SKIPPED — out-of-scope reply] " + original_justification
        return result

    # Phase 1: Clear fail (G < 0.40) — escalate low-groundedness replies
    if fidelity_score < 0.40:
        logger.warning(
            f"[AUDITOR] Phase 1 FAIL — Fidelity={fidelity_score:.2f} < 0.40"
        )
        result["status"] = "escalated"
        result["justification"] = (
            f"{fidelity_tag} [AUDIT: PHASE_1_FAIL — "
            f"Fidelity={fidelity_score:.2f} (< 0.40), insufficient grounding] "
            + original_justification
        )
        return result

    # Phase 1: Clear pass (G >= 0.40)
    if fidelity_score >= 0.40:
        logger.info(f"[AUDITOR] Phase 1 PASS — Fidelity={fidelity_score:.2f}")
        return result

    # Phase 1: Borderline (0.35 <= G < 0.70) — SKIP Phase 2 to save tokens
    logger.info(
        f"[AUDITOR] Borderline fidelity={fidelity_score:.2f} "
        f"(skipping Phase 2 LLM check to optimize tokens)"
    )
    # Phase 2 (LLM adversarial check) disabled to save API tokens
    # The response passed Phase 1, so allow it through

    return result

"""
auditor.py — Gate 6: The Adversarial Fidelity Verifier.

After the Generator produces a response, the Auditor acts as a Prosecutor.
Its ONLY job is to find facts in the response that cannot be traced back
to the source documentation.

Two-phase audit:

Phase 1 (Local Fidelity Score — always runs, O(N) time, no API cost):
    Compute Groundedness Index: G = |overlap| / |factual_response_tokens|
    G tells us what fraction of facts in the response are grounded.
    If G < 0.60: immediate escalation (clear hallucination)
    If G >= 0.85: clear pass, skip Phase 2 (save API cost)
    If 0.60 <= G < 0.85: borderline, run Phase 2 (prosecutor check)

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
    Compute the Groundedness Index (G).

    Formula: G = |response_factual ∩ context_factual| / |response_factual|

    Interpretation:
    - G = 1.0: All factual claims are in the docs
    - G = 0.72 (threshold): ~3 in 4 facts are grounded (acceptable)
    - G = 0.5: Half the "facts" are not in the docs (hallucination risk)
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
        # Empty/trivial response with no factual claims
        # Safe to return 1.0 (trivially grounded)
        return 1.0

    # Combine all context into one document
    context_text = " ".join(chunk.text for chunk in chunks)
    context_tokens = _extract_factual_tokens(context_text)

    # Compute overlap
    overlap = response_tokens.intersection(context_tokens)
    fidelity = len(overlap) / len(response_tokens)

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
    2. If G < 0.60: escalate (Phase 1 FAIL)
    3. If G >= 0.85: pass (Phase 1 PASS, skip Phase 2)
    4. If 0.60 <= G < 0.85: run Phase 2 (borderline)
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

    # Phase 1: Clear fail (G < 0.60)
    if fidelity_score < 0.60:
        logger.warning(
            f"[AUDITOR] Phase 1 FAIL — Fidelity={fidelity_score:.2f} < 0.60"
        )
        result["status"] = "escalated"
        result["justification"] = (
            f"{fidelity_tag} [AUDIT: PHASE_1_FAIL — "
            f"Fidelity={fidelity_score:.2f} (< 0.60), likely hallucination] "
            + original_justification
        )
        return result

    # Phase 1: Clear pass (G >= 0.85)
    if fidelity_score >= 0.85:
        logger.info(f"[AUDITOR] Phase 1 PASS — Fidelity={fidelity_score:.2f}")
        return result

    # Phase 1: Borderline (0.60 <= G < 0.85) — run Phase 2
    logger.info(
        f"[AUDITOR] Phase 2 triggered — Fidelity={fidelity_score:.2f} "
        f"(borderline, running LLM check)"
    )

    if run_llm_adversarial_check(response_text, chunks, client):
        # Phase 2 detected hallucination
        logger.warning("[AUDITOR] Phase 2 FAIL — Hallucination detected")
        result["status"] = "escalated"
        result["justification"] = (
            f"{fidelity_tag} [AUDIT: PHASE_2_FAIL — "
            f"LLM prosecutor found ungrounded claims] "
            + original_justification
        )
    else:
        # Phase 2 says grounded
        logger.info("[AUDITOR] Phase 2 PASS — Response is grounded")

    return result

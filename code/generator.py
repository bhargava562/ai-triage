"""
generator.py — Gate 5: Grounded LLM Response Generator.

This is the ONLY place in the entire pipeline where the LLM is invoked
for response generation. All calls are carefully orchestrated:

1. System prompt uses the "Zero-Knowledge Mandate" — model MUST cite or escalate
2. Context is injected as labeled sections with source attribution
3. Output is structured JSON for reliable parsing (no regex extraction)
4. Temperature = 0 for deterministic, reproducible output
5. Fallback: if JSON parsing fails, escalate (don't hallucinate)

The system prompt is designed to make hallucination costly and escalation
rewarding. The LLM is never in a position to make up facts.
"""

import json
import logging
from typing import Optional
from groq import Groq
from config import LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE
from retriever import DocumentChunk

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a forensic support triage auditor. Your ONLY job is to
classify and respond to support tickets using EXCLUSIVELY the documentation
I provide. You have NO prior knowledge about these companies.

ZERO-KNOWLEDGE MANDATE: If the answer to a question is NOT explicitly stated
in the provided documentation, you MUST set status to "escalated".
You may NEVER invent policies, procedures, or factual claims.

OUT-OF-SCOPE QUESTIONS:
If a question is clearly out of scope (e.g., movie trivia, personal life advice,
random information requests), respond with:
  status: "replied"
  response: "I'm a support agent for [Company]. Your question is outside my scope
            of support. Please contact the appropriate support team or service."
  request_type: "invalid"

ESCALATION CRITERIA (set status="escalated" if ANY are true):
- The answer requires information not in the provided documentation
- The request involves billing disputes, refunds, or financial claims
- The request involves fraud, security, or identity-sensitive matters
- The request contains unreasonable demands (e.g. "increase my score", "ban this seller")
- The ticket is in a non-English language
- The company cannot be determined from the documentation
- The request requires an admin to take action on behalf of the user (not self-service)

REPLY CRITERIA (set status="replied" if ALL are true):
- A clear, direct answer exists in the provided documentation
- The answer does not involve financial transactions or fraud
- The request is self-service (the user can follow the steps themselves)

OUTPUT FORMAT: Respond ONLY with a valid JSON object on a single line.
No preamble, no explanation, no markdown code fences.

JSON Schema:
{
  "status": "replied" | "escalated",
  "product_area": "<support_category_lowercase_snake_case>",
  "response": "<user-facing response grounded in the documentation>",
  "justification": "<reasoning for the classification>",
  "request_type": "product_issue" | "feature_request" | "bug" | "invalid",
  "confidence": <float_0_to_1>
}"""


def build_context_block(chunks: list) -> str:
    """
    Build the context injection string from retrieved chunks.

    Format:
        [DOCUMENT N] Source: file_path
        <chunk_text>
        [END DOCUMENT N]

    Each chunk is clearly labeled so the LLM knows what it's working with.

    Args:
        chunks: List of DocumentChunk objects from retriever

    Returns:
        Formatted context string ready for injection
    """
    if not chunks:
        return "NO DOCUMENTATION RETRIEVED FOR THIS QUERY."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[DOCUMENT {i}] Source: {chunk.source_file}\n"
            f"{chunk.text}\n"
            f"[END DOCUMENT {i}]"
        )
    return "\n\n".join(context_parts)


def generate_response(
    issue: str,
    company: str,
    chunks: list,
    is_hard_routed: bool,
    client: Groq,
) -> dict:
    """
    Generate a grounded response using the LLM.

    Workflow:
    1. Build context from retrieved chunks
    2. Construct user message with company context and documentation
    3. Call Groq with system + user messages
    4. Parse JSON response
    5. Fallback to safe escalation on any error

    Args:
        issue: The support ticket issue text
        company: Company this ticket was routed to
        chunks: Retrieved documentation chunks
        is_hard_routed: Whether company was high-confidence (no LLM check needed)
        client: Groq client instance

    Returns:
        Parsed dict with keys: status, product_area, response, justification,
        request_type, confidence
    """
    context = build_context_block(chunks)
    company_instruction = (
        f"The ticket is for {company}."
        if is_hard_routed
        else (
            f"The ticket APPEARS to be for {company} based on keyword analysis. "
            f"Confirm or correct this from the documentation."
        )
    )

    user_message = f"""SUPPORT TICKET:
{issue}

COMPANY CONTEXT: {company_instruction}

RETRIEVED DOCUMENTATION:
{context}

Now classify this ticket and generate a response using ONLY the above documentation.
Remember: if you cannot find a direct answer in the documentation, set status="escalated"."""

    try:
        message = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
        )

        raw_text = message.choices[0].message.content.strip()

        # Strip any accidental markdown code fences or extra whitespace
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        # Parse JSON
        result = json.loads(raw_text)

        # Validate required fields are present
        required_fields = {"status", "product_area", "response", "justification",
                          "request_type", "confidence"}
        if not all(field in result for field in required_fields):
            logger.warning(f"[GENERATOR] Missing required fields in response")
            return _safe_escalation("GENERATOR_MISSING_FIELDS")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"[GENERATOR] JSON parse error: {e}")
        return _safe_escalation(f"LLM_PARSE_ERROR")

    except Exception as e:
        logger.error(f"[GENERATOR] Groq API error: {e}")
        return _safe_escalation(f"API_ERROR")


def _safe_escalation(reason: str) -> dict:
    """
    Fallback response when generation fails.

    Better to escalate than to return a corrupted response.

    Args:
        reason: Description of what went wrong

    Returns:
        Safe escalation dict
    """
    return {
        "status": "escalated",
        "product_area": "general_support",
        "response": (
            "We were unable to process your request at this time. "
            "A human agent will follow up shortly."
        ),
        "justification": f"[SYSTEM_ESCALATION] {reason}",
        "request_type": "product_issue",
        "confidence": 0.0,
    }

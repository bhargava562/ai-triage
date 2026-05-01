"""
agent.py — The 6-Gate Pipeline Orchestrator.

This is the "brain" of the system. It receives one ticket at a time
and runs it through gates sequentially, short-circuiting early
whenever a deterministic decision can be made.

Gate Summary:
  Gate 1: Trivial / Ambiguous Filter      → local, no API
  Gate 2: Safety Shield                   → local, no API
  Gate 3: Brand DNA Router                → local, no API
  Gate 4: BM25 Corpus Retriever           → local, no API
  Gate 5: Grounded LLM Generator         → 1 API call
  Gate 6: Adversarial Fidelity Auditor   → 0-1 API calls (conditional)

Total API calls per ticket: typically 1-2.
Average expected: ~1.3 calls per ticket (10% need Phase 2 auditor).
"""

import re
import time
import logging
from groq import Groq
from dataclasses import dataclass
from typing import Optional

from config import TRIVIAL_PATTERNS, AMBIGUOUS_TICKET_MIN_WORDS
from safety import run_safety_gate
from router import route_company
from retriever import CorpusRetriever
from generator import generate_response
from auditor import audit_response

logger = logging.getLogger(__name__)


@dataclass
class TicketResult:
    """Result of processing a single ticket through the pipeline."""

    # Required output fields for CSV
    status: str = "escalated"
    product_area: str = "general_support"
    response: str = ""
    justification: str = ""
    request_type: str = "product_issue"

    # Pipeline metadata (for logging, not written to CSV)
    gate_stopped: int = 0  # Which gate made the final decision
    processing_time_ms: float = 0
    api_calls_made: int = 0
    brand_confidence: float = 0.0


class ForensicTriageAgent:
    """The main triage agent. Orchestrates all 6 gates."""

    def __init__(self):
        """Initialize agent with Groq client and BM25 retriever."""
        self.client = Groq()  # Reads GROQ_API_KEY from env
        self.retriever = CorpusRetriever()   # Builds BM25 index at startup
        logger.info(
            f"[AGENT] Initialized with {len(self.retriever.chunks)} chunks"
        )

    def process_ticket(
        self, issue: str, subject: str, company: str
    ) -> TicketResult:
        """
        Run a single ticket through all 6 gates.

        Returns: TicketResult with all required output fields populated.

        Args:
            issue: The support ticket issue/body text
            subject: The ticket subject line
            company: The company field from CSV (may be empty or wrong)

        Returns:
            TicketResult with status, product_area, response, etc.
        """
        start = time.time()
        result = TicketResult()
        full_text = f"{subject} {issue}".strip() if subject else issue

        # ──────────────────────────────────────────────────────────
        # GATE 1: Trivial / Ambiguous Filter
        # ──────────────────────────────────────────────────────────
        if self._is_trivial(issue):
            result.status = "replied"
            result.request_type = "invalid"
            result.product_area = "general"
            result.response = (
                "This request is out of scope or lacks sufficient detail. "
                "How can I assist you further?"
            )
            result.justification = (
                "[GATE_1] Trivial or ambiguous ticket — "
                "insufficient content for triage."
            )
            result.gate_stopped = 1
            result.processing_time_ms = (time.time() - start) * 1000
            logger.info(f"[GATE_1] Trivial ticket detected, escalating")
            return result

        # ──────────────────────────────────────────────────────────
        # GATE 2: Safety Shield
        # ──────────────────────────────────────────────────────────
        safety = run_safety_gate(full_text)
        if not safety.is_safe:
            result.status = "escalated"
            result.request_type = "product_issue"
            result.product_area = "safety_escalation"

            if safety.is_injection:
                result.response = (
                    "We detected patterns in this request that cannot be processed "
                    "through automated support. A human agent will review your case."
                )
                result.justification = (
                    f"[GATE_2] [PROMPT_INJECTION] Adversarial input pattern detected. "
                    f"Language: {safety.detected_language}."
                )
            else:
                result.response = (
                    "Your request has been escalated to our specialized support team. "
                    "A human agent will contact you shortly."
                )
                result.justification = (
                    f"[GATE_2] [SAFETY_TRIGGER: {safety.trigger_label}] "
                    f"Policy-based escalation."
                )

            result.gate_stopped = 2
            result.processing_time_ms = (time.time() - start) * 1000
            logger.info(f"[GATE_2] Safety trigger: {safety.trigger_label}")
            return result

        # ──────────────────────────────────────────────────────────
        # GATE 3: Brand DNA Router
        # ──────────────────────────────────────────────────────────
        routed_company, confidence, is_hard_routed = route_company(
            full_text, company
        )
        result.brand_confidence = confidence
        logger.info(
            f"[GATE_3] Company: {routed_company} "
            f"(confidence: {confidence:.2f}, hard_routed: {is_hard_routed})"
        )

        # Company undeterminable — escalate
        if routed_company == "None" and not company:
            result.status = "escalated"
            result.request_type = "invalid"
            result.product_area = "cross_domain"
            result.response = (
                "We were unable to determine which product this request belongs to. "
                "Please contact the relevant support team directly."
            )
            result.justification = (
                "[GATE_3] Brand DNA score below minimum threshold. "
                "Company undeterminable."
            )
            result.gate_stopped = 3
            result.processing_time_ms = (time.time() - start) * 1000
            return result

        # ──────────────────────────────────────────────────────────
        # GATE 4: BM25 Corpus Retrieval
        # ──────────────────────────────────────────────────────────
        chunks = self.retriever.retrieve(issue, routed_company)
        logger.info(f"[GATE_4] Retrieved {len(chunks)} chunks")

        if not chunks:
            result.status = "escalated"
            result.justification = (
                f"[GATE_4] No relevant documentation found for "
                f"company={routed_company}."
            )
            result.processing_time_ms = (time.time() - start) * 1000
            result.gate_stopped = 4
            return result

        # ──────────────────────────────────────────────────────────
        # GATE 5: LLM Generator
        # ──────────────────────────────────────────────────────────
        gen_result = generate_response(
            issue=issue,
            company=routed_company,
            chunks=chunks,
            is_hard_routed=is_hard_routed,
            client=self.client,
        )
        result.api_calls_made += 1
        logger.info(f"[GATE_5] Response generated, status={gen_result['status']}")

        # ──────────────────────────────────────────────────────────
        # GATE 6: Adversarial Auditor
        # ──────────────────────────────────────────────────────────
        audited = audit_response(gen_result, chunks, self.client)
        # Note: audit_response may call LLM for Phase 2, but we can't easily
        # detect it. Assume it may add an API call if fidelity is borderline.
        # For accurate counting, we'd need to return this from audit_response.
        logger.info(f"[GATE_6] Audit complete, status={audited['status']}")

        # ──────────────────────────────────────────────────────────
        # Populate final result
        # ──────────────────────────────────────────────────────────
        result.status = audited.get("status", "escalated")
        result.product_area = audited.get("product_area", "general_support")
        result.response = audited.get("response", "")
        result.justification = audited.get("justification", "")
        result.request_type = audited.get("request_type", "product_issue")
        result.gate_stopped = 6
        result.processing_time_ms = (time.time() - start) * 1000

        return result

    def _is_trivial(self, text: str) -> bool:
        """
        Gate 1: Check if ticket is trivial or ambiguous.

        Criteria:
        1. Too few words (< AMBIGUOUS_TICKET_MIN_WORDS)
        2. Matches a trivial pattern (e.g., "thank you", "ok", "none")

        Args:
            text: The ticket issue text

        Returns:
            True if ticket is trivial
        """
        stripped = text.strip()

        # Too short
        if len(stripped.split()) < AMBIGUOUS_TICKET_MIN_WORDS:
            logger.debug(f"[GATE_1] Too short: {len(stripped.split())} words")
            return True

        # Matches a trivial pattern
        for pattern in TRIVIAL_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                logger.debug(f"[GATE_1] Matched pattern: {pattern}")
                return True

        return False

"""
safety.py — Gate 2: Radioactive Content Shield + Prompt Injection Detector.

This gate runs BEFORE any LLM call. If it triggers, the ticket is
immediately escalated with status="escalated" and request_type="invalid".
No retrieval, no generation, no auditing occurs.

Design principle: It is safer to over-escalate than to under-escalate.
A false positive is recoverable. A false negative (a fraud ticket
answered with wrong advice) is catastrophic.
"""

import re
import logging
from typing import Optional
from langdetect import detect, LangDetectException
from config import HARD_ESCALATION_TRIGGERS, PROMPT_INJECTION_PATTERNS

logger = logging.getLogger(__name__)


class SafetyResult:
    """Result object from safety gate evaluation."""

    def __init__(
        self,
        is_safe: bool,
        trigger_label: Optional[str] = None,
        is_injection: bool = False,
        detected_language: str = "en",
    ):
        """
        Initialize safety result.

        Args:
            is_safe: Whether the ticket passed all safety checks
            trigger_label: Name of the safety trigger that fired (if any)
            is_injection: Whether this was specifically a prompt injection attempt
            detected_language: Detected language of the ticket
        """
        self.is_safe = is_safe
        self.trigger_label = trigger_label
        self.is_injection = is_injection
        self.detected_language = detected_language


def detect_language(text: str) -> str:
    """
    Detect the language of the input text using langdetect.

    Non-English tickets are not automatically flagged, but they trigger
    additional scrutiny for injection patterns (combined with imperatives).

    Args:
        text: The text to analyze

    Returns:
        Two-letter language code (e.g., "en", "fr", "es") or "unknown"
    """
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def check_prompt_injection(text: str, detected_lang: str) -> bool:
    """
    Check for prompt injection attack patterns.

    Two-phase detection:
    1. Direct pattern matching (applies to all languages)
    2. Secondary check: non-English + instruction imperatives

    The secondary check catches the French ticket attack where the user
    is trying to get the agent to expose its internal retrieval logic.

    Args:
        text: The ticket text
        detected_lang: The detected language

    Returns:
        True if injection pattern is detected
    """
    text_lower = text.lower()

    # Phase 1: Check direct injection patterns
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning(
                f"[INJECTION_DETECTED] Pattern matched in {detected_lang}: "
                f"{pattern[:50]}..."
            )
            return True

    # Phase 2: Non-English + instruction imperatives = high suspicion
    # This catches cases where someone is trying to manipulate the system
    # in a language other than English
    if detected_lang not in ("en", "unknown"):
        instruction_imperatives = [
            r"\b(show|display|reveal|tell|give|print|output|explain|affiche|montre|zeige)\b"
        ]
        for pattern in instruction_imperatives:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.warning(
                    f"[INJECTION_SUSPECTED] Non-English ({detected_lang}) + "
                    f"imperative detected"
                )
                return True

    return False


def run_safety_gate(issue_text: str) -> SafetyResult:
    """
    Run all safety checks on the ticket text.

    Execution order:
    1. Detect language
    2. Check prompt injection (highest priority)
    3. Check hard escalation triggers

    Any match → returns SafetyResult with is_safe=False and appropriate label.
    A ticket that fails safety never reaches the LLM.

    Args:
        issue_text: The full ticket text (subject + issue combined)

    Returns:
        SafetyResult object indicating whether ticket is safe to process
    """
    text_lower = issue_text.lower()
    detected_lang = detect_language(issue_text)

    # Check prompt injection first (highest priority)
    if check_prompt_injection(issue_text, detected_lang):
        return SafetyResult(
            is_safe=False,
            trigger_label="PROMPT_INJECTION_DETECTED",
            is_injection=True,
            detected_language=detected_lang,
        )

    # Check hard escalation triggers (policy-based escalations)
    for pattern, label in HARD_ESCALATION_TRIGGERS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning(f"[SAFETY_TRIGGER] {label}")
            return SafetyResult(
                is_safe=False,
                trigger_label=label,
                is_injection=False,
                detected_language=detected_lang,
            )

    # All checks passed
    return SafetyResult(is_safe=True, detected_language=detected_lang)

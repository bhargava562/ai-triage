"""
router.py — Gate 3: Brand DNA Fingerprinter.

Determines which company a ticket belongs to using deterministic,
weighted keyword scoring (no LLM call needed).

Algorithm:
    For each company DNA map, compute weighted score:
    S_c = Σ(weight_i × count_i) / sqrt(word_count)

    The sqrt(word_count) normalization prevents long tickets from
    artificially inflating scores (saturation effect).

    Return company with highest score and its confidence level.

If confidence >= BRAND_CONFIDENCE_THRESHOLD:
    Hard route (no LLM confirmation needed)
Else if score >= BRAND_SCORE_MIN_THRESHOLD:
    Soft route (return best guess, let LLM confirm)
Else:
    Cannot determine (escalate)
"""

import re
import math
import logging
from typing import Optional, Tuple
from config import (
    VISA_DNA,
    HACKERRANK_DNA,
    CLAUDE_DNA,
    BRAND_CONFIDENCE_THRESHOLD,
    BRAND_SCORE_MIN_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Map company names to their DNA keyword maps
BRAND_DNA_MAP = {
    "Visa": VISA_DNA,
    "HackerRank": HACKERRANK_DNA,
    "Claude": CLAUDE_DNA,
}


def compute_brand_score(text: str, dna: dict) -> float:
    """
    Compute weighted brand affinity score.

    Formula: S = Σ(weight_i × count_i) / sqrt(word_count)

    This gives each keyword-weight pair a score proportional to how
    often it appears, scaled down by document length (prevents gaming
    with repetition).

    Args:
        text: The ticket text to analyze
        dna: A DNA map (keyword -> weight dictionary)

    Returns:
        Raw score (float). Higher = more likely this company
    """
    text_lower = text.lower()
    words = text_lower.split()
    word_count = max(len(words), 1)  # Avoid division by zero

    raw_score = 0.0
    for keyword, weight in dna.items():
        # Count occurrences of multi-word and single-word keywords
        count = len(re.findall(re.escape(keyword), text_lower))
        raw_score += weight * count

    # Normalize by sqrt(word_count) to prevent saturation on long docs
    normalized_score = raw_score / math.sqrt(word_count)
    return normalized_score


def route_company(
    issue_text: str, given_company: Optional[str]
) -> Tuple[str, float, bool]:
    """
    Route a ticket to the appropriate company.

    Returns: (company_name, confidence_score, is_hard_routed)

    is_hard_routed=True means we determined this without LLM
    (confidence is high enough to trust).

    is_hard_routed=False means the LLM should confirm our guess
    (borderline confidence case).

    If given_company is already provided in the CSV and is a valid brand,
    we trust it but still compute a validation score for audit trails.

    Args:
        issue_text: Full ticket text (subject + issue)
        given_company: Company field from CSV (if any)

    Returns:
        Tuple of (company, confidence_0_to_1, is_hard_routed)
    """
    VALID_COMPANIES = {"Visa", "HackerRank", "Claude"}

    # Trust the CSV-provided company if it's in our valid set
    if given_company and given_company.strip() in VALID_COMPANIES:
        company = given_company.strip()
        score = compute_brand_score(issue_text, BRAND_DNA_MAP[company])
        # Boost confidence since it's explicitly declared in CSV
        confidence = min(score + 0.5, 1.0)
        return company, confidence, True

    # Compute scores for all brands
    scores = {
        brand: compute_brand_score(issue_text, dna)
        for brand, dna in BRAND_DNA_MAP.items()
    }

    best_brand = max(scores, key=scores.get)
    best_score = scores[best_brand]

    # Compute relative confidence (0-1 scale)
    # This represents how much better the best match is compared to others
    total = sum(scores.values())
    if total == 0:
        # No keywords found for any brand
        return "None", 0.0, False

    relative_confidence = best_score / total

    # Decision thresholds
    if relative_confidence >= BRAND_CONFIDENCE_THRESHOLD:
        # High confidence — hard route
        return best_brand, relative_confidence, True
    elif best_score >= BRAND_SCORE_MIN_THRESHOLD:
        # Weak but non-negligible signal — return best guess, LLM confirms
        return best_brand, relative_confidence, False
    else:
        # Below minimum threshold — cannot route
        return "None", 0.0, False

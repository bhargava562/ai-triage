"""
config.py — Single Source of Truth for all constants and thresholds.

This file contains NO logic — only data. Changing a threshold here
changes behavior everywhere in the pipeline. All Brand DNA maps,
safety triggers, and pipeline parameters are centralized here.

Usage:
    from config import VISA_DNA, BRAND_CONFIDENCE_THRESHOLD, etc.
"""

# ────────────────────────────────────────────────────────────────────
# LLM CONFIGURATION (GROQ)
# ────────────────────────────────────────────────────────────────────

LLM_MODEL = "llama-3.1-8b-instant"
LLM_MAX_TOKENS = 1024
LLM_TEMPERATURE = 0.0  # Deterministic: always 0 for reproducible triage decisions
AUDITOR_MAX_TOKENS = 256

# ────────────────────────────────────────────────────────────────────
# PIPELINE THRESHOLDS
# ────────────────────────────────────────────────────────────────────

# Brand routing confidence threshold.
# If computed score >= this value, route is hard (no LLM confirmation needed)
BRAND_CONFIDENCE_THRESHOLD = 0.60

# Minimum brand score to attempt routing at all.
# Below this and company=None → immediate escalation
BRAND_SCORE_MIN_THRESHOLD = 0.30

# Fidelity (groundedness) threshold for auditor.
# If computed G < this, ticket is escalated (likely hallucination)
FIDELITY_THRESHOLD = 0.60

# Minimum word count for non-trivial tickets.
# Below this word count → Gate 1 marks as "invalid"
AMBIGUOUS_TICKET_MIN_WORDS = 4

# ────────────────────────────────────────────────────────────────────
# BRAND DNA MAPS
# ────────────────────────────────────────────────────────────────────
# Keywords mapped to weights reflecting how uniquely identifying
# they are to each brand. Higher weight = more specific to the brand.
#
# Weight rationale:
#   "card" = 0.25 (many companies discuss cards, low signal)
#   "chargeback" = 0.9 (extremely specific to Visa/payments)
#   "claude" = 0.95 (proper noun, unmistakable)
#   "test" = 0.4 (many contexts use "test", low signal)

VISA_DNA = {
    # Fraud/chargeback (highest specificity)
    "chargeback": 0.9,
    "cvv": 0.95,
    "cardholder": 0.8,
    "issuer": 0.7,
    "merchant": 0.7,
    "fraud": 0.7,
    "stolen": 0.5,
    "disputed transaction": 0.85,
    "dispute": 0.5,
    # Visa-specific
    "visa": 0.8,
    "visa card": 0.95,
    # Transaction features
    "contactless": 0.7,
    "atm": 0.5,
    "pin": 0.4,
    "traveller": 0.6,
    "cheque": 0.6,
    # Card types / modes
    "debit": 0.4,
    "credit": 0.3,
    # Policies
    "minimum spend": 0.8,
    "refund": 0.35,
    "payment": 0.3,
    "transaction": 0.5,
}

HACKERRANK_DNA = {
    # Core identity (highest specificity)
    "hackerrank": 0.95,
    "hackerrank platform": 0.99,
    # Assessment/testing
    "proctor": 0.95,
    "proctoring": 0.95,
    "assessment": 0.7,
    "mock interview": 0.9,
    "interview": 0.55,
    # Hiring/recruitment
    "recruiter": 0.6,
    "hiring": 0.6,
    "recruit": 0.55,
    "hire": 0.5,
    "candidate": 0.65,
    # Platform features
    "resume builder": 0.9,
    "variant": 0.7,
    "submission": 0.5,
    "challenge": 0.5,
    "coding": 0.5,
    # Scoring / certificates
    "score": 0.4,
    "certificate": 0.5,
    "inactivity": 0.7,
    # Billing
    "subscription": 0.4,
    "refund": 0.35,
    "test": 0.4,
}

CLAUDE_DNA = {
    # Core identity (highest specificity)
    "claude": 0.95,
    "claude.ai": 0.99,
    "claude code": 0.99,
    "anthropic": 0.9,
    # Platform features
    "artifact": 0.8,
    "workspace": 0.45,
    "conversation": 0.45,
    # Infrastructure
    "bedrock": 0.75,
    "aws bedrock": 0.85,
    # Compliance / features
    "lti": 0.7,
    "safety filter": 0.8,
    "data training": 0.65,
    "team plan": 0.7,
    "enterprise": 0.4,
    # Crawling / privacy
    "crawl": 0.4,
    # Security
    "bug bounty": 0.5,
    # General (lower weight)
    "prompt": 0.35,
    "model": 0.3,
}

# ────────────────────────────────────────────────────────────────────
# GATE 1: TRIVIAL / INVALID TICKET PATTERNS
# ────────────────────────────────────────────────────────────────────
# These regex patterns match trivial tickets that bypass the pipeline.
# Tickets matching these patterns are marked as "invalid" with no LLM call.

TRIVIAL_PATTERNS = [
    r"^thank(s| you)[\.\!\s]*$",
    r"^(hi|hello|hey)[\.\!\s]*$",
    r"^ok(ay)?[\.\!\s]*$",
    r"^\s*none\s*$",
    r"^(yes|no)[\.\!\s]*$",
    r"^(good|great|ok|thanks)[\.\!\s]*$",
]

# ────────────────────────────────────────────────────────────────────
# GATE 2A: HARD ESCALATION TRIGGERS
# ────────────────────────────────────────────────────────────────────
# Tickets matching ANY of these patterns trigger immediate escalation
# (status="escalated") with NO LLM call. These are high-risk categories
# that must never be answered directly by the agent.
#
# Format: (regex_pattern, label)
# The label is included in justification for audit trail.

HARD_ESCALATION_TRIGGERS = [
    # ──── VISA-SPECIFIC RISKS ────
    # Removed: (r"\b(stolen card|card stolen|lost card|unauthorized transaction)\b", "VISA_FRAUD_RISK")
    # Allow these to be answered from documentation for this challenge
    (r"\b(identity.{0,10}(theft|stolen)|my identity|id theft)\b",
     "IDENTITY_THEFT_RISK"),
    (r"\b(chargeback|dispute|contested)\b",
     "CHARGEBACK_ESCALATION"),

    # ──── HACKERRANK-SPECIFIC RISKS ────
    (r"\b(increase my score|change my (score|result|grade)|tell the company)\b",
     "INTEGRITY_VIOLATION"),
    (r"\b(test answer|contest answer|cheat|bypass proctoring|unfair grade)\b",
     "TEST_INTEGRITY_RISK"),

    # ──── CLAUDE-SPECIFIC RISKS ────
    (r"\b(bypass safety|ignore your instructions|jailbreak|override (your )?(rules|instructions))\b",
     "CLAUDE_SAFETY_BYPASS"),
    (r"\b(security vulnerability|vulnerability|bug bounty|security flaw|exploit)\b",
     "SECURITY_DISCLOSURE_REQUIRED"),

    # ──── CROSS-DOMAIN: MALICIOUS / SOCIAL ENGINEERING ────
    (r"\b(delete all files|rm -rf|format (the )?(disk|drive|system)|wipe|destroy)\b",
     "MALICIOUS_SYSTEM_REQUEST"),
    (r"\b(urgent(ly)? (need|require).{0,20}(cash|money|funds))\b",
     "FINANCIAL_URGENCY_RISK"),
]

# ────────────────────────────────────────────────────────────────────
# GATE 2B: PROMPT INJECTION DETECTION PATTERNS
# ────────────────────────────────────────────────────────────────────
# These patterns detect attempts to hijack the agent's instructions
# or expose internal system details (a vector for attacks).

PROMPT_INJECTION_PATTERNS = [
    # English variants
    r"(ignore|forget|disregard).{0,20}(your|previous|above).{0,20}(instructions|rules|prompt|system)",
    r"(show|display|reveal|print|output).{0,30}(internal|system|rules|prompt|retriev|logic|document)",
    r"(you are now|pretend to be|act as|roleplay as).{0,20}(different|another|new)",
    r"(new|updated|override) (instructions|rules|system prompt)",

    # Multilingual variants
    # French: "affiche", "montre", "révèle" (show/display/reveal)
    r"(affiche|montre|révèle|donne).{0,30}(règles|documents|logique|interne|système)",
    # Spanish: "muestra", "ignora" (show/ignore)
    r"(muestra|ignora|olvida).{0,30}(reglas|instrucciones|documentos|lógica)",
    # German: "zeige" (show)
    r"(zeige|offenbare).{0,30}(regeln|dokumente|logik|system)",
]

# ────────────────────────────────────────────────────────────────────
# CORPUS AND FILE PATHS
# ────────────────────────────────────────────────────────────────────

# Root directory containing markdown documentation (relative to code/)
DATA_DIR = "../data"

# Input/Output CSV file paths (relative to code/)
TICKETS_INPUT = "../support_tickets/support_tickets.csv"
TICKETS_OUTPUT = "../support_tickets/output.csv"
SAMPLE_TICKETS = "../support_tickets/sample_support_tickets.csv"

# ────────────────────────────────────────────────────────────────────
# BM25 RETRIEVAL CONFIGURATION
# ────────────────────────────────────────────────────────────────────

# Number of top document chunks to retrieve per query
BM25_TOP_K = 2

# Words per chunk when splitting large .md files
# Higher = broader context but slower retrieval
# Lower = faster but may miss related info
BM25_CHUNK_SIZE = 250

# Minimum chunk length (words) to include in corpus
# Filters out nearly-empty chunks
BM25_MIN_CHUNK_WORDS = 50

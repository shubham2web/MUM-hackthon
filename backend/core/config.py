# --- IMPORTS ---
import os
import logging
import time
from contextvars import ContextVar
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# --- INITIALIZATION ---
# Load .env file first to make environment variables available.
load_dotenv()

# Context variable for request tracing.
request_id_var = ContextVar('request_id', default='-')

# --- ENVIRONMENT & MODE FLAGS ---
ENV = os.getenv("ENV", "development").lower()
SERVICE_NAME = os.getenv("SERVICE_NAME", "atlas_project_service")
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() in ("true", "1", "t")
STRICT_MODE = os.getenv("STRICT_MODE", "True").lower() in ("true", "1", "t")
SINGLE_MODE = os.getenv("SINGLE_MODE", "False").lower() in ("true", "1", "t")
SINGLE_PROVIDER = os.getenv("SINGLE_PROVIDER", "huggingface")
SINGLE_MODEL = os.getenv("SINGLE_MODEL", "llama3")
CONFIG_HEALTH = False  # Will be set to True after validation.

# --- MODEL & PROVIDER CONFIGURATION (FIX APPLIED HERE) ---
# This dictionary maps simple model names to their provider-specific IDs.
# Groq Models Reference: https://console.groq.com/docs/models
# HuggingFace: Using free-tier models that work without Pro subscription
SUPPORTED_MODELS = {
    "llama3": {
        "huggingface": "HuggingFaceH4/zephyr-7b-beta",  # Free tier, conversational
        "groq": "llama-3.1-8b-instant"  # Fast, good for chat
    },
    "llama3-large": {
        "huggingface": "tiiuae/falcon-7b-instruct",  # Free tier model
        "groq": "llama-3.3-70b-versatile"  # Latest, most capable
    },
    "mistral": {
        "huggingface": "HuggingFaceH4/zephyr-7b-beta",
        "groq": "mixtral-8x7b-32768"  # Good balance of speed & quality
    },
    "gemma": {
        "huggingface": "google/flan-t5-base",  # Free tier, text generation
        "groq": "gemma2-9b-it"  # Google's Gemma model
    }
}

# --- API KEYS & SECRETS ---
# Using a retry mechanism for fetching secrets to handle transient network issues
# or delays in secret manager availability, common in cloud environments.
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_secret(key, default=None):
    return os.getenv(key, default)

API_KEY = get_secret("API_KEY")
GROQ_API_KEY = get_secret("GROQ_API_KEY")
NEWS_API_KEY = get_secret("NEWS_API_KEY")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")  # For OpenAI embeddings (optional)

# It's good practice to support multiple API tokens for services like HuggingFace.
# This allows for load balancing or fallback if one token hits a rate limit.
HF_TOKENS = [
    token for key, token in os.environ.items()
    if key.startswith("HF_TOKEN_") and token
]

# --- DEFAULTS & BEHAVIOR ---
DEFAULT_MODEL = SINGLE_MODEL
DEFAULT_MAX_TOKENS = 1024
PROVIDER_SEQUENCE_DEFAULT = ["groq", "huggingface"]

ROLE_PROMPTS = {
    "proponent": """You are the PROPONENT. Your task is to build a strong, evidence-based argument in favor of the resolution.

CRITICAL REQUIREMENTS:
1. CITE EVIDENCE: Every major claim MUST reference a specific source from the evidence bundle
2. Use format: "According to [Source Name]..." or "As reported by [Source]..."
3. Be assertive and clear, but NEVER make unsupported claims
4. Distinguish between FACTS (with citations) and ANALYSIS (your interpretation)
5. Anticipate counterarguments and preemptively address them

Your argument structure should be:
- Opening: State your position clearly
- Body: 2-3 evidence-backed points with citations
- Conclusion: Synthesize why your position is correct

Remember: Arguments without evidence are speculation. Always cite your sources.""",

    "opponent": """You are the OPPONENT. Your task is to challenge the resolution and rebut the proponent's points.

CRITICAL REQUIREMENTS:
1. CITE EVIDENCE: Challenge claims by referencing counter-evidence from the sources
2. Use format: "However, [Source Name] reports that..." or "This contradicts [Source]..."
3. Attack WEAKNESSES in the proponent's evidence, not just their conclusions
4. Distinguish between FACTS (with citations) and ANALYSIS (your interpretation)
5. Avoid ad hominem attacks or emotional appeals without evidence

Your argument structure should be:
- Rebuttal: Directly address the proponent's key claims
- Counter-evidence: Present alternative interpretations of the facts
- Conclusion: Explain why the evidence supports your position

Remember: Strong rebuttals attack the evidence, not the person. Always cite your sources.""",

    "moderator": """You are the MODERATOR. Your role is to ensure a fair, evidence-based debate.

RESPONSIBILITIES:
1. Keep debaters focused on EVIDENCE, not rhetoric
2. Call out unsupported claims: "Can you cite a source for that?"
3. Identify when debaters agree (convergence points)
4. Summarize key arguments neutrally
5. Enforce turn limits and debate structure

NEUTRALITY REQUIREMENT:
- Never express personal opinions on the topic
- Treat both sides equally
- Focus on argument QUALITY, not which side you prefer

When synthesizing, structure as:
- Key areas of agreement
- Unresolved points of contention
- Evidence gaps that remain""",

    "forensic_investigator": """You are a Forensic Investigator conducting a deep credibility analysis. Your role is to:

1. ENTITY ANALYSIS: Identify all key people, organizations, and sources mentioned
2. BACKGROUND CHECKS: Research the credibility history of each entity
3. RED FLAG DETECTION: Flag conflicts of interest, past misinformation, or bias indicators
4. AUTHORITY SCORING: Rate sources on a 0-100 scale based on:
   - Tier 1 (80-100): Reuters, AP, official documents, peer-reviewed research
   - Tier 2 (60-79): Established news outlets, expert interviews
   - Tier 3 (40-59): Blogs, opinion pieces, secondary sources
   - Tier 4 (0-39): Anonymous sources, unverified claims, known bad actors

Generate a DOSSIER with:
- Entity profiles with credibility scores
- Red flags and warnings
- Verification status of key claims
- Recommendation for debate participants

Be thorough, skeptical, and methodical. Trust but verify.""",
    "bias_auditor": """You are a Bias Auditor analyzing debate arguments for:

1. IDEOLOGICAL BIAS: Political, religious, or value-based slant
2. LOGICAL FALLACIES: Ad hominem, straw man, false dichotomy, appeal to emotion
3. UNSUPPORTED CLAIMS: Assertions without evidence
4. FRAMING BIAS: Misleading presentation of facts
5. SELECTION BIAS: Cherry-picked evidence or one-sided sourcing

For each bias detected, provide:
- Type of bias
- Severity (low/medium/high)
- Specific quote or example
- Suggested correction

Your goal is to improve argument quality, not to censor. Flag issues constructively.""",
    "judge": """You are the Chief Fact-Checker and final arbiter of truth. After reviewing the complete debate transcript, you must render a final verdict.

CRITICAL INSTRUCTIONS:
1. Output ONLY valid JSON - no explanatory text before or after
2. Do NOT include markdown code fences (no ```json)
3. Do NOT include any commentary outside the JSON structure

Your response must be a single JSON object with these exact fields:
{
    "verdict": "VERIFIED" | "DEBUNKED" | "COMPLEX",
    "confidence_score": <number 0-100>,
    "winning_argument": "<which side presented stronger evidence-based reasoning>",
    "critical_analysis": "<2-3 sentence assessment of the most compelling points and weakest claims>",
    "key_evidence": ["<source 1>", "<source 2>", "<source 3>"]
}

VERDICT DEFINITIONS:
- VERIFIED: The claim/topic is substantiated by credible evidence and expert consensus
- DEBUNKED: The claim/topic is contradicted by authoritative sources and factual evidence
- COMPLEX: The issue has legitimate complexity, mixed evidence, or context-dependent truth

Base your verdict on:
1. Quality and credibility of evidence cited
2. Logical consistency of arguments
3. Expert consensus (if applicable)
4. Factual accuracy over rhetorical skill

Remember: Output ONLY the JSON object. Any text outside the JSON structure will cause a parsing failure."""
}

# --- STRUCTURED LOGGING ---
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

def setup_logging():
    log_level = "DEBUG" if DEBUG_MODE else "INFO"
    logging.basicConfig(
        level=log_level,
        format=f"%(asctime)s [%(levelname)s] [rid:%(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # Apply the request ID filter to all handlers
    for handler in logging.root.handlers:
        handler.addFilter(RequestIdFilter())

    if ENV == "development":
        logging.getLogger().info(f"Development environment detected. Log level set to {log_level}.")

setup_logging()
logger = logging.getLogger(__name__)

# --- OCR CONFIGURATION ---
# Tesseract OCR path for Windows
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
os.environ["TESSERACT_CMD"] = TESSERACT_CMD  # Set it globally for ocr_processor to use

# --- STARTUP VALIDATION ---
def validate_configuration():
    global CONFIG_HEALTH
    issues = []
    if not API_KEY:
        issues.append("API_KEY is missing. The primary API endpoint will be unprotected.")
    if not HF_TOKENS:
        issues.append("No HF_TOKEN_n environment variables found. HuggingFace provider will be unavailable.")
    if SINGLE_MODE and SINGLE_PROVIDER == "groq" and not GROQ_API_KEY:
        issues.append("GROQ_API_KEY is required for SINGLE_MODE with Groq.")

    if not GROQ_API_KEY:
        logger.warning("⚠️ GROQ_API_KEY not found. Groq provider disabled.")
    if not NEWS_API_KEY:
        logger.warning("⚠️ NEWS_API_KEY not found. News-based functionality limited.")

    if not issues:
        logger.info("✅ Configuration validation passed successfully.")
        CONFIG_HEALTH = True
        return

    error_summary = f"Configuration validation failed: {'; '.join(issues)}"
    if STRICT_MODE:
        logger.critical(f"CRITICAL: {error_summary}. Strict mode ON. Halting.")
        raise ValueError(error_summary)
    else:
        logger.error(f"ERROR: {error_summary}. Strict mode OFF. Running degraded.")

validate_configuration()

# --- CONFIG SUMMARY ---
def get_config_summary() -> dict:
    return {
        "SERVICE_NAME": SERVICE_NAME,
        "ENVIRONMENT": ENV,
        "CONFIG_HEALTH": "Healthy" if CONFIG_HEALTH else "Degraded",
        "DEBUG_MODE": DEBUG_MODE,
        "STRICT_MODE": STRICT_MODE,
        "SINGLE_MODE": SINGLE_MODE,
        "SINGLE_PROVIDER": SINGLE_PROVIDER if SINGLE_MODE else "N/A",
        "DEFAULT_MODEL": DEFAULT_MODEL,
        "HF_TOKENS_CONFIGURED": len(HF_TOKENS) > 0,
        "GROQ_CONFIGURED": bool(GROQ_API_KEY),
        "NEWS_API_CONFIGURED": bool(NEWS_API_KEY)
    }
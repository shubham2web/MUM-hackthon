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
SUPPORTED_MODELS = {
    "llama3": {
        "huggingface": "meta-llama/Meta-Llama-3-8B-Instruct",
        "groq": "llama3-8b-8192"
    },
    "mistral": {
        "huggingface": "mistralai/Mistral-7B-Instruct-v0.2",
        "groq": "mixtral-8x7b-32768"
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
    "proponent": "You are the proponent. Your task is to build a strong, evidence-based argument in favor of the resolution. Start by introducing your main points and supporting them with the evidence provided. Be assertive and clear.",
    "opponent": "You are the opponent. Your task is to argue against the resolution and rebut the proponent's points. Use the evidence to challenge their claims and present a compelling counter-argument.",
    "moderator": "You are the moderator. Your role is to guide the debate, ensure both sides adhere to the rules, and summarize the key arguments. Pose clarifying questions and keep the discussion focused."
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
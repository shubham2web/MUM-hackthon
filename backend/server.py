import asyncio
import json
import logging
import os
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
import sys

from quart import Quart, Response, jsonify, render_template, request
from quart_cors import cors
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

# Note: These local imports need to exist in your project structure
from ai_agent import AiAgent
from config import API_KEY, DEBUG_MODE, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, ROLE_PROMPTS
from db_manager import AsyncDbManager, DATABASE_FILE
from pro_scraper import get_diversified_evidence
from utils import compute_advanced_analytics, format_sse

# --------------------------
# Setup Quart App & Executor
# --------------------------
app = Quart(__name__)

# --- CORS setup with environment variable ---
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
app = cors(app, allow_origin=ALLOWED_ORIGIN)

executor = ThreadPoolExecutor(max_workers=10)

# --- JSON logging (production-ready) ---
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
        }
        if record.exc_info:
            payload["exception"] = traceback.format_exc()
        return json.dumps(payload)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
root = logging.getLogger()
root.handlers = [handler]
root.setLevel(logging.INFO)

# --- Custom Rate Limiter for Quart using limits ---
storage = MemoryStorage()
rate_limiter = MovingWindowRateLimiter(storage)

def limit(rule: str):
    """Decorator for Quart endpoints to apply rate limiting."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            if not rate_limiter.hit(parse(rule), client_ip):
                return jsonify({"error": "Rate limit exceeded"}), 429
            return await func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# -----------------------------
# Security & Middleware
# -----------------------------
@app.before_request
async def check_api_key():
    if request.endpoint in ['home', 'chat_page', 'healthz'] or not API_KEY or request.method == 'OPTIONS':
        return
    if request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

@app.after_request
async def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
async def home():
    return jsonify({"message": "AI Debate Server running (Quart)."})

@app.route("/healthz")
async def healthz():
    """Provides a simple health check endpoint."""
    return jsonify({"status": "ok"})

@app.route("/chat")
async def chat_page():
    return await render_template("index.html")

@app.route("/run_debate", methods=["POST"])
@limit("5/minute")
async def run_debate_route():
    try:
        raw_data = await request.get_data()
        logging.info(f"Received raw data: {raw_data}")

        data = await request.get_json()
        topic = data.get("topic")
        if not topic:
            return jsonify({"error": "Missing topic"}), 400
    except Exception as e:
        logging.error(f"Error processing request: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Invalid request: {e}"}), 400

    async def stream():
        async for chunk in generate_debate(topic):
            yield chunk

    return Response(stream(), mimetype="text/event-stream")


# -----------------------------
# Debate Generator
# -----------------------------
async def generate_debate(topic: str):
    loop = asyncio.get_running_loop()
    
    debate_id = str(uuid.uuid4())
    transcript = ""
    log_entries = []
    evidence_bundle = []
    turn_metrics = {"turn_count": 0, "rebuttal_count": 0, "audited_turn_count": 0}

    try:
        yield format_sse({"topic": topic, "model_used": DEFAULT_MODEL, "debate_id": debate_id}, "metadata")

        evidence_bundle = await loop.run_in_executor(executor, get_diversified_evidence, topic)
        
        article_text = "\n\n".join(
            f"Title: {article.get('title', 'N/A')}\nText: {article.get('text', '')}"
            for article in evidence_bundle
        )
        transcript = f"Debate ID: {debate_id}\nTopic: {topic}\n\nSources:\n{article_text}\n\n"

        debaters = {"proponent": ROLE_PROMPTS["proponent"], "opponent": ROLE_PROMPTS["opponent"]}

        # --- Moderator Introduction ---
        intro_prompt = ROLE_PROMPTS.get("moderator", "Introduce the debate topic based on the sources.")
        async for event, data in run_turn("moderator", intro_prompt, transcript, loop, log_entries, debate_id, topic, turn_metrics):
            if event == "token":
                transcript += f"--- INTRODUCTION FROM MODERATOR ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # --- Round 1: Opening Statements ---
        for role, prompt in debaters.items():
            input_text = f"The moderator has introduced the topic. Please provide your opening statement based on the provided sources.\n\nTranscript:\n{transcript}"
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics):
                if event == "token":
                    transcript += f"--- STATEMENT FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # --- Moderator Poses a Question for Rebuttals ---
        question_prompt = ROLE_PROMPTS.get("moderator", "Based on the opening statements, pose a challenging question for both sides.")
        async for event, data in run_turn("moderator", question_prompt, transcript, loop, log_entries, debate_id, topic, turn_metrics):
            if event == "token":
                transcript += f"--- QUESTION FROM MODERATOR ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # --- Round 2: Rebuttals ---
        for role, prompt in debaters.items():
            input_text = f"Address the moderator's latest question and rebut the opposing view.\n\nTranscript:\n{transcript}"
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, is_rebuttal=True):
                if event == "token":
                    transcript += f"--- REBUTTAL FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # --- Round 3: Convergence ---
        for role, prompt in debaters.items():
            input_text = f"Review the entire debate. Your goal is now to find common ground and synthesize a final viewpoint.\n\nTranscript:\n{transcript}"
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics):
                if event == "token":
                    transcript += f"--- CONVERGENCE FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)
        
        # --- Final Synthesis by Moderator ---
        synthesis_text = ""
        moderator_prompt = ROLE_PROMPTS.get("moderator", "Provide a final, structured synthesis of the entire debate.")
        async for event, data in run_turn("moderator", moderator_prompt, transcript, loop, log_entries, debate_id, topic, turn_metrics):
            if event == "token":
                synthesis_text += data.get("text", "")
            if event != "token" or data.get("text"):
                yield format_sse(data, event)
        
        # --- Final Analytics ---
        metrics = await loop.run_in_executor(executor, compute_advanced_analytics, evidence_bundle, transcript, turn_metrics)
        yield format_sse(metrics, "analytics_metrics")

    except Exception as e:
        logging.error(f"Fatal error during debate generation: {e}", exc_info=True)
        yield format_sse({"message": "A fatal error occurred, stopping the debate."}, "error")
    finally:
        if log_entries:
            await AsyncDbManager.add_log_entries_batch(log_entries)
            logging.info(f"Successfully wrote {len(log_entries)} log entries to the database.")
        yield format_sse({"message": "Debate complete."}, "end")


# -----------------------------
# Debate Turn
# -----------------------------
async def run_turn(role: str, system_prompt: str, input_text: str, loop, log_entries: list, debate_id: str, topic: str, turn_metrics: dict, is_rebuttal: bool = False):
    ai_agent = AiAgent()
    try:
        yield "start_role", {"role": role}

        full_response = ""
        stream_generator = ai_agent.stream(
            user_message=input_text,
            system_prompt=system_prompt,
            max_tokens=DEFAULT_MAX_TOKENS
        )
        
        while True:
            try:
                chunk = await loop.run_in_executor(executor, next, stream_generator)
                full_response += chunk
                yield "token", {"role": role, "text": chunk}
            except StopIteration:
                break
        
        turn_metrics["turn_count"] += 1
        if is_rebuttal:
            turn_metrics["rebuttal_count"] += 1

        log_entries.append({
            "debate_id": debate_id, "topic": topic, "model_used": DEFAULT_MODEL, "role": role,
            "user_message": input_text, "ai_response": full_response
        })

        yield "end_role", {"role": role}
    except Exception as e:
        logging.error(f"Error during turn for role '{role}': {e}", exc_info=True)
        # --- CHANGE START: Send the actual error message to the client ---
        yield "turn_error", {"role": role, "message": f"An error occurred for {role}: {str(e)}"}
        # --- CHANGE END ---


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    if DEBUG_MODE and os.path.exists(DATABASE_FILE):
        try:
            logging.warning(f"Development mode: Removing existing database file '{DATABASE_FILE}'.")
            os.remove(DATABASE_FILE)
        except PermissionError:
            logging.error(
                f"Could not remove '{DATABASE_FILE}' because it is in use. "
                "Please close any other programs that might be using it and restart the server."
            )
            exit()

    async def initialize():
        await AsyncDbManager.init_db()
        logging.info("Database has been initialized.")

    if not os.path.exists("templates"):
        os.makedirs("templates")
    if not os.path.exists("templates/index.html"):
        with open("templates/index.html", "w") as f:
            f.write("<h1>AI Debate Server Chat Interface</h1>")

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(initialize())

    logging.info("Starting Quart async server. Use Hypercorn/Uvicorn in production.")
    app.run(debug=DEBUG_MODE, port=5000)


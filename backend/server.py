import asyncio
import json
import logging
import mimetypes
import os
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
import sys

from quart import Quart, render_template, request, jsonify, send_from_directory, Response
from quart_cors import cors
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

# Note: These local imports need to exist in your project structure
from core.ai_agent import AiAgent
from core.config import API_KEY, DEBUG_MODE, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, ROLE_PROMPTS
from services.db_manager import AsyncDbManager, DATABASE_FILE
from services.pro_scraper import get_diversified_evidence
from core.utils import compute_advanced_analytics, format_sse

# Import OCR functionality (EasyOCR - no Tesseract needed!)
# Temporarily disabled due to slow PyTorch loading
OCR_AVAILABLE = False
logging.warning("OCR functionality temporarily disabled to speed up server startup. PyTorch/EasyOCR will be loaded on-demand.")
# try:
#     from services.ocr_processor import get_ocr_processor
#     OCR_AVAILABLE = True
#     logging.info("✅ EasyOCR module loaded successfully (no Tesseract needed!)")
# except (ImportError, OSError, RuntimeError) as e:
#     OCR_AVAILABLE = False
#     logging.warning(f"OCR functionality not available: {e}. Install dependencies: pip install easyocr pillow torch torchvision")

# Import v2.0 routes
# Temporarily disabled due to slow transformers loading
try:
    from api.api_v2_routes import v2_bp
    V2_AVAILABLE = True
    logging.info("✅ ATLAS v2.0 routes loaded successfully")
except ImportError as e:
    V2_AVAILABLE = False
    logging.warning(f"⚠️ ATLAS v2.0 routes not available: {e}")

# --------------------------
# Setup Quart App & Executor
# --------------------------
app = Quart(__name__, 
            static_folder='static',
            static_url_path='/static')

# --- CORS setup with environment variable ---
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
app = cors(app, 
           allow_origin=ALLOWED_ORIGIN,
           allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
           allow_headers=["Content-Type", "Authorization"])

# --- Register v2.0 Blueprint ---
if V2_AVAILABLE:
    app.register_blueprint(v2_bp)
    logging.info("✅ ATLAS v2.0 endpoints registered at /v2/*")

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
    # Allow access without API key for these endpoints
    if (request.endpoint in ['home', 'chat', 'healthz', 'analyze_topic', 'ocr_upload'] or  # Added ocr_upload
        request.path.startswith('/static/') or
        request.path.startswith('/v2/') or  # Allow v2.0 endpoints without API key
        not API_KEY or 
        request.method == 'OPTIONS'):
        return

    # Check API key for other endpoints
    received_key = request.headers.get("X-API-Key")
    if received_key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

@app.after_request
async def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response

# Add this to ensure correct MIME types
@app.after_request
async def add_header(response):
    if request.path.endswith('.js'):
        response.headers['Content-Type'] = 'application/javascript'
    elif request.path.endswith('.css'):
        response.headers['Content-Type'] = 'text/css'
    return response

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
async def home():
    """Landing/Hero page"""
    return await render_template("homepage.html")

@app.route("/chat")
async def chat():
    """Render the chat interface with optional mode parameter"""
    mode = request.args.get('mode', 'analytical')
    return await render_template('index.html', mode=mode)

@app.route("/ocr")
async def ocr_page():
    """Render the OCR interface"""
    return await render_template('ocr.html')

@app.route("/healthz")
async def healthz():
    """Provides a simple health check endpoint."""
    return jsonify({"status": "ok"})

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

@app.route("/analyze_topic", methods=["POST"])
async def analyze_topic():
    """Analyze a topic and return insights"""
    try:
        data = await request.get_json()
        topic = data.get("topic", "")
        model = data.get("model", "llama3")
        
        if not topic:
            return jsonify({"error": "No topic provided"}), 400
        
        logging.info(f"Analyzing topic: {topic}")
        
        loop = asyncio.get_running_loop()
        
        try:
            # Get evidence with timeout
            evidence_bundle = await asyncio.wait_for(
                loop.run_in_executor(executor, get_diversified_evidence, topic),
                timeout=30.0
            )
            logging.info(f"Found {len(evidence_bundle)} sources")
            
        except asyncio.TimeoutError:
            logging.warning("Evidence gathering timed out")
            evidence_bundle = []
        
        # Create context
        if evidence_bundle:
            context = "\n\n".join(
                f"Source: {article.get('title', 'N/A')}\n{article.get('text', '')[:500]}"
                for article in evidence_bundle[:3]
            )
            user_message = f"Question: {topic}\n\nEvidence:\n{context}"
        else:
            user_message = f"Question: {topic}"
        
        system_prompt = """You are Atlas, an AI misinformation fighter. 
Today's date is November 12, 2025. You have knowledge up to 2025 and can discuss current events, trends, and updates from 2025.
Analyze the user's question and provide a clear, factual response.
Keep your response concise (2-3 paragraphs)."""
        
        # Generate response - FIX: Collect generator properly
        ai_agent = AiAgent()
        full_response = ""
        
        def collect_stream():
            """Helper function to collect stream in thread"""
            result = ""
            try:
                stream_gen = ai_agent.stream(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    max_tokens=500
                )
                for chunk in stream_gen:  # Use for loop instead of next()
                    result += chunk
            except Exception as e:
                logging.error(f"Stream collection error: {e}")
            return result
        
        # Run in executor with timeout
        try:
            full_response = await asyncio.wait_for(
                loop.run_in_executor(executor, collect_stream),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            full_response = "Response generation timed out. Please try a simpler question."
        
        if not full_response:
            full_response = "I couldn't generate a response. Please try again."
        
        logging.info(f"Response generated: {len(full_response)} characters")
        
        return jsonify({
            "success": True,
            "topic": topic,
            "analysis": full_response,
            "model": model,
            "sources_used": len(evidence_bundle)
        })
        
    except Exception as e:
        logging.error(f"Error in analyze_topic: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
            "analysis": "Sorry, I encountered an error processing your request."
        }), 500

@app.route("/ocr_upload", methods=["POST"])
async def ocr_upload():
    """
    Handle image upload and OCR processing.
    Extracts text from image and optionally analyzes it with AI.
    Uses EasyOCR - no Tesseract installation required!
    """
    if not OCR_AVAILABLE:
        return jsonify({
            "success": False,
            "error": "OCR functionality not available. Please install dependencies: pip install easyocr pillow"
        }), 503
    
    try:
        files = await request.files
        
        if 'image' not in files:
            return jsonify({"error": "No image file provided"}), 400
        
        image_file = files['image']
        
        if not image_file.filename:
            return jsonify({"error": "Empty filename"}), 400
        
        # Check file format
        from services.ocr_processor import OCRProcessor
        if not OCRProcessor.is_supported_format(image_file.filename):
            return jsonify({
                "error": f"Unsupported file format. Supported formats: {', '.join(OCRProcessor.get_supported_formats())}"
            }), 400
        
        # Read image bytes - FileStorage.read() is synchronous, not async
        image_bytes = image_file.read()
        
        if len(image_bytes) == 0:
            return jsonify({"error": "Empty file"}), 400
        
        # Log file info
        logging.info(f"Processing OCR for image: {image_file.filename} ({len(image_bytes)} bytes)")
        
        # Check if OCR is available (lazy load)
        if not OCR_AVAILABLE:
            try:
                from services.ocr_processor import get_ocr_processor
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": f"OCR functionality not available: {str(e)}"
                }), 503
        
        # Process OCR
        loop = asyncio.get_running_loop()
        from services.ocr_processor import get_ocr_processor
        ocr_processor = get_ocr_processor()
        
        # Run OCR in executor to avoid blocking
        ocr_result = await loop.run_in_executor(
            executor,
            ocr_processor.extract_text_from_bytes,
            image_bytes
        )
        
        if not ocr_result["success"]:
            return jsonify({
                "success": False,
                "error": ocr_result.get("error", "OCR processing failed")
            }), 500
        
        extracted_text = ocr_result["text"]
        
        # Get analysis request from form data
        form_data = await request.form
        analyze = form_data.get('analyze', 'true').lower() == 'true'
        use_scraper = form_data.get('use_scraper', 'true').lower() == 'true'
        question = form_data.get('question', '')
        
        ai_analysis = None
        evidence_articles = []
        
        if analyze and extracted_text:
            # If scraper is enabled, gather evidence first
            if use_scraper and len(extracted_text.split()) > 10:
                try:
                    logging.info(f"🔍 Using scraper to gather evidence for OCR text...")
                    
                    # Use first 200 chars or key phrases as search query
                    search_query = extracted_text[:200] if len(extracted_text) > 200 else extracted_text
                    
                    # Get evidence from scraper
                    evidence_articles = await loop.run_in_executor(
                        executor,
                        get_diversified_evidence,
                        search_query,
                        3  # Get 3 articles for evidence
                    )
                    
                    logging.info(f"✅ Gathered {len(evidence_articles)} evidence articles")
                    
                except Exception as scraper_error:
                    logging.error(f"Scraper error: {scraper_error}")
                    # Continue without scraper evidence
            
            # Prepare AI analysis with evidence
            if evidence_articles:
                # Build context from evidence
                evidence_context = "\n\n---EVIDENCE FROM WEB SOURCES---\n\n"
                for idx, article in enumerate(evidence_articles, 1):
                    evidence_context += f"Source {idx}: {article.get('title', 'Unknown')}\n"
                    evidence_context += f"URL: {article.get('url', 'N/A')}\n"
                    summary = article.get('summary') or article.get('text', '')[:300]
                    evidence_context += f"Content: {summary}...\n\n"
                
                if question:
                    user_message = f"""Here is text extracted from an image:

{extracted_text}

{evidence_context}

User's question: {question}

Please analyze the extracted text using the evidence provided from web sources. Verify claims, identify any misinformation, and provide a fact-checked analysis."""
                else:
                    user_message = f"""Here is text extracted from an image:

{extracted_text}

{evidence_context}

Please analyze this text using the evidence provided from web sources. Verify the accuracy of any claims, identify potential misinformation, and provide a comprehensive fact-checked analysis."""
                
                system_prompt = """You are Atlas, an advanced misinformation fighter and fact-checker.
Today's date is November 12, 2025. You have knowledge up to 2025 and can discuss current events.
You have been provided with text extracted from an image along with evidence from credible web sources.
Your task is to:
1. Identify key claims or information in the extracted text
2. Cross-reference with the provided evidence
3. Verify accuracy and flag any misinformation
4. Provide a clear, evidence-based analysis
5. Cite sources when referencing evidence

Be thorough, objective, and help users understand the truth."""
            else:
                # No evidence available, proceed with basic analysis
                if question:
                    user_message = f"Here is text extracted from an image:\n\n{extracted_text}\n\nUser's question: {question}"
                else:
                    user_message = f"Here is text extracted from an image:\n\n{extracted_text}\n\nPlease analyze this text and provide insights."
                
                system_prompt = """You are Atlas, an AI assistant helping analyze text from images.
Today's date is November 12, 2025. You have knowledge up to 2025.
Provide clear, helpful analysis of the text content.
If the text appears to contain claims or information, verify its accuracy."""
            
            # Generate AI response
            ai_agent = AiAgent()
            
            def collect_ai_stream():
                result = ""
                try:
                    stream_gen = ai_agent.stream(
                        user_message=user_message,
                        system_prompt=system_prompt,
                        max_tokens=800
                    )
                    for chunk in stream_gen:
                        result += chunk
                except Exception as e:
                    logging.error(f"AI analysis error: {e}")
                return result
            
            try:
                ai_analysis = await asyncio.wait_for(
                    loop.run_in_executor(executor, collect_ai_stream),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                ai_analysis = "Analysis timed out. Please try again."
        
        return jsonify({
            "success": True,
            "ocr_result": {
                "text": extracted_text,
                "confidence": ocr_result["confidence"],
                "word_count": ocr_result["word_count"]
            },
            "ai_analysis": ai_analysis,
            "evidence_count": len(evidence_articles),
            "evidence_sources": [
                {
                    "title": article.get('title', 'Unknown'),
                    "url": article.get('url', ''),
                    "domain": article.get('domain', ''),
                    "summary": article.get('summary', '')
                }
                for article in evidence_articles
            ] if evidence_articles else [],
            "filename": image_file.filename
        })
        
    except Exception as e:
        logging.error(f"Error in OCR upload: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# -----------------------------
# Helper: Truncate transcript to prevent payload bloat
# -----------------------------
def get_recent_transcript(transcript: str, max_chars: int = 3000) -> str:
    """Keep only the most recent portion of the transcript to avoid payload size issues"""
    if len(transcript) <= max_chars:
        return transcript
    
    # Keep the last max_chars characters
    truncated = transcript[-max_chars:]
    
    # Find the first complete section marker to avoid cutting mid-sentence
    markers = ["---", "Debate ID:", "Topic:"]
    for marker in markers:
        pos = truncated.find(marker)
        if pos > 0 and pos < 500:  # If we find a marker near the start
            return "...[earlier debate content truncated]...\n\n" + truncated[pos:]
    
    return "...[earlier debate content truncated]...\n\n" + truncated

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
        
        # Truncate articles to prevent payload bloat (limit each article to 300 chars)
        article_text = "\n\n".join(
            f"Title: {article.get('title', 'N/A')}\nText: {article.get('text', '')[:300]}..."
            for article in evidence_bundle[:3]  # Limit to 3 articles max
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


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
try:
    from services.ocr_processor import get_ocr_processor
    OCR_AVAILABLE = True
    logging.info("✅ EasyOCR module loaded successfully (no Tesseract needed!)")
except (ImportError, OSError, RuntimeError) as e:
    OCR_AVAILABLE = False
    logging.warning(f"OCR functionality not available: {e}. Install dependencies: pip install easyocr pillow torch torchvision")

# Import v2.0 routes
try:
    from api.api_v2_routes import v2_bp
    V2_AVAILABLE = True
    logging.info("✅ ATLAS v2.0 routes loaded successfully")
except ImportError as e:
    V2_AVAILABLE = False
    logging.warning(f"⚠️ ATLAS v2.0 routes not available: {e}")

# Import Hybrid Memory System routes
try:
    from api.memory_routes import memory_bp
    from memory.memory_manager import get_memory_manager
    MEMORY_AVAILABLE = True
    logging.info("✅ Hybrid Memory System routes loaded successfully")
except ImportError as e:
    MEMORY_AVAILABLE = False
    logging.warning(f"⚠️ Memory System routes not available: {e}. Install: pip install -r memory_requirements.txt")

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

# --- Register Memory System Blueprint ---
if MEMORY_AVAILABLE:
    app.register_blueprint(memory_bp)
    logging.info("✅ Hybrid Memory System endpoints registered at /memory/*")

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
    """Analyze a topic and return insights (with memory support)"""
    try:
        data = await request.get_json()
        topic = data.get("topic", "")
        model = data.get("model", "llama3")
        session_id = data.get("session_id")  # Optional: maintain conversation context
        mode = data.get("mode", "analytical")  # Get mode parameter
        
        if not topic:
            return jsonify({"error": "No topic provided"}), 400
        
        # 🎯 DEBATE MODE: If mode is 'debate', run debate instead of analysis
        if mode == "debate":
            logging.info(f"Running debate on topic: {topic}")
            
            async def stream():
                async for chunk in generate_debate(topic):
                    yield chunk
            
            return Response(stream(), mimetype="text/event-stream")
        
        logging.info(f"Analyzing topic: {topic} (session: {session_id or 'new'})")
        
        # 🧠 MEMORY INTEGRATION: Initialize or retrieve memory session
        memory = None
        if MEMORY_AVAILABLE:
            try:
                memory = get_memory_manager()
                if session_id:
                    memory.set_debate_context(session_id)
                    logging.info(f"🧠 Using existing chat session: {session_id}")
                else:
                    session_id = str(uuid.uuid4())
                    memory.set_debate_context(session_id)
                    logging.info(f"🧠 Created new chat session: {session_id}")
            except Exception as e:
                logging.warning(f"Memory initialization failed: {e}")
                memory = None
        
        loop = asyncio.get_running_loop()
        
        try:
            # Get evidence with timeout
            evidence_bundle = await asyncio.wait_for(
                get_diversified_evidence(topic),
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
Analyze the user's question and provide a clear, factual response.
Keep your response concise (2-3 paragraphs)."""
        
        # 🧠 MEMORY INTEGRATION: Build memory-enhanced context
        if memory:
            try:
                user_message = memory.build_context_payload(
                    system_prompt=system_prompt,
                    current_task=user_message,
                    query=topic,  # RAG query to retrieve relevant past conversations
                    top_k_rag=2,
                    use_short_term=True,
                    use_long_term=True
                )
                system_prompt = None  # Already in context payload
                logging.info(f"🧠 Memory-enhanced context built for analysis")
            except Exception as e:
                logging.warning(f"Memory context building failed: {e}")
        
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
        
        # 🧠 MEMORY INTEGRATION: Store interaction in memory
        if memory:
            try:
                memory.add_interaction(
                    role="user",
                    content=topic,
                    metadata={"type": "question", "model": model},
                    store_in_rag=False  # Don't RAG-store user questions
                )
                memory.add_interaction(
                    role="assistant",
                    content=full_response,
                    metadata={"type": "analysis", "model": model, "sources": len(evidence_bundle)},
                    store_in_rag=True  # Store AI responses for future retrieval
                )
                logging.debug(f"🧠 Stored analysis in memory session {session_id}")
            except Exception as e:
                logging.warning(f"Failed to store in memory: {e}")
        
        logging.info(f"Response generated: {len(full_response)} characters")
        
        return jsonify({
            "success": True,
            "topic": topic,
            "analysis": full_response,
            "model": model,
            "sources_used": len(evidence_bundle),
            "session_id": session_id if memory else None  # Return session ID for multi-turn conversations
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
    Handle image upload and OCR processing (with memory support).
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
        
        # Process OCR
        loop = asyncio.get_running_loop()
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
        session_id = form_data.get('session_id')  # Optional: OCR conversation session
        
        # 🧠 MEMORY INTEGRATION: Initialize memory for OCR analysis
        memory = None
        if MEMORY_AVAILABLE and analyze:
            try:
                memory = get_memory_manager()
                if session_id:
                    memory.set_debate_context(session_id)
                    logging.info(f"🧠 Using existing OCR session: {session_id}")
                else:
                    session_id = str(uuid.uuid4())
                    memory.set_debate_context(session_id)
                    logging.info(f"🧠 Created new OCR session: {session_id}")
            except Exception as e:
                logging.warning(f"Memory initialization failed: {e}")
                memory = None
        
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
Provide clear, helpful analysis of the text content.
If the text appears to contain claims or information, verify its accuracy."""
            
            # 🧠 MEMORY INTEGRATION: Build memory-enhanced context for OCR
            if memory:
                try:
                    user_message = memory.build_context_payload(
                        system_prompt=system_prompt,
                        current_task=user_message,
                        query=extracted_text[:100],  # Use OCR text snippet for RAG
                        top_k_rag=2,
                        use_short_term=True,
                        use_long_term=True
                    )
                    system_prompt = None  # Already in context payload
                    logging.info(f"🧠 Memory-enhanced OCR context built")
                except Exception as e:
                    logging.warning(f"Memory context building failed: {e}")
            
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
            
            # 🧠 MEMORY INTEGRATION: Store OCR analysis in memory
            if memory and ai_analysis:
                try:
                    memory.add_interaction(
                        role="user",
                        content=f"OCR Text: {extracted_text[:200]}...",
                        metadata={"type": "ocr_input", "filename": image_file.filename},
                        store_in_rag=False
                    )
                    memory.add_interaction(
                        role="assistant",
                        content=ai_analysis,
                        metadata={"type": "ocr_analysis", "evidence_count": len(evidence_articles)},
                        store_in_rag=True  # Store analysis for future reference
                    )
                    logging.debug(f"🧠 Stored OCR analysis in memory session {session_id}")
                except Exception as e:
                    logging.warning(f"Failed to store OCR in memory: {e}")
        
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
            "filename": image_file.filename,
            "session_id": session_id if memory else None  # Return session ID for follow-up questions
        })
        
    except Exception as e:
        logging.error(f"Error in OCR upload: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

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
    
    # 🧠 MEMORY INTEGRATION: Initialize memory system for this debate
    memory = None
    if MEMORY_AVAILABLE:
        try:
            memory = get_memory_manager()
            memory.set_debate_context(debate_id)
            logging.info(f"🧠 Memory system enabled for debate: {debate_id}")
        except Exception as e:
            logging.warning(f"Memory system initialization failed: {e}. Continuing without memory.")
            memory = None

    try:
        yield format_sse({"topic": topic, "model_used": DEFAULT_MODEL, "debate_id": debate_id, "memory_enabled": memory is not None}, "metadata")

        evidence_bundle = await get_diversified_evidence(topic)
        
        article_text = "\n\n".join(
            f"Title: {article.get('title', 'N/A')}\nText: {article.get('text', '')}"
            for article in evidence_bundle
        )
        transcript = f"Debate ID: {debate_id}\nTopic: {topic}\n\nSources:\n{article_text}\n\n"

        debaters = {"proponent": ROLE_PROMPTS["proponent"], "opponent": ROLE_PROMPTS["opponent"]}

        # --- Moderator Introduction ---
        intro_prompt = ROLE_PROMPTS.get("moderator", "Introduce the debate topic based on the sources.")
        async for event, data in run_turn("moderator", intro_prompt, transcript, loop, log_entries, debate_id, topic, turn_metrics, memory):
            if event == "token":
                transcript += f"--- INTRODUCTION FROM MODERATOR ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # --- Round 1: Opening Statements ---
        for role, prompt in debaters.items():
            input_text = f"The moderator has introduced the topic. Please provide your opening statement based on the provided sources.\n\nTranscript:\n{transcript}"
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, memory):
                if event == "token":
                    transcript += f"--- STATEMENT FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # --- Moderator Poses a Question for Rebuttals ---
        question_prompt = ROLE_PROMPTS.get("moderator", "Based on the opening statements, pose a challenging question for both sides.")
        async for event, data in run_turn("moderator", question_prompt, transcript, loop, log_entries, debate_id, topic, turn_metrics, memory):
            if event == "token":
                transcript += f"--- QUESTION FROM MODERATOR ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # --- Round 2: Rebuttals ---
        for role, prompt in debaters.items():
            input_text = f"Address the moderator's latest question and rebut the opposing view.\n\nTranscript:\n{transcript}"
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, memory, is_rebuttal=True):
                if event == "token":
                    transcript += f"--- REBUTTAL FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # --- Round 3: Convergence ---
        for role, prompt in debaters.items():
            input_text = f"Review the entire debate. Your goal is now to find common ground and synthesize a final viewpoint.\n\nTranscript:\n{transcript}"
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, memory):
                if event == "token":
                    transcript += f"--- CONVERGENCE FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)
        
        # --- Final Synthesis by Moderator ---
        synthesis_text = ""
        moderator_prompt = ROLE_PROMPTS.get("moderator", "Provide a final, structured synthesis of the entire debate.")
        async for event, data in run_turn("moderator", moderator_prompt, transcript, loop, log_entries, debate_id, topic, turn_metrics, memory):
            if event == "token":
                synthesis_text += data.get("text", "")
            if event != "token" or data.get("text"):
                yield format_sse(data, event)
        
        # --- Final Analytics ---
        metrics = await loop.run_in_executor(executor, compute_advanced_analytics, evidence_bundle, transcript, turn_metrics)
        
        # 🧠 MEMORY INTEGRATION: Include memory statistics in analytics
        if memory:
            try:
                memory_summary = memory.get_memory_summary()
                metrics['memory_stats'] = {
                    'total_turns': memory_summary.get('turn_counter', 0),
                    'short_term_messages': memory_summary['short_term']['current_count'],
                    'long_term_memories': memory_summary['long_term']['total_memories'] if memory_summary.get('long_term') else 0
                }
            except Exception as e:
                logging.warning(f"Failed to get memory stats: {e}")
        
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
# Debate Turn (with Memory Integration)
# -----------------------------
async def run_turn(role: str, system_prompt: str, input_text: str, loop, log_entries: list, debate_id: str, topic: str, turn_metrics: dict, memory=None, is_rebuttal: bool = False):
    ai_agent = AiAgent()
    try:
        yield "start_role", {"role": role}

        # 🧠 MEMORY INTEGRATION: Build context with memory if available
        if memory:
            try:
                # Build 4-zone context payload
                memory_enhanced_input = memory.build_context_payload(
                    system_prompt=system_prompt,
                    current_task=input_text,
                    query=f"{role} arguments about {topic}",  # RAG query
                    top_k_rag=3,  # Retrieve top 3 relevant memories
                    use_short_term=True,
                    use_long_term=True
                )
                # Use memory-enhanced context
                final_input = memory_enhanced_input
                final_system_prompt = None  # System prompt is in ZONE 1
                logging.info(f"🧠 Memory-enhanced context built for {role} (turn {turn_metrics['turn_count'] + 1})")
            except Exception as e:
                logging.warning(f"Memory context building failed: {e}. Using traditional context.")
                final_input = input_text
                final_system_prompt = system_prompt
        else:
            # No memory available, use traditional approach
            final_input = input_text
            final_system_prompt = system_prompt

        full_response = ""
        stream_generator = ai_agent.stream(
            user_message=final_input,
            system_prompt=final_system_prompt,
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
        
        # 🧠 MEMORY INTEGRATION: Store interaction in memory
        if memory:
            try:
                memory.add_interaction(
                    role=role,
                    content=full_response,
                    metadata={
                        "turn": turn_metrics["turn_count"],
                        "is_rebuttal": is_rebuttal,
                        "topic": topic,
                        "model": DEFAULT_MODEL
                    },
                    store_in_rag=True
                )
                logging.debug(f"🧠 Stored {role}'s response in memory (turn {turn_metrics['turn_count']})")
            except Exception as e:
                logging.warning(f"Failed to store in memory: {e}")

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
# Initialize database on module load (needed for uvicorn/hypercorn)
async def initialize():
    await AsyncDbManager.init_db()
    logging.info("Database has been initialized.")

# Set Windows event loop policy
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Startup event for Quart (runs when server starts)
@app.before_serving
async def startup():
    """Initialize database before server starts accepting requests"""
    await AsyncDbManager.init_db()
    logging.info("Database has been initialized.")

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

    if not os.path.exists("templates"):
        os.makedirs("templates")
    if not os.path.exists("templates/index.html"):
        with open("templates/index.html", "w") as f:
            f.write("<h1>AI Debate Server Chat Interface</h1>")

    logging.info("Starting Quart server on http://127.0.0.1:8000")
    
    # Use Quart with explicit Hypercorn config for Windows compatibility
    from hypercorn.config import Config
    from hypercorn.asyncio import serve
    import asyncio
    
    config = Config()
    config.bind = ["127.0.0.1:8000"]  # Bind to localhost for Windows compatibility
    config.use_reloader = False
    config.workers = 1  # Single worker for Windows
    config.accesslog = "-"  # Log to stdout
    config.errorlog = "-"   # Log errors to stdout
    
    # Set Windows-compatible event loop
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run with asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(serve(app, config))



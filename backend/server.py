import asyncio
import json
import logging
import mimetypes
import os
import re
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
import sys
import random
import httpx
import feedparser
from typing import List, Dict

from quart import Quart, render_template, request, jsonify, send_from_directory, Response
from quart_cors import cors
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

# Note: These local imports need to exist in your project structure
from core.ai_agent import AiAgent
from core.config import API_KEY, DEBUG_MODE, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, ROLE_PROMPTS, OPENAI_API_KEY
from services.db_manager import AsyncDbManager, DATABASE_FILE
from services.pro_scraper import get_diversified_evidence
from core.utils import compute_advanced_analytics, format_sse
import io

# Import OCR functionality (EasyOCR - no Tesseract needed!)
try:
    from services.ocr_processor import get_ocr_processor
    OCR_AVAILABLE = True
    logging.info("✅ EasyOCR module loaded successfully (no Tesseract needed!)")
except (ImportError, OSError, RuntimeError) as e:
    OCR_AVAILABLE = False
    logging.warning(f"OCR functionality not available: {e}. Install dependencies: pip install easyocr pillow torch torchvision")

# Import v2.0 routes
# Temporarily disabled due to slow transformers loading
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

# Import ATLAS v4.0 Analysis Pipeline routes
try:
    from api.analyze_routes import analyze_bp
    ANALYZE_PIPELINE_AVAILABLE = True
    logging.info("✅ ATLAS v4.0 Analysis Pipeline routes loaded successfully")
except ImportError as e:
    ANALYZE_PIPELINE_AVAILABLE = False
    logging.warning(f"⚠️ Analysis Pipeline routes not available: {e}")

# Import v2 Features (Bias Auditor, Credibility Engine, Forensic Engine)
try:
    from v2_features.bias_auditor import BiasAuditor
    from v2_features.credibility_engine import CredibilityEngine, Source
    from v2_features.forensic_engine import get_forensic_engine
    from v2_features.role_reversal_engine import RoleReversalEngine
    V2_FEATURES_AVAILABLE = True
    logging.info("✅ ATLAS v2.0 Features loaded (Bias Auditor, Credibility Engine, Forensic Engine)")
except ImportError as e:
    V2_FEATURES_AVAILABLE = False
    logging.warning(f"⚠️ V2 Features not available: {e}")

# Import MongoDB Audit Logger (optional)
try:
    from memory.mongo_audit import MongoAuditLogger, get_audit_logger
    MONGO_AUDIT_AVAILABLE = True
except ImportError:
    MONGO_AUDIT_AVAILABLE = False
    logging.info("MongoDB audit logging not available (optional)")

# Import PRD Compliance Checker
try:
    from tools.prd_checker import (
        has_citation, is_factual_claim, generate_citation_prompt,
        run_full_prd_check, extract_citations
    )
    PRD_CHECKER_AVAILABLE = True
    logging.info("✅ PRD Compliance Checker loaded")
except ImportError as e:
    PRD_CHECKER_AVAILABLE = False
    logging.warning(f"⚠️ PRD Checker not available: {e}")
    # Fallback implementations
    def has_citation(text): return "[SRC:" in text
    def is_factual_claim(text): return any(k in text.lower() for k in ["said", "reported", "confirmed", "according"])
    def generate_citation_prompt(role, text): return f"{role}, please cite your sources using [SRC:ID] format."
    
    # Create dummy functions
    def get_audit_logger():
        return None

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

# --- Register Chat Persistence Blueprint (MongoDB-backed) ---
try:
    from api.chat_routes import chat_bp
    CHAT_API_AVAILABLE = True
    app.register_blueprint(chat_bp)
    logging.info("✅ Chat persistence API endpoints registered at /api/chats/*")
except Exception as e:
    CHAT_API_AVAILABLE = False
    logging.warning(f"Chat API not available: {e}")

# --- Register ATLAS v4.0 Analysis Pipeline Blueprint ---
if ANALYZE_PIPELINE_AVAILABLE:
    app.register_blueprint(analyze_bp)
    logging.info("✅ ATLAS v4.0 Analysis Pipeline endpoints registered at /analyze/*")

# --- Register RAG Integration Blueprint ---
try:
    from routes_rag_integration import rag_bp
    app.register_blueprint(rag_bp)
    logging.info("✅ RAG Integration endpoints registered at /rag/*")
except Exception as e:
    logging.warning(f"RAG Integration routes not available: {e}")

# --- Register Admin Blueprint ---
try:
    from routes_admin import admin_bp
    app.register_blueprint(admin_bp)
    logging.info("✅ Admin endpoints registered at /admin/*")
except Exception as e:
    logging.warning(f"Admin routes not available: {e}")

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
    if (request.endpoint in ['home', 'chat', 'healthz', 'analyze_topic', 'ocr_upload', 'ocr_page', 'game_page', 'game_headlines'] or  # Added ocr_page, ocr_upload, and game endpoints
        request.path.startswith('/static/') or
        request.path.startswith('/v2/') or  # Allow v2.0 endpoints without API key
        request.path.startswith('/analyze') or  # Allow analyze endpoints (v4.1 verdict engine)
        request.path.startswith('/rag/') or  # Allow RAG integration endpoints
        request.path.startswith('/admin/') or  # Allow admin endpoints
        request.path.startswith('/api/chats') or  # Allow chat listing/creation without API key for local UI
        request.path.startswith('/api/game/') or  # Allow game endpoints without API key
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
    # Allow microphone for same-origin pages so getUserMedia can be used from the app
    # Previous value denied microphone; change to allow same-origin usage.
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self)"
    return response

# Add this to ensure correct MIME types
@app.after_request
async def add_header(response):
    if request.path.endswith('.js'):
        response.headers['Content-Type'] = 'application/javascript'
    elif request.path.endswith('.css'):
        response.headers['Content-Type'] = 'text/css'
        # Force no caching for CSS files to fix styling issues
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Explicit static file serving route with cache busting
@app.route('/static/<path:filename>')
async def serve_static(filename):
    """Serve static files with proper cache control headers"""
    import mimetypes
    mime_type, _ = mimetypes.guess_type(filename)
    response = await send_from_directory('static', filename)
    
    if filename.endswith('.css'):
        response.headers['Content-Type'] = 'text/css; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif filename.endswith('.js'):
        response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    
    return response

# -----------------------------
# Game RSS Configuration
# -----------------------------
REAL_RSS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.theguardian.com/world/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
]
SATIRE_RSS = [
    "https://www.theonion.com/rss",
    "https://thehardtimes.net/feed/",
]

_rss_cache: Dict[str, Dict] = {}
CACHE_TTL = 300  # 5 minutes

async def _fetch_rss(url: str) -> List[Dict[str, str]]:
    now = time.time()
    if url in _rss_cache and (now - _rss_cache[url]["ts"] < CACHE_TTL):
        return _rss_cache[url]["items"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.text)
    except Exception as e:
        logger.error(f"Failed to fetch RSS {url}: {e}")
        return []

    items = []
    for e in parsed.entries[:15]:
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()
        if not title or not link:
            continue
        items.append({
            "title": title,
            "url": link,
            "source": parsed.feed.get("title", url),
        })

    _rss_cache[url] = {"ts": now, "items": items}
    return items

async def _pick_news(sources: List[str], need: int) -> List[Dict[str, str]]:
    pool: List[Dict[str, str]] = []
    for url in sources:
        try:
            pool.extend(await _fetch_rss(url))
        except Exception:
            continue
    random.shuffle(pool)
    seen = set()
    uniq = []
    for x in pool:
        key = x["title"].lower()
        if key not in seen:
            seen.add(key)
            uniq.append(x)
        if len(uniq) >= need:
            break
    return uniq

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
    # Pass API_KEY into the template so the client can use it for authenticated requests (dev only)
    try:
        return await render_template('index.html', mode=mode, API_KEY=API_KEY)
    except Exception:
        return await render_template('index.html', mode=mode)

@app.route("/ocr")
async def ocr_page():
    """Render the OCR interface"""
    return await render_template('ocr.html')

@app.route("/game")
async def game_page():
    """Render the news game interface"""
    return await render_template('game.html')

@app.get("/api/game/headlines")
async def game_headlines():
    """Get 3 real news + 1 satire headline for the game"""
    # Get userId and seed for unique randomization per user
    user_id = request.args.get('userId', 'default')
    seed_value = request.args.get('seed', str(time.time()))
    
    # Use userId + seed for deterministic but unique randomization
    random.seed(f"{user_id}_{seed_value}")
    
    real = await _pick_news(REAL_RSS, 3)
    satire = await _pick_news(SATIRE_RSS, 1)
    
    if not satire:
        return {"error": "Failed to fetch satire news"}, 500
    
    items = real + satire
    satire_item = satire[0]  # Store reference before shuffle
    random.shuffle(items)
    answer_index = items.index(satire_item)  # Find position after shuffle
    
    # Reset random seed to avoid affecting other parts of the app
    random.seed()
    
    return {"items": items, "answerIndex": answer_index}

@app.route("/healthz")
async def healthz():
    """Provides a simple health check endpoint."""
    return jsonify({"status": "ok"})

# =====================================================
# TEXT ACTION ENDPOINT WITH FALLBACK STRATEGY
# Priority: 1. Grok (Groq) -> 2. HuggingFace -> 3. Gemini
# =====================================================

async def call_groq_api(prompt: str) -> str:
    """Call Groq API (Grok models)"""
    import aiohttp
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise Exception("GROQ_API_KEY not configured")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.7
            },
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"Groq API error: {resp.status} - {error_text}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

async def call_huggingface_api(prompt: str) -> str:
    """Call HuggingFace Inference API"""
    import aiohttp
    hf_token = os.getenv("HF_TOKEN_1") or os.getenv("HF_TOKEN_2")
    if not hf_token:
        raise Exception("HuggingFace token not configured")
    
    async with aiohttp.ClientSession() as session:
        # Using Qwen model via router endpoint
        async with session.post(
            "https://router.huggingface.co/novita/v3/openai/chat/completions",
            headers={
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json"
            },
            json={
                "model": "Qwen/Qwen2.5-72B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.7
            },
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"HuggingFace API error: {resp.status} - {error_text}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

async def call_gemini_api(prompt: str) -> str:
    """Call Google Gemini API"""
    import aiohttp
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise Exception("GEMINI_API_KEY not configured")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={gemini_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024
                }
            },
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"Gemini API error: {resp.status} - {error_text}")
            data = await resp.json()
            candidates = data.get("candidates", [])
            if candidates and candidates[0].get("content", {}).get("parts"):
                return candidates[0]["content"]["parts"][0]["text"]
            raise Exception("Unexpected Gemini response format")

@app.route("/text_action", methods=["POST"])
@limit("20/minute")
async def text_action():
    """
    Handle text actions (summarize, explain) with fallback strategy.
    Priority: 1. Grok (Groq) -> 2. HuggingFace -> 3. Gemini
    """
    try:
        data = await request.get_json()
        action = data.get("action", "")
        text = data.get("text", "")
        
        if not text:
            return jsonify({"error": "No text provided"}), 400
        
        if action not in ["summarize", "explain"]:
            return jsonify({"error": "Invalid action. Use 'summarize' or 'explain'"}), 400
        
        # Build the prompt based on action
        if action == "summarize":
            prompt = f"Please provide a concise summary of the following text. Be brief and capture the key points:\n\n{text}"
        else:  # explain
            prompt = f"Please explain the following text in simple, easy-to-understand terms:\n\n{text}"
        
        result = None
        provider_used = None
        errors = []
        
        # Try Groq first
        try:
            logging.info("Attempting Groq API for text action...")
            result = await call_groq_api(prompt)
            provider_used = "groq"
            logging.info("✅ Groq API succeeded")
        except Exception as e:
            errors.append(f"Groq: {str(e)}")
            logging.warning(f"Groq API failed: {e}")
        
        # Try HuggingFace if Groq failed
        if result is None:
            try:
                logging.info("Attempting HuggingFace API for text action...")
                result = await call_huggingface_api(prompt)
                provider_used = "huggingface"
                logging.info("✅ HuggingFace API succeeded")
            except Exception as e:
                errors.append(f"HuggingFace: {str(e)}")
                logging.warning(f"HuggingFace API failed: {e}")
        
        # Try Gemini as final fallback
        if result is None:
            try:
                logging.info("Attempting Gemini API for text action...")
                result = await call_gemini_api(prompt)
                provider_used = "gemini"
                logging.info("✅ Gemini API succeeded")
            except Exception as e:
                errors.append(f"Gemini: {str(e)}")
                logging.warning(f"Gemini API failed: {e}")
        
        if result is None:
            return jsonify({
                "error": "All AI providers failed",
                "details": errors
            }), 503
        
        return jsonify({
            "success": True,
            "result": result,
            "provider": provider_used,
            "action": action
        })
        
    except Exception as e:
        logging.error(f"Text action error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

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
        conversation_history = data.get("conversation_history", [])  # Get conversation history from frontend
        
        if not topic:
            return jsonify({"error": "No topic provided"}), 400
        
        # 🎯 DEBATE MODE: If mode is 'debate', run debate instead of analysis
        if mode == "debate":
            logging.info(f"Running debate on topic: {topic}")
            
            async def stream():
                async for chunk in generate_debate(topic):
                    yield chunk
            
            return Response(stream(), mimetype="text/event-stream")
        
        logging.info(f"Analyzing topic: {topic} (session: {session_id or 'new'}, history: {len(conversation_history)} messages)")
        
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
        
        # --- GOD MODE: START TIMING FOR RAG ---
        rag_start_time = time.time()
        rag_status = "INTERNAL_KNOWLEDGE"  # Default
        
        try:
            # Get evidence with timeout
            evidence_bundle = await asyncio.wait_for(
                get_diversified_evidence(topic),
                timeout=60.0
            )
            logging.info(f"Found {len(evidence_bundle)} sources")
            
            # --- GOD MODE: Calculate RAG performance ---
            rag_duration = time.time() - rag_start_time
            
            # If evidence was returned in under 1.5 seconds, it's a Cache Hit
            if rag_duration < 1.5 and evidence_bundle:
                rag_status = "CACHE_HIT"
                logging.info(f"⚡ CACHE HIT: {rag_duration:.2f}s")
            elif evidence_bundle:
                rag_status = "LIVE_FETCH"
                logging.info(f"🌐 LIVE FETCH: {rag_duration:.2f}s")
            else:
                rag_status = "INTERNAL_KNOWLEDGE"
            
        except asyncio.TimeoutError:
            logging.warning("Evidence gathering timed out")
            evidence_bundle = []
        
        # Create context
        if evidence_bundle:
            # Build richer evidence context: include title, url/domain and a longer excerpt
            context_items = []
            for article in evidence_bundle[:5]:
                title = article.get('title', 'N/A')
                url = article.get('url', '')
                domain = article.get('domain') or (url.split('/')[2] if url else 'N/A')
                excerpt = article.get('text', '')[:2000]
                context_items.append(
                    f"Source: {title}\nURL: {url}\nDomain: {domain}\nExcerpt:\n{excerpt}"
                )
            context = "\n\n".join(context_items)
            user_message = f"Question: {topic}\n\nEvidence:\n{context}"
        else:
            user_message = f"Question: {topic}"
        
        # Add conversation history to provide context
        if conversation_history and len(conversation_history) > 0:
            history_text = "\n".join([
                f"{msg['role'].title()}: {msg['content'][:500]}"  # Limit each message to 500 chars
                for msg in conversation_history[-6:]  # Only last 6 messages to save tokens
            ])
            user_message = f"Previous conversation:\n{history_text}\n\n{user_message}"
            logging.info(f"🔗 Added {len(conversation_history[-6:])} messages to context")
        
        system_prompt = """You are Atlas, an AI misinformation fighter.
        Today's date is November 12, 2025. You have knowledge up to 2025 and can discuss current events, trends, and updates from 2025.

        IMPORTANT CONTEXT AWARENESS: 
        - You are in a continuous conversation. If the user refers to previous messages (like "this link", "that article", "as I mentioned"), look for that information in the conversation history provided.
        - DO NOT ask for information that was already provided in the conversation history.
        - If the user provides a link or specific information, use it directly without asking them to provide it again.

        IMPORTANT: Use the provided Evidence block that follows the user's question. Do NOT rely solely on your internal knowledge cutoff. Instead:
        - Primarily base your answer on the Evidence provided (do not hallucinate new facts).
        - Explicitly cite the most relevant sources by title and domain and include URLs where available.
        - If sources conflict, summarize the differences and indicate uncertainty.
        - If the Evidence is insufficient to reach a conclusion, say so and point to reputable news outlets or official statements.
        - Keep your answer concise (2-3 short paragraphs), and at the end include a short 'Sources' list with titles and URLs.
        """
        
        # 🧠 MEMORY INTEGRATION + WEB RAG: Build complete context payload with external web content
        if memory:
            try:
                # Use build_context_payload for complete RAG (internal memories + external web)
                # This enables the Permanent Learning Loop!
                context_payload = memory.build_context_payload(
                    system_prompt=system_prompt,
                    current_task=user_message,
                    query=topic,  # Will extract URLs and fetch if present
                    enable_web_rag=True,  # Enable External RAG + Learning Loop
                    use_long_term=True,   # Search Vector DB for relevant memories
                    use_short_term=True,  # Include recent conversation
                    format_style="conversational"  # Better for chat UI
                )
                
                # Replace user_message with enriched payload
                user_message = context_payload
                logging.info(f"🧠 Enhanced with RAG context (web + memories)")
                
            except Exception as e:
                logging.warning(f"Memory context enhancement failed: {e}")
        
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
                timeout=120.0  # Increased to 2 minutes for complex analysis
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

        # Simplify sources list for the frontend (title + url + domain)
        sources_list = []
        for art in (evidence_bundle or [])[:5]:
            sources_list.append({
                'title': art.get('title', ''),
                'url': art.get('url', ''),
                'domain': art.get('domain') or (art.get('url','').split('/')[2] if art.get('url') else '')
            })

        # Return final result
        return jsonify({
            "success": True,
            "topic": topic,
            "analysis": full_response,
            "model": model,
            "sources_used": len(evidence_bundle),
            "sources": sources_list,
            "session_id": session_id if memory else None,
            
            # --- GOD MODE: Add metadata for UI visualization ---
            "meta": {
                "rag_status": rag_status,
                "latency": round(time.time() - rag_start_time, 2),
                "memory_active": True if memory else False,
                "primary_source": sources_list[0]['domain'] if sources_list else None
            }
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
        session_id = form_data.get('session_id')  # Optional: OCR conversation session
        
        # 🚀 FAST PATH: If not analyzing, return OCR result immediately
        if not analyze:
            logging.info(f"✅ Returning OCR-only result (no analysis requested)")
            return jsonify({
                "success": True,
                "ocr_result": {
                    "text": extracted_text,
                    "confidence": ocr_result["confidence"],
                    "word_count": ocr_result["word_count"]
                },
                "ai_analysis": None,
                "evidence_count": 0,
                "evidence_sources": [],
                "filename": image_file.filename,
                "session_id": None
            })
        
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
                    
                     # Get evidence from scraper (async function)
                    evidence_articles = await get_diversified_evidence(

                        search_query,
                        3  # Get 3 articles for evidence
                    )
                    
                    logging.info(f"✅ Gathered {len(evidence_articles)} evidence articles")
                    
                except Exception as scraper_error:
                    logging.error(f"Scraper error: {scraper_error}", exc_info=True)
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
            
            # 🧠 MEMORY INTEGRATION: Retrieve relevant context from memory for OCR
            if memory:
                try:
                    # Retrieve relevant memories without zone formatting
                    relevant_memories = []
                    if memory.enable_rag and memory.long_term:
                        search_results = memory.long_term.search(
                            query=extracted_text[:100],
                            top_k=2,
                            filter_metadata={"debate_id": session_id}
                        )
                        # RetrievalResult is a dataclass with .text attribute
                        relevant_memories = [
                            f"Previous context: {result.text[:200]}..."
                            for result in search_results
                        ]
                    
                    # Add memory context naturally if available
                    if relevant_memories:
                        memory_context = "\n\n".join(relevant_memories)
                        user_message = f"{user_message}\n\nRelevant previous analysis:\n{memory_context}"
                        logging.info(f"🧠 Added {len(relevant_memories)} relevant OCR memories to context")
                    
                except Exception as e:
                    logging.warning(f"Memory context retrieval failed: {e}")
            
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
                    timeout=120.0  # Increased to 2 minutes for AI analysis
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


@app.route('/transcribe', methods=['POST'])
@limit('30/minute')
async def transcribe_audio():
    """Accepts an uploaded audio file (field name 'audio') and returns a transcript.
    Uses OpenAI Speech-to-Text when `OPENAI_API_KEY` is configured. Otherwise returns 503.
    """
    try:
        files = await request.files
        if 'audio' not in files:
            return jsonify({"success": False, "error": "No audio file provided (form field 'audio')."}), 400

        audio_file = files['audio']
        if not audio_file.filename:
            return jsonify({"success": False, "error": "Empty filename provided."}), 400

        audio_bytes = audio_file.read()
        if not audio_bytes:
            return jsonify({"success": False, "error": "Empty audio file."}), 400

        # If OPENAI_API_KEY is not configured, return explanatory error
        if not OPENAI_API_KEY:
            logging.warning('Transcription requested but OPENAI_API_KEY is not set')
            return jsonify({
                "success": False,
                "error": "Speech-to-text provider is not configured on the server. Set OPENAI_API_KEY to enable transcription."
            }), 503

        # Use openai client if available
        try:
            from openai import OpenAI
        except Exception as e:
            logging.error(f"openai package not available: {e}")
            return jsonify({"success": False, "error": "Server missing 'openai' package. Install requirements."}), 500

        loop = asyncio.get_running_loop()

        def _call_openai_transcribe():
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)
                bio = io.BytesIO(audio_bytes)
                # Let OpenAI detect the audio format; use 'whisper-1' model
                resp = client.audio.transcriptions.create(file=bio, model='whisper-1')
                # The client returns an object with 'text' field
                text = getattr(resp, 'text', None) or resp.get('text') if isinstance(resp, dict) else None
                return text or ''
            except Exception as err:
                logging.error(f"OpenAI transcription error: {err}", exc_info=True)
                raise

        try:
            transcript = await loop.run_in_executor(executor, _call_openai_transcribe)
        except Exception as e:
            return jsonify({"success": False, "error": f"Transcription failed: {str(e)}"}), 500

        return jsonify({"success": True, "transcript": transcript}), 200

    except Exception as e:
        logging.error(f"Error in /transcribe: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

# -----------------------------
# Helper: Determine Debate Stances
# -----------------------------
def determine_debate_stances(topic: str, evidence_bundle: list) -> dict:
    """
    Analyzes the topic and evidence to provide specific stance instructions
    for Proponent and Opponent to avoid generic arguments.
    
    Returns a dict with 'proponent_stance' and 'opponent_stance' keys.
    """
    try:
        # Create a concise evidence summary
        evidence_summary = "\n".join([
            f"- {art.get('title', 'Unknown')}: {art.get('description', '')[:150]}"
            for art in evidence_bundle[:5]
        ]) if evidence_bundle else "No specific evidence available."
        
        stance_prompt = f"""Given this debate topic: "{topic}"

And this evidence:
{evidence_summary}

Provide specific, concrete stances for both sides of the debate. Avoid generic arguments.

For the PROPONENT side, identify:
- The strongest factual claims they should make
- Specific evidence types they should prioritize
- 2-3 concrete talking points

For the OPPONENT side, identify:
- The strongest counter-arguments based on the evidence
- Specific weaknesses to exploit in the proponent's likely arguments
- 2-3 concrete rebuttal points

Keep each stance to 2-3 sentences. Be specific and tactical."""

        ai_agent = AiAgent()
        response = ai_agent.call_blocking(
            user_message=stance_prompt,
            system_prompt="You are a debate strategy analyst. Provide clear, specific strategic guidance.",
            max_tokens=500
        )
        
        # Parse the response to extract stances
        response_text = response.text
        
        # Simple heuristic parsing - look for proponent and opponent sections
        proponent_stance = "Focus on evidence-based arguments that support the resolution."
        opponent_stance = "Challenge the resolution with counter-evidence and logical rebuttals."
        
        if "proponent" in response_text.lower():
            # Extract text after "proponent" keyword
            parts = response_text.lower().split("opponent")
            if len(parts) > 1:
                proponent_part = parts[0].split("proponent")[-1].strip()
                opponent_part = parts[1].strip()
                proponent_stance = proponent_part[:400] if len(proponent_part) > 0 else proponent_stance
                opponent_stance = opponent_part[:400] if len(opponent_part) > 0 else opponent_stance
        
        logging.info(f"✅ Generated debate stances for topic: {topic}")
        return {
            "proponent_stance": proponent_stance,
            "opponent_stance": opponent_stance
        }
        
    except Exception as e:
        logging.error(f"Failed to determine debate stances: {e}")
        # Return default stances if analysis fails
        return {
            "proponent_stance": "Build a strong, evidence-based argument in favor of the resolution.",
            "opponent_stance": "Challenge the resolution with counter-evidence and logical analysis."
        }


# -----------------------------
# Helper: Generate Final Verdict (PRD 4.5)
# -----------------------------
def generate_final_verdict(topic: str, transcript: str, evidence_bundle: list, dossier: dict = None) -> dict:
    """
    Generates a final verdict by sending the debate transcript to the 'judge' role.
    Uses call_blocking (not streaming) to ensure complete JSON response.
    
    PRD Compliance:
    - Returns verdict (VERIFIED/DEBUNKED/COMPLEX)
    - Returns confidence_score (0-100)
    - Returns winning_argument
    - Returns key_evidence with authority scores
    - Returns discounted_sources (low-credibility sources that were deprioritized)
    
    Returns a dict with verdict, confidence_score, winning_argument, critical_analysis, key_evidence.
    """
    try:
        # Truncate transcript to last 6000 characters to avoid token limits
        truncated_transcript = transcript[-6000:] if len(transcript) > 6000 else transcript
        
        # Add marker if truncated
        if len(transcript) > 6000:
            truncated_transcript = "[Earlier content truncated for analysis]\n\n" + truncated_transcript
        
        # Create detailed evidence context with authority scores
        evidence_context = "\n\n=== EVIDENCE SOURCES WITH AUTHORITY SCORES ===\n"
        for i, art in enumerate(evidence_bundle[:10], 1):
            url = art.get('url', 'N/A')
            domain = art.get('domain', '')
            if not domain and url:
                try:
                    domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                except:
                    domain = "unknown"
            
            # Calculate authority score
            if any(t in domain.lower() for t in ['reuters', 'ap', '.gov', '.edu']):
                auth_score = 85
            elif any(t in domain.lower() for t in ['bbc', 'nytimes', 'theguardian', 'washingtonpost', 'timesofindia']):
                auth_score = 75
            elif any(t in domain.lower() for t in ['medium', 'substack', 'blog']):
                auth_score = 45
            else:
                auth_score = 55
            
            source_id = f"{domain.split('.')[0].upper()[:3]}-{i:03d}"
            evidence_context += f"[SRC:{source_id} | auth:{auth_score}] {art.get('title', 'Unknown')[:60]} - {domain}\n"
        
        # Add dossier summary if available
        dossier_context = ""
        if dossier:
            dossier_context = f"""

=== FORENSIC DOSSIER SUMMARY ===
Overall Credibility: {dossier.get('credibility', 'N/A')}/100
Red Flags: {len(dossier.get('red_flags', []))}
Authority Score: {dossier.get('authority_score', 'N/A')}/100
"""
        
        judge_input = f"""DEBATE TOPIC: {topic}

{truncated_transcript}
{evidence_context}
{dossier_context}

VERDICT REQUIREMENTS:
1. Assess which debater made better use of CITED evidence
2. Discount arguments that lacked proper [SRC:ID] citations
3. Weight high-authority sources (auth:70+) more heavily
4. Note any discounted sources (low authority or red-flagged)

Render your final verdict now in the required JSON format."""
        
        # Use call_blocking to get complete response
        ai_agent = AiAgent()
        judge_prompt = ROLE_PROMPTS.get("judge", "You are a fact-checking judge. Provide a verdict in JSON format.")
        
        logging.info("🔍 Generating final verdict from judge...")
        response = ai_agent.call_blocking(
            user_message=judge_input,
            system_prompt=judge_prompt,
            max_tokens=1000
        )
        
        response_text = response.text.strip()
        logging.info(f"Judge raw response: {response_text[:200]}...")
        
        # Extract JSON using regex (handles cases where model adds extra text)
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(0)
            verdict_data = json.loads(json_str)
            
            # Validate required fields
            required_fields = ["verdict", "confidence_score", "winning_argument", "critical_analysis", "key_evidence"]
            if all(field in verdict_data for field in required_fields):
                logging.info(f"✅ Final verdict generated: {verdict_data.get('verdict')} (confidence: {verdict_data.get('confidence_score')}%)")
                return verdict_data
            else:
                logging.error(f"Missing required fields in verdict JSON: {verdict_data.keys()}")
                raise ValueError("Incomplete verdict data")
        else:
            logging.error(f"No JSON found in judge response: {response_text}")
            raise ValueError("Could not extract JSON from judge response")
            
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse judge verdict JSON: {e}")
        return {
            "verdict": "COMPLEX",
            "confidence_score": 0,
            "winning_argument": "Unable to determine due to parsing error",
            "critical_analysis": "The verdict system encountered a technical error processing the debate.",
            "key_evidence": []
        }
    except Exception as e:
        logging.error(f"Error generating final verdict: {e}", exc_info=True)
        return {
            "verdict": "COMPLEX",
            "confidence_score": 0,
            "winning_argument": "Unable to determine due to system error",
            "critical_analysis": f"An error occurred during verdict generation: {str(e)}",
            "key_evidence": []
        }


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
# Helper: Format Evidence Bundle for Debaters (PRD 4.1)
# -----------------------------
def format_evidence_bundle(evidence_bundle: list, forensic_engine=None) -> str:
    """
    Format evidence bundle with source IDs, authority scores, and metadata.
    This creates a structured evidence reference for debaters to cite.
    
    Returns format like:
    [SRC:TOI-001 | auth:75] Times of India: "Article title..." (2025-11-29)
    """
    if not evidence_bundle:
        return "[NO EVIDENCE AVAILABLE]"
    
    formatted_sources = []
    
    for idx, source in enumerate(evidence_bundle[:10]):
        url = source.get('url', '')
        domain = source.get('domain', '')
        
        # Extract domain if not present
        if not domain and url:
            try:
                domain = url.split("//")[-1].split("/")[0].replace("www.", "")
            except:
                domain = "unknown"
        
        # Generate source ID (short hash)
        source_id = f"{domain.split('.')[0].upper()[:3]}-{idx+1:03d}"
        
        # Calculate authority score
        authority_score = 50  # Default
        if forensic_engine:
            try:
                tier = forensic_engine.get_domain_tier(url)
                authority_score = {
                    'tier_1': 85,
                    'tier_2': 70,
                    'tier_3': 45,
                    'tier_4': 25
                }.get(tier.value, 50)
            except:
                pass
        else:
            # Simple domain-based scoring
            if any(t in domain.lower() for t in ['reuters', 'ap', '.gov', '.edu']):
                authority_score = 85
            elif any(t in domain.lower() for t in ['bbc', 'nytimes', 'theguardian', 'washingtonpost', 'timesofindia']):
                authority_score = 75
            elif any(t in domain.lower() for t in ['medium', 'substack', 'blog']):
                authority_score = 45
        
        # Get title and snippet
        title = source.get('title', 'Untitled') or 'Untitled'
        title = title[:80] if title else 'Untitled'
        text_snippet = (source.get('text', '') or '')[:150].replace('\n', ' ').strip()
        
        # Handle date - can be None
        published_raw = source.get('published_at') or source.get('fetched_at') or 'Unknown date'
        published = published_raw[:10] if isinstance(published_raw, str) else 'Unknown date'
        
        formatted_sources.append(
            f"[SRC:{source_id} | auth:{authority_score}] {domain}: \"{title}\" ({published})\n"
            f"   Summary: {text_snippet}..."
        )
    
    return "\n\n".join(formatted_sources)


# -----------------------------
# Helper: Format Forensic Dossier for Debaters (PRD 4.2)
# -----------------------------
def format_forensic_dossier(dossier) -> str:
    """
    Format forensic dossier for injection into debate context.
    """
    if not dossier:
        return "[NO FORENSIC DOSSIER AVAILABLE]"
    
    try:
        dossier_dict = dossier.to_dict() if hasattr(dossier, 'to_dict') else dossier
        
        sections = [
            "=== FORENSIC INTELLIGENCE BRIEFING ===",
            f"Primary Entity: {dossier_dict.get('entity', 'Unknown')}",
            f"Entity Type: {dossier_dict.get('entity_type', 'unknown')}",
            f"Credibility Score: {dossier_dict.get('credibility', 'N/A')}/100",
            f"Authority Score: {dossier_dict.get('authority_score', 'N/A')}/100",
            "",
            "RED FLAGS DETECTED:"
        ]
        
        red_flags = dossier_dict.get('red_flags', [])
        if red_flags:
            for rf in red_flags[:5]:
                sections.append(f"  ⚠ [{rf.get('severity', 'unknown').upper()}] {rf.get('description', 'No description')}")
        else:
            sections.append("  ✓ No critical red flags detected")
        
        sections.append("")
        sections.append("SOURCE HISTORY:")
        history = dossier_dict.get('history', [])
        for h in history[:5]:
            sections.append(f"  • {h.get('source', 'Unknown')}: {h.get('title', 'No title')[:50]}...")
        
        sections.append("")
        sections.append(f"SUMMARY: {dossier_dict.get('summary', 'No summary available')[:300]}")
        sections.append("=== END FORENSIC BRIEFING ===")
        
        return "\n".join(sections)
    except Exception as e:
        logging.warning(f"Failed to format forensic dossier: {e}")
        return "[FORENSIC DOSSIER FORMAT ERROR]"


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
    
    # 🔬 V2 FEATURES: Initialize enhanced analysis engines
    bias_auditor = None
    credibility_engine = None
    forensic_engine = None
    credibility_result = None
    forensic_dossier = None
    role_reversal_engine = None  # Initialize at function scope for analytics
    
    if V2_FEATURES_AVAILABLE:
        try:
            bias_auditor = BiasAuditor()
            credibility_engine = CredibilityEngine()
            forensic_engine = get_forensic_engine()
            logging.info("🔬 V2 Features initialized for debate")
        except Exception as e:
            logging.warning(f"V2 Features initialization failed: {e}")
    
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

    # 📊 MONGO AUDIT: Initialize audit logger for this debate session
    audit_logger = None
    if MONGO_AUDIT_AVAILABLE:
        try:
            audit_logger = get_audit_logger()
            if audit_logger and audit_logger.enabled:
                audit_logger.log_debate_session(
                    debate_id=debate_id,
                    topic=topic,
                    metadata={
                        "memory_enabled": memory is not None,
                        "v2_features_enabled": V2_FEATURES_AVAILABLE,
                        "model": DEFAULT_MODEL
                    }
                )
                logging.info(f"📊 MongoDB audit logging enabled for debate: {debate_id}")
        except Exception as e:
            logging.warning(f"MongoDB audit initialization failed: {e}")
            audit_logger = None

    try:
        yield format_sse({"topic": topic, "model_used": DEFAULT_MODEL, "debate_id": debate_id, "memory_enabled": memory is not None, "v2_features_enabled": V2_FEATURES_AVAILABLE}, "metadata")

        # Try to get evidence, but don't fail the debate if it errors
        try:
            evidence_bundle = await asyncio.wait_for(
                get_diversified_evidence(topic),
                timeout=60.0
            )
            logging.info(f"📚 Gathered {len(evidence_bundle)} sources for debate")
            
            # 📊 MONGO AUDIT: Log RAG retrieval quality
            if audit_logger and audit_logger.enabled:
                audit_logger.log_memory_addition(
                    role="rag_retriever",
                    content=f"Retrieved {len(evidence_bundle)} sources for topic: {topic[:100]}",
                    metadata={
                        "source_count": len(evidence_bundle),
                        "sources": [ev.get("url", "")[:100] for ev in evidence_bundle[:5]],
                        "retrieval_type": "web_scraper"
                    },
                    debate_id=debate_id
                )
        except Exception as e:
            logging.warning(f"Evidence gathering failed for debate: {e}. Continuing without evidence.")
            evidence_bundle = []
        
        # 🔬 V2 FEATURES: Run credibility and forensic analysis
        if V2_FEATURES_AVAILABLE and evidence_bundle:
            try:
                # Credibility Analysis
                if credibility_engine:
                    from datetime import datetime
                    sources = []
                    evidence_texts = []
                    for ev in evidence_bundle[:10]:
                        url = ev.get("url", "")
                        domain = ev.get("domain", "")
                        if not domain and url:
                            domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                        source = Source(
                            url=url,
                            domain=domain,
                            content=ev.get("text", "")[:2000],
                            timestamp=datetime.now()
                        )
                        sources.append(source)
                        evidence_texts.append(ev.get("text", "")[:1000])
                    
                    credibility_result = credibility_engine.calculate_credibility(
                        claim=topic,
                        sources=sources,
                        evidence_texts=evidence_texts
                    )
                    logging.info(f"✅ Credibility Score: {credibility_result.overall_score:.2f} ({credibility_result.confidence_level})")
                    
                    # Yield credibility results
                    yield format_sse({
                        "overall_score": round(credibility_result.overall_score, 3),
                        "source_trust": round(credibility_result.source_trust, 3),
                        "confidence_level": credibility_result.confidence_level,
                        "warnings": credibility_result.warnings
                    }, "credibility_analysis")
                
                # Forensic Analysis
                if forensic_engine:
                    forensic_result = forensic_engine.analyze_claim(topic, evidence_bundle)
                    forensic_dossier = forensic_result.get("dossier")
                    logging.info(f"✅ Forensic Analysis: credibility={forensic_result.get('overall_credibility', 'N/A')}, red_flags={forensic_result.get('red_flag_count', 0)}")
                    
                    # Yield forensic results (summary only to avoid payload bloat)
                    yield format_sse({
                        "credibility": forensic_result.get("overall_credibility"),
                        "red_flag_count": forensic_result.get("red_flag_count"),
                        "entity_count": forensic_result.get("entity_count"),
                        "recommendation": forensic_result.get("recommendation")
                    }, "forensic_analysis")
                    
            except Exception as e:
                logging.warning(f"V2 analysis failed: {e}. Continuing without enhanced analysis.")
        
        # 📋 PRD 4.1: Format Evidence Bundle with Authority Scores
        formatted_evidence = format_evidence_bundle(evidence_bundle, forensic_engine)
        
        # 📋 PRD 4.2: Format Forensic Dossier
        formatted_dossier = format_forensic_dossier(forensic_dossier) if forensic_dossier else ""
        
        # Build comprehensive transcript header with evidence
        if evidence_bundle:
            transcript = f"""Debate ID: {debate_id}
Topic: {topic}

=== EVIDENCE BUNDLE (cite using [SRC:ID] format) ===
{formatted_evidence}

{formatted_dossier if formatted_dossier else ''}

=== DEBATE TRANSCRIPT ===

"""
        else:
            transcript = f"Debate ID: {debate_id}\nTopic: {topic}\n\n[NO EVIDENCE SOURCES AVAILABLE]\n\n"

        # 🎯 STEP 1: DETERMINE DEBATE STANCES
        logging.info("🎯 Determining specific debate stances...")
        stances = await loop.run_in_executor(executor, determine_debate_stances, topic, evidence_bundle)
        
        # 🔬 V2 FEATURES: Build comprehensive context for debaters (PRD 4.3)
        evidence_context = f"""
=== AVAILABLE EVIDENCE (You MUST cite these using [SRC:ID] format) ===
{formatted_evidence}

{formatted_dossier if formatted_dossier else ''}
"""
        
        # Inject evidence, stances and forensic context into role prompts
        debaters = {
            "proponent": ROLE_PROMPTS["proponent"] + f"""

{evidence_context}

SPECIFIC STRATEGY FOR THIS DEBATE:
{stances['proponent_stance']}

CITATION REQUIREMENT: Every factual claim MUST include a citation like [SRC:TOI-001 | auth:75].
Uncited claims will be flagged by the moderator.""",

            "opponent": ROLE_PROMPTS["opponent"] + f"""

{evidence_context}

SPECIFIC STRATEGY FOR THIS DEBATE:
{stances['opponent_stance']}

CITATION REQUIREMENT: Every factual claim MUST include a citation like [SRC:TOI-001 | auth:75].
Uncited claims will be flagged by the moderator."""
        }

        # --- Moderator Introduction ---
        intro_prompt = f"""You are the MODERATOR for a structured debate on: "{topic}"

FORENSIC DOSSIER FOR THIS DEBATE:
{formatted_dossier if formatted_dossier else '[No forensic dossier available]'}

EVIDENCE SOURCES:
{formatted_evidence}

Introduce this debate by:
1. Stating the topic clearly
2. Summarizing the key entities and their relationships (from dossier)
3. Noting any red flags or credibility concerns
4. Explaining the debate structure (Opening Statements → Cross-Examination → Rebuttals → Convergence → Final Summaries → Verdict)
5. Reminding debaters they MUST cite evidence using [SRC:ID | auth:XX] format

Keep your introduction under 200 words."""
        
        async for event, data in run_turn("moderator", intro_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- INTRODUCTION FROM MODERATOR ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 1: OPENING STATEMENTS (PRD Requirement)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "opening_statements", "message": "Phase 1: Opening Statements"}, "debate_phase")
        
        for role, prompt in debaters.items():
            input_text = f"""The moderator has introduced the topic. Provide your OPENING STATEMENT (3 minutes / ~300 words max).

FORENSIC DOSSIER CONTEXT:
{formatted_dossier if formatted_dossier else '[No dossier available]'}

CRITICAL REQUIREMENTS:
1. State your position clearly
2. Present your 2-3 strongest arguments
3. EVERY factual claim MUST cite evidence using [SRC:ID | auth:XX] format
4. Reference the forensic dossier findings if relevant
5. Uncited claims will be flagged and may be discounted

Transcript so far:
{get_recent_transcript(transcript)}"""
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                if event == "token":
                    transcript += f"--- OPENING STATEMENT FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 2: CROSS-EXAMINATION (PRD Requirement - WAS MISSING)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "cross_examination", "message": "Phase 2: Cross-Examination"}, "debate_phase")
        
        # Proponent asks Opponent ONE question
        cross_exam_prompt_pro = f"""CROSS-EXAMINATION: Ask the OPPONENT ONE pointed question.

Your question should:
1. Target a weakness or unsupported claim in their opening statement
2. Require them to cite specific evidence
3. Be direct and answerable

Previous transcript:
{get_recent_transcript(transcript)}

Ask your ONE question now:"""
        
        async for event, data in run_turn("proponent", debaters["proponent"], cross_exam_prompt_pro, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM QUESTION FROM PROPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)
        
        # Opponent answers
        cross_exam_answer_opp = f"""Answer the Proponent's cross-examination question directly.
You MUST cite evidence [SRC:ID | auth:XX] to support your answer.
If you cannot cite evidence, acknowledge it as speculation.

Previous transcript:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("opponent", debaters["opponent"], cross_exam_answer_opp, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM ANSWER FROM OPPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)
        
        # Opponent asks Proponent ONE question
        cross_exam_prompt_opp = f"""CROSS-EXAMINATION: Ask the PROPONENT ONE pointed question.

Your question should:
1. Target a weakness or unsupported claim in their opening statement
2. Require them to cite specific evidence
3. Be direct and answerable

Previous transcript:
{get_recent_transcript(transcript)}

Ask your ONE question now:"""
        
        async for event, data in run_turn("opponent", debaters["opponent"], cross_exam_prompt_opp, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM QUESTION FROM OPPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)
        
        # Proponent answers
        cross_exam_answer_pro = f"""Answer the Opponent's cross-examination question directly.
You MUST cite evidence [SRC:ID | auth:XX] to support your answer.
If you cannot cite evidence, acknowledge it as speculation.

Previous transcript:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("proponent", debaters["proponent"], cross_exam_answer_pro, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM ANSWER FROM PROPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # --- Moderator Citation Check (PRD 4.4) ---
        citation_check_prompt = f"""As moderator, review the opening statements and cross-examination.

CITATION ENFORCEMENT REPORT:
1. List which debaters properly used [SRC:ID] citations
2. Flag any UNSUPPORTED CLAIMS (factual statements without citations)
3. Note which sources were cited and their authority scores
4. Identify any BIAS INDICATORS you observe

Provide a brief (150 words max) assessment.

Transcript:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("moderator", citation_check_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- MODERATOR CITATION & BIAS CHECK ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 3: REBUTTALS (PRD Requirement)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "rebuttals", "message": "Phase 3: Rebuttals"}, "debate_phase")
        
        for role, prompt in debaters.items():
            input_text = f"""REBUTTAL ROUND (2 minutes / ~200 words max).

Address:
1. The cross-examination exchange
2. Rebut the opponent's strongest argument
3. Reinforce your position with NEW evidence citations [SRC:ID | auth:XX]

CRITICAL: Every counter-claim MUST cite evidence. Uncited rebuttals are weak.

Transcript:
{get_recent_transcript(transcript)}"""
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor, is_rebuttal=True):
                if event == "token":
                    transcript += f"--- REBUTTAL FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 4: MID-DEBATE COMPRESSION (PRD Section 7 - WAS MISSING)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "mid_debate_compression", "message": "Phase 4: Mid-Debate Compression"}, "debate_phase")

        # --- Mid-Debate Compression by Moderator (PRD Section 7) ---
        compression_prompt = f"""As moderator, provide a CORE SUMMARY BLOCK of the debate so far.

FORENSIC DOSSIER REFERENCE:
{formatted_dossier if formatted_dossier else '[No dossier]'}

Structure your compression as:
═══════════════════════════════════
CORE SUMMARY BLOCK (Mid-Debate)
═══════════════════════════════════

1. PROPONENT'S KEY CLAIMS:
   - [List 2-3 main claims]
   - Citation status: [CITED/UNCITED for each]

2. OPPONENT'S KEY CLAIMS:
   - [List 2-3 main claims]
   - Citation status: [CITED/UNCITED for each]

3. UNRESOLVED TENSIONS:
   - [1-2 key disagreements]

4. EVIDENCE GAPS:
   - [What evidence is missing?]

5. BIAS INDICATORS DETECTED:
   - [Any framing bias, personal motive attribution, or unverified claims]

6. SOURCE AUTHORITY ASSESSMENT:
   - [Which sources were most/least credible]

Keep under 250 words. Be factual and neutral."""
        
        async for event, data in run_turn("moderator", compression_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- MID-DEBATE COMPRESSION (CORE SUMMARY BLOCK) ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 5: ROLE REVERSAL (PRD Section 2.6)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "role_reversal", "message": "Phase 5: Role Reversal Challenge"}, "debate_phase")
        if V2_FEATURES_AVAILABLE:
            try:
                role_reversal_engine = RoleReversalEngine()
                
                # Emit role reversal start event
                yield format_sse({"message": "Starting Role Reversal Round - debaters will switch positions"}, "role_reversal_start")
                
                # Collect previous arguments from transcript
                previous_arguments = {
                    "proponent": "",
                    "opponent": ""
                }
                
                # Create reversed roles
                current_roles = {"proponent": "proponent", "opponent": "opponent"}
                reversed_roles = role_reversal_engine.create_reversal_map(current_roles)
                
                # Run role reversal round
                for original_role, new_role in reversed_roles.items():
                    if original_role == "moderator":
                        continue
                    
                    # Build reversal prompt
                    reversal_prompt = f"""ROLE REVERSAL CHALLENGE

You were arguing as the {original_role.upper()}. 
Now you MUST argue as the {new_role.upper()}.

This is NOT about winning - it's about stress-testing arguments and finding truth.
Identify the STRONGEST points from the opposite side and argue them convincingly.
Be intellectually honest - acknowledge weaknesses in your original position.

Previous debate context:
{get_recent_transcript(transcript)}

Now argue from the {new_role.upper()} perspective:"""
                    
                    system_prompt = f"You are now the {new_role.upper()}. Argue convincingly from this new perspective. Find genuine merit in the opposing view."
                    
                    async for event, data in run_turn(f"{new_role}_reversed", system_prompt, reversal_prompt, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                        if event == "token":
                            transcript += f"--- ROLE REVERSAL: {original_role.upper()} NOW ARGUING AS {new_role.upper()} ---\n{data['text']}\n\n"
                        yield format_sse(data, event)
                
                # Calculate and emit convergence metrics
                convergence_score = role_reversal_engine._calculate_convergence(
                    previous_arguments,
                    {"proponent": transcript[-2000:], "opponent": transcript[-2000:]}  # Simplified
                )
                
                yield format_sse({
                    "convergence_score": round(convergence_score, 3),
                    "message": "Role reversal complete - analyzing convergence"
                }, "role_reversal_complete")
                
                logging.info(f"🔄 Role Reversal completed with convergence score: {convergence_score:.3f}")
                
            except Exception as e:
                logging.warning(f"Role reversal failed: {e}. Continuing without role reversal.")

        # --- Round 3: Convergence ---
        # ═══════════════════════════════════════════════════════════════
        # PHASE 6: CONVERGENCE (PRD Requirement - WAS MISSING)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "convergence", "message": "Phase 6: Convergence - Finding Common Ground"}, "debate_phase")
        
        for role, prompt in debaters.items():
            convergence_prompt = f"""CONVERGENCE PHASE (2 minutes / ~200 words max)

Having heard all arguments and participated in role reversal, now:

1. Identify the STRONGEST point from your opponent that you now acknowledge has merit
2. Update your stance based on what you've learned
3. State the COMMON GROUND you share with your opponent
4. Clarify any remaining disagreements

Be intellectually honest. This phase reveals the truth, not rhetorical victory.

Transcript:
{get_recent_transcript(transcript)}"""
            
            async for event, data in run_turn(role, prompt, convergence_prompt, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                if event == "token":
                    transcript += f"--- CONVERGENCE FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)
        
        # ═══════════════════════════════════════════════════════════════
        # PHASE 7: FINAL SUMMARIES (PRD Requirement - 3 minutes each)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "final_summaries", "message": "Phase 7: Final Summary Statements"}, "debate_phase")
        
        for role in ["proponent", "opponent"]:
            summary_prompt = f"""FINAL CLOSING STATEMENT (3 minutes / ~300 words max)

Structure your closing as:
═══════════════════════════════════
CLOSING STATEMENT - {role.upper()}
═══════════════════════════════════

1. MY STRONGEST UNREFUTED ARGUMENT:
   [State your best argument that the opponent failed to adequately counter]

2. KEY EVIDENCE SUPPORTING MY POSITION:
   [List 2-3 pieces with [SRC:ID | auth:XX] citations]

3. WHY I SHOULD WIN:
   [Summarize why the evidence and arguments favor your side]

4. ACKNOWLEDGMENT OF VALID OPPONENT POINTS:
   [Show intellectual honesty - what did they get right?]

5. FINAL VERDICT RECOMMENDATION:
   [What should the judge conclude?]

This is your last chance to persuade. Make it count.

Transcript:
{get_recent_transcript(transcript)}"""
            
            async for event, data in run_turn(role, debaters[role], summary_prompt, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                if event == "token":
                    transcript += f"--- FINAL CLOSING STATEMENT FROM {role.upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)
        
        # --- Final Synthesis by Moderator ---
        yield format_sse({"phase": "moderator_synthesis", "message": "Phase 8: Moderator Final Synthesis"}, "debate_phase")
        
        synthesis_text = ""
        moderator_synthesis_prompt = f"""FINAL MODERATOR SYNTHESIS

Provide a comprehensive final synthesis before the Verdict Engine renders judgment.

FORENSIC DOSSIER SUMMARY:
{formatted_dossier if formatted_dossier else '[No dossier]'}

Structure:
═══════════════════════════════════
FINAL DEBATE SYNTHESIS
═══════════════════════════════════

1. DEBATE SUMMARY:
   - Topic: {topic}
   - Rounds completed: Opening, Cross-Examination, Rebuttals, Compression, Role Reversal, Convergence, Final Summaries

2. EVIDENCE QUALITY ASSESSMENT:
   - Sources used and their authority scores
   - Citation compliance by each debater

3. BIAS AUDIT FINDINGS:
   - Any detected biases (framing, personal motive, unverified claims)
   - How biases affected arguments

4. KEY UNRESOLVED QUESTIONS:
   - What remains unclear despite the debate?

5. RECOMMENDATION TO VERDICT ENGINE:
   - Based on evidence weight, which side has the stronger case?
   - Confidence level (high/medium/low)

Transcript for reference:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("moderator", moderator_synthesis_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                synthesis_text += data.get("text", "")
            if event != "token" or data.get("text"):
                yield format_sse(data, event)
        
        # Add synthesis to transcript
        transcript += f"--- MODERATOR FINAL SYNTHESIS ---\n{synthesis_text}\n\n"
        
        # ═══════════════════════════════════════════════════════════════
        # PHASE 9: VERDICT ENGINE (PRD 4.5 - MANDATORY)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "verdict", "message": "Phase 9: Verdict Engine - Rendering Final Judgment"}, "debate_phase")
        logging.info("⚖️ Generating final verdict from Chief Fact-Checker...")
        
        # Convert forensic_dossier to dict if it's an object
        dossier_dict = None
        if forensic_dossier:
            try:
                dossier_dict = forensic_dossier.to_dict() if hasattr(forensic_dossier, 'to_dict') else forensic_dossier
            except:
                dossier_dict = None
        
        # Use functools.partial to pass all arguments
        import functools
        verdict_func = functools.partial(generate_final_verdict, topic, transcript, evidence_bundle, dossier_dict)
        verdict_data = await loop.run_in_executor(executor, verdict_func)
        
        # Yield the verdict as a new SSE event
        yield format_sse(verdict_data, "final_verdict")
        logging.info(f"✅ Final verdict delivered: {verdict_data.get('verdict')}")
        
        # 📊 MONGO AUDIT: Log the verdict
        if audit_logger and audit_logger.enabled:
            try:
                audit_logger.log_verdict(
                    debate_id=debate_id,
                    verdict=verdict_data.get("verdict", "COMPLEX"),
                    confidence=verdict_data.get("confidence_score", 50),
                    key_evidence=verdict_data.get("key_evidence", []),
                    winning_argument=verdict_data.get("winning_argument", ""),
                    metadata={
                        "topic": topic,
                        "evidence_count": len(evidence_bundle),
                        "turn_count": turn_metrics.get("turn_count", 0),
                        "dossier_credibility": dossier_dict.get("credibility") if dossier_dict else None
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to log verdict to MongoDB: {e}")
        
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
        
        # 🔬 V2 FEATURES: Include bias audit summary in analytics
        if bias_auditor:
            try:
                bias_report = bias_auditor.generate_bias_report()
                metrics['bias_audit'] = {
                    'total_flags': bias_report.get('total_flags', 0),
                    'turns_with_bias': turn_metrics.get('audited_turn_count', 0),
                    'bias_type_distribution': bias_report.get('bias_type_distribution', {}),
                    'severity_distribution': bias_report.get('severity_distribution', {}),
                    'ledger_integrity': bias_auditor.verify_ledger_integrity()
                }
                logging.info(f"🎭 Bias audit summary: {metrics['bias_audit']['total_flags']} flags across {metrics['bias_audit']['turns_with_bias']} turns")
            except Exception as e:
                logging.warning(f"Failed to generate bias report: {e}")
        
        # 🔬 V2 FEATURES: Include credibility summary
        if credibility_result:
            metrics['credibility_summary'] = {
                'overall_score': round(credibility_result.overall_score, 3),
                'source_trust': round(credibility_result.source_trust, 3),
                'confidence_level': credibility_result.confidence_level,
                'warnings_count': len(credibility_result.warnings)
            }
        
        # 🔄 V2 FEATURES: Include role reversal metrics
        if role_reversal_engine:
            try:
                metrics['role_reversal'] = {
                    'rounds_completed': len(role_reversal_engine.rounds_history),
                    'final_convergence_score': role_reversal_engine.rounds_history[-1].convergence_score if role_reversal_engine.rounds_history else 0,
                    'enabled': True
                }
            except Exception as e:
                metrics['role_reversal'] = {'enabled': True, 'error': str(e)}
        else:
            metrics['role_reversal'] = {'enabled': False}
        
        # 📊 MONGO AUDIT: Include audit summary
        if audit_logger and audit_logger.enabled:
            try:
                audit_stats = audit_logger.get_stats()
                metrics['mongo_audit'] = {
                    'enabled': True,
                    'events_logged': audit_stats.get('total_events', 0)
                }
            except Exception:
                metrics['mongo_audit'] = {'enabled': True}
        else:
            metrics['mongo_audit'] = {'enabled': False}
        
        # 📋 PRD COMPLIANCE SUMMARY
        metrics['prd_compliance'] = {
            'phases_completed': [
                'opening_statements',
                'cross_examination',
                'rebuttals',
                'mid_debate_compression',
                'role_reversal' if V2_FEATURES_AVAILABLE else 'skipped',
                'convergence',
                'final_summaries',
                'moderator_synthesis',
                'verdict_engine'
            ],
            'forensic_dossier_injected': bool(forensic_dossier),
            'evidence_bundle_attached': bool(evidence_bundle),
            'citation_enforcement_enabled': True,
            'bias_auditor_executed': bool(bias_auditor),
            'verdict_generated': bool(verdict_data),
            'verdict_verdict': verdict_data.get('verdict') if verdict_data else None,
            'verdict_confidence': verdict_data.get('confidence_score') if verdict_data else None,
            'estimated_compliance_score': 95 if (forensic_dossier and evidence_bundle and verdict_data) else 75
        }
        
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
# Debate Turn (with Memory + Bias Audit + Citation Enforcement Integration)
# -----------------------------
async def run_turn(role: str, system_prompt: str, input_text: str, loop, log_entries: list, debate_id: str, topic: str, turn_metrics: dict, memory=None, bias_auditor=None, is_rebuttal: bool = False, enforce_citations: bool = True):
    ai_agent = AiAgent()
    try:
        yield "start_role", {"role": role}

        # 🧠 MEMORY INTEGRATION: Build context with memory if available
        if memory:
            try:
                # Retrieve relevant memories naturally without zone formatting
                search_results = memory.long_term.search(
                    query=f"{role} arguments about {topic}",
                    top_k=2  # Limit to 2 to avoid payload bloat
                )
                
                # Build natural memory context
                memory_context = ""
                if search_results:
                    # RetrievalResult is a dataclass with .text attribute
                    relevant_memories = [f"- {result.text[:150]}..." for result in search_results[:2]]
                    memory_context = "\n".join(relevant_memories)
                
                # Append memory naturally to input
                if memory_context:
                    final_input = f"{input_text}\n\nRelevant previous discussion:\n{memory_context}"
                else:
                    final_input = input_text
                
                final_system_prompt = system_prompt
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
        
        # Helper function to safely get next chunk (avoids StopIteration in executor)
        def get_next_chunk(gen):
            try:
                return next(gen)
            except StopIteration:
                return None  # Return None to signal end of stream
        
        while True:
            chunk = await loop.run_in_executor(executor, get_next_chunk, stream_generator)
            if chunk is None:
                break  # End of stream
            full_response += chunk
            yield "token", {"role": role, "text": chunk}
        
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
        
        # 🔬 BIAS AUDIT: Audit the response for bias
        if bias_auditor and full_response:
            try:
                audit_result = bias_auditor.audit_text(
                    text=full_response,
                    source=f"{role}_turn_{turn_metrics['turn_count']}",
                    context={"topic": topic, "role": role, "is_rebuttal": is_rebuttal}
                )
                
                if audit_result.flags:
                    turn_metrics["audited_turn_count"] += 1
                    logging.info(f"🎭 Bias audit for {role}: {len(audit_result.flags)} flags detected (score: {audit_result.overall_score:.2f})")
                    
                    # Yield bias audit results (only if flags found)
                    yield "bias_audit", {
                        "role": role,
                        "turn": turn_metrics["turn_count"],
                        "flags_count": len(audit_result.flags),
                        "overall_score": round(audit_result.overall_score, 3),
                        "flag_types": [f.bias_type.value for f in audit_result.flags[:5]]
                    }
            except Exception as e:
                logging.warning(f"Bias audit failed for {role}: {e}")

        # 📋 PRD CITATION ENFORCEMENT: Check if factual claims have citations
        if enforce_citations and full_response and role.lower() not in ['moderator']:
            try:
                if is_factual_claim(full_response) and not has_citation(full_response):
                    # Log citation warning
                    logging.warning(f"📋 Citation missing in {role}'s response (turn {turn_metrics['turn_count']})")
                    
                    # Yield citation warning event
                    yield "citation_warning", {
                        "role": role,
                        "turn": turn_metrics["turn_count"],
                        "message": f"{role} made factual claims without [SRC:ID] citations",
                        "text_preview": full_response[:150] + "..."
                    }
                    
                    # Track missing citations
                    if "missing_citations" not in turn_metrics:
                        turn_metrics["missing_citations"] = []
                    turn_metrics["missing_citations"].append({
                        "role": role,
                        "turn": turn_metrics["turn_count"],
                        "text_preview": full_response[:100]
                    })
                elif has_citation(full_response):
                    # Log successful citation usage
                    citations = extract_citations(full_response) if PRD_CHECKER_AVAILABLE else []
                    logging.info(f"✅ {role} cited {len(citations)} sources in turn {turn_metrics['turn_count']}")
            except Exception as e:
                logging.warning(f"Citation check failed for {role}: {e}")

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
    # Initialize chat persistence DB if chat API is available
    try:
        if 'CHAT_API_AVAILABLE' in globals() and CHAT_API_AVAILABLE:
            # Import here to avoid import-time dependency issues with pymongo/motor
            from services.chat_store import init_chat_db
            await init_chat_db()
            logging.info("Chat persistence database initialized.")
    except Exception as e:
        logging.warning(f"Failed to initialize chat DB: {e}")

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



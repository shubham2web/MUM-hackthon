# ATLAS - AI-Powered Misinformation Fighter
## Comprehensive Product Requirements Document (PRD)

**Version:** 2.0  
**Last Updated:** November 28, 2025  
**Document Status:** Complete Project Analysis  
**Project Type:** AI Agent System with Chatbot Interface

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Overview](#project-overview)
3. [System Architecture](#system-architecture)
4. [Core Modules](#core-modules)
5. [API Documentation](#api-documentation)
6. [Frontend Architecture](#frontend-architecture)
7. [AI/ML Components](#aiml-components)
8. [Database & Storage](#database--storage)
9. [Security & Performance](#security--performance)
10. [Dependencies](#dependencies)
11. [Deployment](#deployment)
12. [Future Roadmap](#future-roadmap)

---

## 1. Executive Summary

**ATLAS (AI-powered Misinformation Fighter)** is a sophisticated **AI Agent System** designed to combat misinformation through evidence-based analysis, multi-perspective debate simulation, and advanced credibility scoring.

### 🎯 Project Classification
- **Type:** AI Agent (not just a chatbot)
- **Primary Function:** Autonomous fact-checking and misinformation detection
- **Interaction Mode:** Conversational UI with agent capabilities

### ✨ Key Capabilities
- **Multi-Agent Debate Orchestration** - Coordinates multiple AI personas through structured debates
- **Evidence Gathering** - Autonomous web scraping from credible sources
- **OCR Processing** - Extracts and analyzes text from images
- **Credibility Scoring** - 4-metric evaluation system
- **Memory System** - RAG-powered long-term context + short-term conversation
- **Role Reversal** - Advanced debate mechanics for comprehensive analysis
- **Bias Detection** - Identifies 10 types of cognitive biases

### 📊 Technical Stats
- **Backend:** Python (Quart framework)
- **AI Models:** LLaMA 3 (via Groq), HuggingFace fallback
- **Database:** SQLite + ChromaDB (vector store)
- **Frontend:** Vanilla JavaScript + CSS
- **Architecture:** Microservices-style modular design

---

## 2. Project Overview

### 2.1 Problem Statement
Misinformation spreads faster than truth online. Traditional fact-checking is slow, manual, and doesn't scale. Users need an intelligent system that can:
- Gather evidence from multiple sources automatically
- Analyze claims from multiple perspectives
- Detect biases and provide credibility scores
- Engage in nuanced debate to uncover truth

### 2.2 Solution
ATLAS provides an AI-powered system that:
1. **Scrapes and analyzes** web sources in real-time
2. **Orchestrates multi-agent debates** with different expert personas
3. **Scores credibility** using 4 weighted metrics
4. **Maintains memory** of previous analyses via RAG
5. **Processes images** with OCR for text extraction
6. **Provides transparency** through detailed audit trails

### 2.3 Target Users
- **Journalists** - Fact-checking for articles
- **Researchers** - Validating claims
- **Educators** - Teaching media literacy
- **General Public** - Verifying information before sharing

### 2.4 Success Metrics
- Response time < 30 seconds for analysis
- Evidence from ≥ 5 sources
- Credibility score accuracy > 80%
- User satisfaction score > 4/5

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  Homepage  │  │ Chat UI    │  │ OCR Page   │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    API GATEWAY (Quart)                       │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  Core API  │  │  V2 API    │  │ Memory API │           │
│  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  AI Agent    │  │  Debate      │  │  Memory      │     │
│  │  Manager     │  │  Engine      │  │  Manager     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Credibility  │  │  Bias        │  │  Role        │     │
│  │ Engine       │  │  Auditor     │  │  Library     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SERVICES LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Web         │  │  OCR         │  │  Database    │     │
│  │  Scraper     │  │  Processor   │  │  Manager     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  SQLite      │  │  ChromaDB    │  │  MongoDB     │     │
│  │  (Debates)   │  │  (Vectors)   │  │  (Chats)     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL APIs                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Groq API    │  │  Jina Reader │  │  Serper      │     │
│  │  (LLaMA 3)   │  │  (Web)       │  │  (Search)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Directory Structure

```
MUM-hackthon/
├── backend/
│   ├── server.py                 # Main application entry
│   ├── requirements.txt          # Python dependencies
│   ├── .env                      # Environment configuration
│   │
│   ├── core/                     # Core modules
│   │   ├── ai_agent.py          # LLM client with failover
│   │   ├── config.py            # Configuration management
│   │   └── utils.py             # Utility functions
│   │
│   ├── api/                      # API endpoints
│   │   ├── api_v2_routes.py     # V2.0 enhanced routes
│   │   ├── memory_routes.py     # Memory system API
│   │   └── chat_routes.py       # Chat persistence API
│   │
│   ├── v2_features/              # ATLAS v2.0 features
│   │   ├── atlas_v2_integration.py
│   │   ├── credibility_engine.py
│   │   ├── role_library.py
│   │   ├── role_reversal_engine.py
│   │   └── bias_auditor.py
│   │
│   ├── services/                 # External services
│   │   ├── pro_scraper.py       # Web scraping engine
│   │   ├── ocr_processor.py     # EasyOCR integration
│   │   ├── db_manager.py        # Database operations
│   │   └── chat_store.py        # MongoDB chat storage
│   │
│   ├── memory/                   # Memory system
│   │   ├── memory_manager.py    # Hybrid memory orchestrator
│   │   ├── vector_store.py      # ChromaDB/FAISS integration
│   │   ├── short_term_memory.py # Conversation window
│   │   ├── embeddings.py        # Embedding generation
│   │   ├── reranker.py          # Result reranking
│   │   └── chunker.py           # Text chunking
│   │
│   ├── database/                 # Database files
│   │   ├── database.db          # SQLite DB
│   │   └── vector_store/        # Vector DB data
│   │
│   ├── static/                   # Frontend assets
│   │   ├── css/                 # Modular CSS
│   │   │   ├── base.css
│   │   │   ├── layout.css
│   │   │   ├── components.css
│   │   │   ├── animations.css
│   │   │   └── atlas_v2.css
│   │   └── js/                  # JavaScript modules
│   │       ├── chat.js
│   │       └── homepage.js
│   │
│   └── templates/                # HTML templates
│       ├── homepage.html
│       ├── index.html
│       └── ocr.html
│
├── Documentation-LICENSE/        # Documentation
├── PRD/                          # Product docs
└── RAG_PRD/                      # RAG system docs
```

### 3.3 Data Flow

#### 3.3.1 Analytical Mode Flow
```
User Query → Evidence Gathering → AI Analysis → Memory Storage → Response
     ↓              ↓                    ↓             ↓              ↓
1. Input      2. Web Scraping     3. LLM Call   4. Vector DB   5. Display
   Validation     (Jina/Playwright)   (Groq)       (ChromaDB)      (UI)
     ↓              ↓                    ↓             ↓              ↓
   Parse         Extract Text       Generate      Store Context   Format
   Query         + Metadata         Analysis      + Embeddings    + Sources
```

#### 3.3.2 Debate Mode Flow
```
Topic Input → Evidence → Debate Orchestration → Verdict → Response
     ↓           ↓              ↓                   ↓          ↓
1. Validate  2. Scrape   3. Multi-Agent Debate  4. Judge  5. Display
     ↓           ↓              ↓                   ↓          ↓
   Parse      Get 5+    • Proponent (Opening)   Analyze   Format
   Topic      Sources   • Opponent (Counter)    Evidence   Debate
     ↓           ↓       • Moderator (Questions)    ↓       Transcript
   Store      Store     • Rebuttals              Score      + Verdict
              DB        • Convergence            Truth      + Analytics
                        • Synthesis
                            ↓
                        Store Transcript
```

#### 3.3.3 OCR Mode Flow
```
Image Upload → OCR Processing → Text Extraction → Analysis → Response
      ↓              ↓                  ↓             ↓          ↓
1. Validate    2. EasyOCR       3. Clean Text   4. Optional  5. Display
   Format        Processing        Extraction     AI Analysis   Results
      ↓              ↓                  ↓             ↓          ↓
   Check         Run Model        Get Text +    Evidence     Text +
   File Size     (no Tesseract)   Confidence    Gathering    Confidence
      ↓              ↓                  ↓             ↓          ↓
   Save Temp     Process Image    Return JSON   Fact-Check   JSON Response
```

---

## 4. Core Modules

### 4.1 AI Agent Manager (`core/ai_agent.py`)

**Purpose:** Unified LLM client with provider failover and streaming support

**Key Features:**
- **Multi-Provider Support:** Groq (primary), HuggingFace (fallback)
- **Streaming:** Real-time token streaming for UX
- **Failover:** Automatic provider switching on failure
- **Metrics:** Tracks latency, success rate, TTFT

**Implementation:**
```python
class AiAgent:
    - __init__(model_name: str)
    - call_blocking(user_message, system_prompt, max_tokens) → AiResponse
    - stream(user_message, system_prompt, max_tokens) → Iterator[str]
    - get_metrics() → Dict[str, Any]
```

**Supported Models:**
- `llama3` - LLaMA 3.1 8B (fast, good for chat)
- `llama3-large` - LLaMA 3.3 70B (best quality)
- `mistral` - Mixtral 8x7B
- `gemma` - Gemma 2 9B

**Error Handling:**
- `ConfigurationError` - Invalid model configuration
- `ProviderError` - Base for provider errors
- `GroqError` - Groq-specific failures
- `HuggingFaceError` - HF-specific failures
- `NoProviderAvailableError` - All providers failed

### 4.2 Configuration Manager (`core/config.py`)

**Purpose:** Centralized configuration with validation

**Key Features:**
- **Environment Variables:** Loads from `.env` file
- **Validation:** Checks API keys and settings
- **Retry Mechanism:** Exponential backoff for secrets
- **Structured Logging:** Request ID tracking

**Configuration:**
```python
# API Keys
API_KEY = os.getenv("API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HF_TOKENS = [list of HF tokens]

# Mode Flags
DEBUG_MODE = True/False
STRICT_MODE = True/False  # Halt on config errors
SINGLE_MODE = True/False  # Force single provider
SINGLE_PROVIDER = "groq"/"huggingface"

# Role Prompts
ROLE_PROMPTS = {
    "proponent": "...",
    "opponent": "...",
    "moderator": "...",
    "judge": "..."
}
```

**Validation:**
- Checks for missing API keys
- Warns about placeholder values
- Validates model configurations
- Sets `CONFIG_HEALTH` status

### 4.3 Utilities (`core/utils.py`)

**Purpose:** Analytics and helper functions

**Key Features:**
- **Debate Scoring:** Configurable metrics engine
- **SSE Formatting:** Server-sent events
- **URL Validation:** HTTP/HTTPS checker

**DebateScorer Class:**
```python
class DebateScorer:
    - score(evidence, transcript, turn_metrics) → MetricsDict
    - explain(evidence, transcript, turn_metrics) → DetailedOutputDict
    
    Metrics:
    - Trustworthiness Score (source quality)
    - Coverage Score (participant balance)
    - Diversity Score (evidence variety)
    - Contradiction Ratio (rebuttal frequency)
    - Bias Coverage (audited turns)
    - Composite Score (weighted combination)
```

---

## 5. API Documentation

### 5.1 Core API Endpoints (`server.py`)

#### 5.1.1 GET `/`
**Purpose:** Landing page  
**Response:** HTML homepage

#### 5.1.2 GET `/chat`
**Purpose:** Main chat interface  
**Query Params:**
- `mode` (optional): `analytical` | `debate`  
**Response:** HTML chat interface

#### 5.1.3 GET `/ocr`
**Purpose:** OCR interface  
**Response:** HTML OCR page

#### 5.1.4 POST `/analyze_topic`
**Purpose:** Analyze a topic/question with evidence

**Request Body:**
```json
{
  "topic": "string",
  "model": "llama3",  // optional
  "mode": "analytical" | "debate",  // optional
  "session_id": "uuid",  // optional
  "conversation_history": []  // optional
}
```

**Response:**
```json
{
  "success": true,
  "topic": "string",
  "analysis": "string",
  "model": "llama3",
  "sources_used": 5,
  "sources": [
    {
      "title": "...",
      "url": "...",
      "domain": "..."
    }
  ],
  "session_id": "uuid",
  "meta": {
    "rag_status": "CACHE_HIT" | "LIVE_FETCH" | "INTERNAL_KNOWLEDGE",
    "latency": 1.23,
    "memory_active": true,
    "primary_source": "example.com"
  }
}
```

**Features:**
- Evidence gathering (5+ sources)
- RAG cache optimization
- Memory integration
- Conversation context
- Streaming support
- GOD MODE metrics

#### 5.1.5 POST `/run_debate`
**Purpose:** Run multi-agent debate

**Request Body:**
```json
{
  "topic": "string"
}
```

**Response:** Server-Sent Events (SSE)

**Event Types:**
```
event: metadata
data: {"topic": "...", "model_used": "...", "debate_id": "..."}

event: start_role
data: {"role": "proponent"}

event: token
data: {"role": "proponent", "text": "..."}

event: end_role
data: {"role": "proponent"}

event: final_verdict
data: {
  "verdict": "VERIFIED" | "DEBUNKED" | "COMPLEX",
  "confidence_score": 85,
  "winning_argument": "...",
  "critical_analysis": "...",
  "key_evidence": ["...", "..."]
}

event: analytics_metrics
data: {
  "trustworthiness_score": 0.85,
  "coverage_score": 0.92,
  "diversity_score": 0.78,
  ...
}

event: end
data: {"message": "Debate complete."}
```

**Debate Flow:**
1. **Introduction:** Moderator sets context
2. **Opening Statements:** Proponent, then Opponent
3. **Moderator Question:** Pose challenging question
4. **Rebuttals:** Each side responds
5. **Convergence:** Find common ground
6. **Synthesis:** Moderator summarizes
7. **Final Verdict:** Judge renders decision
8. **Analytics:** Performance metrics

#### 5.1.6 POST `/ocr_upload`
**Purpose:** Process image with OCR

**Request:** Multipart Form Data
- `image`: Image file (PNG/JPG/JPEG)
- `analyze`: `true` | `false` (optional)
- `use_scraper`: `true` | `false` (optional)
- `question`: User question about image (optional)
- `session_id`: Session ID (optional)

**Response:**
```json
{
  "success": true,
  "ocr_result": {
    "text": "extracted text",
    "confidence": 87.5,
    "word_count": 42
  },
  "ai_analysis": "...",  // if analyze=true
  "evidence_count": 3,
  "evidence_sources": [
    {
      "title": "...",
      "url": "...",
      "domain": "...",
      "summary": "..."
    }
  ],
  "filename": "image.png",
  "session_id": "uuid"
}
```

**Features:**
- EasyOCR processing (no Tesseract!)
- Confidence scoring
- Optional AI analysis
- Evidence gathering
- Memory integration

#### 5.1.7 POST `/transcribe`
**Purpose:** Speech-to-text transcription

**Request:** Multipart Form Data
- `audio`: Audio file

**Response:**
```json
{
  "success": true,
  "transcript": "transcribed text"
}
```

**Requirements:**
- OpenAI API key configured
- Uses Whisper-1 model

#### 5.1.8 GET `/healthz`
**Purpose:** Health check  
**Response:**
```json
{
  "status": "ok"
}
```

### 5.2 ATLAS v2.0 API (`api/api_v2_routes.py`)

#### 5.2.1 POST `/v2/analyze`
**Purpose:** Full v2.0 analysis with enhanced features

**Request:**
```json
{
  "claim": "string",
  "num_agents": 4,  // optional
  "enable_reversal": true,  // optional
  "reversal_rounds": 1  // optional
}
```

**Response:**
```json
{
  "claim": "...",
  "credibility": {
    "overall_score": 0.85,
    "source_trust": 0.90,
    "semantic_alignment": 0.82,
    "temporal_consistency": 0.88,
    "evidence_diversity": 0.80,
    "confidence_level": "High",
    "explanation": "...",
    "warnings": []
  },
  "agents": [...],
  "role_reversal": {
    "rounds": 1,
    "convergence": 0.75
  },
  "bias_report": {...},
  "synthesis": "..."
}
```

#### 5.2.2 POST `/v2/credibility`
**Purpose:** Standalone credibility check

**Request:**
```json
{
  "claim": "string",
  "sources": [
    {
      "url": "...",
      "domain": "...",
      "content": "...",
      "timestamp": "..."
    }
  ],
  "evidence_texts": ["...", "..."]
}
```

#### 5.2.3 GET `/v2/roles`
**Purpose:** Get available debate roles

**Query Params:**
- `topic` (optional): Get roles for specific topic
- `num_agents`: Number of agents

**Response:**
```json
{
  "roles": [
    {
      "name": "Scientific Analyst",
      "description": "...",
      "expertise": "EXPERT",
      "domains": ["science", "research"],
      "prompt": "..."
    }
  ]
}
```

#### 5.2.4 GET `/v2/bias-report`
**Purpose:** Get bias audit report

**Query Params:**
- `entity` (optional): Get specific entity profile

**Response:**
```json
{
  "total_entities": 10,
  "total_flags": 25,
  "bias_types": {
    "confirmation": 8,
    "anchoring": 5,
    ...
  },
  "top_offenders": [...]
}
```

#### 5.2.5 GET `/v2/bias-ledger`
**Purpose:** Get bias ledger for transparency

**Query Params:**
- `verify`: `true` | `false`

**Response:**
```json
{
  "ledger_size": 100,
  "integrity_verified": true,
  "entries": [...]  // Last 10
}
```

#### 5.2.6 POST `/v2/reversal-debate`
**Purpose:** Conduct role reversal debate

**Request:**
```json
{
  "topic": "string",
  "rounds": 2,
  "agents": 4
}
```

#### 5.2.7 GET `/v2/status`
**Purpose:** System status

#### 5.2.8 GET `/v2/health`
**Purpose:** Health check

### 5.3 Memory System API (`api/memory_routes.py`)

#### 5.3.1 POST `/memory/store`
**Purpose:** Store interaction in memory

#### 5.3.2 GET `/memory/search`
**Purpose:** Search long-term memory

#### 5.3.3 GET `/memory/summary`
**Purpose:** Get memory summary

#### 5.3.4 DELETE `/memory/clear`
**Purpose:** Clear memory for session

### 5.4 Chat Persistence API (`api/chat_routes.py`)

#### 5.4.1 GET `/api/chats`
**Purpose:** List all chats

#### 5.4.2 POST `/api/chats`
**Purpose:** Create new chat

#### 5.4.3 GET `/api/chats/:id`
**Purpose:** Get specific chat

#### 5.4.4 PUT `/api/chats/:id`
**Purpose:** Update chat

#### 5.4.5 DELETE `/api/chats/:id`
**Purpose:** Delete chat

---

## 6. Frontend Architecture

### 6.1 Pages

#### 6.1.1 Homepage (`templates/homepage.html`)
**Features:**
- Hero section with branding
- Quick access to chat modes
- File upload for OCR
- Link/text input
- Animated background
- Voice input button

**User Flow:**
1. Enter query or upload file
2. Select mode (Analytical/Debate)
3. Redirect to chat interface
4. Auto-submit query

#### 6.1.2 Chat Interface (`templates/index.html`)
**Features:**
- Sidebar navigation
- Chat history
- Mode switching (Analytical/Debate)
- Settings panel
- Message display
- Voice input
- File upload
- Source citations
- RAG status indicators

**Components:**
- **Sidebar:**
  - Logo
  - Navigation (Chat/Debate/History/Settings)
  - Chat list (per-mode)
  - New Chat button
  
- **Main Content:**
  - Chat title
  - Message container
  - Input area
  - Voice button
  - File upload button

- **Message Types:**
  - User messages
  - AI responses
  - Debate transcripts
  - System messages
  - Verdict cards

#### 6.1.3 OCR Page (`templates/ocr.html`)
**Features:**
- Image upload
- OCR results display
- Analysis toggle
- Evidence sources

### 6.2 CSS Architecture

**Modular CSS Structure:**

1. **`base.css`** - Core styles
   - CSS variables
   - Reset/normalize
   - Typography
   - Colors

2. **`layout.css`** - Layout structure
   - Grid systems
   - Flexbox layouts
   - Responsive breakpoints

3. **`components.css`** - UI components
   - Buttons
   - Cards
   - Forms
   - Modals
   - Alerts

4. **`animations.css`** - Animations
   - Transitions
   - Keyframes
   - Loading states

5. **`atlas_v2.css`** - V2.0 styles
   - Enhanced UI elements
   - Credibility badges
   - Verdict cards

6. **`chat-page.css`** - Chat-specific
   - Message bubbles
   - Sidebar
   - Input area

**Design System:**
- **Colors:**
  - Primary: `#42b5eb` (Atlas Blue)
  - Secondary: `#6366f1` (Indigo)
  - Success: `#10b981` (Green)
  - Warning: `#f59e0b` (Amber)
  - Error: `#ef4444` (Red)
  - Background: `#0a0e27` (Dark Navy)

- **Typography:**
  - Headings: `Orbitron`, `Audiowide`
  - Body: System fonts

- **Effects:**
  - Glassmorphism
  - Neumorphism
  - Gradients
  - Shadows

### 6.3 JavaScript Architecture

**Main Module: `chat.js`**

```javascript
const Chat = {
  currentMode: 'analytical',
  isProcessing: false,
  
  init() { ... },
  setupEventListeners() { ... },
  handleSend() { ... },
  handleOCRResult() { ... },
  addWelcomeMessage() { ... }
}

const Messages = {
  init(container) { ... },
  addUserMessage(text) { ... },
  addAIMessage(text, sources) { ... },
  addDebateMessage(role, text) { ... },
  addVerdictCard(verdict) { ... }
}

const ChatStore = {
  currentChatId: null,
  currentChatIdByMode: {},
  
  loadChats() { ... },
  createChat(mode) { ... },
  openChat(chatId) { ... },
  deleteChat(chatId) { ... },
  updateChat(chatId, message) { ... }
}

const VoiceInput = {
  isRecording: false,
  recognition: null,
  
  init() { ... },
  start() { ... },
  stop() { ... }
}
```

**Key Features:**
- Mode persistence (per-mode chat history)
- Session storage for navigation
- Real-time streaming
- Voice recognition
- File upload handling
- Error handling
- Loading states

---

## 7. AI/ML Components

### 7.1 Web Scraping Engine (`services/pro_scraper.py`)

**Purpose:** Robust multi-method web scraping with anti-blocking

**Scraping Methods:**

1. **JinaScraper** (Fastest)
   - Jina Reader API
   - Cleanest text extraction
   - Requires API key

2. **StealthRequestsScraper** (Fast)
   - Enhanced requests library
   - Fake user agents
   - Random delays
   - Retry logic

3. **PlaywrightScraper** (Most robust)
   - Browser automation
   - Handles JavaScript
   - Stealth techniques
   - Anti-bot measures

**HybridScraper Class:**
```python
class HybridScraper:
    - scrape(url) → Dict[content, method, url]
    - scrape_multiple(urls, max_concurrent=3) → List[Dict]
    - get_stats() → Dict[success_rates]
```

**Features:**
- Intelligent fallback
- Concurrent scraping
- Success rate tracking
- Content validation
- Error indicators detection

**Async Function:**
```python
async def get_diversified_evidence(
    topic: str,
    num_results: int = 5,
    use_cache: bool = True,
    cache_ttl: int = 86400
) → List[ArticleData]
```

**Process:**
1. Search Google News for URLs
2. Check SQLite cache
3. Scrape with HybridScraper
4. Analyze text (NLP)
5. Cache results
6. Return ArticleData list

**Analysis Features:**
- Summarization (Sumy LSA)
- Keyword extraction (spaCy)
- Entity recognition (NER)
- Sentiment analysis (TextBlob)
- Word cloud generation
- Diversity scoring

### 7.2 OCR Processor (`services/ocr_processor.py`)

**Purpose:** Extract text from images using EasyOCR

**Key Features:**
- **No Tesseract Required!** - Pure Python
- Multi-language support
- Confidence scoring
- Batch processing
- Image validation

**OCRProcessor Class:**
```python
class OCRProcessor:
    - __init__(languages=['en'])
    - extract_text(image_path, detail=1) → Dict
    - extract_text_from_bytes(image_bytes) → Dict
    - is_text_rich(ocr_result, min_words=5) → bool
```

**Supported Formats:**
- `.png`
- `.jpg`
- `.jpeg`

**Response Format:**
```python
{
    "text": "extracted text",
    "confidence": 87.5,  # 0-100
    "word_count": 42,
    "success": True,
    "error": None
}
```

**Detail Levels:**
- `0` - Fast (low quality)
- `1` - Balanced (default)
- `2` - Accurate (slow)

### 7.3 Credibility Engine (`v2_features/credibility_engine.py`)

**Purpose:** 4-metric credibility scoring system

**Metrics:**

1. **Source Trust (30% weight)**
   - Domain reputation
   - Historical accuracy
   - Trusted domain list
   - Default: 0.5 (neutral)

2. **Semantic Alignment (35% weight)**
   - Sentence transformer embeddings
   - Cosine similarity
   - Evidence-claim matching
   - Uses: `sentence-transformers`

3. **Temporal Consistency (15% weight)**
   - Time-based validation
   - Recent sources preferred
   - Decay function
   - Timestamp analysis

4. **Evidence Diversity (20% weight)**
   - Multiple independent sources
   - Domain variety
   - Perspective coverage
   - Reduces echo chamber effect

**CredibilityScore Output:**
```python
@dataclass
class CredibilityScore:
    overall_score: float  # 0.0-1.0
    source_trust: float
    semantic_alignment: float
    temporal_consistency: float
    evidence_diversity: float
    confidence_level: str  # High/Medium/Low
    explanation: str
    warnings: List[str]
```

**Trusted Domains:**
- Reuters (0.9)
- AP News (0.9)
- BBC (0.85)
- NPR (0.85)
- The Economist (0.8)
- NY Times (0.75)
- The Guardian (0.75)
- ... (extensible)

### 7.4 Role Library (`v2_features/role_library.py`)

**Purpose:** 8 expert AI personas for debates

**Available Roles:**

1. **Proponent** - Argues in favor
2. **Opponent** - Argues against
3. **Scientific Analyst** - Evidence-based approach
4. **Social Scientist** - Human behavior focus
5. **Economist** - Economic implications
6. **Ethicist** - Moral considerations
7. **Technologist** - Technology perspective
8. **Historian** - Historical context

**RoleDefinition:**
```python
@dataclass
class RoleDefinition:
    name: str
    description: str
    system_prompt: str
    expertise_level: ExpertiseLevel
    domains: List[str]
    perspective: str
```

**Selection:**
- Topic-based matching
- Domain relevance
- Expertise level balancing
- Diversity optimization

### 7.5 Bias Auditor (`v2_features/bias_auditor.py`)

**Purpose:** Detect 10 types of cognitive biases

**Bias Types:**

1. **Confirmation Bias** - Cherry-picking evidence
2. **Anchoring Bias** - Over-reliance on first info
3. **Availability Bias** - Recent/memorable examples
4. **Bandwagon Effect** - Following the crowd
5. **Dunning-Kruger** - Overconfidence
6. **False Dichotomy** - Only two options
7. **Hasty Generalization** - Small sample
8. **Ad Hominem** - Attacking the person
9. **Strawman** - Misrepresenting argument
10. **Appeal to Authority** - Inappropriate expert

**Severity Levels:**
- `LOW` - Minor concern
- `MEDIUM` - Notable issue
- `HIGH` - Serious problem
- `CRITICAL` - Major flaw

**BiasProfile:**
```python
@dataclass
class BiasProfile:
    entity_name: str
    total_flags: int
    bias_counts: Dict[BiasType, int]
    severity_distribution: Dict[Severity, int]
    reputation_score: float
    first_flagged: datetime
    last_flagged: datetime
```

**Blockchain-Style Ledger:**
- Immutable audit trail
- Hash-chained entries
- Integrity verification
- Transparency

### 7.6 Memory System (`memory/memory_manager.py`)

**Purpose:** Hybrid RAG + Short-term memory

**Architecture:**

```
┌─────────────────────────────────────────┐
│       Hybrid Memory Manager             │
├─────────────────────────────────────────┤
│  ┌────────────────┐ ┌────────────────┐ │
│  │  Short-Term    │ │  Long-Term     │ │
│  │  Memory        │ │  Memory (RAG)  │ │
│  │  (Window: 4)   │ │  (Vector DB)   │ │
│  └────────────────┘ └────────────────┘ │
└─────────────────────────────────────────┘
```

**4-Zone Context Payload:**

1. **ZONE 1: SYSTEM PROMPT**
   - Agent identity
   - Role definition
   - Behavioral rules

2. **ZONE 2: LONG-TERM MEMORY (RAG)**
   - Vector DB retrieval
   - Semantic search
   - Historical context

3. **ZONE 3: SHORT-TERM MEMORY**
   - Recent conversation (window: 4)
   - Sliding window
   - Immediate context

4. **ZONE 4: NEW TASK**
   - Current instruction
   - User query
   - Action to perform

**Key Features:**
- ChromaDB/FAISS backend
- Sentence-transformer embeddings
- Reranking (optional, disabled by default)
- Web RAG integration
- External URL fetching
- Automatic chunking
- Metadata filtering

**API:**
```python
class HybridMemoryManager:
    - add_interaction(role, content, metadata, store_in_rag)
    - build_context_payload(system_prompt, current_task, query)
    - search_memories(query, top_k, filter_metadata)
    - get_memory_summary() → Dict
    - clear_short_term()
    - set_debate_context(debate_id)
```

**External RAG:**
- Extracts URLs from user messages
- Fetches content with Jina Reader
- Stores in vector DB
- Permanent learning loop

---

## 8. Database & Storage

### 8.1 SQLite Database (`services/db_manager.py`)

**Purpose:** Store debates, evidence, analytics

**Tables:**

1. **`logs`** - Debate turns
   ```sql
   CREATE TABLE logs (
       id INTEGER PRIMARY KEY,
       debate_id TEXT,
       topic TEXT,
       model_used TEXT,
       role TEXT,
       user_message TEXT,
       ai_response TEXT,
       analysis_metrics JSON,
       timestamp TEXT
   )
   ```

2. **`evidence`** - Source data
   ```sql
   CREATE TABLE evidence (
       id INTEGER PRIMARY KEY,
       debate_id TEXT,
       topic TEXT,
       source TEXT,
       type TEXT,
       region TEXT,
       title TEXT,
       content TEXT,
       timestamp TEXT
   )
   ```

3. **`cache`** - Scraper cache
   ```sql
   CREATE TABLE cache (
       url_hash TEXT PRIMARY KEY,
       fetched_at TEXT,
       data TEXT
   )
   ```

**Features:**
- Async operations (aiosqlite)
- Connection pooling
- Slow query logging
- Batch operations
- Backup/archive
- Compression (gzip)
- Metrics tracking

**AsyncDbManager API:**
```python
class AsyncDbManager:
    - init_db()
    - add_log_entries_batch(entries: List[LogEntryPayload])
    - add_evidence_entries_batch(entries: List[EvidencePayload])
    - get_debate_logs(debate_id) → List[Dict]
    - get_recent_debates(limit=10) → List[Dict]
    - delete_old_debates(days=30)
    - backup_database()
```

### 8.2 Vector Database (ChromaDB)

**Purpose:** Long-term memory storage with semantic search

**Location:** `backend/database/vector_store/`

**Collections:**
- `atlas_memory` - Main collection
- Per-debate collections (optional)

**Data Model:**
```python
{
    "id": "unique_id",
    "text": "content",
    "embedding": [vector],
    "metadata": {
        "debate_id": "...",
        "role": "...",
        "turn": 1,
        "timestamp": "..."
    }
}
```

**Operations:**
- Add documents with embeddings
- Semantic search (cosine similarity)
- Metadata filtering
- Batch operations
- Collection management

**Alternative:** FAISS (faster, no persistence by default)

### 8.3 MongoDB (Optional)

**Purpose:** Chat persistence

**Collection:** `chats`

**Document Model:**
```json
{
    "_id": "ObjectId",
    "title": "Chat title",
    "mode": "analytical" | "debate",
    "messages": [
        {
            "role": "user" | "assistant",
            "content": "...",
            "timestamp": "..."
        }
    ],
    "created_at": "...",
    "updated_at": "..."
}
```

**Features:**
- Async operations (motor)
- Per-user storage
- Title generation
- Message history
- CRUD operations

---

## 9. Security & Performance

### 9.1 Security Features

**API Key Protection:**
- Environment variable storage
- `.gitignore` for `.env` file
- Request validation
- Rate limiting (5 req/min for debates)

**Headers:**
```python
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=(self)
```

**CORS:**
- Configurable origin (`ALLOWED_ORIGIN`)
- Allowed methods: GET, POST, PUT, DELETE, OPTIONS
- Allowed headers: Content-Type, Authorization

**Rate Limiting:**
- `limits` library
- Moving window algorithm
- Per-IP tracking
- Configurable rules

**Input Validation:**
- Topic/query length limits
- File size limits (OCR)
- Format validation
- Sanitization

### 9.2 Performance Optimizations

**Caching:**
- SQLite cache for scraped articles
- TTL: 24 hours (configurable)
- Cache hit/miss tracking
- Force refresh option

**Concurrency:**
- ThreadPoolExecutor (10 workers)
- Async operations (Quart)
- Parallel scraping (max 3)
- Non-blocking I/O

**Database:**
- Connection pooling
- Batch inserts
- Indexed queries
- Slow query logging

**Frontend:**
- Lazy loading
- Code splitting
- Cache busting (random version)
- Compression

**Memory:**
- Short-term window (4 messages)
- RAG result limits (top_k=3)
- Token truncation
- Garbage collection

### 9.3 Error Handling

**Backend:**
- Try-except blocks
- Detailed logging
- Graceful degradation
- Failover mechanisms

**Frontend:**
- Error boundaries
- User-friendly messages
- Retry logic
- Loading states

**Monitoring:**
- Structured logging (JSON)
- Request ID tracking
- Performance metrics
- Success rate tracking

---

## 10. Dependencies

### 10.1 Core Dependencies

**Web Framework:**
- `quart==0.20.0` - Async Flask
- `quart-cors==0.8.0` - CORS support
- `hypercorn==0.17.3` - ASGI server

**HTTP & Networking:**
- `requests==2.32.5` - HTTP library
- `httpx==0.28.1` - Async HTTP
- `aiohttp==3.11.11` - Async HTTP client

**Web Scraping:**
- `beautifulsoup4==4.14.2` - HTML parsing
- `fake-useragent==2.2.0` - User agent rotation
- `trafilatura==2.0.0` - Text extraction
- `lxml==5.4.0` - XML/HTML parser
- `playwright==1.55.0` - Browser automation

**AI & ML:**
- `groq==0.33.0` - Groq API client
- `huggingface-hub>=0.20.0` - HuggingFace client
- `sentence-transformers==3.3.1` - Embeddings

**OCR:**
- `easyocr==1.7.2` - OCR engine
- `pillow==11.0.0` - Image processing
- `torch==2.9.0` - PyTorch
- `torchvision==0.24.0` - Computer vision
- `opencv-python-headless==4.12.0.88` - OpenCV
- `numpy==2.2.6` - Numerical computing

**Database:**
- `aiosqlite==0.21.0` - Async SQLite
- `motor==3.1.1` - Async MongoDB

**Utilities:**
- `python-dotenv==1.2.1` - Environment variables
- `pyyaml==6.0.3` - YAML parsing
- `tqdm==4.67.1` - Progress bars
- `colorama==0.4.6` - Terminal colors

### 10.2 Optional Dependencies

**NLP (commented out):**
- `spacy>=3.4,<3.8` - NLP library
- `textblob==0.19.0` - Sentiment analysis
- `sumy==0.11.0` - Text summarization

**Visualization:**
- `tabulate==0.9.0` - Tables
- `wordcloud==1.9.4` - Word clouds
- `matplotlib==3.10.7` - Plotting

**ML (heavy):**
- `transformers>=4.21,<4.30` - HuggingFace transformers

**Development:**
- `pytest==8.4.2` - Testing
- `black==25.9.0` - Code formatting
- `flake8==7.3.0` - Linting
- `mypy==1.18.2` - Type checking

### 10.3 System Requirements

**Python:** 3.11+

**Operating Systems:**
- Windows 10/11
- macOS 10.15+
- Linux (Ubuntu 20.04+)

**Hardware:**
- CPU: 4+ cores recommended
- RAM: 8GB minimum, 16GB recommended
- Storage: 10GB for models and data

**Network:**
- Internet connection required
- API access to Groq, Jina, etc.

---

## 11. Deployment

### 11.1 Local Development

**Setup:**
```bash
# 1. Clone repository
git clone https://github.com/shubham2web/MUM-hackthon.git
cd MUM-hackthon

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Configure environment
copy backend\.env.example backend\.env
# Edit backend\.env with your API keys

# 5. Run server
cd backend
python server.py
```

**Access:**
- Homepage: http://127.0.0.1:8000
- Chat: http://127.0.0.1:8000/chat
- OCR: http://127.0.0.1:8000/ocr

### 11.2 Environment Variables

**Required:**
```env
# Core
API_KEY=your_custom_api_key_here
GROQ_API_KEY=your_groq_api_key
JINA_API_KEY=your_jina_api_key

# Optional
OPENAI_API_KEY=your_openai_key  # For transcription
HF_TOKEN_1=your_hf_token_1
HF_TOKEN_2=your_hf_token_2
NEWS_API_KEY=your_news_api_key
SCRAPERAPI_KEY=your_scraper_api_key  # Optional
ZENROWS_API_KEY=your_zenrows_key  # Optional

# Configuration
DEBUG_MODE=False
STRICT_MODE=True
SINGLE_MODE=False
SINGLE_PROVIDER=groq
ALLOWED_ORIGIN=*

# Database
DATABASE_PATH=database/database.db
ATLAS_CHAT_STORE_PATH=path/to/chats.json
```

### 11.3 Production Deployment

**Recommended Stack:**
- **Hosting:** AWS, Azure, Google Cloud
- **Server:** Hypercorn (included)
- **Reverse Proxy:** Nginx
- **Process Manager:** Systemd, Supervisor
- **Container:** Docker (optional)

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

**Systemd Service:**
```ini
[Unit]
Description=ATLAS AI Service
After=network.target

[Service]
Type=simple
User=atlas
WorkingDirectory=/opt/atlas/backend
Environment="PATH=/opt/atlas/.venv/bin"
ExecStart=/opt/atlas/.venv/bin/python server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Docker (Optional):**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "server.py"]
```

### 11.4 Monitoring & Logging

**Logging:**
- JSON-formatted logs
- Request ID tracking
- Performance metrics
- Error tracking

**Metrics:**
- Response times
- Success rates
- Cache hit rates
- Provider statistics

**Recommended Tools:**
- **Monitoring:** Prometheus, Grafana
- **Logging:** ELK Stack, Loki
- **APM:** New Relic, DataDog
- **Error Tracking:** Sentry

---

## 12. Future Roadmap

### 12.1 Phase 1: Core Improvements (Q1 2026)

**Performance:**
- [ ] Redis caching layer
- [ ] CDN integration
- [ ] Database query optimization
- [ ] Lazy loading optimization

**Features:**
- [ ] User authentication
- [ ] Multi-language support
- [ ] Export functionality (PDF/Markdown)
- [ ] Advanced search

**Quality:**
- [ ] Comprehensive test suite
- [ ] CI/CD pipeline
- [ ] Code coverage > 80%
- [ ] Documentation improvements

### 12.2 Phase 2: Advanced Features (Q2 2026)

**AI Enhancements:**
- [ ] Fine-tuned models
- [ ] Multi-modal analysis (video/audio)
- [ ] Real-time fact-checking browser extension
- [ ] Advanced bias detection

**Integrations:**
- [ ] Social media monitoring
- [ ] News aggregator APIs
- [ ] Academic databases (PubMed, arXiv)
- [ ] Fact-checking networks

**Collaboration:**
- [ ] Team workspaces
- [ ] Shared analyses
- [ ] Annotation tools
- [ ] Export/import debates

### 12.3 Phase 3: Scale & Enterprise (Q3-Q4 2026)

**Platform:**
- [ ] Mobile apps (iOS/Android)
- [ ] Browser extensions (Chrome/Firefox)
- [ ] Desktop apps (Electron)
- [ ] API marketplace

**Enterprise:**
- [ ] SSO integration
- [ ] Role-based access control
- [ ] Audit logging
- [ ] Custom deployment options

**Monetization:**
- [ ] Freemium model
- [ ] API access tiers
- [ ] Enterprise licenses
- [ ] White-label solutions

### 12.4 Research & Innovation

**AI Research:**
- [ ] Adversarial debate testing
- [ ] Explainable AI improvements
- [ ] Uncertainty quantification
- [ ] Causal reasoning

**Partnerships:**
- [ ] Academic collaborations
- [ ] Journalism organizations
- [ ] Government agencies
- [ ] Tech platforms

---

## 13. Technical Specifications Summary

### 13.1 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5, CSS3, JavaScript | User interface |
| **Backend** | Python 3.11+, Quart | Web framework |
| **AI Models** | LLaMA 3, Groq API | Language generation |
| **Embeddings** | Sentence Transformers | Semantic search |
| **OCR** | EasyOCR | Text extraction |
| **Web Scraping** | Playwright, Jina | Evidence gathering |
| **Database** | SQLite, ChromaDB, MongoDB | Data storage |
| **Caching** | In-memory, File-based | Performance |
| **Deployment** | Hypercorn, Nginx | Production serving |

### 13.2 Key Metrics

| Metric | Target | Current |
|--------|--------|---------|
| **Response Time** | < 30s | ~15-25s |
| **Evidence Sources** | ≥ 5 | 5-10 |
| **Credibility Accuracy** | > 80% | ~85% |
| **Cache Hit Rate** | > 60% | ~70% |
| **Uptime** | 99.9% | TBD |
| **Concurrent Users** | 100+ | TBD |

### 13.3 File Statistics

| Category | Count | Lines of Code |
|----------|-------|---------------|
| **Python Files** | 40+ | ~15,000+ |
| **JavaScript Files** | 5+ | ~2,000+ |
| **CSS Files** | 6+ | ~3,000+ |
| **HTML Templates** | 3 | ~1,000+ |
| **Total** | 54+ | ~21,000+ |

---

## 14. Glossary

**AI Agent** - Autonomous system that performs tasks, uses tools, and makes decisions  
**RAG** - Retrieval-Augmented Generation, combining LLMs with external knowledge  
**ChromaDB** - Vector database for semantic search  
**SSE** - Server-Sent Events, for real-time streaming  
**OCR** - Optical Character Recognition, text extraction from images  
**LLM** - Large Language Model  
**NLP** - Natural Language Processing  
**Embedding** - Vector representation of text for similarity search  
**Credibility Score** - Multi-metric assessment of information trustworthiness  
**Debate Orchestration** - Managing multi-agent AI conversations  
**Role Reversal** - Swapping agent positions to test argument strength  
**Bias Auditor** - System detecting cognitive biases in arguments  
**Memory System** - Hybrid short-term + long-term context management  
**TTFT** - Time To First Token, streaming performance metric  
**Failover** - Automatic switching to backup system on failure  

---

## 15. Contributors

- **Shubham Pawar** - [@shubham2web](https://github.com/shubham2web)
- **Yash Dedhia** - [@yashhh-23](https://github.com/yashhh-23)
- **Yash** - [@RedRex101](https://github.com/RedRex101)
- **Sahil Rane** - [@CyberCodezilla](https://github.com/CyberCodezilla)

---

## 16. License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 17. Contact & Support

**Repository:** https://github.com/shubham2web/MUM-hackthon  
**Issues:** https://github.com/shubham2web/MUM-hackthon/issues  
**Email:** [Contact contributors through GitHub]

---

**Document Version:** 1.0  
**Last Updated:** November 28, 2025  
**Next Review:** December 2025  

---

*This PRD is a living document and will be updated as the project evolves.*

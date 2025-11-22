# Backend data files

This folder contains backend code and (in development) a sample `data/chats.json` file.

To avoid accidentally sharing user chat history via the repository, the application now uses a per-user chat store by default.

Behavior
- By default the file-backed fallback will store chats in a per-user path:
  - Windows: `%LOCALAPPDATA%\atlas_chat\chats.json`
  - Unix: `$XDG_DATA_HOME/atlas_chat/chats.json` or `~/.local/share/atlas_chat/chats.json`
- You can override the path by setting the environment variable `ATLAS_CHAT_STORE_PATH` or `ATLAS_CHAT_DATA_PATH` to an absolute file path.
- On first run, if the repo contains `backend/data/chats.json`, the server will copy it into your per-user path (best-effort) and then continue using the per-user file.

Recommended Git cleanup (one-time)
1. Copy your current repo `backend/data/chats.json` to the per-user path (PowerShell):

```powershell
$target = Join-Path $env:LOCALAPPDATA 'atlas_chat\chats.json'
New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
Copy-Item -Path .\backend\data\chats.json -Destination $target -Force
```

2. Stop tracking the repo file and commit the change:

```powershell
git rm --cached backend/data/chats.json
git commit -m "Stop tracking chat history; use per-user chat store"
git pull --rebase origin main
```

If you prefer to keep the file in the repo for now, stash your changes first, pull, then apply the stash.

Security note
- This change prevents casual sharing of chat histories by removing the repo as the canonical store. For multi-device or cross-user persistence, integrate a proper server-side user account or API key-based ownership and store `owner_id` in chat metadata.

If you'd like, I can automate the git untrack step in a script or implement server-side ownership next.
# ATLAS Backend - Organized Structure

## 📁 Directory Structure

```
backend/
├── server.py                 # Main application entry point
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
│
├── core/                     # Core application modules
│   ├── __init__.py
│   ├── ai_agent.py          # AI agent wrapper (Groq/HuggingFace)
│   ├── config.py            # Configuration and environment settings
│   └── utils.py             # Utility functions and helpers
│
├── api/                      # API routes and endpoints
│   ├── __init__.py
│   └── api_v2_routes.py     # ATLAS v2.0 REST API endpoints
│
├── v2_features/              # ATLAS v2.0 Enhanced Features
│   ├── __init__.py
│   ├── atlas_v2_integration.py    # Main v2.0 orchestrator
│   ├── credibility_engine.py      # 4-metric credibility scoring
│   ├── role_library.py            # 8 expert agent personas
│   ├── role_reversal_engine.py    # Role swapping mechanics
│   └── bias_auditor.py            # 10 bias types detection
│
├── services/                 # External services and utilities
│   ├── __init__.py
│   ├── ocr_processor.py     # EasyOCR text extraction
│   ├── pro_scraper.py       # Web scraping for evidence
│   ├── db_manager.py        # SQLite database operations
│   └── file_parser.py       # File parsing utilities
│
├── database/                 # Database files
│   ├── database.db          # SQLite database
│   ├── database.db-shm      # Shared memory file
│   └── database.db-wal      # Write-ahead log
│
├── static/                   # Static assets (CSS, JS, images)
│   ├── css/
│   │   ├── base.css
│   │   ├── layout.css
│   │   ├── components.css
│   │   ├── animations.css
│   │   ├── homepage.css
│   │   └── atlas_v2.css     # v2.0 styling
│   └── js/
│       ├── homepage.js
│       └── atlas_v2.js       # v2.0 frontend integration
│
├── templates/                # HTML templates
│   ├── homepage.html
│   ├── index.html           # Main chat interface
│   └── ocr.html
│
├── tests/                    # Test files
│   ├── test_ocr.py
│   ├── test_v2_endpoints.py
│   ├── test_v2_frontend.html
│   └── test_chat.html
│
├── docs/                     # Documentation
│   ├── # ATLAS — Project Documentation.md
│   ├── social_media_report.html
│   └── social_media_report.json
│
└── venv_fix/                 # Virtual environment fix files

```

## 🚀 Features by Module

### Core Modules
- **ai_agent.py**: Unified AI client (Groq primary, HuggingFace fallback)
- **config.py**: API keys, model settings, rate limits
- **utils.py**: Analytics, formatting, helper functions

### API Layer
- **api_v2_routes.py**: 8 REST endpoints for v2.0 features
  - `/v2/analyze` - Full analysis
  - `/v2/credibility` - Credibility scoring
  - `/v2/roles` - Available roles
  - `/v2/bias-report` - Bias detection
  - `/v2/reversal-debate` - Role reversal debates
  - `/v2/status` - System status
  - `/v2/health` - Health check
  - `/v2/bias-ledger` - Bias history

### V2.0 Features
- **Credibility Engine**: 4-metric scoring (source trust, semantic alignment, temporal, diversity)
- **Role Library**: 8 expert personas (Proponent, Opponent, Scientific Analyst, etc.)
- **Role Reversal**: Debate mechanics with convergence tracking
- **Bias Auditor**: 10 bias types with blockchain-style ledger

### Services
- **OCR Processor**: EasyOCR-based text extraction from images
- **Pro Scraper**: Web scraping with diversity scoring
- **DB Manager**: Async SQLite operations
- **File Parser**: Document parsing utilities

## 📦 Installation

```bash
cd backend
pip install -r requirements.txt
```

## 🏃 Running

```bash
cd backend
python server.py
```

Server runs on: http://127.0.0.1:5000

## 🔧 Environment Variables

Create a `.env` file:
```
GROQ_API_KEY=your_groq_key_here
HUGGINGFACE_API_KEY=your_hf_key_here
DEBUG_MODE=false
```

## 📚 Import Examples

```python
# Core modules
from core.ai_agent import AiAgent
from core.config import API_KEY, DEFAULT_MODEL
from core.utils import compute_advanced_analytics

# API routes
from api.api_v2_routes import v2_bp

# V2.0 features
from v2_features.atlas_v2_integration import ATLASv2
from v2_features.credibility_engine import CredibilityEngine
from v2_features.role_library import RoleLibrary

# Services
from services.ocr_processor import get_ocr_processor
from services.pro_scraper import get_diversified_evidence
from services.db_manager import AsyncDbManager
```

## 🧪 Testing

```bash
cd backend/tests
python test_ocr.py
python test_v2_endpoints.py
```

## 📄 License

See LICENSE file in project root.

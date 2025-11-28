# ATLAS Installation Guide

## Quick Installation

### Step 1: Prerequisites
- Python 3.11+ (Python 3.13 works too)
- pip (Python package manager)

### Step 2: Clone Repository
```bash
git clone https://github.com/shubham2web/MUM-hackthon.git
cd MUM-hackthon
```

### Step 3: Create Virtual Environment
```bash
# Windows
cd backend
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### Step 4: Install Dependencies
```bash
# Install core dependencies (minimal, fast)
pip install -r requirements.txt

# Or install ALL dependencies including optional packages
# pip install -r requirements_full.txt
```

### Step 5: Configure Environment
```bash
# Copy example env file
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# Edit .env and add your API keys:
# - GROQ_API_KEY (Required - get from https://console.groq.com/)
# - SERPER_API_KEY (Optional - for web search)
# - JINA_API_KEY (Optional - for content extraction)
# - HF_TOKEN_1 (Optional - HuggingFace token)
```

### Step 6: Run the Server
```bash
python server.py
```

The server will start at: http://127.0.0.1:5000

## Installation Options

### Option 1: Minimal Installation (Recommended for Getting Started)
Installs only the core packages needed to run the server:
```bash
pip install quart quart-cors requests beautifulsoup4 groq huggingface-hub playwright python-dotenv aiosqlite limits tenacity fake-useragent trafilatura python-dateutil lxml
```

### Option 2: Full Installation (All Features)
Installs all dependencies including ML libraries (requires more disk space and C compiler for some packages):
```bash
pip install -r requirements.txt
pip install numpy spacy transformers torch  # Optional ML packages
```

### Option 3: Docker Installation (Coming Soon)
```bash
docker build -t atlas .
docker run -p 5000:5000 --env-file .env atlas
```

## Post-Installation

### Install Playwright Browsers (Required for web scraping)
```bash
playwright install chromium
```

### Verify Installation
```bash
python -c "import quart; import groq; import huggingface_hub; print('All core packages installed!')"
```

### Test the Server
1. Start the server: `python server.py`
2. Open browser: http://127.0.0.1:5000
3. Navigate to chat: http://127.0.0.1:5000/chat
4. Test health endpoint: http://127.0.0.1:5000/healthz

## Troubleshooting

### Issue: ModuleNotFoundError
**Solution:** Install the missing package
```bash
pip install <package-name>
```

### Issue: NumPy installation fails on Windows
**Cause:** NumPy requires a C compiler on Windows

**Solution 1 (Recommended):** Skip NumPy - it's optional for basic functionality
```bash
# NumPy is only needed for advanced analytics
```

**Solution 2:** Install prebuilt wheel
```bash
pip install --upgrade pip
pip install numpy==1.26.4
```

**Solution 3:** Install Visual Studio Build Tools
- Download from: https://visualstudio.microsoft.com/downloads/
- Install "Desktop development with C++"

### Issue: Playwright browser not found
**Solution:** Install Chromium browser for Playwright
```bash
playwright install chromium
```

### Issue: Port 5000 already in use
**Solution:** Change port in server.py or kill the process using port 5000
```bash
# Windows: Find and kill process
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac: Find and kill process
lsof -i :5000
kill -9 <PID>
```

### Issue: API Key errors
**Solution:** Ensure .env file exists and contains valid API keys
```bash
# Check if .env file exists
ls .env  # Linux/Mac
dir .env  # Windows

# Verify API keys are set (don't share output!)
python -c "from config import GROQ_API_KEY; print('GROQ key:', 'SET' if GROQ_API_KEY else 'MISSING')"
```

## Dependencies Overview

### Core Dependencies (Required)
- **quart** - Async web framework
- **groq** - Groq AI API client
- **requests** - HTTP library
- **beautifulsoup4** - HTML parsing
- **playwright** - Browser automation

### Optional Dependencies
- **numpy** - Numerical computing (for analytics)
- **spacy** - NLP processing
- **transformers** - Hugging Face models
- **torch** - PyTorch (for ML models)

## Development Setup

### Install Development Tools
```bash
pip install pytest black flake8 mypy isort
```

### Run Tests
```bash
pytest
```

### Format Code
```bash
black .
isort .
```

### Type Checking
```bash
mypy .
```

## Getting API Keys

### Groq API Key (Required)
1. Go to https://console.groq.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create new API key
5. Copy and add to .env file

### Serper API Key (Optional - for web search)
1. Go to https://serper.dev/
2. Sign up for free account
3. Get API key from dashboard
4. Add to .env file

### Jina API Key (Optional - for content extraction)
1. Go to https://jina.ai/
2. Sign up for account
3. Get API key
4. Add to .env file

### HuggingFace Token (Optional - for HF models)
1. Go to https://huggingface.co/
2. Sign up or log in
3. Settings → Access Tokens
4. Create new token
5. Add to .env file

## Next Steps

After installation:
1. ✅ Configure your .env file with API keys
2. ✅ Start the server
3. ✅ Open the chat interface
4. ✅ Ask questions and test the AI debate feature
5. ✅ Explore the documentation

## Support

For issues or questions:
- Open an issue: https://github.com/shubham2web/MUM-hackthon/issues
- Check documentation: /Documentation-LICENSE/
- Contact maintainers (see README.md)

---
**Happy Hacking! 🚀**

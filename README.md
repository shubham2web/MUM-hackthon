# ATLAS - Advanced Text Learning and Analysis System

## Overview
ATLAS is a comprehensive backend system featuring AI-powered document parsing, professional data scraping, social media analytics, and intelligent agent capabilities.

## Features
- 📄 **Document Parser**: Multi-format file parsing with OCR support
- 🤖 **AI Agent**: Intelligent automation and analysis
- 🔍 **Professional Scraper**: Extract professional profile data
- 📊 **Social Media Analytics**: Generate detailed social media reports
- 💾 **Database Management**: SQLite-based data persistence
- 🔐 **API Key Management**: Secure API key generation and validation

## Project Structure
```
ATLAS/
├── backend/
│   ├── server.py              # Main Flask/FastAPI server
│   ├── file_parser.py         # Document parsing engine
│   ├── ai_agent.py            # AI agent logic
│   ├── pro_scraper.py         # Professional profile scraper
│   ├── db_manager.py          # Database operations
│   ├── config.py              # Configuration management
│   ├── utils.py               # Utility functions
│   ├── requirements.txt       # Python dependencies
│   └── templates/
│       └── index.html         # Web interface
```

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/shubham2web/MUM-hackthon.git
   cd MUM-hackthon
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file in the `backend` directory:
   ```env
   # Add your configuration here
   DATABASE_URL=sqlite:///database.db
   SECRET_KEY=your_secret_key_here
   ```

5. **Run the application:**
   ```bash
   python server.py
   ```

## Usage
Access the application at `http://localhost:5000` (or the configured port)

## Configuration
Edit `backend/config.py` to customize settings.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
MIT License

## Contact
GitHub: [@shubham2web](https://github.com/shubham2web)
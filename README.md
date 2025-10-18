# 🛡️ ATLAS - AI-Powered Misinformation Fighter

ATLAS is an advanced AI system designed to combat misinformation through evidence-based analysis and multi-perspective debate simulation.

![ATLAS Banner](https://via.placeholder.com/1200x300/0a0e27/42b5eb?text=ATLAS+Misinformation+Fighter)

## ✨ Features

- 🤖 **AI-Powered Analysis**: Leverages LLaMA models via Groq for fast, intelligent responses
- 🔍 **Evidence Gathering**: Automatically scrapes and analyzes multiple sources
- ⚡ **Real-Time Chat Interface**: Beautiful, responsive UI with glassmorphism design
- 🎯 **Debate Simulation**: Multi-agent debate system for comprehensive analysis
- 🌐 **Source Verification**: Cross-references claims with credible sources
- 📊 **Credibility Scoring**: Evaluates information reliability

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- API Keys for:
  - [Groq](https://console.groq.com/)
  - [Serper](https://serper.dev/)
  - [Jina AI](https://jina.ai/)
  - [HuggingFace](https://huggingface.co/) (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/shubham2web/MUM-hackthon.git
   cd MUM-hackthon
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Copy the example file
   copy backend\.env.example backend\.env
   
   # Edit backend\.env and add your API keys
   ```

5. **Run the server**
   ```bash
   cd backend
   python server.py
   ```

6. **Open your browser**
   ```
   http://127.0.0.1:5000
   ```

## 📁 Project Structure

```
ATLAS/
├── backend/
│   ├── server.py           # Main Flask/Quart server
│   ├── ai_agent.py         # AI agent with multi-provider support
│   ├── pro_scraper.py      # Evidence gathering and web scraping
│   ├── db_manager.py       # Database operations
│   ├── config.py           # Configuration management
│   ├── utils.py            # Utility functions
│   ├── static/
│   │   └── css/            # Modular CSS files
│   │       ├── base.css
│   │       ├── layout.css
│   │       ├── components.css
│   │       └── animations.css
│   └── templates/
│       ├── homepage.html   # Landing page
│       └── index.html      # Chat interface
├── .gitignore
├── requirements.txt
└── README.md
```

## 🎨 UI Features

- **Glassmorphism Design**: Modern, translucent UI elements
- **Animated Background**: Interactive starry space theme
- **Responsive Layout**: Works on desktop and mobile
- **Real-Time Updates**: Streaming responses with typing indicators
- **Dark Mode**: Eye-friendly dark theme

## 🔧 Configuration

Edit `backend/.env`:

```env
GROQ_API_KEY=your_key_here
SERPER_API_KEY=your_key_here
JINA_API_KEY=your_key_here
ATLAS_API_KEY=optional_custom_key

DATABASE_PATH=db/atlas.db
DEBUG_MODE=False
```

## 🤝 API Endpoints

### Chat Analysis
```http
POST /analyze_topic
Content-Type: application/json

{
  "topic": "Your question here",
  "model": "llama3"
}
```

### Debate Generation
```http
POST /run_debate
Content-Type: application/json

{
  "topic": "Debate topic",
  "model": "llama-3.3-70b-versatile"
}
```

## 🛠️ Technologies Used

- **Backend**: Python, Quart (Async Flask)
- **AI**: Groq (LLaMA 3), HuggingFace
- **Web Scraping**: BeautifulSoup, Requests
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **APIs**: Serper (Google Search), Jina (Reader)

## 📊 How It Works

1. **User Query**: User asks a question or submits a claim
2. **Evidence Gathering**: System searches multiple sources using Serper API
3. **Content Extraction**: Jina Reader extracts clean text from sources
4. **AI Analysis**: LLaMA model analyzes evidence and generates response
5. **Debate Mode**: Multiple AI agents debate different perspectives
6. **Result**: User receives comprehensive, evidence-based answer

## 🐛 Known Issues

- [ ] Chat interface requires server restart for full functionality
- [ ] Evidence gathering timeout on complex queries
- [ ] Database initialization on first run

## 🚧 Roadmap

- [ ] Add user authentication
- [ ] Implement chat history
- [ ] Add export functionality (PDF/Markdown)
- [ ] Multi-language support
- [ ] Mobile app version
- [ ] Browser extension

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Contributors

- **Shubham** - [GitHub](https://github.com/shubham2web)
- **Yash** - [GitHub](https://github.com/yashhh-23)
- **Yash** -[GitHub](https://github.com/RedRex101)
- **Sahil** -[GitHub](https://github.com/CyberCodezilla)

## 🙏 Acknowledgments

- MUM Hackathon organizers
- Groq for fast LLaMA inference
- Open-source community

## 📧 Contact

For questions or suggestions, please open an issue or contact 
1. [@shubham2web](https://github.com/shubham2web)
2. [@yashhh-23](https://github.com/yashhh-23)
3. [@RedRex101](https://github.com/RedRex101)
4. [@CyberCodeZilla](https://github.com/CyberCodezilla)
   
---

**⭐ If you find this project useful, please give it a star!**

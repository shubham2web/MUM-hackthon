# ATLAS v4.0 — Master Product Requirements Document (PRD)

## 📌 Overview
ATLAS v4.0 is an adversarial fact‑verification and analysis engine that merges:
- **Hybrid RAG Retrieval** (Embedding + Keyword Search + Fusion + Re‑Ranking)
- **Web Evidence Scraping** (pro_scraper, web_scraper)
- **Forensic Engine** (credibility scoring, entity background checks, dossier generation)
- **Multi‑Agent Debate Engine** (Proponent, Opponent, Moderator)
- **Verdict Engine** (Strict Judge with confidence scoring)
- **Memory System** (short‑term memory, conversation memory, Mongo audits)
- **Bias Auditor + Role Reversal Engine** (for adversarial robustness)

ATLAS v4.0 acts as a **Supreme Court of Truth**, delivering a final verdict:
- ✅ VERIFIED
- ❌ DEBUNKED
- ⚠️ COMPLEX / UNSURE

Each verdict includes:
- Key Evidence
- Winning Argument
- Critical Reasoning
- Confidence Score (0–100)

---

# 1. System Architecture
```
User Query
   ↓
Hybrid RAG Retriever → Vector Store → Fusion → Rerankers
   ↓
Web Scraper (pro_scraper + web_scraper)
   ↓
OCR Evidence (ocr_processor)
   ↓
Credibility Engine (Authority Scoring)
   ↓
Forensic Engine (Dossier + Background Scan)
   ↓
Debate Engine (generate_debate → run_turn)
   ↓
Bias Auditor + Role Reversal (Optional)
   ↓
Verdict Engine (generate_final_verdict)
   ↓
Final JSON Verdict
```

---

# 2. Module Responsibilities
## 2.1 Hybrid RAG Engine
**Files:**
- chunker.py
- embeddings.py
- vector_store.py
- hybrid_fusion.py
- cross_encoder_reranker.py
- ltr_reranker.py
- reranker.py
- memory_manager.py
- short_term_memory.py

### Responsibilities:
- Convert claims to embedding vectors
- Perform hybrid search (semantic + keyword)
- Apply cross‑encoder reranking
- Use LTR (Learning-To-Rank) for contextual matching
- Compress and store relevant evidence
- Log retrieval quality into mongo_audit

---

## 2.2 Web Scraper & Evidence Engine
**Files:**
- pro_scraper.py
- web_scraper.py
- file_parser.py
- ocr_processor.py
- professional_client.py

### Responsibilities:
- Extract current web evidence with summaries
- Parse PDFs, images, URLs via OCR + parsing
- Remove duplicates and low-authority sources
- Produce **Evidence Bundle**:
```
{
  "sources": [...],
  "authority_scores": {...},
  "cleaned_text": "...",
  "raw_metadata": {...}
}
```

---

## 2.3 Forensic Engine (Entity Background)
**Files:**
- credibility_engine.py
- role_library.py
- role_reversal_engine.py
- bias_auditor.py
- background_check.py (if exists)

### Responsibilities:
- Named Entity Extraction (People/Organizations)
- Generate background checks using structured queries
- Score sources using authority metrics
- Build **Reputation Dossier**:
```
{
  "entity": "...",
  "credibility": 0–100,
  "red_flags": [...],
  "history": [...]
}
```
- Provide dossier to agents before debate

---

## 2.4 Debate Engine (Inside server.py)
**Functions:**
- determine_debate_stances()
- generate_debate()
- run_turn()

### Flow:
1. **Stance Assignment**
   - Proponent = supports claim
   - Opponent = attacks claim
   - Uses stance determination + evidence bundle

2. **Debate Rounds**
```
Introduction
Opening Statements
Rebuttals
Cross‑Examination
Convergence
Moderator Synthesis
```

3. **AI Turn Execution (run_turn)**
- Loads memory
- Adds evidence blocks
- Builds agent-specific prompts from role_library
- Streams LLM responses
- Stores turn-level memory

4. **Transcript Assembly**
- Each turn appended
- Moderator final synthesis returned

---

## 2.5 Bias Auditor
**Files:**
- bias_auditor.py

### Purpose:
- Detect ideological bias
- Detect logical fallacies
- Detect unsupported claims
- Provide self‑correction feedback to agents

---

## 2.6 Verdict Engine (Inside server.py)
**Function:** generate_final_verdict()

### Responsibilities:
- Reads entire transcript + evidence bundle
- Applies strict boolean logic:
```
IF evidence strongly supports → VERIFIED
IF evidence contradicts → DEBUNKED
ELSE → COMPLEX
```

### Output Format:
```
{
  "verdict": "VERIFIED / DEBUNKED / COMPLEX",
  "confidence": 0–100,
  "winning_argument": "...",
  "critical_analysis": "...",
  "key_evidence": [...]
}
```

---

# 3. Core Pipeline (analyze → debate → verdict)
```
def analyze(query):
    rag_evidence = rag_pipeline(query)
    web_evidence = pro_scraper(query)
    dossier = forensic_engine(query)

    debate_output = generate_debate(
        topic=query,
        evidence_bundle={...},
        dossier=dossier
    )

    final_verdict = generate_final_verdict(
        topic=query,
        transcript=debate_output.transcript,
        evidence_bundle={...}
    )

    return final_verdict
```
---

# 4. API Layer
**Routes:**
- `/debate` → debate generation
- `/analyze` → full pipeline
- `/memory/*` → memory endpoints
- `/ocr` → file OCR
- `/scrape` → evidence scraping

---

# 5. Prompt Architecture
All prompts stored in:
- role_library.py

### Roles:
- Proponent
- Opponent
- Moderator
- Judge
- Forensic Investigator
- Bias Auditor

Each role has:
- system prompt
- behavior rules
- banned behavior

---

# 6. Scoring Framework
## 6.1 Evidence Authority
- Tier 1: Reuters/AP/Official Docs → +40
- Tier 2: Established outlets → +20
- Tier 3: Blogs → +5
- Tier 4: Anonymous sources → −20

## 6.2 Debate Persuasiveness
- Argument coherence
- Use of evidence
- Refutation power

## 6.3 Verdict Confidence
```
confidence = authority_score_weight + debate_strength_weight
```
---

# 7. Safety & Truncation System
- Middle-of-transcript compression
- Memory windowing
- Turn-length normalization

Ensures:
- No overflow tokens
- No hallucinations
- Consistent reasoning

---

# 8. Data Structures
## Evidence Bundle
```
{
  "extracted_text": "",
  "sources": [...],
  "authority": {...},
  "ocr": [...],
  "chunks": [...]
}
```

## Debate Transcript
```
[
  {"role": "proponent", "text": "..."},
  {"role": "opponent", "text": "..."},
  {"role": "moderator", "text": "..."}
]
```

## Verdict
```
{
  "verdict": "...",
  "confidence": 0–100,
  "justification": "...",
  "evidence": [...]
}
```
---

# 9. Execution Sequence Diagram (High Level)
```
User
  ↓
/analyze
  ↓
RAG → Web Scraper → OCR
  ↓
Evidence Bundle
  ↓
Forensic Engine
  ↓
Debate Engine
  ↓
Verdict Engine
  ↓
Final JSON Output
```

---

# 10. Future Expansions
- Source clustering
- Multi‑judge panel voting
- Audio debate support
- Emotion‑aware refutation
- Graph‑based evidence mapping

---

# ✔ ATLAS v4.0 PRD — Complete & Ready for Editing
You can now edit anything, reorganize sections, or ask me to:
- Add diagrams
- Expand any section
- Convert this into a downloadable Markdown file
- Generate architecture images
- Create implementation tasks for your team


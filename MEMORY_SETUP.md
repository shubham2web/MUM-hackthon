# 🧠 Hybrid Memory System - Quick Setup

## Prerequisites

- Python 3.8+
- pip installed
- 500MB free disk space (for embedding models)

## Installation

### Step 1: Install Dependencies

```powershell
# Navigate to project directory
cd C:\Users\sunanda.AMFIIND\Documents\GitHub\MUM-hackthon

# Install memory system dependencies
pip install -r backend\memory_requirements.txt
```

**Dependencies installed:**
- `sentence-transformers` - Local embeddings (no API key needed)
- `chromadb` - Persistent vector database
- `faiss-cpu` - Fast in-memory vector search
- `numpy` - Numerical operations

### Step 2: Verify Installation

```powershell
# Run verification
python -c "from memory import HybridMemoryManager; print('✅ Memory system ready!')"
```

## Quick Test

### Option 1: Run Demo Script

```powershell
# Interactive demonstration
python demo_memory_system.py
```

This will show:
1. Basic memory operations
2. 4-zone context building
3. Semantic search
4. Memory-enhanced agents
5. Before/after comparison

### Option 2: Start Server

```powershell
# Start ATLAS server with memory system
cd backend
python server.py
```

Server runs on: `http://127.0.0.1:5000`

**Available endpoints:**
- `/memory/status` - Check system status
- `/memory/search` - Semantic search
- `/memory/context` - Build context payload
- `/memory/add` - Add interaction
- `/memory/clear` - Clear memory

### Option 3: Python REPL Test

```powershell
python
```

```python
>>> from memory.memory_manager import HybridMemoryManager
>>> 
>>> # Initialize
>>> memory = HybridMemoryManager()
>>> print("✅ Memory initialized")
>>> 
>>> # Add interaction
>>> memory.set_debate_context("test_001")
>>> memory.add_interaction("user", "Hello, AI!")
>>> 
>>> # Check status
>>> summary = memory.get_memory_summary()
>>> print(f"Turns: {summary['turn_counter']}")
>>> print(f"Short-term: {summary['short_term']['current_count']} messages")
>>> 
>>> print("\n✅ Memory system working!")
```

## Test API Endpoints

```powershell
# Terminal 1: Start server
cd backend
python server.py

# Terminal 2: Test endpoints
```

### Test 1: Check Status

```powershell
curl http://localhost:5000/memory/status
```

Expected response:
```json
{
  "status": "ok",
  "memory_summary": {...},
  "rag_enabled": true
}
```

### Test 2: Add Interaction

```powershell
curl -X POST http://localhost:5000/memory/add `
  -H "Content-Type: application/json" `
  -d '{\"role\": \"user\", \"content\": \"Tell me about AI\"}'
```

### Test 3: Search Memories

```powershell
curl -X POST http://localhost:5000/memory/search `
  -H "Content-Type: application/json" `
  -d '{\"query\": \"AI benefits\", \"top_k\": 5}'
```

### Test 4: Build Context

```powershell
curl -X POST http://localhost:5000/memory/context `
  -H "Content-Type: application/json" `
  -d '{\"system_prompt\": \"You are helpful.\", \"current_task\": \"Summarize.\"}'
```

## Troubleshooting

### Issue: Import Error

```
ImportError: No module named 'sentence_transformers'
```

**Solution:**
```powershell
pip install sentence-transformers
```

### Issue: ChromaDB Error

```
ImportError: No module named 'chromadb'
```

**Solution:**
```powershell
pip install chromadb
```

Or use FAISS backend:
```python
memory = HybridMemoryManager(long_term_backend="faiss")
```

### Issue: Slow First Run

**Explanation:** sentence-transformers downloads model on first use (~80MB)

**Wait for:**
```
Downloading model files... (this happens once)
```

### Issue: Memory Error

**Solution:** Use FAISS backend (lighter):
```python
memory = HybridMemoryManager(
    long_term_backend="faiss",
    short_term_window=2  # Smaller window
)
```

## Configuration

### Change Embedding Provider

Edit `backend/memory/embeddings.py`:

```python
# Line 14
EMBEDDING_PROVIDER = "sentence-transformers"  # Default

# Or use OpenAI (requires API key in .env)
# EMBEDDING_PROVIDER = "openai"
```

### Change Vector Store Backend

```python
# ChromaDB (persistent, recommended)
memory = HybridMemoryManager(long_term_backend="chromadb")

# FAISS (in-memory, faster)
memory = HybridMemoryManager(long_term_backend="faiss")
```

### Adjust Memory Window

```python
# Keep more recent messages
memory = HybridMemoryManager(short_term_window=8)

# Or adjust after creation
memory.short_term.resize_window(6)
```

## Next Steps

1. **Read Full Guide:** See `MEMORY_SYSTEM_GUIDE.md`
2. **Review Implementation:** See `MEMORY_IMPLEMENTATION.md`
3. **Integrate with ATLAS v2.0:** Enhance debate system
4. **Test with Real Debates:** Run multi-agent conversations

## Performance Tips

### For Development (Fast)
```python
memory = HybridMemoryManager(
    long_term_backend="faiss",  # In-memory, fast
    short_term_window=4,
    enable_rag=True
)
```

### For Production (Persistent)
```python
memory = HybridMemoryManager(
    long_term_backend="chromadb",  # Persistent storage
    short_term_window=4,
    enable_rag=True
)
```

### For Limited Resources
```python
memory = HybridMemoryManager(
    long_term_backend="faiss",
    short_term_window=2,  # Smaller window
    enable_rag=False  # Disable RAG if needed
)
```

## Verification Checklist

- [ ] Dependencies installed
- [ ] Import test passes
- [ ] Demo script runs
- [ ] Server starts without errors
- [ ] API endpoints respond
- [ ] Memory operations work

## Success Indicators

✅ **Working:**
- No import errors
- Demo completes successfully
- Server shows: "✅ Hybrid Memory System endpoints registered"
- API returns valid JSON responses
- Memory statistics show data

❌ **Not Working:**
- Import errors (install dependencies)
- Server crashes (check logs)
- API returns 500 errors (check backend/server.log)

## Support

**Issue:** Dependencies won't install  
**Try:**
```powershell
pip install --upgrade pip
pip install -r backend\memory_requirements.txt --no-cache-dir
```

**Issue:** Server won't start  
**Check:**
```powershell
cd backend
python -c "from memory import HybridMemoryManager"
```

**Issue:** Slow performance  
**Solution:** Use FAISS backend and reduce RAG top_k

---

## Summary

```powershell
# Installation (5 minutes)
pip install -r backend\memory_requirements.txt

# Quick test (1 minute)
python demo_memory_system.py

# Start using (immediate)
python backend\server.py
```

**That's it!** 🎉 Memory system is ready.

See `MEMORY_SYSTEM_GUIDE.md` for detailed usage examples.

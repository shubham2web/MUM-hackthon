# 🧠 Hybrid Memory System - Implementation Guide

## Overview

The **Hybrid Memory System** combines **RAG (Retrieval-Augmented Generation)** for long-term context with **short-term conversational memory** to enable continuity, reasoning, and natural interactions within ATLAS multi-agent debates.

## Architecture

### 4-Zone Context Payload

Every LLM call receives a structured context with four distinct zones:

```
[ZONE 1: SYSTEM PROMPT] — Agent's core identity, rules, and role
[ZONE 2: LONG-TERM MEMORY (RAG)] — Relevant retrieved context from vector DB
[ZONE 3: SHORT-TERM MEMORY (Window)] — Last few conversational turns
[ZONE 4: NEW TASK] — The current action or task instruction
```

## Installation

### 1. Install Dependencies

```bash
# Install memory system dependencies
pip install -r backend/memory_requirements.txt

# Core dependencies:
# - sentence-transformers (local embeddings, no API key needed)
# - chromadb (persistent vector database)
# - faiss-cpu (alternative in-memory vector search)
# - numpy
```

### 2. Verify Installation

```bash
cd backend
python -c "from memory import HybridMemoryManager; print('✅ Memory system ready!')"
```

## Quick Start

### Basic Usage

```python
from memory.memory_manager import HybridMemoryManager

# Initialize memory manager
memory = HybridMemoryManager(
    short_term_window=4,  # Keep last 4 messages
    long_term_backend="chromadb",  # or "faiss"
    enable_rag=True
)

# Set debate context
memory.set_debate_context("debate_001")

# Add interactions
memory.add_interaction(
    role="proponent",
    content="Climate change is primarily caused by human activity.",
    metadata={"turn": 1}
)

memory.add_interaction(
    role="opponent",
    content="Natural cycles play a significant role as well.",
    metadata={"turn": 2}
)

# Build context payload for LLM
context = memory.build_context_payload(
    system_prompt="You are an expert moderator.",
    current_task="Summarize the key points of disagreement.",
    query="What are the main arguments about climate change causes?"
)

print(context)
```

### Memory-Enhanced Agent

```python
from core.memory_enhanced_agent import MemoryEnhancedAgent

# Create memory-enhanced agent
agent = MemoryEnhancedAgent(
    role="proponent",
    model_name="llama3",
    auto_store_responses=True
)

# Generate response with automatic memory integration
response = agent.generate(
    task="Argue in favor of renewable energy",
    system_prompt="You are a debate proponent supporting clean energy.",
    use_rag=True,
    top_k_rag=4
)

print(response.text)

# Search agent's memory
results = agent.search_memory(
    query="renewable energy benefits",
    top_k=5
)

for result in results:
    print(f"[Score: {result['score']:.2f}] {result['text'][:100]}...")
```

## API Endpoints

### Start Server

```bash
cd backend
python server.py
```

Server runs on `http://127.0.0.1:5000`

### Endpoints

#### 1. Memory Status
```bash
GET /memory/status
```

**Response:**
```json
{
  "status": "ok",
  "memory_summary": {
    "current_debate_id": "debate_001",
    "turn_counter": 5,
    "short_term": {
      "window_size": 4,
      "current_count": 4
    },
    "long_term": {
      "backend": "chromadb",
      "total_memories": 50
    },
    "rag_enabled": true
  }
}
```

#### 2. Search Memories
```bash
POST /memory/search
Content-Type: application/json

{
  "query": "What was discussed about climate change?",
  "top_k": 10,
  "filter": {"role": "proponent"}
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "uuid-123",
      "text": "Climate change is accelerating...",
      "score": 0.89,
      "rank": 1,
      "metadata": {
        "role": "proponent",
        "turn": 3,
        "debate_id": "debate_001"
      }
    }
  ],
  "count": 10
}
```

#### 3. Build Context Payload
```bash
POST /memory/context
Content-Type: application/json

{
  "system_prompt": "You are an expert moderator.",
  "current_task": "Summarize the debate so far.",
  "query": "key points discussed",
  "top_k_rag": 4,
  "use_short_term": true,
  "use_long_term": true
}
```

**Response:**
```json
{
  "context_payload": "================...[ZONE 1]...[ZONE 2]...[ZONE 3]...[ZONE 4]...",
  "zones_included": ["zone1", "zone2", "zone3", "zone4"],
  "token_estimate": 1234
}
```

#### 4. Add Interaction
```bash
POST /memory/add
Content-Type: application/json

{
  "role": "moderator",
  "content": "Let's move to the next topic.",
  "metadata": {"section": "transition"},
  "store_in_rag": true
}
```

#### 5. Clear Memory
```bash
POST /memory/clear
Content-Type: application/json

{
  "target": "short_term"  # or "long_term" or "all"
}
```

#### 6. Start New Debate
```bash
POST /memory/debate/start
Content-Type: application/json

{
  "debate_id": "debate_002",
  "clear_previous": true
}
```

## Configuration

### Embedding Providers

Edit `.env` or `backend/memory/embeddings.py`:

```python
EMBEDDING_PROVIDER = "sentence-transformers"  # Default: local, free
# EMBEDDING_PROVIDER = "openai"  # Requires OPENAI_API_KEY
# EMBEDDING_PROVIDER = "huggingface"  # Requires HF_TOKENS
```

### Vector Store Backend

```python
# ChromaDB (persistent, recommended for production)
memory = HybridMemoryManager(long_term_backend="chromadb")

# FAISS (in-memory, faster, good for development)
memory = HybridMemoryManager(long_term_backend="faiss")
```

### Memory Window Size

```python
# Adjust short-term memory window
memory = HybridMemoryManager(short_term_window=6)  # Keep last 6 messages
```

## Integration with ATLAS v2.0

### Enhanced Debate with Memory

```python
from v2_features.atlas_v2_integration import ATLASv2
from memory.memory_manager import get_memory_manager

# Initialize ATLAS v2.0 with memory
atlas = ATLASv2(model_name="llama3")
memory = get_memory_manager()

# Set debate context
memory.set_debate_context("enhanced_debate_001")

# Run debate with memory-enhanced agents
result = await atlas.analyze_claim_v2(
    claim="Artificial intelligence will benefit humanity",
    num_agents=4,
    enable_reversal=True
)

# Memory automatically tracks all interactions
summary = memory.get_memory_summary()
print(f"Debate completed: {summary['turn_counter']} turns")

# Search debate history
key_points = memory.search_memories(
    query="main arguments about AI benefits",
    top_k=5
)
```

## Advanced Features

### Role Reversal with Memory Coherence

The memory system ensures agents recall their original stance during role reversal:

```python
# Agent A's original stance is stored in memory
memory.add_interaction(
    role="agent_a_original",
    content="I believe AI will replace jobs",
    metadata={"phase": "initial"}
)

# During reversal, agent retrieves original stance
context = memory.build_context_payload(
    system_prompt="You are now defending the opposite view.",
    current_task="Argue that AI will create jobs",
    query="my original stance on AI and jobs"  # RAG retrieves contradictory view
)
```

### Token Usage Optimization

```python
# Use shorter window for token efficiency
memory.short_term.resize_window(2)  # Only keep 2 recent messages

# Reduce RAG retrieval
context = memory.build_context_payload(
    system_prompt="...",
    current_task="...",
    top_k_rag=2,  # Only retrieve 2 most relevant memories
    use_long_term=True  # Can disable entirely if not needed
)
```

### Memory Diagnostics

```python
# Get detailed memory statistics
stats = memory.get_memory_summary()
print(f"Short-term: {stats['short_term']['capacity_used']}")
print(f"Long-term: {stats['long_term']['total_memories']} memories")

# Export memory state
state = memory.export_memory_state()

# Search specific debates
results = memory.search_memories(
    query="climate change arguments",
    filter_metadata={"debate_id": "debate_001"}
)
```

## Performance Optimization

### Batch Operations

```python
# Add multiple interactions efficiently
memory.long_term.add_memories_batch(
    texts=["Turn 1 content", "Turn 2 content", "Turn 3 content"],
    metadatas=[{"turn": 1}, {"turn": 2}, {"turn": 3}]
)
```

### Embedding Cache

Embeddings are automatically cached by ChromaDB/FAISS. For additional caching:

```python
from memory.embeddings import get_embedding_service

embedding_service = get_embedding_service()

# Batch embed for efficiency
texts = ["text1", "text2", "text3"]
embeddings = embedding_service.embed_batch(texts, batch_size=32)
```

## Troubleshooting

### ChromaDB Not Available

```bash
# Install ChromaDB
pip install chromadb

# Or use FAISS fallback
memory = HybridMemoryManager(long_term_backend="faiss")
```

### Out of Memory

```python
# Reduce window size
memory.short_term.resize_window(2)

# Clear old memories
memory.clear_long_term()

# Use FAISS instead of ChromaDB (lighter)
memory = HybridMemoryManager(long_term_backend="faiss")
```

### Slow RAG Retrieval

```python
# Reduce retrieval count
context = memory.build_context_payload(..., top_k_rag=2)

# Use sentence-transformers (faster than OpenAI API)
# Set EMBEDDING_PROVIDER="sentence-transformers" in embeddings.py
```

## Metrics & Monitoring

### Track Memory Usage

```python
import logging
logging.basicConfig(level=logging.INFO)

# Memory operations are automatically logged
memory.add_interaction(...)  # Logs: "Added interaction: proponent (turn 5)"
memory.search_memories(...)  # Logs: "Search completed: 10 results"
```

### Visualize RAG Hits

```python
# Get search results with scores
results = memory.search_memories(query="...", top_k=10)

for result in results:
    print(f"Rank {result['rank']}: Score {result['score']:.3f}")
    print(f"  {result['text'][:100]}...")
```

## Future Enhancements

See `Hybrid_Memory_System_PRD.md` for planned features:

- **Phase 4: Optimization & Monitoring**
  - Token usage optimization
  - RAG retrieval hit visualization on dashboard
  - Memory diagnostics module

- **Future Enhancements**
  - Episodic memory tagging
  - Emotional tone awareness
  - Self-healing memory (auto-pruning + summarization)

## License

© 2025 ATLAS Project — Hybrid Memory Architecture (RAG + Short-Term)

---

## Quick Reference

| Component | Purpose | Zone |
|-----------|---------|------|
| `HybridMemoryManager` | Main orchestrator | All |
| `VectorStore` | Long-term RAG storage | Zone 2 |
| `ShortTermMemory` | Conversational window | Zone 3 |
| `EmbeddingService` | Semantic embeddings | Zone 2 |
| `MemoryEnhancedAgent` | Agent with memory | All |

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/memory/status` | GET | Memory statistics |
| `/memory/search` | POST | Semantic search |
| `/memory/context` | POST | Build 4-zone payload |
| `/memory/add` | POST | Add interaction |
| `/memory/clear` | POST | Clear memory |
| `/memory/debate/start` | POST | Initialize debate |

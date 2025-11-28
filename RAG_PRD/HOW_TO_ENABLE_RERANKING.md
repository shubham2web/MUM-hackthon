# How to Enable LLM Re-ranking

## Quick Start

LLM re-ranking is **disabled by default** to avoid API rate limits during testing. Here's how to enable it:

### Option 1: Enable Globally (Production)

In `backend/memory/vector_store.py`, change line 62:

```python
# Before (default)
enable_reranking: bool = False

# After (production)
enable_reranking: bool = True
```

### Option 2: Enable Per-Instance (Flexible)

```python
from memory.memory_manager import HybridMemoryManager

# Enable re-ranking for this instance
memory = HybridMemoryManager(
    enable_long_term=True,
    enable_short_term=True,
    enable_reranking=True  # 🆕 Add this parameter
)

# Or via vector store directly
from memory.vector_store import VectorStore

vector_store = VectorStore(
    collection_name="atlas_memory",
    backend="chromadb",
    enable_reranking=True  # 🆕 Enable here
)
```

### Option 3: Enable for Benchmark Only

In `backend/tests/run_rag_benchmark.py`, modify line 56:

```python
# Initialize memory manager with re-ranking enabled
memory = get_memory_manager(
    collection_name="rag_benchmark",
    enable_reranking=True  # 🆕 Add this
)
```

## Configuration

### API Provider

Default is Groq (free tier). To use OpenAI:

In `backend/memory/reranker.py`, modify line 40:

```python
# Before (Groq)
llm_provider: str = "groq"
model: str = "llama-3.1-8b-instant"

# After (OpenAI)
llm_provider: str = "openai"
model: str = "gpt-4o-mini"
```

### Rate Limiting

Adjust delay to avoid 429 errors:

```python
from memory.reranker import LLMReranker

reranker = LLMReranker(
    rate_limit_delay=0.2  # 200ms between API calls (default 0.1)
)
```

### Caching

Disable caching for testing (forces fresh scores):

```python
reranker = LLMReranker(
    use_cache=False  # Default: True
)
```

## API Keys

### Groq (Default)

1. Get free API key: https://console.groq.com
2. Add to `backend/.env`:
   ```bash
   GROQ_API_KEY=gsk_your_key_here
   ```

### OpenAI (Alternative)

1. Get API key: https://platform.openai.com/api-keys
2. Add to `backend/.env`:
   ```bash
   OPENAI_API_KEY=sk-your_key_here
   ```

## Troubleshooting

### Error: "No Groq API key - disabling re-ranking"

**Cause**: `.env` file not loaded or key missing

**Fix**:
```python
# Add to top of your script
from dotenv import load_dotenv
load_dotenv()
```

### Error: "429 Too Many Requests"

**Cause**: Groq free tier rate limit (30 req/min)

**Fixes**:
1. Increase `rate_limit_delay`:
   ```python
   reranker = LLMReranker(rate_limit_delay=2.0)  # 2 seconds
   ```

2. Upgrade to Groq paid tier

3. Switch to OpenAI (higher limits)

### Error: "Re-ranking failed, using vector scores"

**Cause**: API error or JSON parsing issue

**Fix**: Check logs for details:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Impact

### Speed
- **Without re-ranking**: ~0.3s per search
- **With re-ranking**: ~1-2s per search (API latency)

### Cost (Groq)
- **Model**: llama-3.1-8b-instant
- **Cost**: $0.05 / 1M input tokens, $0.08 / 1M output tokens
- **Per search**: ~100 tokens → ~$0.00001 per search
- **Monthly estimate**: 10K searches → ~$0.10/month 🎉

### Cost (OpenAI)
- **Model**: gpt-4o-mini
- **Cost**: $0.15 / 1M input tokens, $0.60 / 1M output tokens
- **Per search**: ~100 tokens → ~$0.00002 per search
- **Monthly estimate**: 10K searches → ~$0.20/month

## Expected Results

### Before Re-ranking (BGE alone)
- Relevance: 60.9%
- Precision: 32.95%
- Recall: 92.31%

### After Re-ranking (BGE + LLM)
- Relevance: **80-90%** ✨ (+19-29 points)
- Precision: **60-75%** (+27-42 points)
- Recall: **85-95%** (-7 to +3 points)

## Testing

### Quick Test

```python
from memory.vector_store import VectorStore

# Create vector store with re-ranking
vs = VectorStore(enable_reranking=True)

# Add test memories
vs.add_memory("Python is a programming language", {"topic": "coding"})
vs.add_memory("Pizza is delicious", {"topic": "food"})
vs.add_memory("Neural networks use backpropagation", {"topic": "AI"})

# Search with re-ranking
results = vs.search("What is Python?", top_k=2)

# Check scores (should be higher for relevant results)
for r in results:
    print(f"Score: {r.score:.2f} | Text: {r.text}")
```

### Expected Output
```
INFO:LLMReranker:✅ LLM re-ranker initialized: llama-3.1-8b-instant
INFO:VectorStore:LLM re-ranking applied: 2 results after re-ranking
Score: 0.95 | Text: Python is a programming language
Score: 0.42 | Text: Neural networks use backpropagation
```

### Full Benchmark

```bash
cd backend
python tests/run_rag_benchmark.py
```

**Note**: Requires ~100-250 API calls. Ensure sufficient API quota.

## Production Checklist

- [ ] API keys configured in `.env`
- [ ] `enable_reranking=True` in production config
- [ ] Rate limiting tuned (`rate_limit_delay` ≥ 0.1)
- [ ] Caching enabled (`use_cache=True`)
- [ ] Error handling verified (fallback to vector scores)
- [ ] Monitoring setup (track API errors, latency)
- [ ] Budget alert configured (API costs)

## Advanced: Custom Re-ranker

Implement your own scoring logic:

```python
from memory.reranker import LLMReranker
from memory.vector_store import RetrievalResult

class CustomReranker(LLMReranker):
    def _score_relevance(self, query: str, document: str) -> float:
        # Your custom scoring logic here
        # Example: keyword matching + LLM
        keyword_score = self._keyword_match(query, document)
        llm_score = super()._score_relevance(query, document)
        
        # Weighted average
        return 0.3 * keyword_score + 0.7 * llm_score
    
    def _keyword_match(self, query: str, document: str) -> float:
        query_words = set(query.lower().split())
        doc_words = set(document.lower().split())
        overlap = len(query_words & doc_words)
        return min(overlap / len(query_words), 1.0)
```

---

**Ready to enable?** Just set `enable_reranking=True` and watch your relevance scores soar! 🚀

# 🎯 RAG Retrieval Benchmark Suite

Comprehensive testing framework for validating the quality of RAG (Retrieval Augmented Generation) memory retrieval in the ATLAS Hybrid Memory System.

## 🎪 Overview

This benchmark suite validates that **ZONE 2 (Long-Term RAG Memory)** retrieves relevant context with **>85% relevance score** across various scenarios including:

- ✅ Debate cross-references
- ✅ Multi-turn chat context
- ✅ OCR image analysis history
- ✅ **Role reversal memory** (CRITICAL for ATLAS)
- ✅ Edge cases and stress tests

## 📁 Files

```
tests/
├── __init__.py                   # Package initialization
├── test_rag_benchmark.py         # Core test harness (RAGBenchmark class)
├── rag_test_scenarios.py         # 13+ test scenarios
├── run_rag_benchmark.py          # Benchmark runner script
├── llm_judge.py                  # LLM-as-Judge relevance scorer (advanced)
└── README_BENCHMARK.md           # This file
```

## 🚀 Quick Start

### Run Full Benchmark Suite

```bash
cd backend
python tests/run_rag_benchmark.py
```

### Run with Options

```bash
# Show detailed output
python tests/run_rag_benchmark.py --verbose

# Don't export JSON results
python tests/run_rag_benchmark.py --no-export

# Run a specific test
python tests/run_rag_benchmark.py --test "Role Reversal"
```

## 📊 Test Scenarios

### Debate Tests (5 scenarios)

1. **Exact Turn Recall** - Retrieve specific turn by number
2. **Topic-Based Retrieval** - Semantic search by topic
3. **Role Filtering** - Filter memories by role metadata
4. **Recent Context Retrieval** - Prioritize recent memories
5. **Irrelevant Query Handling** - No false positives on irrelevant queries

### Role Reversal Tests (2 scenarios) ⭐ CRITICAL

6. **Original Stance Retrieval** - Reversed agent retrieves their original position
7. **Adopt Opponent's Position** - Reversed agent adopts opponent's arguments

**Why Critical**: Role reversal is a core ATLAS feature. The RAG system must overcome the agent's current prompt (ZONE 1) to retrieve factual historical context about the OPPOSITE position.

### Chat Tests (2 scenarios)

8. **Multi-Turn Chat Context** - Follow-up question context
9. **Topic Switching** - Retrieve correct topic after switching

### OCR Tests (2 scenarios)

10. **OCR Context Recall** - Reference previously analyzed images
11. **Multi-Image Context** - Connect related misinformation across images

### Edge Cases (2 scenarios)

12. **Similar Content Disambiguation** - Distinguish between very similar statements
13. **Long-Term Memory Retention** - Retrieve early content after many memories

## 📈 Evaluation Metrics

### Primary Metric: **Relevance Score** (Target: ≥85%)
- Mean semantic similarity of retrieved memories to query
- Directly measures if RAG finds contextually relevant information

### Secondary Metrics:

| Metric | Target | Description |
|--------|--------|-------------|
| **Precision** | ≥80% | % of retrieved memories that are relevant (avoid noise) |
| **Recall** | ≥90% | % of relevant memories that were retrieved (don't miss context) |
| **F1 Score** | ≥85% | Harmonic mean of precision and recall (balance) |
| **Pass Rate** | 100% | % of test cases that meet their threshold |

## 🔍 Understanding Results

### Sample Output

```
====================================================================
📊 RAG RETRIEVAL BENCHMARK RESULTS
====================================================================
Total Tests:        13
Tests Passed:       11
Pass Rate:          84.6%

Average Precision:  82.00%
Average Recall:     88.00%
Average F1 Score:   84.90%
Average Relevance:  87.30%

🎯 Target (>85% relevance): ✅ MET
====================================================================
```

### Result Interpretation

**✅ Target Met (≥85% relevance)**
- RAG system is production-ready
- Memory retrieval is helping, not hurting
- Move to Priority 3: Memory coherence & token optimization

**❌ Target Not Met (<85% relevance)**
- RAG needs optimization before production
- Review failing tests for patterns
- Apply optimization strategies (see below)

## 🔧 Optimization Strategies

### If Relevance Score < 85%

#### 1. Low Precision (too many irrelevant results)
```python
# Increase similarity threshold
MIN_SIMILARITY_THRESHOLD = 0.75  # instead of 0.5

# Enable stricter metadata filtering
results = memory.search_memories(
    query=query,
    filter_metadata={"role": "proponent", "turn": {"$gte": 5}}
)
```

#### 2. Low Recall (missing relevant memories)
```python
# Increase top_k
top_k_rag = 5  # instead of 2-3

# Hybrid search (semantic + keyword)
semantic_results = vector_store.semantic_search(query)
keyword_results = vector_store.keyword_search(query)
merged = merge_and_deduplicate(semantic_results, keyword_results)
```

#### 3. Low Relevance (embedding quality)
```python
# Try better embedding model
EMBEDDING_OPTIONS = [
    "sentence-transformers/all-MiniLM-L6-v2",  # Current (384 dim, fast)
    "sentence-transformers/all-mpnet-base-v2",  # Better quality (768 dim)
    "BAAI/bge-small-en-v1.5",  # Optimized for retrieval
]
```

## 🧪 Advanced: LLM-as-Judge

For more nuanced evaluation, use the LLM-as-Judge scorer:

```python
from tests.llm_judge import LLMRelevanceJudge

judge = LLMRelevanceJudge()
result = judge.judge_relevance(
    query="What did proponent say about safety?",
    retrieved_memory="Nuclear energy is the safest energy source..."
)

print(f"Score: {result['raw_score']}/10")
print(f"Rationale: {result['rationale']}")
```

**Output Example**:
```json
{
  "score": 0.9,
  "raw_score": 9,
  "rationale": "This memory directly answers the query by stating the proponent's position on nuclear safety with specific data (lowest death rate).",
  "success": true
}
```

**Why Use LLM-as-Judge**:
- More nuanced than pure semantic similarity
- Provides **reasoning** for debugging
- Can understand context, partial matches, and paraphrasing

## 📝 Adding Custom Test Cases

### Example: Add New Test

```python
# In rag_test_scenarios.py

def create_custom_test_cases(benchmark):
    benchmark.add_test_case(
        scenario_name="My Custom Test",
        setup_memories=[
            ("role1", "First memory content", {"metadata": "value"}),
            ("role2", "Second memory content", {"metadata": "value"}),
        ],
        query="What was said about X?",
        expected_memories=[0],  # Indices of memories that should be retrieved
        relevance_threshold=0.85,
        description="Tests custom scenario"
    )

# Load in run_rag_benchmark.py
load_all_test_scenarios(benchmark)
create_custom_test_cases(benchmark)
```

## 🐛 Debugging Failing Tests

### Step 1: Identify Failure Pattern

```bash
# Run specific failing test
python tests/run_rag_benchmark.py --test "Role Reversal"
```

### Step 2: Inspect Retrieved Memories

```python
# In test_rag_benchmark.py, add logging:
retrieved = self.memory.search_memories(query=test_case["query"], top_k=5)

for r in retrieved:
    print(f"Retrieved: {r.content[:100]}")
    print(f"Score: {r.score:.2f}")
    print(f"Expected: {r.id in expected_ids}")
```

### Step 3: Use LLM-as-Judge for Insight

```python
from tests.llm_judge import LLMRelevanceJudge

judge = LLMRelevanceJudge()
result = judge.judge_relevance(query, retrieved_memory)
print(f"LLM Rationale: {result['rationale']}")
```

**Example Rationale**:
> "This memory is on the correct topic (nuclear) but discusses economics, not the query's focus on safety."

This immediately tells you **why** it failed (topic vs. subtopic mismatch).

## 📊 Continuous Monitoring (Production)

After benchmark passes, implement ongoing monitoring:

```python
# backend/memory/metrics_tracker.py

class RAGMetricsTracker:
    def log_retrieval(self, query, retrieved_memories, user_feedback=None):
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "retrieved_count": len(retrieved_memories),
            "avg_similarity": sum(m.score for m in retrieved_memories) / len(retrieved_memories),
            "user_feedback": user_feedback  # 1-5 stars from user
        }
        self.metrics_db.append(metrics)
    
    def weekly_report(self):
        return {
            "avg_retrieval_count": ...,
            "avg_similarity": ...,
            "user_satisfaction": ...,
            "queries_with_no_results": ...
        }
```

## 🎯 Success Criteria

### ✅ Benchmark Passes If:
- Average relevance score ≥85%
- Average precision ≥80%
- Average recall ≥90%
- Average F1 score ≥85%
- All role reversal tests pass (CRITICAL)

### 📈 Next Steps After Passing:
1. Document optimal configuration (embedding model, top_k, thresholds)
2. Deploy to production with monitoring
3. Move to Priority 3: Memory coherence & token optimization
4. Gather real usage data for continuous improvement

## 🔬 Technical Details

### Ground Truth Testing
- Hand-crafted test cases where we KNOW the correct answer
- No subjective evaluation - objective pass/fail
- Tests mirror real usage patterns

### Metrics Calculation

**Precision** = True Positives / (True Positives + False Positives)
- "Of the memories we retrieved, how many were relevant?"

**Recall** = True Positives / (True Positives + False Negatives)
- "Of the relevant memories, how many did we retrieve?"

**F1 Score** = 2 × (Precision × Recall) / (Precision + Recall)
- Harmonic mean balances precision and recall

**Relevance Score** = Average(semantic_similarity of correct retrievals)
- Mean embedding similarity of true positive memories

## 💡 Key Insights

1. **Ground Truth is Critical** - We control the answer, so evaluation is objective
2. **Multiple Metrics** - Single metric can be gamed; use precision + recall + relevance
3. **Real Scenarios** - Test cases mirror actual usage (debate turns, chat context)
4. **Continuous Improvement** - Benchmark is not one-time; re-run after every change
5. **User Feedback** - In production, implicit feedback (was memory used?) is gold

## 🚀 Performance

- **Execution Time**: ~2-5 seconds per test case
- **Total Suite**: ~30-60 seconds for 13 tests
- **Memory Usage**: Negligible (ChromaDB handles persistence)

## 📚 References

- [RAG Benchmark Strategy](../RAG_BENCHMARK_STRATEGY.md) - Detailed design document
- [Memory System Guide](../MEMORY_SYSTEM_GUIDE.md) - Complete memory system documentation
- [Memory Implementation](../MEMORY_IMPLEMENTATION.md) - Technical architecture

---

**Ready to validate your RAG system? Run the benchmark now!** 🚀

```bash
python tests/run_rag_benchmark.py
```

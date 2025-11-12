# 🚀 Quick Start: Run Your First RAG Benchmark

## Prerequisites

1. **Memory System Installed**
   ```bash
   pip install sentence-transformers chromadb
   ```

2. **Backend Directory**
   ```bash
   cd backend
   ```

## Step 1: Run the Benchmark

```bash
python tests/run_rag_benchmark.py
```

**What Happens**:
- Initializes memory system
- Loads 13 test scenarios
- Executes each test (stores memories, searches, evaluates)
- Calculates metrics (precision, recall, F1, relevance)
- Prints formatted report
- Saves results to JSON file

**Expected Output**:
```
🎯 RAG RETRIEVAL BENCHMARK
======================================================================
Objective: Validate RAG retrieval quality with >85% relevance score
======================================================================

✅ Memory manager initialized
✅ Benchmark harness created

📋 Loading test scenarios...
✅ Loaded 13 test scenarios
   - Debate tests: 5
   - Role Reversal tests: 2 (CRITICAL)
   - Chat tests: 2
   - OCR tests: 2
   - Edge case tests: 2

🚀 Executing benchmark suite...

[1/13] Running: Exact Turn Recall
  ✅ PASS - Relevance: 92.3%
[2/13] Running: Topic-Based Retrieval
  ✅ PASS - Relevance: 87.1%
...
```

## Step 2: Interpret Results

### ✅ Success (≥85% relevance)

```
====================================================================
📊 RAG RETRIEVAL BENCHMARK RESULTS
====================================================================
Total Tests:        13
Tests Passed:       11
Pass Rate:          84.6%

Average Precision:  85.20%
Average Recall:     91.30%
Average F1 Score:   88.10%
Average Relevance:  87.30%

🎯 Target (>85% relevance): ✅ MET
====================================================================
```

**Next Steps**:
1. ✅ RAG system is production-ready!
2. Document optimal configuration
3. Deploy to production with monitoring
4. Move to Priority 3: Memory coherence & token optimization

### ❌ Failure (<85% relevance)

```
====================================================================
📊 RAG RETRIEVAL BENCHMARK RESULTS
====================================================================
Total Tests:        13
Tests Passed:       8
Pass Rate:          61.5%

Average Precision:  72.00%
Average Recall:     81.00%
Average F1 Score:   76.20%
Average Relevance:  74.50%

🎯 Target (>85% relevance): ❌ NOT MET
====================================================================
```

**Optimization Recommendations**:
```
💡 RECOMMENDATIONS
====================================================================
⚠️  RAG system needs optimization (target not met)

Current relevance: 74.5%
Target relevance: 85%
Gap: 10.5 percentage points

🔧 Suggested optimizations:

  1. LOW PRECISION (too many irrelevant results)
     - Increase similarity threshold (e.g., 0.75 instead of 0.5)
     - Enable stricter metadata filtering
     - Consider re-ranking retrieved results

  2. LOW RECALL (missing relevant memories)
     - Increase top_k (retrieve more results)
     - Try hybrid search (semantic + keyword)
     - Expand queries with synonyms
```

## Step 3: Debug Failing Tests

### View Failing Test Details

Check the individual test results in the output:

```
📋 Individual Test Results:
----------------------------------------------------------------------

❌ FAIL Role Reversal - Original Stance Retrieval
   Description: Tests if reversed agent can retrieve original position
   Precision:  60.00% (3/5 correct)
   Recall:     75.00% (3/4 found)
   F1 Score:   66.67%
   Relevance:  72.30%
```

### Run Single Failing Test

```bash
python tests/run_rag_benchmark.py --test "Role Reversal"
```

### Use LLM-as-Judge for Insight

```python
from tests.llm_judge import LLMRelevanceJudge

judge = LLMRelevanceJudge()

# Test the query that failed
result = judge.judge_relevance(
    query="What was my original argument FOR solar?",
    retrieved_memory="Solar is unreliable and intermittent..."
)

print(f"Score: {result['raw_score']}/10")
print(f"Rationale: {result['rationale']}")
```

**Example Output**:
```
Score: 3/10
Rationale: This memory discusses AGAINST solar, not FOR solar as requested in the query. Wrong perspective retrieved.
```

**Insight**: The RAG is retrieving opponent arguments instead of proponent arguments → metadata filtering issue.

## Step 4: Apply Optimizations

### Example: Increase Similarity Threshold

Edit `backend/memory/vector_store.py`:

```python
# Before
results = self.collection.query(
    query_embeddings=[embedding],
    n_results=top_k
)

# After - only return results with score > 0.75
results = self.collection.query(
    query_embeddings=[embedding],
    n_results=top_k * 2  # Get more candidates
)

# Filter by similarity threshold
filtered_results = [
    r for r in results['documents'][0] 
    if results['distances'][0][i] > 0.75
]
```

### Re-run Benchmark

```bash
python tests/run_rag_benchmark.py
```

**Check if relevance improved!**

## Common Issues & Solutions

### Issue 1: ImportError for memory modules

```bash
ModuleNotFoundError: No module named 'memory'
```

**Solution**: Ensure you're in the `backend` directory
```bash
cd backend
python tests/run_rag_benchmark.py
```

### Issue 2: ChromaDB not found

```bash
ModuleNotFoundError: No module named 'chromadb'
```

**Solution**: Install dependencies
```bash
pip install chromadb sentence-transformers
```

### Issue 3: All tests failing with 0% relevance

```bash
Average Relevance:  0.00%
```

**Likely Cause**: Embedding model not loaded properly

**Solution**: Check embedding service initialization
```python
from memory.embeddings import EmbeddingService

service = EmbeddingService()
test_embedding = service.embed_text("test")
print(f"Embedding dimension: {len(test_embedding)}")
# Should print: Embedding dimension: 384
```

## Advanced Usage

### Run Without Exporting Results

```bash
python tests/run_rag_benchmark.py --no-export
```

### Run Quietly (No Verbose Output)

```bash
python tests/run_rag_benchmark.py --verbose=False
```

### Compare Before/After Optimization

```bash
# Before optimization
python tests/run_rag_benchmark.py > results_before.txt

# Apply optimization...

# After optimization
python tests/run_rag_benchmark.py > results_after.txt

# Compare
diff results_before.txt results_after.txt
```

## Next Steps After Benchmark Passes

1. **Document Configuration**
   - Record embedding model used
   - Document top_k value
   - Note similarity thresholds
   - Save optimal parameters

2. **Enable Production Monitoring**
   ```python
   # Track RAG performance in production
   memory.log_retrieval_metrics(query, results, user_feedback)
   ```

3. **Move to Priority 3**
   - Memory coherence validation for role reversal
   - Token usage optimization
   - Memory compression/summarization

4. **Continuous Improvement**
   - Re-run benchmark monthly
   - Analyze production metrics
   - Tune based on real usage patterns

## 🎯 Success Checklist

- [ ] Benchmark runs without errors
- [ ] Average relevance score ≥85%
- [ ] All role reversal tests pass
- [ ] Precision ≥80%, Recall ≥90%
- [ ] Results exported to JSON
- [ ] Optimization recommendations reviewed (if needed)
- [ ] Configuration documented

## 📞 Need Help?

Check the comprehensive documentation:
- `tests/README_BENCHMARK.md` - Full benchmark guide
- `tests/BENCHMARK_IMPLEMENTATION.md` - Implementation details
- `RAG_BENCHMARK_STRATEGY.md` - Design strategy
- `MEMORY_SYSTEM_GUIDE.md` - Memory system documentation

---

**Ready? Let's validate your RAG system!** 🚀

```bash
cd backend
python tests/run_rag_benchmark.py
```

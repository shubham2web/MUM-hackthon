# Step 9f - Cross-Encoder Reranking (DESIGN PHASE)

**Status**: 🔄 IN PROGRESS - Design & Research  
**Date Started**: November 11, 2025, 20:10  
**Expected Duration**: 3-4 hours (design + implementation + testing)  
**Expected Gains**: +1-2pp precision, +1-2pp relevance

---

## Executive Summary

**Step 9f** implements **cross-encoder reranking** to improve ranking quality and reduce false positives. Unlike bi-encoder embeddings (used in initial retrieval), cross-encoders jointly encode query+document pairs for more accurate semantic similarity scoring.

**Strategy**: Two-stage retrieval → (1) Fast bi-encoder retrieval (BM25 + semantic), (2) Accurate cross-encoder reranking of top-K candidates

**Expected Outcome**: 76-77% relevance (+1-2pp), 34-35% precision (+1-2pp) → **MEETS Alpha-v9 criteria**

---

## Current Baseline (November 11, 2025)

| Metric | Value | Target | Gap |
|--------|-------|--------|-----|
| **Relevance** | 74.78% | ≥76% | +1.22pp |
| **Precision** | 32.95% | ≥34% | +1.05pp |
| **Recall** | 92.31% | ≥90% | ✅ MET |
| **Tests Passing** | 6/13 (46.2%) | 7/13 (54%) | +1 test |
| **F1 Score** | 47.51% | - | - |

**Source**: `backend/tests/rag_benchmark_results_20251111_200452.json`

---

## Why Cross-Encoder Reranking?

### Problem with Current System

1. **Bi-Encoder Limitations**:
   - Query and document encoded independently
   - Similarity computed via dot product/cosine
   - Misses subtle semantic nuances
   - Can't model query-document interactions

2. **False Positives** (Low Precision):
   - 32.95% precision = 67% of retrieved docs are irrelevant
   - Bi-encoders retrieve broadly similar content
   - Lack of fine-grained relevance scoring

3. **Ranking Quality** (Relevance Ceiling):
   - 74.78% relevance = some relevant docs ranked too low
   - Fixed hybrid fusion weights (vector=0.97, lexical=0.03)
   - No adaptive reranking based on query type

### Cross-Encoder Advantages

1. **Joint Encoding**:
   - Concatenate query + document: `[CLS] query [SEP] document [SEP]`
   - Transformer processes full context together
   - Models interaction between query and document tokens

2. **Better Semantic Matching**:
   - Learns which parts of document answer query
   - Captures subtle relevance signals
   - Trained on query-document relevance datasets (MS MARCO, etc.)

3. **Reranking Precision**:
   - Improves top-K ranking quality (K=5-10)
   - Pushes irrelevant docs down (improves precision)
   - Promotes highly relevant docs up (improves relevance)

### Two-Stage Retrieval Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: Fast Bi-Encoder Retrieval (Current System)        │
│                                                             │
│  Query → Embedding → Hybrid Search (BM25 + Semantic)       │
│         ↓                                                   │
│  Top-20 Candidates (cast wide net)                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: Accurate Cross-Encoder Reranking (NEW)            │
│                                                             │
│  For each candidate:                                        │
│    Score = CrossEncoder(query, document)                   │
│                                                             │
│  Sort by cross-encoder scores                              │
│         ↓                                                   │
│  Top-5 Reranked Results (high precision)                   │
└─────────────────────────────────────────────────────────────┘
```

**Key Insight**: Retrieve broadly (recall), rerank precisely (precision)

---

## Model Selection

### Candidate Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| **ms-marco-MiniLM-L6-v2** | 80MB | Fast | Good | General reranking |
| **ms-marco-MiniLM-L12-v2** | 120MB | Medium | Better | Higher quality |
| **bge-reranker-base** | 278MB | Slow | Best | Maximum quality |
| **cross-encoder/ms-marco-TinyBERT-L-6** | 67MB | Very Fast | Decent | Low latency |

### Recommended: **ms-marco-MiniLM-L6-v2**

**Rationale**:
- ✅ Fast inference (~10-20ms per query-doc pair)
- ✅ Small model size (80MB, easy to deploy)
- ✅ Trained on MS MARCO (query-document relevance)
- ✅ Proven track record in RAG systems
- ✅ Compatible with `sentence-transformers` library

**Alternative**: **bge-reranker-base** if quality more important than speed

---

## Implementation Design

### Architecture Overview

```python
# PROPOSED IMPLEMENTATION

class CrossEncoderReranker:
    """Reranks retrieved documents using cross-encoder scoring."""
    
    def __init__(self, model_name='cross-encoder/ms-marco-MiniLM-L6-v2'):
        self.model = CrossEncoder(model_name)
        self.enabled = True
    
    def rerank(self, query: str, documents: List[Dict], top_k: int = 5):
        """
        Rerank documents using cross-encoder scores.
        
        Args:
            query: User query
            documents: List of candidate documents (from stage 1)
            top_k: Number of top results to return
        
        Returns:
            Reranked documents sorted by cross-encoder score
        """
        if not self.enabled or len(documents) == 0:
            return documents[:top_k]
        
        # Prepare query-document pairs
        pairs = [(query, doc['text']) for doc in documents]
        
        # Score with cross-encoder
        scores = self.model.predict(pairs)
        
        # Rerank by cross-encoder scores
        for doc, score in zip(documents, scores):
            doc['rerank_score'] = float(score)
        
        # Sort by rerank score (descending)
        reranked = sorted(documents, key=lambda x: x['rerank_score'], reverse=True)
        
        return reranked[:top_k]
```

### Integration Points

#### Option A: Monkey-Patch `search_memories()` (LIKE STEP 9c)

```python
# Wrap memory_manager.search_memories() to add reranking

original_search = memory_manager.search_memories

def reranked_search(query: str, top_k: int = 5, **kwargs):
    # Stage 1: Retrieve top-20 candidates (cast wide net)
    candidates = original_search(query, top_k=20, **kwargs)
    
    # Stage 2: Rerank with cross-encoder
    reranked = reranker.rerank(query, candidates, top_k=top_k)
    
    return reranked

memory_manager.search_memories = reranked_search
```

**Pros**: Non-invasive, easy to test  
**Cons**: Monkey-patching fragile (learned from Step 9c)

#### Option B: Add Reranking to `VectorStore.hybrid_search()` (PERMANENT)

```python
# Modify backend/memory/vector_store.py

class VectorStore:
    def __init__(self, ...):
        self.reranker = CrossEncoderReranker() if enable_reranking else None
    
    def hybrid_search(self, query: str, top_k: int = 5, ...):
        # Existing hybrid search (BM25 + semantic)
        candidates = self._retrieve_candidates(query, top_k=20)
        
        # Rerank if enabled
        if self.reranker:
            results = self.reranker.rerank(query, candidates, top_k=top_k)
        else:
            results = candidates[:top_k]
        
        return results
```

**Pros**: Clean integration, permanent solution  
**Cons**: Modifies production code, harder to A/B test

#### **RECOMMENDATION**: Use **Option A** for Step 9f testing, migrate to Option B if successful

---

## Testing Strategy

### Test Script: `step9f_cross_encoder_reranking_tests.py`

**Structure**:
```python
# 1. Load cross-encoder model
reranker = CrossEncoderReranker('cross-encoder/ms-marco-MiniLM-L6-v2')

# 2. Define reranking strategies
strategies = [
    '9f-0-baseline': No reranking (control),
    '9f-1-rerank-10': Retrieve 10, rerank to 5,
    '9f-2-rerank-20': Retrieve 20, rerank to 5,
    '9f-3-rerank-30': Retrieve 30, rerank to 5,
]

# 3. For each strategy:
for strategy in strategies:
    # Monkey-patch search_memories()
    patch_search_with_reranking(strategy)
    
    # Run RAG benchmark (13 tests)
    results = benchmark.run_all_tests()
    
    # Save results
    save_results(strategy, results)

# 4. Compare strategies
best_strategy = analyze_results(all_results)

# 5. Promote Alpha-v9 if criteria met
if best_strategy.relevance >= 76 and best_strategy.precision >= 34:
    promote_to_alpha_v9(best_strategy)
```

### Reranking Strategies

| Strategy | Retrieve | Rerank | Description |
|----------|----------|--------|-------------|
| **9f-0-baseline** | top-5 | No reranking | Control group (current system) |
| **9f-1-rerank-10** | top-10 | → top-5 | Retrieve 2x, rerank to final |
| **9f-2-rerank-20** | top-20 | → top-5 | Retrieve 4x, rerank to final |
| **9f-3-rerank-30** | top-30 | → top-5 | Retrieve 6x, rerank to final |

**Hypothesis**: Larger candidate pool (top-20) allows cross-encoder to find better results buried by bi-encoder

---

## Expected Results

### Conservative Estimate

| Strategy | Relevance | Precision | Recall | Tests Passing |
|----------|-----------|-----------|--------|---------------|
| 9f-0-baseline | 74.78% | 32.95% | 92.31% | 6/13 |
| 9f-1-rerank-10 | 75.5% (+0.72pp) | 33.5% (+0.55pp) | 92% | 6/13 |
| 9f-2-rerank-20 | **76.5%** (+1.72pp) | **34.5%** (+1.55pp) | 91% | **7/13** ✅ |
| 9f-3-rerank-30 | 76.8% (+2.02pp) | 34.8% (+1.85pp) | 90% | 7/13 |

### Optimistic Estimate

| Strategy | Relevance | Precision | Recall | Tests Passing |
|----------|-----------|-----------|--------|---------------|
| 9f-0-baseline | 74.78% | 32.95% | 92.31% | 6/13 |
| 9f-1-rerank-10 | 76.0% (+1.22pp) | 34.0% (+1.05pp) | 92% | 7/13 ✅ |
| 9f-2-rerank-20 | **77.5%** (+2.72pp) | **35.5%** (+2.55pp) | 91% | **8/13** ✅ |
| 9f-3-rerank-30 | 78.0% (+3.22pp) | 36.0% (+3.05pp) | 90% | 8/13 |

**Target for Alpha-v9**: ≥76% relevance, ≥34% precision, ≥7/13 tests passing

**Likelihood**: High (70-80%) - cross-encoder reranking proven technique

---

## Implementation Checklist

### Phase 1: Model Setup (15 minutes)
- [ ] Install `sentence-transformers` library
- [ ] Download `cross-encoder/ms-marco-MiniLM-L6-v2` model
- [ ] Test model loading and inference
- [ ] Benchmark inference speed (latency per query-doc pair)

### Phase 2: Reranker Class (30 minutes)
- [ ] Create `CrossEncoderReranker` class
- [ ] Implement `rerank()` method
- [ ] Add caching for repeated queries (optional)
- [ ] Test with sample query-document pairs

### Phase 3: Test Script (45 minutes)
- [ ] Create `step9f_cross_encoder_reranking_tests.py`
- [ ] Implement 4 reranking strategies (baseline + 3 rerank)
- [ ] Monkey-patch `search_memories()` with reranking wrapper
- [ ] Integrate with `RAGBenchmark`
- [ ] Add results saving (JSON)

### Phase 4: Testing (60 minutes)
- [ ] Run baseline (9f-0) to confirm no regression
- [ ] Run 9f-1-rerank-10 strategy
- [ ] Run 9f-2-rerank-20 strategy
- [ ] Run 9f-3-rerank-30 strategy
- [ ] Total: 4 strategies × 13 tests = 52 test executions

### Phase 5: Analysis (20 minutes)
- [ ] Compare strategies vs baseline
- [ ] Identify best performer
- [ ] Check Alpha-v9 criteria (≥76% relevance, ≥34% precision)
- [ ] Generate comparison charts (optional)

### Phase 6: Promotion (20 minutes)
- [ ] Save winning configuration via `rag_version_control.py`
- [ ] Update `PHASE2_LOG.md` with Step 9f results
- [ ] Document cross-encoder settings
- [ ] Announce Alpha-v9 promotion (if criteria met)

**Total Estimated Time**: 3 hours 10 minutes

---

## Dependencies

### Python Libraries

```bash
pip install sentence-transformers
```

**Why**: Provides `CrossEncoder` class for cross-encoder models

### Model Download (Automatic)

```python
from sentence_transformers import CrossEncoder

# Automatically downloads on first use (~80MB)
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')
```

---

## Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Model loading fails | Low | High | Test loading in isolation first |
| Inference too slow | Medium | Medium | Benchmark latency, use smaller model if needed |
| Monkey-patch breaks | Medium | High | Learned from Step 9c, careful validation |
| No improvement | Low | Medium | Cross-encoder proven technique, expect gains |
| Memory overhead | Low | Low | Model is only 80MB, acceptable |

### Schedule Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Implementation takes >4 hours | Medium | Low | Simplify design if needed, defer optional features |
| Testing runs too long | Low | Low | 52 tests should complete in <10 minutes |
| Results unclear | Low | Medium | Use baseline comparison, statistical significance |

**Overall Risk**: **LOW** - Cross-encoder reranking is well-established technique

---

## Success Criteria

### Minimum Viable Success (Alpha-v9)
- ✅ **Relevance**: ≥76% (+1.22pp from baseline)
- ✅ **Precision**: ≥34% (+1.05pp from baseline)
- ✅ **Recall**: ≥90% (maintain or slight drop acceptable)
- ✅ **Tests Passing**: ≥7/13 (54% pass rate)

### Stretch Goals (Alpha-v10)
- 🎯 **Relevance**: ≥78% (+3.22pp)
- 🎯 **Precision**: ≥36% (+3.05pp)
- 🎯 **Tests Passing**: ≥8/13 (62% pass rate)

### Failure Criteria (Proceed to Step 9g)
- ❌ **Relevance**: <75.5% (less than +0.72pp improvement)
- ❌ **Precision**: <33.5% (less than +0.55pp improvement)
- ❌ **No differentiation**: All strategies perform identically

---

## Next Steps

### Immediate Actions
1. ✅ Document Step 9f design (this file)
2. 🔄 Install `sentence-transformers` library
3. 🔄 Test cross-encoder model loading
4. 🔄 Create `CrossEncoderReranker` class
5. 🔄 Build test script `step9f_cross_encoder_reranking_tests.py`

### After Implementation
1. Run all 4 strategies (baseline + 3 reranking)
2. Analyze results and identify best performer
3. Promote to Alpha-v9 if criteria met
4. Document in PHASE2_LOG.md
5. Consider combining with Step 9c if further gains needed

---

## References

- **MS MARCO Cross-Encoder**: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2
- **Sentence Transformers Docs**: https://www.sbert.net/docs/pretrained-models/ce-msmarco.html
- **BGE Reranker**: https://huggingface.co/BAAI/bge-reranker-base
- **Current Baseline**: `backend/tests/rag_benchmark_results_20251111_200452.json`

---

**Last Updated**: November 11, 2025, 20:15  
**Status**: Design complete, ready for implementation  
**Next Action**: Install sentence-transformers and test model loading

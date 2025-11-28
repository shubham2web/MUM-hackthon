
### Step 9a: Embedding Model Upgrade (Expected +1-3pp)  CRITICAL
**Target**: Replace BGE-small-en-v1.5 (384-dim) with all-mpnet-base-v2 (768-dim)

**Rationale**: Higher-dimensional embeddings capture more semantic nuance, improving initial retrieval quality.

**Implementation**:
1. Install sentence-transformers library
2. Update embeddings.py model configuration
3. Re-index all documents with 768-dim embeddings
4. Run full benchmark and compare vs alpha-v7
5. Measure latency impact (~10-15ms expected)

**Success Criteria**: +1pp relevance gain, <50ms total latency

---

### Step 9c: Metadata Expansion (Expected +0.5-1pp)  HIGH PRIORITY
**Target**: Add structured metadata fields (document_type, role, topic, confidence)

**Rationale**: Enable context-aware retrieval and metadata-based filtering.

**Implementation**:
1. Define metadata schema (4-6 fields)
2. Extract metadata from documents (heuristics or LLM)
3. Store metadata in FAISS alongside embeddings
4. Implement metadata-aware search filters
5. Test with role/topic-specific queries

**Success Criteria**: +0.5pp relevance, improved role filtering (90%+ target)

---

### Step 9d: Hybrid Query Expansion (Expected +1-2pp)  HIGH PRIORITY
**Target**: Expand semantic queries, preserve keyword queries

**Rationale**: Exploratory queries benefit from expansion, exact matches need precision.

**Implementation**:
1. Classify query intent (keyword vs semantic)
2. For semantic: expand with synonyms/related terms
3. For keyword: preserve exact terms
4. Blend original + expanded queries (60/40 weight)
5. Benchmark with query-type breakdown

**Success Criteria**: +1pp relevance, no regression on keyword queries

---

### Step 9e: Smart Adaptive Thresholding (Expected +0.5-1pp)  MEDIUM PRIORITY
**Target**: Percentile-based threshold per query instead of fixed 0.50

**Rationale**: Step 7d showed query-specific optimal thresholds vary. Adaptive approach prevents over-filtering.

**Implementation**:
1. Calculate score distribution per query
2. Use 75th percentile as dynamic threshold
3. Fallback to 0.50 if distribution too tight
4. Track threshold values per query type
5. Benchmark with adaptive vs fixed

**Success Criteria**: +0.5pp relevance, improved precision without relevance loss

---

### Step 9f: Cross-Encoder Clean Test (Expected +0.5-1pp)  MEDIUM PRIORITY
**Target**: Re-test alpha-v8 without LTR interference (Step 9b completed)

**Rationale**: Old HGB reranker was dampening cross-encoder gains. Clean test may show +0.5-1pp additional.

**Implementation**:
1. Verify LTR disabled (already done in Step 9b)
2. Enable cross-encoder reranking (enable_reranking=True)
3. Run full 13-test benchmark
4. Compare vs alpha-v7 baseline
5. Analyze per-query improvements

**Success Criteria**: +0.8pp total gain from alpha-v7 (vs +0.31pp current)

---

##  Phase 2 Projected Outcomes

**Best Case** (all steps +max gain):
- Alpha-v7: 74.78%
- +9a: +3pp  77.78%
- +9c: +1pp  78.78%
- +9d: +2pp  80.78%
- +9e: +1pp  81.78%
- +9f: +1pp  82.78%
- **Total: 82.78% relevance** (+8.00pp from alpha-v7)

**Realistic Case** (conservative estimates):
- Alpha-v7: 74.78%
- +9a: +1.5pp  76.28%
- +9c: +0.7pp  76.98%
- +9d: +1.2pp  78.18%
- +9e: +0.7pp  78.88%
- +9f: +0.6pp  79.48%
- **Total: 79.48% relevance** (+4.70pp from alpha-v7)

**Gap to 90% after Phase 2**: 10.52pp (realistic) to 7.22pp (best case)

---

##  Phase 3 Outlook (Steps 10+)

If Phase 2 achieves 79-83% relevance, remaining strategies:

1. **Advanced Reranking** (+2-3pp)
   - Larger cross-encoders (deberta-v3-large)
   - Fine-tune on domain data

2. **Ensemble Embeddings** (+3-5pp)
   - Multiple models (mpnet + bge-large + e5)
   - Learned fusion weights

3. **Query Understanding** (+1-2pp)
   - Intent classification
   - Complexity scoring
   - Dynamic strategy selection

4. **Document Expansion** (+1-2pp)
   - Generate pseudo-queries per document
   - Index expansions alongside originals

**Phase 3 Potential**: +7-12pp  **86-95% relevance**

---

**Roadmap Complete** 

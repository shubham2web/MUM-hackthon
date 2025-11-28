# Cross-Encoder Analysis & Next Steps
## Date: November 11, 2025

---

## 🔍 PART 1: Why Cross-Encoder Failed

### Tuning Results Summary:
```
Rank   Configuration                          Relevance    Change from Baseline
1      Baseline (BGE only)                    60.9%        --
2      Hybrid: Vector Dominant (60/40)        44.0%        -16.9%
3      Hybrid: Balanced (50/50)               39.8%        -21.1%
4      Hybrid: CE Dominant (80/20)            27.1%        -33.8%
5      Pure Cross-Encoder (100%)              18.7%        -42.2%
```

### Root Cause Analysis:

#### 1. **Domain Mismatch**
- **Model Used**: `ms-marco-MiniLM-L-6-v2`
- **Training Data**: MS MARCO (Microsoft Machine Reading Comprehension)
  - Web search queries: "what is the capital of France?"
  - Passage ranking for information retrieval
  - Short queries, factual answers

- **Our Use Case**: ATLAS Debate & Chat System
  - Complex debate arguments with nuanced positions
  - Role reversal queries: "What was MY original argument that I now critique?"
  - Multi-turn conversational context
  - OCR fact-checking with misinformation detection
  - Opponent/proponent role filtering

**Result**: Model doesn't understand our semantic space!

#### 2. **Score Distribution Problem**
Looking at the minmax normalization (raw scores -5 to +15):
- MS MARCO model outputs may be calibrated for different query types
- Our queries likely produce consistently low raw scores
- After normalization, even "good" matches get low scores
- This penalizes results that BGE embeddings correctly identified

#### 3. **The Hybrid Scoring Issue**
Formula: `combined = (0.2 × vector_score) + (0.8 × ce_score)`

When CE scores are systematically low:
- Vector similarity: 0.75 → weighted: 0.15
- Cross-encoder: 0.12 → weighted: 0.096
- **Combined: 0.246** (worse than vector alone!)

The cross-encoder is essentially **downweighting** good vector matches.

---

## 🎯 PART 2: Better Cross-Encoder Models

### Option A: General-Purpose Cross-Encoders (Better than MS-MARCO)

1. **cross-encoder/ms-marco-MiniLM-L-12-v2** (Larger version)
   - Size: ~130MB (vs 91MB current)
   - Better capacity, same domain
   - Likely still has domain mismatch issue
   - **Verdict**: Minor improvement expected

2. **cross-encoder/nli-deberta-v3-large**
   - Size: ~1.5GB
   - Trained on Natural Language Inference
   - Better at understanding argument relationships
   - Good for debate/contradiction detection
   - **Verdict**: PROMISING for debate use case

3. **cross-encoder/qnli-electra-base**
   - Size: ~420MB
   - Trained on Question-Natural Language Inference
   - Better for conversational queries
   - **Verdict**: Good for chat context

### Option B: Sentence-Transformer Cross-Encoders

4. **cross-encoder/stsb-roberta-large**
   - Size: ~1.3GB
   - Trained on Semantic Textual Similarity Benchmark
   - Excellent at nuanced similarity scoring
   - **Verdict**: BEST GENERAL-PURPOSE OPTION

5. **cross-encoder/stsb-distilroberta-base**
   - Size: ~290MB
   - Distilled version (faster, smaller)
   - Good balance of size/performance
   - **Verdict**: GOOD COMPROMISE

### Option C: Domain-Specific (If Available)

6. **Fine-tuned on Debate/Argument Mining**
   - Models: Various on HuggingFace
   - Search: "argument mining", "debate", "persuasion"
   - **Verdict**: IDEAL but requires research

### Recommendation Ranking:
1. **cross-encoder/stsb-roberta-large** - Best semantic understanding
2. **cross-encoder/nli-deberta-v3-large** - Best for debates/arguments
3. **cross-encoder/stsb-distilroberta-base** - Best size/performance tradeoff

---

## 🚀 PART 3: Optimize BGE-Only Approach

### Current Performance:
- Relevance: 60.9% (Target: 85% = **24.1 point gap**)
- Precision: 32.9% (Target: 60% = **27.1 point gap**)
- Recall: 92.3% ✅ (Target: 90% = **EXCEEDS**)

### Key Insight:
**We're finding the RIGHT documents (92.3% recall), but returning too many WRONG ones (32.9% precision)**

### Optimization Strategy:

#### 1. **Similarity Threshold Tuning** (HIGHEST IMPACT)
Current: 0.45 (from Optimization 1)

**Experiment Plan**:
```python
thresholds = [0.50, 0.55, 0.60, 0.65, 0.70]
# Higher threshold = fewer results = higher precision
# Goal: Find sweet spot where precision improves without hurting recall
```

**Expected Impact**: +10-15 percentage points in precision

#### 2. **Top-K Optimization** (MEDIUM IMPACT)
Current: Returns top 5 results per query

**Experiment Plan**:
```python
top_k_values = [3, 4, 5, 6, 7]
# Fewer results = higher precision (if right docs are in top positions)
# More results = higher recall (but may hurt precision)
```

**Expected Impact**: +5-10 percentage points in precision

#### 3. **Query Preprocessing** (MEDIUM IMPACT)
Current: Raw queries sent to embedding model

**Improvements**:
- Remove stop words for semantic queries
- Expand role-specific queries: "opponent said" → ["opponent", "said", "argued", "claimed"]
- Boost recent context with temporal weighting

**Expected Impact**: +5-8 percentage points in relevance

#### 4. **Metadata Filtering Enhancement** (LOW-MEDIUM IMPACT)
Current: Basic role filtering implemented

**Improvements**:
- Time-based filtering (recency boost)
- Source-based filtering (debate vs chat vs OCR)
- Turn number filtering (for exact turn queries)

**Expected Impact**: +3-5 percentage points in precision

#### 5. **Embedding Model Upgrade** (HIGH RISK/HIGH REWARD)
Current: BGE-small-en-v1.5 (384 dim, 133MB)

**Alternatives**:
- **BGE-base-en-v1.5** (768 dim, ~420MB) - 2x capacity
- **BGE-large-en-v1.5** (1024 dim, ~1.3GB) - 3x capacity
- **all-mpnet-base-v2** (768 dim, ~420MB) - Different architecture

**Expected Impact**: +5-15 percentage points (but slower inference)

---

## 📋 PART 4: Action Plan

### Immediate Actions (This Week):

**Phase 1: Low-Hanging Fruit** (2-3 hours)
1. ✅ Disable cross-encoder re-ranking (use baseline)
2. Run threshold tuning experiments (0.50-0.70 in 0.05 steps)
3. Run top-k tuning experiments (3-7)
4. Deploy best combination

**Expected Result**: 60.9% → 72-78% relevance

**Phase 2: Query & Metadata Optimization** (1 day)
1. Implement query preprocessing
2. Enhance metadata filtering with time/source/turn
3. Re-run benchmark

**Expected Result**: 72-78% → 80-82% relevance

**Phase 3: Model Upgrade Evaluation** (2-3 hours)
1. Test BGE-base-en-v1.5 (2x capacity)
2. Test all-mpnet-base-v2 (different approach)
3. Compare speed vs quality tradeoff

**Expected Result**: 80-82% → 85%+ relevance ✅ TARGET MET

### Future Exploration (Next Sprint):

**Phase 4: Better Cross-Encoder** (1-2 days)
1. Download and test `cross-encoder/stsb-roberta-large`
2. Re-run tuning experiments with new model
3. Compare with optimized BGE-only

**Expected Result**: May exceed 85% with hybrid approach

---

## 💾 PART 5: Implementation Code

### Disable Cross-Encoder (Immediate)
```python
# In memory/vector_store.py line 62
enable_reranking: bool = False  # Disable cross-encoder
```

### Threshold & Top-K Tuning Script
```python
# Create: tests/tune_threshold_topk.py

thresholds = [0.50, 0.55, 0.60, 0.65, 0.70]
top_k_values = [3, 4, 5, 6, 7]

for threshold in thresholds:
    for top_k in top_k_values:
        os.environ['SIMILARITY_THRESHOLD'] = str(threshold)
        os.environ['DEFAULT_TOP_K'] = str(top_k)
        
        # Run benchmark
        results = run_benchmark()
        
        # Track best combination
```

### Query Preprocessing
```python
# Add to memory/vector_store.py

def preprocess_query(self, query: str) -> str:
    """Enhance query for better semantic search"""
    
    # Expand role mentions
    query = query.replace("opponent said", "opponent argued claimed stated")
    query = query.replace("proponent said", "proponent argued claimed stated")
    
    # Remove noise words for semantic queries
    if not any(word in query.lower() for word in ["what", "when", "where", "who"]):
        # Keep stop words for factual queries, remove for semantic
        stop_words = ["the", "a", "an", "in", "on", "at"]
        query = " ".join(w for w in query.split() if w.lower() not in stop_words)
    
    return query
```

---

## 🎯 Success Metrics

### Target Achievement Path:

| Phase | Action | Expected Relevance | Gap to 85% |
|-------|--------|-------------------|-----------|
| Current | Baseline BGE | 60.9% | -24.1% |
| Phase 1 | Threshold + Top-K | 72-78% | -7 to -13% |
| Phase 2 | Query + Metadata | 80-82% | -3 to -5% |
| Phase 3 | Model Upgrade | **85%+** ✅ | **TARGET MET** |
| Phase 4 | Better Cross-Encoder | 87-90%? | Exceed target |

### Timeline:
- **Week 1**: Phases 1-2 (Quick wins)
- **Week 2**: Phase 3 (Model evaluation)
- **Week 3**: Phase 4 (Advanced optimization)

---

## 📊 Lessons Learned

1. **Domain matters more than model size**: A small domain-specific model beats a large general model
2. **BGE embeddings are excellent**: 60.9% with minimal tuning shows strong foundation
3. **Singleton patterns need careful handling**: Debug took hours due to reranker caching
4. **Systematic tuning is essential**: Without the full experiment suite, we wouldn't have discovered the cross-encoder failure
5. **High recall is good news**: Finding right documents means the problem is filtering, not retrieval

---

## 🔧 Next Commands to Run

```bash
# 1. Disable cross-encoder immediately
# Edit memory/vector_store.py: enable_reranking = False

# 2. Create threshold tuning script
cd backend/tests
python create_threshold_tuner.py

# 3. Run threshold tuning
python tune_threshold_topk.py

# 4. Deploy best config
# Update default values in config

# 5. Test BGE-base model
python test_bge_base.py
```

---

**Status**: Ready to proceed with Phase 1 optimizations
**Next Step**: Disable cross-encoder and begin threshold tuning
**Owner**: Development Team
**Priority**: HIGH (blocking 85% target)

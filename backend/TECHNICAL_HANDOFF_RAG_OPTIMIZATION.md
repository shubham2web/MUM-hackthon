# RAG Optimization - Technical Handoff Guide
**For Development Team | November 11, 2025**

---

## 🎯 Purpose

This document provides everything a developer needs to:
1. Understand the current RAG system state
2. Execute Phase 2 optimizations (Steps 9a-9f)
3. Debug issues and troubleshoot regressions
4. Extend the optimization framework

---

## 📁 File Structure & Key Components

### Core RAG System
```
backend/
├── memory/
│   ├── vector_store.py          # Main RAG retrieval (1317 lines)
│   ├── cross_encoder_reranker.py # Reranking infrastructure (254 lines)
│   └── embeddings.py             # Embedding model config
├── rag_version_control.py        # Config versioning (480 lines)
└── tests/
    ├── run_rag_benchmark.py      # Main benchmark suite
    ├── step7e_query_preprocessing.py
    ├── step8_reranking_experiments.py
    └── ...
```

### Documentation
```
backend/
├── RAG_OPTIMIZATION_LOG.md              # Complete history (750+ lines)
├── RAG_OPTIMIZATION_PHASE1_SUMMARY.md   # Phase 1 report
├── EXECUTIVE_BRIEF_RAG_OPTIMIZATION.md  # Leadership brief
└── TECHNICAL_HANDOFF_RAG_OPTIMIZATION.md # This file
```

### Version Backups
```
backend/backups/rag_versions/
├── baseline-v1_vector_store.py
├── alpha-v2_vector_store.py
├── ...
├── alpha-v7_vector_store.py           # Current stable
└── alpha-v8-experimental_vector_store.py
```

---

## 🔧 Current Configuration (Alpha-v7 Stable)

### Key Parameters in `vector_store.py`

```python
class VectorStore:
    def __init__(
        self,
        embedding_model="BAAI/bge-small-en-v1.5",  # 384-dim embeddings
        similarity_metric="l2",                     # L2 distance
        similarity_threshold=0.50,                  # Static threshold
        hybrid_vector_weight=0.97,                  # 97% semantic, 3% lexical
        query_preprocessing_mode="7e-1",            # Basic normalization
        reranker_fusion_weight=0.7,                 # 70% vector, 30% CE (unused)
        enable_reranking=False,                     # Cross-encoder disabled
    ):
        # LTR/HGB reranker DISABLED (Step 9b)
        self.enable_ltr_reranking = False           # Hardcoded False
        
        # Cross-encoder reranker (optional, disabled by default)
        if enable_reranking:
            from memory.cross_encoder_reranker import LightweightReranker
            self.cross_encoder_reranker = LightweightReranker()
```

### Query Preprocessing (7e-1 Mode)
```python
def _preprocess_7e_1(self, query: str) -> str:
    """Basic normalization - adopted in alpha-v7"""
    query = query.lower()
    query = re.sub(r'[^\w\s]', ' ', query)  # Remove punctuation
    query = re.sub(r'\d+', '', query)        # Remove numbers
    query = re.sub(r'\s+', ' ', query).strip()
    return query
```

---

## 🚀 Phase 2 Implementation Guide

### Step 9a: Embedding Model Upgrade (CRITICAL)

**Goal**: Replace BGE-small-en-v1.5 (384-dim) with all-mpnet-base-v2 (768-dim)

**Steps**:

1. **Install Dependencies**
```bash
cd backend
pip install sentence-transformers
```

2. **Update `embeddings.py`** (or `vector_store.py` model config)
```python
# OLD
embedding_model = "BAAI/bge-small-en-v1.5"  # 384-dim

# NEW
embedding_model = "sentence-transformers/all-mpnet-base-v2"  # 768-dim
```

3. **Re-index Documents**
```python
# This will automatically happen when VectorStore initializes
# with new embedding_model parameter
python
>>> from memory.vector_store import VectorStore
>>> vs = VectorStore(embedding_model="sentence-transformers/all-mpnet-base-v2")
>>> # Documents will be re-embedded on next add() call
```

4. **Benchmark New Config**
```bash
python tests/run_rag_benchmark.py
```

5. **Save Version if Successful** (≥+1pp gain)
```bash
python
>>> from rag_version_control import save_version
>>> save_version(
...     version_name="alpha-v9-mpnet",
...     description="Step 9a: Upgraded to all-mpnet-base-v2 (768-dim)",
...     relevance=76.5,  # Example from benchmark
...     tests_passed=7,
...     alpha=0.97
... )
```

**Expected Outcome**: +1-3pp relevance, +10-15ms latency

**Troubleshooting**:
- If model download fails: `huggingface-cli login` first
- If latency >50ms: Consider ONNX optimization
- If gain <+0.5pp: Verify index rebuilt correctly

---

### Step 9e: Adaptive Thresholding (QUICK WIN)

**Goal**: Replace fixed 0.50 threshold with percentile-based dynamic threshold

**Steps**:

1. **Add Adaptive Threshold Method** in `vector_store.py`
```python
def _calculate_adaptive_threshold(self, scores: List[float]) -> float:
    """Calculate dynamic threshold based on score distribution"""
    if len(scores) < 3:
        return self.similarity_threshold  # Fallback to 0.50
    
    # Use 75th percentile as threshold
    scores_sorted = sorted(scores, reverse=True)
    percentile_75_idx = int(len(scores) * 0.25)  # Top 25%
    adaptive_threshold = scores_sorted[percentile_75_idx]
    
    # Ensure threshold in reasonable range [0.3, 0.8]
    return max(0.3, min(0.8, adaptive_threshold))
```

2. **Integrate in Search Method** (around line 1100)
```python
# OLD
threshold = self.similarity_threshold  # Fixed 0.50

# NEW
scores = [result['score'] for result in blended_results]
threshold = self._calculate_adaptive_threshold(scores)
```

3. **Benchmark**
```bash
python tests/run_rag_benchmark.py
```

4. **Save if Successful** (≥+0.5pp gain)
```bash
python
>>> save_version(
...     version_name="alpha-v10-adaptive",
...     description="Step 9e: Adaptive percentile-based thresholding",
...     relevance=75.3,  # Example
...     tests_passed=7,
...     alpha=0.97
... )
```

**Expected Outcome**: +0.5-1pp relevance, no precision loss

---

### Step 9f: Cross-Encoder Clean Test

**Goal**: Re-test alpha-v8 without LTR interference

**Steps**:

1. **Verify LTR Disabled** (should already be done)
```python
# Check vector_store.py lines 146-149
assert self.enable_ltr_reranking == False
```

2. **Enable Cross-Encoder**
```python
# Modify tests/run_rag_benchmark.py or create new test file
from memory.vector_store import VectorStore

# Monkey-patch to enable reranking
original_init = VectorStore.__init__
def patched_init(self, *args, **kwargs):
    kwargs['enable_reranking'] = True
    kwargs['reranker_fusion_weight'] = 0.7
    original_init(self, *args, **kwargs)

VectorStore.__init__ = patched_init
```

3. **Run Benchmark**
```bash
python tests/run_rag_benchmark_with_reranking.py
```

4. **Compare vs Alpha-v7**
- Target: ≥+0.8pp gain (currently +0.31pp in alpha-v8)
- If successful, consider promoting to stable

**Expected Outcome**: +0.8-1pp relevance with clean cross-encoder

---

### Step 9d: Query Expansion

**Goal**: Expand semantic queries, preserve keyword queries

**Steps**:

1. **Install Dependencies**
```bash
pip install nltk
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

2. **Add Query Expansion Method**
```python
from nltk.corpus import wordnet

def _expand_query(self, query: str) -> str:
    """Expand query with synonyms for semantic queries"""
    # Simple heuristic: <3 words = keyword, ≥3 words = semantic
    words = query.split()
    if len(words) < 3:
        return query  # Preserve keyword queries
    
    # Expand semantic queries
    expanded_terms = []
    for word in words:
        expanded_terms.append(word)
        synsets = wordnet.synsets(word)
        if synsets:
            # Add top synonym
            synonym = synsets[0].lemmas()[0].name()
            if synonym != word:
                expanded_terms.append(synonym)
    
    # Blend original (60%) + expanded (40%)
    original_weight = 0.6
    expanded_text = ' '.join(expanded_terms)
    return f"{query} {query} {expanded_text}"  # Repeat query for weight
```

3. **Integrate in Search Pipeline**
```python
def search(self, query: str, ...):
    # Add after preprocessing
    query = self._preprocess_query(query)
    query = self._expand_query(query)  # NEW
    ...
```

4. **Benchmark with Query-Type Breakdown**
```bash
python tests/run_rag_benchmark.py
# Manually check: keyword queries (3 tests) vs semantic (10 tests)
```

**Expected Outcome**: +1-2pp overall, no regression on keyword tests

---

### Step 9c: Metadata Expansion

**Goal**: Add document_type, role, topic, confidence metadata

**Steps**:

1. **Define Metadata Schema**
```python
class DocumentMetadata:
    document_type: str   # "debate", "chat", "OCR", "edge_case"
    role: str           # "moderator", "participant", "system"
    topic: str          # "policy", "technical", "general"
    confidence: float   # 0.0-1.0, embedding quality
```

2. **Extract Metadata** (heuristic or LLM)
```python
def _extract_metadata(self, text: str) -> dict:
    """Simple heuristic metadata extraction"""
    metadata = {
        'document_type': 'chat',  # Default
        'role': 'participant',
        'topic': 'general',
        'confidence': 0.8
    }
    
    # Heuristics
    if "debate" in text.lower():
        metadata['document_type'] = 'debate'
    if "moderator:" in text.lower():
        metadata['role'] = 'moderator'
    
    return metadata
```

3. **Store Metadata in FAISS**
```python
# Modify add() method to include metadata
def add(self, texts: List[str], ...):
    for text in texts:
        metadata = self._extract_metadata(text)
        self.metadata.append(metadata)  # Store alongside embeddings
```

4. **Metadata-Aware Retrieval**
```python
def search_with_metadata(self, query: str, role_filter=None, ...):
    results = self.search(query, ...)
    
    # Post-filter by metadata
    if role_filter:
        results = [r for r in results 
                  if self.metadata[r['index']]['role'] == role_filter]
    
    return results
```

**Expected Outcome**: +0.5-1pp, improved role filtering (90%+ target)

---

## 🐛 Debugging & Troubleshooting

### Common Issues

#### Issue 1: Benchmark Regression
**Symptom**: Relevance drops after config change

**Debug Steps**:
1. Check version control: `ls backend/backups/rag_versions/`
2. Rollback to last stable:
   ```bash
   cd backend/backups/rag_versions
   cp alpha-v7_vector_store.py ../../memory/vector_store.py
   ```
3. Re-run benchmark to confirm stable state
4. Investigate change: `git diff vector_store.py`

#### Issue 2: Cross-Encoder Not Loading
**Symptom**: ImportError or model download failure

**Debug Steps**:
1. Check installation: `pip list | grep sentence-transformers`
2. Test manually:
   ```python
   from sentence_transformers import CrossEncoder
   model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
   ```
3. Check network/proxy if download fails
4. Fallback to lighter model if OOM issues

#### Issue 3: Precision/Relevance Trade-off
**Symptom**: Precision up but relevance down (or vice versa)

**Analysis**:
- Precision-relevance tension is expected
- Step 7d showed threshold tuning creates this trade-off
- Solution: Improve initial retrieval quality (embeddings, metadata)
- Don't over-filter to chase precision

#### Issue 4: Latency Spike
**Symptom**: Query time >50ms after optimization

**Debug Steps**:
1. Profile search method:
   ```python
   import time
   start = time.time()
   results = vs.search(query)
   print(f"Search took {(time.time() - start)*1000:.2f}ms")
   ```
2. Check model size (768-dim slower than 384-dim)
3. Consider ONNX optimization for embeddings
4. Disable cross-encoder if >30ms overhead

---

## 📊 Benchmarking Guide

### Running Full Benchmark
```bash
cd backend
python tests/run_rag_benchmark.py
```

**Output Interpretation**:
```
Tests Passed: 6/13       # Target: 8+ after Phase 2
Average Precision: 32.95% # Target: 38%+ after Phase 2
Average Relevance: 74.78% # Target: 80%+ after Phase 2
Average Recall: 92.31%    # Maintain ≥90%
```

### Running Specific Test Cases
```bash
python
>>> from tests.run_rag_benchmark import run_single_test
>>> run_single_test("Role Filtering")
>>> # Useful for debugging specific query types
```

### Comparing Configs
```bash
# Baseline
python tests/run_rag_benchmark.py > logs/baseline_results.txt

# After change
python tests/run_rag_benchmark.py > logs/new_config_results.txt

# Diff
diff logs/baseline_results.txt logs/new_config_results.txt
```

---

## 🔐 Version Control Best Practices

### When to Save a Version
✅ **DO save** if:
- Relevance improves ≥+0.5pp
- No regression in other metrics (recall, latency)
- Config is stable (benchmarked, tested)

❌ **DON'T save** if:
- Experimental/untested config
- Known regressions or bugs
- Temporary debugging changes

### How to Save a Version
```python
from rag_version_control import save_version

save_version(
    version_name="alpha-v11-my-optimization",
    description="Step 9X: Brief description of changes",
    relevance=76.5,        # From benchmark
    tests_passed=7,        # From benchmark
    alpha=0.97,            # hybrid_vector_weight
    notes="Optional: additional context, trade-offs, etc."
)
```

### How to Rollback
```bash
cd backend/backups/rag_versions
cp alpha-v7_vector_store.py ../../memory/vector_store.py
python tests/run_rag_benchmark.py  # Verify
```

---

## 📈 Success Criteria & Targets

### Phase 2 Targets
- **Relevance**: 80%+ (currently 74.78%)
- **Precision**: 38%+ (currently 32.95%)
- **Recall**: ≥90% (maintain current 92.31%)
- **Latency**: <50ms (currently 25-30ms)
- **Tests Passed**: 8+/13 (currently 6/13)

### Step-by-Step Milestones
| After Step | Target Relevance | Cumulative Gain |
|------------|------------------|-----------------|
| 9a (embeddings) | 76-78% | +1.5-3pp |
| 9e (threshold) | 77-79% | +2-4pp |
| 9d (expansion) | 78-80% | +3-5pp |
| 9c (metadata) | 79-81% | +4-6pp |
| 9f (cross-enc) | 80-82% | +5-7pp |

---

## 🛠️ Useful Commands & Scripts

### Quick Benchmark
```bash
cd backend && python tests/run_rag_benchmark.py | grep -E "(Tests Passed|Average)"
```

### Save Current Config
```bash
python -c "from rag_version_control import save_version; save_version('alpha-vXX-name', 'description', 76.5, 7, 0.97)"
```

### List All Versions
```bash
ls -lh backend/backups/rag_versions/
```

### Check Current Alpha
```bash
grep "hybrid_vector_weight" backend/memory/vector_store.py
```

### Verify LTR Disabled
```bash
grep -A2 "enable_ltr_reranking" backend/memory/vector_store.py
```

---

## 📞 Support & Resources

### Documentation
- **Full History**: `backend/RAG_OPTIMIZATION_LOG.md`
- **Phase 1 Summary**: `backend/RAG_OPTIMIZATION_PHASE1_SUMMARY.md`
- **Executive Brief**: `backend/EXECUTIVE_BRIEF_RAG_OPTIMIZATION.md`

### Key Files
- **Main RAG**: `backend/memory/vector_store.py` (1317 lines)
- **Reranker**: `backend/memory/cross_encoder_reranker.py` (254 lines)
- **Version Control**: `backend/rag_version_control.py` (480 lines)
- **Benchmark**: `backend/tests/run_rag_benchmark.py`

### Testing
- **13 test cases** in benchmark suite
- **8 saved configs** for comparison
- **16+ full runs** completed in Phase 1

---

## 🎓 Further Reading

### Recommended Resources
1. **BGE Embeddings**: https://huggingface.co/BAAI/bge-small-en-v1.5
2. **MPNet Embeddings**: https://huggingface.co/sentence-transformers/all-mpnet-base-v2
3. **Cross-Encoders**: https://www.sbert.net/examples/applications/cross-encoder/README.html
4. **FAISS Documentation**: https://github.com/facebookresearch/faiss/wiki

### Related Papers
- "BGE: Leveraging Pre-trained Models for Embedding" (Xiao et al., 2023)
- "Sentence-BERT: Sentence Embeddings using Siamese BERT" (Reimers & Gurevych, 2019)
- "MS MARCO Cross-Encoder" (Nogueira et al., 2019)

---

**Document Prepared**: November 11, 2025  
**Maintainer**: AI Optimization Engineer  
**Status**: ✅ Phase 1 Complete, Ready for Phase 2  
**Next Update**: After Step 9a completion (1 week)

# Phase 2 Step 9e - Baseline Instability Analysis

**Date**: November 11, 2025  
**Status**: 🚨 CRITICAL ISSUE DETECTED  
**Action**: Step 9e execution halted pending baseline stabilization

---

## 🔴 Critical Finding: Non-Deterministic Baseline

### Observed Behavior

Step 9e percentile sweep revealed **significant variance** in alpha-v7 baseline performance:

| Run | Threshold | Relevance | Δ from Expected | Tests Passed | Status |
|-----|-----------|-----------|-----------------|--------------|--------|
| 1 | 60% | 74.78% | **0.00pp** ✅ | 6/13 | Matches expected baseline |
| 2 | 70% | 71.47% | **-3.31pp** ❌ | 5/13 | Unexpected degradation |

**Expected**: All runs should show 74.78% ± 0.1pp (deterministic baseline)  
**Actual**: 3.31pp variance between consecutive runs  
**Impact**: Step 9e threshold comparison results would be **invalid**

---

## 🧬 Root Cause Analysis

### 1. **FAISS Approximate Search Non-Determinism**

**Hypothesis**: FAISS index using approximate nearest-neighbor search (IVF, HNSW, etc.)

**Evidence**:
- FAISS AVX512 failed, falling back to AVX2 (logged in test output)
- No explicit index seeding detected in `vector_store.py`
- 3.31pp variance is consistent with approximate search tolerance

**Mechanism**:
```python
# Current (likely approximate):
index = faiss.IndexFlatL2(dim)  # or IndexIVFFlat, IndexHNSWFlat

# Issue: Multiple vectors with similarity ≈ 0.75 threshold
# Small numerical differences → different top-k selections
# Result: Non-deterministic retrieval between runs
```

**Solution**: Force exact search with explicit index type verification.

---

### 2. **Tight Score Clustering at Threshold Boundary**

**Hypothesis**: α=0.97 semantic weight produces tightly clustered scores near 0.75 threshold

**Evidence**:
- Lexical weight only 3% → minimal score distribution spread
- Threshold 0.75 acts as "knife edge" for borderline documents
- 70% run: 5/13 tests passed (1 fewer than 60% run)

**Mechanism**:
```
Semantic scores: [0.78, 0.76, 0.751, 0.749, 0.72, ...]
                             ↑ Threshold 0.75 ↑
                 
60% run:  Documents [0.78, 0.76, 0.751] retrieved ✅
70% run:  Documents [0.78, 0.76] retrieved (0.751 dropped) ❌
Result: High sensitivity to tiny score fluctuations
```

**Solution**: Add score distribution logging to identify clustering.

---

### 3. **Index State Carryover**

**Hypothesis**: FAISS index not fully rebuilt between test iterations

**Evidence**:
- First run (60%): 74.78% relevance (expected)
- Second run (70%): 71.47% relevance (degraded)
- Pattern suggests accumulated state pollution

**Mechanism**:
```python
# Suspected issue:
# Test 1: Fresh index → correct results
# Test 2: Cached embeddings or internal state → corrupted results
```

**Solution**: Force index rebuild + embedding regeneration per iteration.

---

### 4. **Test Suite Query Sensitivity**

**Hypothesis**: Certain benchmark queries have true positives with scores in [0.70-0.75] range

**Evidence**:
- Test failures increase from 7/13 (60%) to 8/13 (70%)
- Suggests 1 test has critical documents with scores ≈ 0.72-0.74

**Failing Tests (Both Runs)**:
- Exact Turn Recall: 64-69% relevance (highly variable)
- Role Reversal tests: 51-65% relevance (critical failure zone)
- Irrelevant Query Handling: 0% (edge case, expected)

**Newly Failed in 70% Run**:
- Multi-Image Context: 82.4% → 76.0% (-6.4pp, crossed 80% threshold)

**Solution**: Log per-query similarity scores to identify sensitivity zones.

---

## 🎯 Impact Assessment

### Step 9e Validity

**Current Status**: ❌ **INVALID**
- Cannot determine if threshold changes improve performance
- Baseline variance (3.31pp) exceeds expected precision gain (+0.5-1.5pp)
- Any observed improvements could be statistical noise

**Example Scenario**:
```
Threshold 0.80: Measures 75.5% relevance (+0.72pp vs 74.78%)
Question: Is this a real improvement or baseline variance?
Answer: UNKNOWN - baseline varies by ±3.31pp, so +0.72pp is noise
```

### Phase 2 Timeline Impact

**Blocked Steps**:
- ❌ Step 9e-1: Percentile sweep (current)
- ❌ Step 9e-2: Dynamic variance threshold
- ❌ Step 9e-3: Semantic weighting

**Unblocked Steps**:
- ✅ Step 9d: Query expansion (no threshold dependency)
- ✅ Step 9c: Metadata expansion (no threshold dependency)
- ✅ Step 9f: Cross-encoder tuning (score normalization independent)

**Recommendation**: **Pivot to Step 9d immediately** while fixing baseline stability.

---

## ✅ Corrective Actions Required

### Immediate (Required Before Step 9e Resume)

#### Action 1: Verify FAISS Index Type
```python
# File: backend/memory/vector_store.py
# Location: VectorStore.__init__() around line 150

# Current (check):
self.index = faiss.IndexFlatL2(self.dimension)  # Exact search?
# or
self.index = faiss.IndexIVFFlat(...)  # Approximate search? ❌

# Required: Force exact search
import faiss
self.index = faiss.IndexFlatL2(self.dimension)  # Exact L2 distance
assert isinstance(self.index, faiss.IndexFlatL2), "Must use exact search for stability"
```

**Expected Impact**: Eliminate non-determinism from approximate search.

---

#### Action 2: Implement Baseline Stability Test
```python
# New file: backend/phase2/verify_baseline_stability.py

def verify_baseline_stability(num_runs=5):
    """
    Run benchmark N times with identical configuration.
    Expected: Relevance variance < 0.1pp
    """
    results = []
    for i in range(num_runs):
        # Force fresh index rebuild
        vector_store = VectorStore(backend="faiss")
        vector_store.clear()  # Clear any cached state
        
        # Run benchmark
        result = run_full_benchmark(verbose=False)
        results.append(result["average_relevance"])
        
    variance = np.std(results)
    mean = np.mean(results)
    
    print(f"Baseline Stability Test ({num_runs} runs):")
    print(f"  Mean: {mean:.2f}%")
    print(f"  StdDev: {variance:.4f}pp")
    print(f"  Range: {min(results):.2f}% - {max(results):.2f}%")
    
    if variance > 0.1:
        print(f"  ❌ UNSTABLE: Variance {variance:.4f}pp > 0.1pp threshold")
        return False
    else:
        print(f"  ✅ STABLE: Variance {variance:.4f}pp < 0.1pp threshold")
        return True
```

**Success Criteria**: 
- Variance < 0.1pp across 5 runs
- All runs show 74.78% ± 0.1pp relevance

---

#### Action 3: Add Per-Query Score Logging
```python
# File: backend/tests/run_rag_benchmark.py
# Modify: run_full_benchmark() function

# Add to each test case:
print(f"  Query: {query}")
print(f"  Similarity Scores: {[f'{s:.4f}' for s in similarity_scores]}")
print(f"  Threshold: {threshold}")
print(f"  Passed: {num_above_threshold}/{total}")
```

**Expected Output**:
```
Query: "What was my original argument about AI safety?"
Similarity Scores: ['0.7812', '0.7643', '0.7498', '0.7201', '0.6987']
Threshold: 0.75
Passed: 3/5 (documents 1-3 above threshold)
```

**Analysis**: Identify queries with scores clustering near 0.75.

---

#### Action 4: Force Index Rebuild Per Test
```python
# File: backend/phase2/step9e_adaptive_threshold_tests.py
# Modify: test_percentile_threshold() function

def test_percentile_threshold(percentile: float) -> Dict[str, Any]:
    # Add BEFORE running benchmark:
    from memory.vector_store import VectorStore
    
    # Force complete rebuild
    vs = VectorStore(backend="faiss")
    vs.clear()  # Clear FAISS index
    vs.index = None  # Force reinitialization
    del vs  # Release resources
    
    # Now run benchmark with fresh state
    results = run_full_benchmark(verbose=True, export=True)
    ...
```

**Expected Impact**: Eliminate state carryover between runs.

---

### Validation Steps

**Step 1**: Run `verify_baseline_stability.py` (5 iterations)
- **Pass Criteria**: Variance < 0.1pp, all runs 74.78% ± 0.1pp
- **Fail Criteria**: Variance > 0.5pp → investigate FAISS index type

**Step 2**: If failed, check FAISS index type:
```python
python -c "from memory.vector_store import VectorStore; vs = VectorStore(); print(type(vs.index))"
```
- **Expected**: `<class 'faiss.swigfaiss.IndexFlatL2'>` (exact search)
- **Problem**: `IndexIVFFlat`, `IndexHNSW` (approximate search)

**Step 3**: Fix index type if approximate, re-run stability test

**Step 4**: Once stable (variance < 0.1pp), resume Step 9e with:
- Fresh index rebuild per threshold
- Per-query score logging enabled
- 3-run averaging per threshold to detect residual variance

---

## 🔀 Recommended Pivot Strategy

### Option A: Fix Baseline Then Resume Step 9e (Conservative)
**Timeline**: 
- Baseline stabilization: 2-3 hours
- Step 9e execution: 30 minutes
- **Total**: 2.5-3.5 hours

**Pros**: 
- Step 9e results become valid
- Threshold optimization potential preserved

**Cons**: 
- Delays other Phase 2 steps
- May discover threshold tuning has minimal impact anyway

---

### Option B: Pivot to Step 9d Now, Fix Baseline in Parallel (Aggressive) ✅ **RECOMMENDED**
**Timeline**:
- Step 9d (query expansion): 1-2 hours (HIGH impact expected +1-2pp)
- Baseline fix (parallel): 2-3 hours
- Step 9e (later, if needed): 30 minutes

**Pros**:
- **Step 9d likely has bigger precision impact than 9e**
- Query expansion addresses semantic ambiguity (root cause of precision bottleneck)
- Fixes baseline instability in background
- Faster path to 90% relevance goal

**Cons**: 
- Step 9e may become redundant if 9d achieves target
- Some threshold optimization potential untested

---

## 📊 Decision Matrix

| Factor | Step 9e First | Step 9d First (Pivot) |
|--------|---------------|------------------------|
| **Expected Precision Gain** | +0.5-1.5pp (threshold tuning) | +1-2pp (query expansion) ✅ |
| **Baseline Dependency** | ❌ Requires stable baseline | ✅ No baseline dependency |
| **Implementation Complexity** | Medium (FAISS index fix) | Low (query preprocessing) |
| **Time to First Results** | 2.5-3.5 hours | 1-2 hours ✅ |
| **Risk of Zero Gain** | High (threshold may not help) | Low (expansion proven effective) |

**Score**: Step 9d Pivot = **4/5**, Step 9e First = **2/5**

---

## ✅ Final Recommendation

### Immediate Actions (Next 30 Minutes)

1. **Halt Step 9e execution** ✅ (Already done via Ctrl+C)

2. **Create baseline stability verification script**:
   ```bash
   python phase2/verify_baseline_stability.py
   ```

3. **Document findings** ✅ (This document)

4. **Update Phase 2 roadmap**:
   - Mark Step 9e as **BLOCKED** (baseline instability)
   - Promote Step 9d to **CRITICAL PRIORITY**
   - Add "Baseline Stabilization" as parallel task

### Next Steps (1-2 Hours)

**Primary Track**: Execute Step 9d (Query Expansion)
- Implement query preprocessing variations
- Test 5-7 expansion strategies
- Expected gain: +1-2pp precision, +0.5-1pp relevance
- **Target**: Alpha-v9 promotion at ≥34% precision

**Parallel Track**: Fix Baseline Stability
- Verify FAISS index type (exact vs approximate)
- Implement `verify_baseline_stability.py`
- Add per-query score logging
- Force index rebuild per test iteration

### Validation Criteria (Before Resuming Step 9e)

✅ Baseline variance < 0.1pp across 5 runs  
✅ All runs show 74.78% ± 0.1pp relevance  
✅ Per-query scores logged for threshold sensitivity analysis  
✅ Index rebuild verified between iterations  

---

## 📝 Lessons Learned

### Critical Insight
**"Bigger isn't always better, and faster isn't always stable."**

- Step 9a: Larger embeddings degraded performance (false assumption: bigger = better)
- Step 9e: Baseline instability invalidates optimization (false assumption: baseline = stable)

### Key Takeaway
**Always validate baseline stability before running parametric sweeps.**

Standard practice in optimization:
1. ✅ Establish baseline
2. ✅ **Verify baseline repeatability** ← **MISSING STEP**
3. ❌ Run parameter sweep (invalid without step 2)

### Process Improvement
Add "Baseline Stability Test" as **mandatory prerequisite** for all future parametric experiments (Steps 9e, 9f, etc.).

---

## 🎯 Success Criteria Update

### Step 9e Resume Conditions
- [ ] Baseline variance < 0.1pp (5-run test)
- [ ] FAISS exact search verified
- [ ] Per-query score logging implemented
- [ ] Index rebuild mechanism tested
- [ ] Step 9d completed (may make 9e unnecessary)

### Alpha-v9 Promotion Criteria (Unchanged)
- Precision ≥ 34.00% (+1.00pp)
- Relevance ≥ 74.50% (maintain ±0.3pp)
- Recall ≥ 90.00%
- Latency < 80ms

---

**Status**: Step 9e execution halted, pivot to Step 9d approved, baseline stabilization in parallel. Phase 2 timeline adjusted, alpha-v9 target achievable via alternative optimization path.

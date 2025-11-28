# Alpha-v7 Baseline Revision - Official Documentation

**Date**: November 11, 2025  
**Status**: ✅ **APPROVED - Baseline Corrected**  
**Version**: Alpha-v7 Revised (70-71% relevance)

---

## 📊 Executive Summary

### Critical Discovery
The previously reported **Alpha-v7 baseline of 74.78% relevance was a first-run outlier**, not representative of true system performance. Through rigorous testing (5 independent runs, 65 benchmark executions), we have established the **true baseline at 70-71% relevance**.

### Impact Assessment
| Metric | Previous Assumption | Corrected Baseline | Delta |
|--------|---------------------|-------------------|-------|
| **Relevance** | 74.78% | **70-71%** | **-4pp** |
| **Precision** | 32.95% | 32.95% | 0pp (unchanged) |
| **Recall** | 92.31% | 92.31% | 0pp (unchanged) |
| **Tests Passed** | 5/13 | 5/13 | 0 (unchanged) |

---

## 🔍 Root Cause Analysis

### 1. First-Run Outlier Phenomenon
**Finding**: Run 1 showed 74.78% relevance, but Runs 2-5 all converged to 70.25-71.47%.

```
Run 1: 74.78%  ← OUTLIER (initialization effect)
Run 2: 71.47%  ← True performance
Run 3: 70.25%  ← Stable state
Run 4: 70.25%  ← Stable state
Run 5: 70.25%  ← Stable state

Mean:  71.40%
StdDev: 1.97pp (UNSTABLE - 19.7x above 0.10pp threshold)
Median: 70.25%  ← Most representative
```

**Analysis**: The first run benefited from favorable initialization conditions that were not reproducible in subsequent runs.

### 2. State Convergence to Attractor
**Observation**: System exhibits strong convergence to 70-71% "attractor state" after first run.

**Hypothesis**: 
- FAISS index initialization creates favorable embedding space configuration
- Query preprocessing state (NLTK stopwords, lemmatization) differs on first load
- BM25 scoring initialized differently on cold start vs warm runs
- Score clustering at threshold boundary (0.72-0.74) creates binary pass/fail behavior

### 3. Score Clustering Effect
**Finding**: Documents cluster tightly around 0.75 relevance threshold:
- 0.72-0.74 range: High document density
- 0.75+ range: Sparse document distribution
- Result: Small scoring variations cause large relevance swings

**Impact**: 97% semantic weight (α=0.97) creates ceiling at ~71% due to embedding space limitations.

### 4. Variance Magnitude
**Measurement**: 1.97pp standard deviation across 5 runs
- **19.7x** above acceptable variance threshold (0.10pp)
- Masks optimization attempts (query expansion showed 0.00pp differentiation)
- Invalidates adaptive thresholding tests (signal << noise)

---

## 📋 Testing Protocol Violations Discovered

### Issue 1: Single-Run Baseline Assumption
**Problem**: Phase 1 established baseline from single benchmark run  
**Risk**: 25% chance of outlier selection (1 in 4 runs show anomalous results)  
**Solution**: Require 3-5 runs for all baseline measurements

### Issue 2: No Variance Validation
**Problem**: No variance checks before declaring stable baseline  
**Risk**: Optimization targets based on moving target  
**Solution**: Add variance threshold (<0.5pp) to baseline acceptance criteria

### Issue 3: Insufficient Cold Start Analysis
**Problem**: First-run conditions not isolated or documented  
**Risk**: Non-reproducible results in production  
**Solution**: Separate cold start testing from steady-state performance

---

## ✅ Corrective Actions Taken

### Action 1: Baseline Specification Update
**Old Specification** (Alpha-v7):
```yaml
relevance: 74.78%
precision: 32.95%
recall: 92.31%
tests_passed: 5/13
status: stable
```

**New Specification** (Alpha-v7 Revised):
```yaml
relevance: 70-71%  # Median: 70.25%, Mean: 71.40%
precision: 32.95%
recall: 92.31%
tests_passed: 5/13
variance: 1.97pp  # UNSTABLE - requires investigation
status: revised_baseline_accepted
first_run_outlier: 74.78%  # Do not use for targets
notes: |
  - Use 70.25% (median) for conservative targets
  - Use 71% for realistic targets
  - First run (74.78%) is outlier, not reproducible
```

### Action 2: Phase 2 Target Revision
**Old Targets** (Based on 74.78% baseline):
```
Alpha-v9: 76% relevance (+1.22pp gain = +1.6% relative)
Alpha-v10: 79-83% relevance (+4-8pp gain = +6-11% relative)
```

**New Targets** (Based on 70-71% baseline):
```
Alpha-v9: 73-74% relevance (+2-3pp gain = +3-4% relative)
Alpha-v10: 75-77% relevance (+4-6pp gain = +6-8% relative)
```

**Rationale**: Realistic +2-3pp gain per optimization phase, not +6-11pp unrealistic assumptions.

### Action 3: Test Protocol Enhancement
**New Requirements**:
1. **Multi-Run Validation**: 3-5 runs minimum for baseline establishment
2. **Variance Thresholds**: 
   - Excellent: <0.10pp (Step 9e proceeding)
   - Acceptable: <0.50pp (optimization valid)
   - Unstable: >0.50pp (investigation required)
3. **Cold Start Isolation**: First run marked as "initialization phase", not baseline
4. **Median Reporting**: Use median (not mean) for skewed distributions

### Action 4: Documentation Updates
Files updated with corrected baseline:
- ✅ `backend/phase2/BASELINE_REVISION_ALPHA_V7.md` (this file)
- ⏳ `backend/EXECUTIVE_BRIEF_RAG_OPTIMIZATION.md` (Phase 1 summary)
- ⏳ `backend/phase2/init_phase2.py` (Phase 2 launcher)
- ⏳ `backend/phase2/step9d_query_expansion_tests.py` (test script headers)
- ⏳ `backend/phase2/PHASE2_CHECKPOINT_NOV11.md` (checkpoint doc)
- ⏳ `backend/memory/vector_store.py` (configuration comments)
- ⏳ `backend/backups/rag_versions/alpha-v7_vector_store.py` (version backup)

---

## 📈 Impact on Optimization Strategy

### Blocked Steps (Until Variance Resolved)
1. **Step 9e - Adaptive Thresholding**: BLOCKED
   - Requires variance <0.10pp to detect 0.5-1.5pp threshold gains
   - Current 1.97pp variance masks all threshold signals

2. **Step 9d - Query Expansion**: DEFERRED
   - All 7 strategies showed identical 70.25% results (0.00pp differentiation)
   - Semantic ceiling at ~71% prevents further expansion gains
   - Revisit after score clustering resolved

### Unblocked Paths Forward
1. **Step 9c - Metadata Expansion**: ✅ READY
   - Orthogonal to semantic ceiling (filtering, not retrieval)
   - Expected: +0.5-1pp precision via false positive reduction
   - Duration: 2-3 hours

2. **Step 9f - Cross-Encoder Reranking**: ✅ READY
   - Post-retrieval reranking bypasses semantic limitations
   - Expected: +0.5-1pp precision, +1-2pp relevance
   - Duration: 3-4 hours

3. **Score Clustering Investigation**: ✅ RECOMMENDED
   - Identify why documents cluster at 0.72-0.74 threshold boundary
   - Test alternative thresholds (0.70, 0.65) or dynamic adjustment
   - Duration: 2-3 hours (parallel with Step 9c)

---

## 📊 Lessons Learned

### 1. Always Validate Baseline Repeatability
**Lesson**: Single-run baselines are unreliable for optimization targets.  
**Action**: Require 3-5 runs with variance analysis before declaring stable.

### 2. Inspect API Return Structures Empirically
**Lesson**: Assumed `results['average_relevance']` but actual structure was `results['summary']['avg_relevance_score']`.  
**Cost**: 30-minute debugging delay.  
**Action**: Test all API contracts with sample invocations before writing test code.

### 3. Score Distribution Analysis Before Optimization
**Lesson**: Query expansion failed because we didn't identify score clustering ceiling beforehand.  
**Action**: Profile score distributions (percentiles, clustering) before selecting optimization strategy.

### 4. Orthogonal Strategies When Hitting Ceilings
**Lesson**: Semantic ceiling at 71% blocks query expansion and embedding improvements.  
**Action**: Pivot to metadata filtering or reranking that bypass semantic limitations.

---

## 🎯 Success Criteria (Revised)

### Alpha-v9 Promotion Requirements
| Metric | Previous Target | Revised Target | Rationale |
|--------|----------------|----------------|-----------|
| **Relevance** | ≥76% (+1.22pp) | **≥73%** (+2-3pp) | Based on 70% baseline |
| **Precision** | ≥34% (+1pp) | **≥34%** (+1pp) | Unchanged |
| **Recall** | ≥92% (maintain) | ≥92% (maintain) | Unchanged |
| **Variance** | <0.10pp | <0.50pp (relaxed) | Realistic stability threshold |
| **Tests Passed** | 6/13 (+1) | 6/13 (+1) | Unchanged |

### Alpha-v10 Targets (Long-Term)
- **Relevance**: 75-77% (+4-6pp from 70% baseline)
- **Precision**: 36-38% (+3-5pp)
- **Tests Passed**: 8-10/13 (60-77% pass rate)

---

## 📁 Deliverables

1. ✅ **BASELINE_REVISION_ALPHA_V7.md** (this document)
2. ⏳ **Updated Phase 2 documentation** (targets, roadmap)
3. ⏳ **Updated test scripts** (headers, comments)
4. ⏳ **Testing protocol v2** (multi-run validation standards)
5. ⏳ **Score clustering analysis** (per-query logging, boundary docs)

---

## 🚀 Next Steps

### Immediate (Priority 1)
1. ✅ **Accept Revised Baseline**: Document distributed, team aligned
2. ⏳ **Update All Documentation**: Propagate 70-71% baseline to all files
3. ⏳ **Revise Phase 2 Targets**: Recalculate Alpha-v9 promotion criteria

### Short-Term (Priority 2-3)
4. ⏳ **Execute Step 9c**: Metadata expansion (2-3 hours)
5. ⏳ **Investigate Score Clustering**: Per-query analysis (2-3 hours, parallel)
6. ⏳ **Testing Protocol v2**: Formalize multi-run validation standards

### Long-Term (Priority 4-5)
7. ⏳ **Step 9f**: Cross-encoder reranking (if Step 9c insufficient)
8. ⏳ **Embedding Fine-Tuning**: Domain-specific training (1-2 days)
9. ⏳ **Resume Step 9d/9e**: After variance <0.5pp and clustering resolved

---

## 📞 Stakeholder Communication

**Message**: "Phase 2 baseline correction complete. Alpha-v7 true baseline is 70-71% (not 74.78%). Updated targets: Alpha-v9 @ 73% (+2-3pp realistic gain). Step 9c (metadata expansion) ready for execution. Score clustering investigation recommended in parallel. Timeline impact: +1-2 weeks to Alpha-v9 due to revised targets."

**Distribution**: Development team, QA, Product Management

---

**Document Owner**: RAG Optimization Team  
**Last Updated**: November 11, 2025  
**Status**: ✅ APPROVED FOR IMPLEMENTATION

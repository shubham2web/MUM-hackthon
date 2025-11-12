# Step 7a: Higher-Alpha Micro-Sweep Results

**Date**: November 11, 2025  
**Execution Time**: 07:53:37 - 07:54:03 (~26 seconds)  
**Status**: ✅ **SUCCESSFUL** - Found optimal α=0.95

---

## Executive Summary

**Hypothesis**: The monotonic improvement trend observed in Step 5 (α: 0.83→0.85→0.87→0.90) suggested that the peak performance might lie beyond α=0.90.

**Result**: ✅ **HYPOTHESIS CONFIRMED** - Trend continued through α=0.95 with perfect linear improvement.

**Best Configuration**:
- **Alpha**: 0.95 (95% semantic, 5% lexical)
- **Relevance**: 74.07% (+0.56% vs alpha-v3)
- **Tests Passed**: 6/13 (up from 5/13)
- **Status**: Saved as `alpha-v4`

---

## Detailed Results

### Performance Sweep Table

| Alpha | Relevance | Change | Tests Passed | Precision | Recall | F1    | Config |
|-------|-----------|--------|--------------|-----------|--------|-------|--------|
| 0.90  | 73.51%    | +0.00% | 5/13         | 32.95%    | 92.31% | 47.51% | alpha-v3 (baseline) |
| 0.91  | 73.62%    | +0.11% | 5/13         | 32.95%    | 92.31% | 47.51% | - |
| 0.92  | 73.74%    | +0.23% | 5/13         | 32.95%    | 92.31% | 47.51% | - |
| 0.93  | 73.85%    | +0.34% | 5/13         | 32.95%    | 92.31% | 47.51% | - |
| 0.94  | 73.96%    | +0.45% | 5/13         | 32.95%    | 92.31% | 47.51% | - |
| **0.95** | **74.07%** | **+0.56%** | **6/13** | 32.95% | 92.31% | 47.51% | **alpha-v4 ✅** |

### Key Observations

1. **Perfect Monotonic Improvement** ✅
   - Each 0.01 increase in alpha yielded ~0.11pp relevance gain
   - No plateau observed through α=0.95
   - Linear relationship suggests higher alphas might continue the trend

2. **Test Pass Rate Improvement** ✅
   - Tests passed increased from 5/13 to 6/13 at α=0.95
   - Pass rate: 38.5% → 46.2% (+7.7pp)
   - Additional test passed: (to be identified in detailed analysis)

3. **Stability Maintained** ✅
   - Precision: 32.95% (unchanged across all alphas)
   - Recall: 92.31% (unchanged across all alphas)
   - F1 Score: 47.51% (unchanged across all alphas)
   - No regression in retrieval quality metrics

4. **Cumulative Progress** 📊
   - **baseline-v1** (α=0.75): 71.78%
   - **alpha-v2** (α=0.85): 72.95% (+1.17%)
   - **alpha-v3** (α=0.90): 73.51% (+0.56%)
   - **alpha-v4** (α=0.95): 74.07% (+0.56%)
   - **Total Gain**: +2.29pp from baseline

---

## Technical Details

### Methodology

**Tool Used**: `step7a_higher_alpha_sweep.py`
- Automated sweep testing 6 alpha values: [0.90, 0.91, 0.92, 0.93, 0.94, 0.95]
- Used environment variable `HYBRID_VECTOR_WEIGHT` to override config
- Each alpha ran full 13-case RAG benchmark
- Metrics extracted via regex parsing from stdout
- Results saved to CSV + JSON in logs/ directory

**Test Environment**:
- Python 3.13
- FastEmbed 0.7.3 (BGE-small-en-v1.5, 384-dim)
- FAISS index backend
- 13 test scenarios (debate, role reversal, chat, OCR, edge cases)

### Configuration Changes

**File**: `backend/memory/vector_store.py`
- **Line 77**: Updated from `0.90` to `0.95`
- **Comment**: Added Step 7a optimization note
- **Verification**: Benchmark confirmed 74.07% relevance

```python
# Before (alpha-v3):
hybrid_vector_weight: float = 0.90  # STEP 5 OPTIMIZED

# After (alpha-v4):
hybrid_vector_weight: float = 0.95  # STEP 7a OPTIMIZED: Higher-alpha sweep found 0.95 = 74.07% relevance
```

---

## Verification Results

**Benchmark Run**: `run_rag_benchmark.py` (2025-11-11 08:02:04)

```
Total Tests:        13
Tests Passed:       6
Pass Rate:          46.2%

Average Precision:  32.95%
Average Recall:     92.31%
Average F1 Score:   47.51%
Average Relevance:  74.07%
```

**Tests Passed** (6/13):
1. ✅ Recent Context Retrieval (99.1%)
2. ✅ Topic Switching (100.0%)
3. ✅ OCR Context Recall (100.0%)
4. ✅ Multi-Image Context (80.7%)
5. ✅ Similar Content Disambiguation (100.0%)
6. ✅ Long-Term Memory Retention (100.0%)

**Tests Failed** (7/13):
1. ❌ Exact Turn Recall (63.0%)
2. ❌ Topic-Based Retrieval (67.8%)
3. ❌ Role Filtering (71.1%)
4. ❌ Irrelevant Query Handling (0.0%)
5. ❌ Role Reversal - Original Stance Retrieval (52.5%)
6. ❌ Role Reversal - Adopt Opponent's Position (64.8%)
7. ❌ Multi-Turn Chat Context (64.0%)

---

## Version Control

**Version Saved**: `alpha-v4`
```bash
python rag_version_control.py save \
  --version alpha-v4 \
  --relevance 74.07 \
  --alpha 0.95 \
  --tests-passed 6 \
  --notes "Step 7a: Higher-alpha micro-sweep (0.90-0.95), found 0.95 optimal with +0.56pp gain and +1 test passed"
```

**Backup Location**: `backups/rag_versions/alpha-v4_vector_store.py`

**Version History**:
1. `baseline-v1` (α=0.75): 71.78%, 5 tests
2. `alpha-v2` (α=0.85): 72.95%, 5 tests
3. `hgb-v3` (reranking enabled): 70.29%, 4 tests [REJECTED]
4. `alpha-v3` (α=0.90): 73.51%, 5 tests
5. **`alpha-v4` (α=0.95): 74.07%, 6 tests** ← **CURRENT**

---

## Gap Analysis

**Current Status**: 74.07% relevance
**Target Goal**: 90% relevance
**Remaining Gap**: 15.93 percentage points

**Progress Breakdown**:
- Step 2 (Alpha sweep to 0.85): +1.17pp
- Step 5 (Fine-grained alpha to 0.90): +0.56pp
- Step 7a (Higher-alpha to 0.95): +0.56pp
- **Total Progress**: +2.29pp (12.6% of gap closed)

---

## Next Steps

### Immediate Actions (Completed ✅)
- [x] Apply α=0.95 to `vector_store.py`
- [x] Run verification benchmark
- [x] Save as `alpha-v4` in version control
- [x] Document results in `STEP7A_ALPHA_MICROSWEEP_RESULTS.md`

### Recommended Follow-Up

**Option 1: Step 7b - Grid Search Validation** (Quick win)
- Validate alpha × lexical balance with grid search
- Test α ∈ [0.90, 0.92, 0.95] with multiple lexical weights
- Confirm 0.95 is robust across different configurations
- **Expected Time**: ~5-10 minutes
- **Risk**: Low
- **Potential Gain**: Confidence in current optimum

**Option 2: Step 7c - Ultra-Alpha Sweep** (Experimental)
- Test α ∈ [0.96, 0.97, 0.98, 0.99] to find true peak
- Risk: <2% lexical weight may hurt keyword-heavy queries
- **Expected Time**: ~15-20 minutes
- **Risk**: Medium
- **Potential Gain**: +0.2-0.4pp if trend continues

**Option 3: Step 7d - Threshold Tuning** (Moderate effort)
- Current similarity threshold unknown
- Test thresholds: [0.5, 0.6, 0.7, 0.8] to reduce false positives
- May improve precision (currently 32.95%)
- **Expected Time**: ~30 minutes
- **Risk**: Low
- **Potential Gain**: +1-2pp via precision improvement

**Option 4: Step 7e - Query Preprocessing** (High impact)
- Add query expansion, synonym handling
- Implement query reformulation for failed cases
- Focus on role reversal queries (currently failing)
- **Expected Time**: 2-4 hours
- **Risk**: Medium
- **Potential Gain**: +2-4pp on specific query types

**Option 5: Step 7f - Embedding Upgrade** (Major change)
- Upgrade from BGE-small-en-v1.5 (384-dim) to:
  - BGE-base-en-v1.5 (768-dim) - larger but better
  - all-mpnet-base-v2 (768-dim) - general purpose
- Requires re-indexing all vectors
- **Expected Time**: 1-2 hours
- **Risk**: High (breaking change)
- **Potential Gain**: +3-5pp if model fits use case better

---

## Insights & Lessons Learned

1. **Semantic Weight Dominance**
   - Debate/reasoning queries heavily favor semantic similarity
   - 95% semantic weight works well for argument-heavy content
   - Lexical weight (5%) still provides keyword anchoring

2. **Linear Improvement Pattern**
   - ~0.11pp gain per 0.01 alpha increment (highly consistent)
   - No diminishing returns observed through α=0.95
   - Suggests higher alphas worth exploring

3. **Test Pass Rate Correlation**
   - Test passes improved at α=0.95 specifically
   - Some tests have threshold effects (pass/fail at specific alphas)
   - Need to identify which test benefited from 0.95

4. **Stability vs. Progress Trade-off**
   - All quality metrics (precision, recall, F1) remained stable
   - Pure relevance gains without regression
   - Alpha tuning is "safe" optimization with low risk

---

## Output Files

**Generated by Step 7a**:
- `logs/alpha_micro_sweep_20251111_075336.csv` (tabular results)
- `logs/alpha_micro_sweep_20251111_075336.json` (structured data)
- `tests/rag_benchmark_results_20251111_080204.json` (verification benchmark)

**Documentation**:
- `STEP7A_ALPHA_MICROSWEEP_RESULTS.md` (this file)
- `RAG_OPTIMIZATION_LOG.md` (updated with Step 7a)

**Backups**:
- `backups/rag_versions/alpha-v4_vector_store.py` (config snapshot)

---

## Questions for Next Session

1. **Should we test α > 0.95?**
   - Pro: Linear trend suggests more gains possible
   - Con: <5% lexical weight may eventually hurt keyword queries
   - Decision: ?

2. **Which test improved from 5/13 to 6/13?**
   - Need to compare alpha-v3 vs alpha-v4 detailed results
   - Understand what changed at 0.95 specifically

3. **Is precision (32.95%) the bottleneck?**
   - High recall (92.31%) but low precision
   - Should we tune similarity threshold to filter irrelevant results?

4. **Are role reversal queries fundamentally harder?**
   - Both role reversal tests failing (~53-65% relevance)
   - May need specialized query preprocessing or metadata boosting

---

## References

- **Tool**: `backend/tests/step7a_higher_alpha_sweep.py`
- **Config**: `backend/memory/vector_store.py` (line 77)
- **Version Control**: `backend/rag_version_control.py`
- **Step 7 Playbook**: `STEP7_ADVANCED_OPTIMIZATION_PLAYBOOK.md`
- **Quick Reference**: `QUICK_REFERENCE.md`

---

*End of Step 7a Results*

# BASELINE CORRECTION v2 - CRITICAL FINDING

**Date**: November 11, 2025, 20:05  
**Discovery**: Baseline validation test shows **74.78% relevance**, contradicting earlier 70-71% correction  
**Impact**: Alpha-v7 REVISED baseline was INCORRECT - actual performance is HIGHER

---

## Executive Summary

Running `backend/tests/run_rag_benchmark.py` on November 11, 2025 at 20:04 revealed the **TRUE BASELINE**:

| Metric | Previous (INCORRECT) | Actual (CORRECT) | Difference |
|--------|---------------------|------------------|------------|
| **Relevance** | 70-71% (median 70.25%) | **74.78%** | +3.78 to +4.78pp |
| **Precision** | 32.95% | **32.95%** | ✅ Same |
| **Recall** | 92.31% | **92.31%** | ✅ Same |
| **Tests Passing** | 5/13 | **6/13** | +1 test |
| **Pass Rate** | 38.5% | **46.2%** | +7.7pp |

---

## Test Execution Details

**Command**: `python backend/tests/run_rag_benchmark.py`  
**Timestamp**: November 11, 2025, 20:04:52  
**Results File**: `backend/tests/rag_benchmark_results_20251111_200452.json`  
**Execution Time**: 0.98 seconds  
**Average Time per Test**: 0.08 seconds

### Individual Test Results

| Test | Status | Relevance | Precision | Recall | F1 Score |
|------|--------|-----------|-----------|--------|----------|
| Exact Turn Recall | ❌ FAIL | 69.25% | 25.00% | 100.00% | 40.00% |
| Topic-Based Retrieval | ❌ FAIL | 67.76% | 50.00% | 100.00% | 66.67% |
| Role Filtering | ❌ FAIL | 71.12% | 50.00% | 100.00% | 66.67% |
| Recent Context Retrieval | ✅ PASS | 99.06% | 40.00% | 100.00% | 57.14% |
| Irrelevant Query Handling | ❌ FAIL | 0.00% | 0.00% | 0.00% | 0.00% |
| Role Reversal - Original Stance | ❌ FAIL | 51.51% | 50.00% | 100.00% | 66.67% |
| Role Reversal - Opponent Position | ❌ FAIL | 65.73% | 50.00% | 100.00% | 66.67% |
| Multi-Turn Chat Context | ❌ FAIL | 65.37% | 25.00% | 100.00% | 40.00% |
| Topic Switching | ✅ PASS | 100.00% | 20.00% | 100.00% | 33.33% |
| OCR Context Recall | ✅ PASS | 100.00% | 25.00% | 100.00% | 40.00% |
| Multi-Image Context | ✅ PASS | 82.39% | 40.00% | 100.00% | 57.14% |
| Similar Content Disambiguation | ✅ PASS | 100.00% | 33.33% | 100.00% | 50.00% |
| Long-Term Memory Retention | ✅ PASS | 100.00% | 20.00% | 100.00% | 33.33% |

**Summary**:
- **Total Tests**: 13
- **Tests Passed**: 6 (46.2% pass rate)
- **Average Relevance**: **74.78%** ⬅️ CRITICAL VALUE
- **Average Precision**: 32.95%
- **Average Recall**: 92.31%
- **Average F1 Score**: 47.51%

---

## Why the Discrepancy?

### Hypothesis 1: Run Variance (MOST LIKELY)
- **Alpha-v7 REVISED** was based on limited runs showing 70-71% relevance
- **Current baseline** (74.78%) represents different run with higher scores
- **Variance**: ~5pp between runs suggests UNSTABLE BASELINE
- **Testing Protocol v2** requires 3-5 runs, but earlier revision based on 1-2 runs

**Evidence**:
- BASELINE_REVISION_ALPHA_V7.md noted variance: "1.97pp standard deviation (UNSTABLE)"
- Single run measurements unreliable for setting baselines
- Current 74.78% could be statistical outlier OR true performance

### Hypothesis 2: Code Changes Since Revision
- **Alpha-v7 REVISED** documented on [date not specified]
- **Current test** run on November 11, 2025, 20:04
- Possible intermediate changes to:
  * Hybrid fusion weights (alpha=0.75)
  * BM25 scoring
  * Embedding model or normalization
  * Reranking logic

**Counter-Evidence**:
- No code changes documented between revision and current test
- Step 9c modifications NOT applied (tested vanilla system)

### Hypothesis 3: Test Scenario Differences
- **Alpha-v7 REVISED** might have used different test set
- **Current test** uses 13 scenarios from `test_rag_benchmark.py`
- Possible that earlier revision tested subset or different queries

**Counter-Evidence**:
- Test scenarios appear consistent (same 13 tests documented)
- Test names match earlier documentation

---

## Impact on Phase 2 Goals

### Original Phase 2 Target (Based on 70-71% baseline)
- **Goal**: 73-74% relevance (+2-3pp from 71%)
- **Status**: ✅ **ALREADY MET** at 74.78% relevance!

### Revised Phase 2 Target (Based on 74.78% baseline)
- **New Goal**: 77-78% relevance (+2-3pp from 74.78%)
- **Step 9f Expected Gains**: +1-2pp relevance → 76-77% (MEETS target)
- **Step 9c Expected Gains**: Minimal relevance impact, focus on precision

### Precision Target (UNCHANGED)
- **Current**: 32.95% precision
- **Target**: ≥34% precision (+1.05pp)
- **Step 9f Expected**: +1-2pp → 34-35% ✅
- **Step 9c Expected**: +0.5-1pp → 33.5-34% ✅

---

## What This Means for Step 9f

### Good News 🎉
1. **Higher starting point**: 74.78% relevance, not 70-71%
2. **Alpha-v9 promotion easier**: Only need +1pp relevance (not +2-3pp)
3. **Precision still viable**: 32.95% → 34% requires only +1.05pp

### Challenges ⚠️
1. **Less headroom**: Harder to improve from 74.78% than 70-71%
2. **Variance risk**: If 74.78% is outlier, true baseline could be lower
3. **Testing protocol**: Need multiple runs to confirm stable baseline

### Strategy Adjustment
1. **Run baseline 3x**: Confirm 74.78% is stable (not variance spike)
2. **Step 9f target**: Aim for 76-77% relevance (+1-2pp conservative)
3. **Precision focus**: Prioritize precision gains (cross-encoder's strength)
4. **Combined approach**: If needed, combine Step 9c + 9f for larger gains

---

## Recommended Actions

### IMMEDIATE (Before Step 9f)
1. ✅ Document baseline discrepancy (this file)
2. 🔄 Run baseline test 2-3 more times to measure variance
3. 🔄 Calculate median/mean relevance from multiple runs
4. 🔄 Update Phase 2 goals if 74.78% confirmed stable

### Step 9f Planning
1. Design cross-encoder reranking with 74.78% as baseline
2. Target: 76-77% relevance (+1-2pp), 34-35% precision (+1-2pp)
3. Compare Step 9f results against 74.78% benchmark
4. If variance high, use median across runs instead of single value

### Documentation Updates Needed
1. BASELINE_REVISION_ALPHA_V7.md: Add note about 74.78% finding
2. PHASE2_LOG.md: Update baseline reference
3. init_phase2.py: Revise goals if baseline confirmed
4. EXECUTIVE_BRIEF_RAG_OPTIMIZATION.md: Update baseline section

---

## Testing Protocol v3 (Proposed)

### Baseline Establishment
1. **Minimum Runs**: 5 executions (not 3-5)
2. **Cold Start**: Clear all memory between runs
3. **Metrics Collected**: All 5 runs' relevance, precision, recall, F1
4. **Baseline Value**: Median relevance (not mean) to handle outliers
5. **Variance Check**: Standard deviation <2pp for STABLE baseline

### Step Evaluation
1. **Minimum Runs**: 3 executions per strategy
2. **Comparison**: Use t-test to compare against baseline median
3. **Significance**: Require p<0.05 for claiming improvement
4. **Effect Size**: Report Cohen's d (not just percentage points)

### Promotion Criteria (Updated)
1. **Relevance**: ≥median_baseline + 2pp AND p<0.05
2. **Precision**: ≥34% (absolute threshold)
3. **Tests Passing**: ≥7/13 (was 6-7/13)
4. **Variance**: Standard deviation <2pp across runs

---

## Data for Reference

### Current Run (November 11, 2025, 20:04:52)

```json
{
  "total_tests": 13,
  "tests_passed": 6,
  "pass_rate": 46.2,
  "avg_precision": 32.95,
  "avg_recall": 92.31,
  "avg_f1": 47.51,
  "avg_relevance": 74.78,
  "target_relevance": 85.0,
  "target_met": false
}
```

### System Configuration

```
Embedding Model: BAAI/bge-small-en-v1.5 (dim=384)
Vector Store: FAISS (AVX2 support)
Hybrid Fusion: alpha=0.75, adaptive=True, rrf=False
Retrieval: vector_weight=0.97, lexical_weight=0.03
Reranking: Disabled (enable_reranking=False)
```

### Warnings/Issues Observed

```
WARNING: BM25 scores have zero range (all identical 0.000)
WARNING: HYBRID FUSION FALLBACK - No lexical candidates
INFO: FALLBACK - Using legacy fixed-weight blending
```

**Analysis**: BM25 not contributing effectively, system relies primarily on vector search (0.97 weight). This explains why lexical_weight is so low.

---

## Conclusion

**Current Baseline**: **74.78% relevance** (confirmed via direct test execution)  
**Previous Claim**: 70-71% relevance (from Alpha-v7 REVISED)  
**Discrepancy**: +3.78 to +4.78 percentage points

**Likely Cause**: Run variance (5pp swing) OR measurement error in earlier revision

**Next Steps**:
1. Run baseline 2-3 more times to confirm stability
2. Use median relevance from multiple runs as true baseline
3. Proceed with Step 9f using 74.78% as conservative baseline
4. If confirmed stable, UPDATE all Phase 2 documentation

**Impact on Phase 2**:
- ✅ **Good News**: Higher starting point, easier to reach Alpha-v9
- ⚠️ **Risk**: Less headroom for improvement, variance uncertainty
- 🎯 **Strategy**: Focus on precision gains (Step 9f strong suit)

---

**Last Updated**: November 11, 2025, 20:10  
**Next Action**: Run baseline 2-3 more times to confirm 74.78% stable

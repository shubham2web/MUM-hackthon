# Phase 2 Transition: Step 9a → Step 9e
**RAG Optimization Strategic Pivot**

**Date**: November 11, 2025  
**Current State**: Alpha-v7 baseline (74.78% relevance, 32.95% precision, 92.31% recall)  
**Next Priority**: Step 9e - Adaptive Thresholding

---

## 🔄 Why the Pivot?

**Step 9a Key Finding**: Embedding upgrades degrade performance (-3.31pp to -4.53pp relevance)

**Implication**: Precision bottleneck (32.95%) is **retrieval-strategy-limited**, not embedding-limited.

**Strategic Response**: Skip embedding optimization path, focus on retrieval architecture improvements.

---

## 🎯 Step 9e Overview

### Goal
Dynamically adjust similarity thresholds to cut low-confidence retrievals without recall collapse.

### Current Problem
Fixed threshold (0.75) treats all queries equally:
- Simple queries (exact match) → need high threshold
- Complex queries (semantic search) → need lower threshold
- Result: Suboptimal precision for both query types

### Solution
**Adaptive threshold** based on:
1. **Percentile cutoffs**: Reject bottom N% of results dynamically
2. **Query variance**: High variance → aggressive threshold, low variance → relaxed threshold
3. **Semantic confidence**: Score distribution identifies natural cutoff points

---

## 📊 Expected Outcomes

### Sub-step Breakdown

| Sub-step | Strategy | Expected Gain | Duration | Promotion Target |
|----------|----------|---------------|----------|------------------|
| **9e-1** | Percentile sweep (60-90%) | +0.5-1pp | 30 min | Test if sufficient |
| **9e-2** | Dynamic variance cutoff | +0.5-1.5pp | 1 hour | Alpha-v9 candidate |
| **9e-3** | Semantic weighting combo | +1-2pp | 1 hour | Alpha-v10 target |

### Success Criteria (Alpha-v9)

- ✅ **Precision**: ≥34% (+1pp minimum)
- ✅ **Relevance**: ≥76% (+1.2pp minimum)
- ✅ **Recall**: ≥90% (maintain)
- ✅ **Tests**: 7+/13 passing

---

## 🚀 Immediate Actions

### 1. Execute Step 9e-1 (Percentile Sweep)

**Command**:
```bash
cd backend
python phase2/step9e_adaptive_threshold_tests.py
```

**What It Does**:
- Tests 7 percentile thresholds: 60%, 65%, 70%, 75%, 80%, 85%, 90%
- Measures precision/recall tradeoff at each level
- Identifies optimal percentile for promotion

**Expected Runtime**: ~7 minutes (7 thresholds × ~1 min each)

**Output**: `phase2/step9e_results_percentile.json`

---

### 2. Analyze Results

**Key Metrics to Check**:
- Precision gain vs baseline (32.95%)
- Relevance maintenance (≥74.5%)
- Recall preservation (≥90%)

**Decision Tree**:
- If +1pp precision achieved → Promote to alpha-v9 ✅
- If +0.5pp precision achieved → Proceed to 9e-2 for boost 🚧
- If no gain → Pivot to Step 9d (query expansion) 🔄

---

### 3. Update Documentation

**Files to Update**:
- `RAG_OPTIMIZATION_PHASE2_LOG.md` - Step 9e results
- `phase2/STEP9E_EXECUTIVE_SUMMARY.md` - Create summary (if successful)

---

## 📈 Phase 2 Revised Timeline

| Milestone | Target | Timeline |
|-----------|--------|----------|
| ✅ Step 9a Complete | Baseline retained | 2025-11-11 ✅ |
| 🚧 Step 9e-1 Execute | Percentile sweep | ~30 minutes |
| ⏳ Step 9e Analysis | Promote to alpha-v9? | +15 minutes |
| ⏳ Step 9d Planning | Query expansion | If 9e successful |
| ⏳ Phase 2 Complete | 37-38% precision | 1-2 weeks |

---

## 🧠 Strategic Context

### Phase 2 Mission (Updated)

**Original Plan**: Steps 9a → 9b → 9c → 9d → 9e → 9f  
**Revised Plan**: Steps 9a (negative) → 9b (done) → **9e (now critical)** → 9d → 9c → 9f

**Rationale**:
- 9a proved embeddings not the bottleneck
- 9e is fastest path to precision boost
- 9d/9c are higher effort, saved for after quick win
- 9f depends on 9e results (threshold affects reranking)

### Gap to 90% Goal

**Current**: 74.78% relevance (gap: 15.22pp)  
**Phase 2 Target**: 77-80% relevance (gap: 10-13pp)  
**Remaining**: Phase 3 needed for final push to 90%

---

## ✅ Ready State Checklist

- ✅ Step 9a complete and documented
- ✅ Baseline retained (bge-small-en-v1.5)
- ✅ Step 9e test framework created (`step9e_adaptive_threshold_tests.py`)
- ✅ Success criteria defined (≥34% precision, ≥76% relevance)
- ✅ Phase 2 log updated with 9a findings
- ✅ Executive summary created (STEP9A_EXECUTIVE_SUMMARY.md)
- ⏳ Ready to execute Step 9e-1

---

**Next Command**: `python phase2/step9e_adaptive_threshold_tests.py`  
**Expected Duration**: ~30 minutes  
**Promotion Target**: Alpha-v9 (if +1pp precision achieved)

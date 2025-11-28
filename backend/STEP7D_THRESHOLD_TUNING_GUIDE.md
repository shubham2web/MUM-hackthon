# Step 7d: Threshold Tuning - Quick Reference

## Goal
Improve precision from 32.95% by optimizing similarity threshold and top-k parameters without hurting recall (92.31%) or relevance (74.30%).

## Current Baseline (alpha-v5)
- Alpha: 0.97 (97% semantic, 3% lexical)
- Relevance: 74.30%
- Precision: 32.95% (LOW - needs improvement)
- Recall: 92.31% (HIGH - maintain this)
- F1 Score: 47.51%
- Top-K: 4-5 results
- Threshold: 0.50 (current default)

## Strategy

### Phase 1: Similarity Threshold Sweep
Test similarity cutoffs: [0.65, 0.70, 0.75, 0.80, 0.85]
- Fixed top_k = 5
- Find threshold that maximizes precision without killing recall

### Phase 2: Top-K Sweep  
Test result counts: [3, 5, 10]
- Use best threshold from Phase 1
- Find optimal number of results to return

### Phase 3: Combined Optimization
- Apply best threshold × top_k combination
- Verify improvement in F1 score
- Save as alpha-v6 if successful

## Expected Outcomes

| Sub-Step | Expected Gain | Risk |
|----------|---------------|------|
| Threshold sweep | +0.5-1.0pp precision | May reduce recall slightly |
| Top-K tuning | +0.3-0.7pp precision | Low risk |
| Combined | +1.0-2.0pp precision | Low to medium |

## Commands

```bash
# Run Step 7d threshold tuning
cd backend
python tests/step7d_threshold_tuning.py

# Results will be saved to:
# logs/threshold_tuning_phase1_threshold_*.json/csv
# logs/threshold_tuning_phase2_topk_*.json/csv
```

## Implementation Details

### Environment Variables Added
- `SIMILARITY_THRESHOLD`: Override default threshold (0.50)
- `TOP_K`: Override default top-k (4)
- `HYBRID_VECTOR_WEIGHT`: Maintained at 0.97 (alpha-v5)

### Code Changes
- `vector_store.py` line ~805: Added env var support for threshold tuning
- `step7d_threshold_tuning.py`: New automated sweep tool

## Success Criteria

✅ Precision improvement: ≥ +1.0pp (target: 33.95%+)
✅ Recall maintained: ≥ 90.0% (currently 92.31%)
✅ Relevance stable: ≥ 74.0% (currently 74.30%)
✅ F1 Score improved: > 47.51%
✅ Tests passed: ≥ 6/13 (maintain or improve)

## Promotion Criteria for alpha-v6

If improvements meet criteria:
1. Update vector_store.py with optimal threshold + top_k
2. Run verification benchmark
3. Save as alpha-v6 with version control
4. Document in RAG_OPTIMIZATION_LOG.md

## Fallback Plan

If no improvement found:
- Document findings (threshold/top-k insensitive)
- Proceed to Step 7e (Query Preprocessing)
- OR Step 7c (Ultra-alpha sweep 0.98-0.99)

## Timeline
- Phase 1: ~15 minutes (5 thresholds × ~3 min each)
- Phase 2: ~10 minutes (3 top-k values × ~3 min each)
- Total: ~25-30 minutes

---

**Status**: Ready to execute
**Prerequisites**: alpha-v5 applied (α=0.97)
**Next**: Run `python tests/step7d_threshold_tuning.py`

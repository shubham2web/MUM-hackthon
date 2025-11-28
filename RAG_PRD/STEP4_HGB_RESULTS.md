## Step 4: HGB Soft Bias Experiment - RESULTS

### Configuration
- **Model**: ltr_reranker_gb.joblib (HistGradientBoostingClassifier, 79.7% ROC-AUC)
- **Weight**: 0.3 (30% HGB, 70% hybrid)
- **Formula**: `final_score = 0.7 * hybrid_score_norm + 0.3 * hgb_score_norm`
- **Normalization**: Min-max scaling for both signals
- **Feature Compatibility**: Truncated 11 features → 10 features (model trained before hybrid_score added)

### Results

| Metric | Baseline (α=0.85) | With HGB (w=0.3) | Delta |
|--------|-------------------|------------------|-------|
| **Relevance** | 72.95% | 70.29% | **-2.66%** ❌ |
| **Tests Passed** | 5/13 | 6/13 | +1 test |
| **Precision** | 32.95% | 32.95% | 0.00% |
| **Recall** | 92.31% | 92.31% | 0.00% |
| **F1 Score** | 47.51% | 47.51% | 0.00% |

### Analysis

**HGB HURT Performance (-2.66%)**

1. **Relevance dropped** from 72.95% to 70.29%
2. Tests passed increased 5→6 (minor improvement in pass rate)
3. Precision/Recall/F1 unchanged (reranking didn't affect these metrics significantly)

### Root Causes

1. **Model trained on insufficient data** (57 samples for 10 features = ~5.7 samples/feature)
   - Industry best practice: 10-20 samples per feature
   - With 10 features, need 100-200 training samples minimum

2. **Feature mismatch during training**
   - Model trained with 10 features
   - Current code has 11 features (hybrid_score added later)
   - Had to truncate features for compatibility

3. **HGB predictions may not align with test scenarios**
   - Model trained on one set of examples
   - Test benchmark has different patterns (role reversal, topic switching)
   - Generalization failed

4. **Conservative weight (0.3) not enough to overcome noise**
   - If HGB predictions are random/poor, even 30% weight degrades performance
   - 70% hybrid can't fully compensate for 30% bad signal

### Recommendation

❌ **REJECT Step 4 (HGB Soft Bias)**
- HGB model hurts performance (-2.66%)
- Revert to baseline: alpha=0.85 only (72.95%)

✅ **Proceed to Step 5 (Grid Search)** with HGB disabled
- Test alpha ∈ [0.80, 0.85, 0.90]
- No metadata boost (not in test data)
- No HGB bias (hurts performance)
- Focus on pure semantic/lexical fusion optimization

### Future Path to LTR Success

To make LTR work in future:

1. **Collect 200+ labeled pairs** from failed test cases
2. **Retrain with proper train/val/test split** (60/20/20)
3. **Feature selection** - remove low-importance features
4. **Cross-validation** to ensure generalization
5. **Start with logistic regression** (simpler, less prone to overfitting)
6. **Gradual weight increase** from 0.1 → 0.2 → 0.3 with validation at each step

### Version Control

- Baseline (alpha-v2): 72.95% relevance ✅ **KEEP THIS**
- HGB (hgb-v3): 70.29% relevance ❌ **REVERT/DISABLE**

### Next Action

Disable HGB reranking in vector_store.py:
```python
enable_reranking: bool = False  # Step 4: HGB hurt performance (-2.66%)
```

Proceed to Step 5: Grid search on alpha only

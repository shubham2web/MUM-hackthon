# RAG Optimization Quick Reference

## 🎯 Current Status
- **Version**: alpha-v3
- **Relevance**: 73.51% (+1.73pp from baseline)
- **Alpha**: 0.90 (90% semantic, 10% lexical)
- **Tests Passed**: 5/13
- **Status**: Stable, ready for next optimization

---

## ⚡ Quick Commands

### Run Optimizations

```bash
# Step 7a: Higher-alpha micro-sweep (15-20 min)
python tests/step7a_higher_alpha_sweep.py

# Step 7b: Grid search (20-30 min)
python tests/step7b_grid_search.py

# Run standard benchmark
python tests/run_rag_benchmark.py
```

### Version Control

```bash
# List all versions
python rag_version_control.py list [--verbose]

# Save new version
python rag_version_control.py save \
  --version alpha-v4 \
  --relevance 74.2 \
  --alpha 0.95 \
  --notes "Description"

# Rollback (dry-run first!)
python rag_version_control.py rollback --version alpha-v3 --dry-run
python rag_version_control.py rollback --version alpha-v3

# Compare versions
python rag_version_control.py compare --version alpha-v3 --version2 alpha-v4

# Promote to stable
python rag_version_control.py promote --version alpha-v4 --tags stable production

# Export history
python rag_version_control.py export
```

---

## 📊 Version History

| Version | Relevance | Alpha | Status | Notes |
|---------|-----------|-------|--------|-------|
| baseline-v1 | 71.78% | 0.75 | Baseline | Step 1 |
| alpha-v2 | 72.95% | 0.85 | Stable | Step 2 (+1.17%) |
| hgb-v3 | 70.29% | 0.85 | ❌ Rejected | Step 4 (-2.66%) |
| **alpha-v3** | **73.51%** | **0.90** | **✅ Current** | **Step 5 (+0.56%)** |

---

## 🚀 Next Steps (Priority Order)

1. **Step 7a**: Higher-alpha micro-sweep → Expected: +0.2-0.5%
2. **Step 7b**: Grid search validation → Expected: Confirm optimum
3. **Step 7c**: Threshold tuning → Expected: +0.5-1%
4. **Step 7d**: Query preprocessing → Expected: +0.5-1%
5. **Step 7e**: Embedding upgrade → Expected: +1-3%

---

## 📈 Progress to Goal

```
Current:  73.51% ████████████████░░░░░░░░░░░░░░░░ (73.5%)
Goal:     90.00% ████████████████████████████████ (100%)
Gap:      16.49pp
Progress: 9.5% of gap closed
```

---

## 📂 Key Files

### Documentation
- `RAG_OPTIMIZATION_LOG.md` - Complete history
- `RAG_OPTIMIZATION_COMPLETE_SUMMARY.md` - Steps 1-6 summary
- `STEP7_ADVANCED_OPTIMIZATION_PLAYBOOK.md` - Next steps guide

### Tools
- `tests/step7a_higher_alpha_sweep.py` - Priority 1 optimization
- `tests/step7b_grid_search.py` - Grid search
- `rag_version_control.py` - Version management

### Data
- `rag_versions.json` - Version metadata
- `rag_optimization_history.csv` - Exportable history
- `backups/rag_versions/` - Config snapshots

---

## 🔧 Configuration

Current `vector_store.py` settings:
```python
enable_reranking = False           # HGB disabled (Step 4 failed)
enable_hybrid_bm25 = True          # Hybrid fusion active
hybrid_vector_weight = 0.90        # 90% semantic, 10% lexical (Step 5)
```

---

## 🎓 Lessons Learned

1. ✅ **Systematic optimization works** - +1.73pp through discipline
2. ✅ **Always measure** - Caught HGB regression immediately
3. ✅ **Quick rollback** - Version control prevents damage
4. ✅ **Document failures** - HGB failure informs future LTR
5. ✅ **Fine-tuning pays off** - Small alpha changes yield gains
6. ✅ **Monotonic trends** - α sweep showed no plateau at 0.90

---

## 🚨 Troubleshooting

### Benchmark fails
```bash
# Check Python environment
python --version  # Should be 3.13

# Verify dependencies
pip install -r requirements.txt

# Run with verbose output
python tests/run_rag_benchmark.py --verbose
```

### Version control issues
```bash
# Check current version
python rag_version_control.py list

# Verify backups exist
ls backups/rag_versions/

# Dry-run rollback first
python rag_version_control.py rollback --version alpha-v3 --dry-run
```

### Performance regression
```bash
# Compare with baseline
python rag_version_control.py compare --version baseline-v1 --version2 alpha-v3

# Rollback if needed
python rag_version_control.py rollback --version alpha-v3

# Verify restoration
python tests/run_rag_benchmark.py
```

---

## 📞 Support

See detailed documentation in:
- `RAG_OPTIMIZATION_LOG.md` - Full optimization history
- `STEP6_VERSION_CONTROL_SYSTEM.md` - Version control guide
- `STEP7_ADVANCED_OPTIMIZATION_PLAYBOOK.md` - Advanced techniques

---

**Last Updated**: 2025-11-11  
**Current Version**: alpha-v3 (73.51% relevance)  
**Status**: ✅ Ready for Step 7a

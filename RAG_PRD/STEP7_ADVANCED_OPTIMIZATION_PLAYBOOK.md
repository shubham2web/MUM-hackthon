# Step 7: Advanced Optimization Playbook

**Date**: 2025-11-11  
**Status**: 🚀 READY TO EXECUTE  
**Current Performance**: 73.51% relevance (alpha-v3)  
**Goal**: Reach 75-80% through systematic advanced optimizations

---

## 📋 Priority Next Steps

Based on monotonic improvement trend and systematic optimization success, here's the recommended execution order:

### Priority 1: Higher-Alpha Micro-Sweep ⚡ (FASTEST ROI)
**Estimated Effort**: 15-20 minutes  
**Expected Gain**: +0.2-0.5%  
**Risk**: Very Low  

**Rationale**: Step 5 showed monotonic improvement through α=0.90. No plateau observed, suggesting potential gains at 0.92-0.95.

**Tool**: `tests/step7a_higher_alpha_sweep.py`

**Command**:
```bash
cd backend
python tests/step7a_higher_alpha_sweep.py
```

**What it tests**: α ∈ [0.90, 0.91, 0.92, 0.93, 0.94, 0.95]

**Expected outcome**:
- If trend continues: α=0.95 reaches 73.8-74.0% (+0.3-0.5%)
- If plateau found: Identifies peak semantic weight
- If regression: Confirms α=0.90 is optimal

**Success criteria**: 
- Relevance improvement ≥+0.2%
- No test regression
- Clear monotonic trend or plateau identification

**Next action if successful**:
```bash
# Save best version
python rag_version_control.py save \
  --version alpha-v4 \
  --relevance 74.0 \
  --alpha 0.95 \
  --notes "Step 7a: Higher-alpha micro-sweep"

# Promote if criteria met
python rag_version_control.py promote --version alpha-v4 --tags stable
```

---

### Priority 2: Alpha × Lexical Grid Search 🔍 (COMPREHENSIVE)
**Estimated Effort**: 20-30 minutes  
**Expected Gain**: Validates optimal balance  
**Risk**: Very Low  

**Rationale**: Systematically explore semantic/lexical tradeoff space around current optimum.

**Tool**: `tests/step7b_grid_search.py`

**Command**:
```bash
cd backend
python tests/step7b_grid_search.py
```

**What it tests**: α ∈ [0.90, 0.92, 0.95] (complementary lexical weights)

**Expected outcome**:
- Confirms optimal semantic/lexical balance
- Identifies any non-linear interactions
- Provides data for decision-making

**Success criteria**:
- Clear optimal point identified
- Results consistent with Step 7a
- No unexpected regressions

---

### Priority 3: Threshold Tuning 🎯 (PRECISION BOOST)
**Estimated Effort**: 1-2 hours  
**Expected Gain**: +0.5-1% relevance, improved precision  
**Risk**: Low  

**Rationale**: Current system uses default thresholds. Tuning can improve precision without hurting recall.

**Approach**:
1. **Adaptive Score Threshold**: Find optimal cutoff for final scores
2. **Top-k Optimization**: Test k ∈ [3, 5, 10, 15, 20]
3. **Query-Length Policies**: Short queries use lower k, long queries use higher k

**Implementation Plan**:
```python
# tests/step7c_threshold_tuning.py
thresholds = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
top_k_values = [3, 5, 10, 15, 20]

for thresh in thresholds:
    for k in top_k_values:
        # Test combination
        # Track precision, recall, F1, relevance
```

**Metrics to track**:
- Precision (target: improve from 32.95%)
- Recall (maintain: 92.31%)
- F1 Score (target: improve from 47.51%)
- Relevance (target: maintain or improve 73.51%+)
- Tests passed (target: improve from 5/13)

**Success criteria**:
- Precision improvement ≥5pp (32.95% → 38%+)
- Recall maintained ≥90%
- Tests passed ≥6/13

---

### Priority 4: Query Preprocessing 🔧 (QUALITY BOOST)
**Estimated Effort**: 2-3 hours  
**Expected Gain**: +0.5-1%  
**Risk**: Medium (may help some queries, hurt others)  

**Techniques to test**:

1. **Stopword Removal** (aggressive)
   - Remove common words that add noise
   - Test on benchmark queries
   - Expected: +0.2-0.4% if queries verbose

2. **Lemmatization**
   - Normalize word forms (running → run)
   - Use spaCy or NLTK
   - Expected: +0.3-0.5% for morphological matching

3. **Query Expansion**
   - Synonym expansion from domain vocabulary
   - FAQ-based expansion
   - Expected: +0.5-1% if vocabulary mismatch exists

4. **Short-Query Boosting**
   - Special handling for queries <5 words
   - Increase lexical weight for short queries
   - Expected: +0.2-0.4% for terse queries

**Implementation approach**:
```python
# Query preprocessing pipeline
def preprocess_query(query: str, config: dict) -> str:
    # 1. Normalize case
    if config.get('normalize_case'):
        query = query.lower()
    
    # 2. Remove stopwords
    if config.get('remove_stopwords'):
        query = remove_stopwords(query)
    
    # 3. Lemmatize
    if config.get('lemmatize'):
        query = lemmatize(query)
    
    # 4. Expand synonyms
    if config.get('expand_synonyms'):
        query = expand_synonyms(query)
    
    return query
```

**A/B testing required**: Run baseline vs each technique independently to measure impact

---

### Priority 5: Embedding Model Upgrade 🚀 (LARGEST POTENTIAL)
**Estimated Effort**: 4-8 hours  
**Expected Gain**: +1-3%  
**Risk**: High (cost, latency, compatibility)  

**Current**: BGE-small-en-v1.5 (384-dim, fast, lightweight)

**Candidates**:

| Model | Dimensions | Size | Speed | Quality | Expected Gain |
|-------|------------|------|-------|---------|---------------|
| BGE-base-en-v1.5 | 768 | ~220MB | 2-3x slower | Higher | +1-1.5% |
| BGE-large-en-v1.5 | 1024 | ~1.2GB | 4-5x slower | Highest | +2-3% |
| BGE-M3 (multilingual) | 1024 | ~2.3GB | 5-6x slower | Very High | +1.5-2.5% |

**Evaluation Plan**:

1. **Create Validation Set** (200 queries)
   ```python
   # Sample 200 queries from benchmark + failed cases
   validation_queries = sample_benchmark_queries(n=200)
   ```

2. **Compute Embeddings** (baseline vs candidate)
   ```python
   baseline_embeddings = compute_embeddings(queries, model='BGE-small')
   candidate_embeddings = compute_embeddings(queries, model='BGE-base')
   ```

3. **Measure Overlap**
   ```python
   # Nearest-neighbor overlap
   overlap = compute_nn_overlap(baseline_embeddings, candidate_embeddings, k=10)
   # Expected: 70-80% overlap for BGE-base, 60-70% for BGE-large
   ```

4. **Run Benchmark**
   ```python
   # Full retrieval benchmark on validation set
   baseline_results = run_benchmark(model='BGE-small')
   candidate_results = run_benchmark(model='BGE-base')
   ```

5. **Measure Metrics**
   - Relevance improvement
   - Latency impact (target: <2x slowdown)
   - Memory usage (target: <2GB)
   - Cost (compute resources)

**Decision criteria**:
- Relevance improvement ≥+1%
- Latency increase ≤3x
- Memory increase acceptable (<4GB total)
- Cost justified by improvement

**Rollout plan** if approved:
1. Re-embed entire corpus with new model
2. Rebuild FAISS index
3. Update embedding service configuration
4. Run full benchmark suite
5. A/B test in production (if applicable)
6. Save as new version (e.g., `bge-base-v1`)

---

## 🔄 A/B Testing & Monitoring

### Promotion to Stable

**Current**: alpha-v3 (73.51%) is development version

**Promotion checklist**:
```bash
# 1. Tag as stable
python rag_version_control.py promote \
  --version alpha-v3 \
  --tags stable production recommended

# 2. Git tag
git add .
git commit -m "feat: Promote alpha-v3 to stable (73.51% relevance)"
git tag -a stable-v1.0 -m "Stable release: 73.51% relevance"
git push origin main --tags
```

### Continuous Monitoring

**Metrics to track**:
- Relevance score (per-query and aggregate)
- Tests passed rate
- Precision / Recall / F1
- Query latency (p50, p95, p99)
- Memory usage
- Error rate

**Alert thresholds**:
| Metric | Threshold | Action |
|--------|-----------|--------|
| Relevance drop | >0.5pp | Alert + investigate |
| Relevance drop | >1pp | Auto-rollback to previous version |
| Tests passed drop | ≥2 tests | Alert + investigate |
| Latency p95 | >2x baseline | Alert + capacity check |
| Error rate | >1% | Alert + debug |

**Implementation**:
```python
# Simple monitoring script
def check_metrics():
    current = run_benchmark()
    baseline = load_baseline('alpha-v3')
    
    if current['relevance'] < baseline['relevance'] - 0.5:
        alert("Relevance drop detected")
        if current['relevance'] < baseline['relevance'] - 1.0:
            auto_rollback('alpha-v3')
```

---

## 🛠️ CI/CD Integration

### Pre-Merge Smoke Test

Add to `.github/workflows/rag-test.yml`:

```yaml
name: RAG Smoke Test

on: [pull_request]

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run benchmark subset
        run: |
          cd backend
          python tests/run_rag_benchmark.py --quick
      
      - name: Check regression
        run: |
          cd backend
          python tests/check_regression.py \
            --baseline 73.51 \
            --threshold 0.3
        # Fails build if relevance drops >0.3pp
```

### Auto-Rollback on Regression

```python
# tests/check_regression.py
import sys
import json

baseline = 73.51  # From alpha-v3
threshold = 0.3   # Alert if drop >0.3pp

results = json.load(open('benchmark_results.json'))
current_relevance = results['relevance']

if current_relevance < baseline - threshold:
    print(f"❌ REGRESSION DETECTED: {current_relevance:.2f}% < {baseline:.2f}% - {threshold:.2f}pp")
    print("Rolling back to alpha-v3...")
    sys.exit(1)
else:
    print(f"✅ PASS: {current_relevance:.2f}% (baseline: {baseline:.2f}%)")
```

---

## 📊 Execution Timeline

### Week 1: Quick Wins
- ✅ Day 1: Higher-alpha micro-sweep (Step 7a)
- ✅ Day 1: Grid search validation (Step 7b)
- 🔄 Day 2-3: Threshold tuning (Step 7c)
- 📊 Day 4: Analyze results, save best version

**Expected outcome**: 74-74.5% relevance

### Week 2: Quality Improvements
- 🔧 Day 1-2: Query preprocessing experiments
- 🧪 Day 3-4: A/B testing of techniques
- 📊 Day 5: Integrate best techniques

**Expected outcome**: 74.5-75% relevance

### Week 3: Major Upgrade
- 🚀 Day 1-2: Embedding model evaluation (validation set)
- 🔬 Day 3-4: Re-embedding + benchmarking
- 🎯 Day 5: Decision + rollout (if approved)

**Expected outcome**: 75-77% relevance (if BGE-base deployed)

### Week 4: Stabilization
- 🔍 Day 1-2: Full regression testing
- 📈 Day 3-4: A/B testing in production
- ✅ Day 5: Promotion to stable

**Expected outcome**: Stable 75%+ system

---

## 🎯 Success Metrics

### Short-Term Goals (Week 1-2)
- [ ] Relevance: 74-75% (+0.5-1.5% from 73.51%)
- [ ] Tests passed: 6-7/13 (+1-2 tests)
- [ ] Precision: 35-40% (+2-7pp from 32.95%)
- [ ] Version control: All experiments saved and documented

### Medium-Term Goals (Week 3-4)
- [ ] Relevance: 75-77% (+1.5-3.5% from 73.51%)
- [ ] Tests passed: 7-9/13 (+2-4 tests)
- [ ] Precision: 40-45% (+7-12pp from 32.95%)
- [ ] CI/CD: Automated regression testing
- [ ] Monitoring: Continuous metrics tracking

### Long-Term Goals (Month 2-3)
- [ ] Relevance: 80%+ (approaching 90% target)
- [ ] Tests passed: 10+/13 (77%+ pass rate)
- [ ] Precision: 50%+ (balanced with recall)
- [ ] Production deployment with A/B testing

---

## 📚 Tools Summary

| Tool | Purpose | Runtime | Output |
|------|---------|---------|--------|
| `step7a_higher_alpha_sweep.py` | Test α=[0.90-0.95] | 15-20min | CSV + JSON |
| `step7b_grid_search.py` | Grid search validation | 20-30min | CSV + JSON |
| `step7c_threshold_tuning.py` | Optimize thresholds | 1-2hr | CSV + JSON |
| `step7d_query_preprocessing.py` | Test preprocessing | 2-3hr | CSV + JSON |
| `step7e_embedding_eval.py` | Evaluate new embeddings | 4-8hr | Report + metrics |
| `rag_version_control.py` | Version management | Instant | Version saved |
| `check_regression.py` | CI/CD smoke test | 2-5min | Pass/Fail |

---

## 🚀 Quick Start

**Run Priority 1 now** (15 minutes):

```bash
# Navigate to backend
cd c:\Users\sunanda.AMFIIND\Documents\GitHub\MUM-hackthon\backend

# Run higher-alpha micro-sweep
python tests/step7a_higher_alpha_sweep.py

# Review results in logs/alpha_micro_sweep_*.{csv,json}

# If improvement found, save version
python rag_version_control.py save \
  --version alpha-v4 \
  --relevance <NEW_RELEVANCE> \
  --alpha <BEST_ALPHA> \
  --notes "Step 7a: Higher-alpha micro-sweep" \
  --tags experimental step-7a

# Promote if criteria met
python rag_version_control.py promote --version alpha-v4
```

---

**Status**: 🚀 READY FOR STEP 7a  
**Next Action**: Run `python tests/step7a_higher_alpha_sweep.py`  
**Expected Duration**: 15-20 minutes  
**Expected Outcome**: +0.2-0.5% relevance improvement

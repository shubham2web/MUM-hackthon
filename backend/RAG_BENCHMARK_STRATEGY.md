# 🎯 RAG Retrieval Benchmark Strategy

## Objective
Validate that ZONE 2 (RAG long-term memory) retrieves relevant context with **>85% relevance score** across various scenarios.

---

## 📊 Benchmark Design

### 1. **Ground Truth Dataset Construction**

Create controlled test scenarios where we **know** what should be retrieved:

#### Scenario A: Debate Cross-Reference
```python
# Turn 1: Proponent makes specific claim
"Nuclear energy produces 50% less CO2 than coal according to IPCC 2021"

# Turn 5: Opponent should retrieve this
Query: "What did proponent say about CO2 emissions?"
Expected: Turn 1 statement (relevance = 1.0)

# Turn 8: Moderator synthesis
Query: "Previous environmental impact arguments"
Expected: Turns 1, 3, 5 (all environment-related)
```

#### Scenario B: Multi-Turn Chat Context
```python
# Message 1: User asks about quantum computing
"Explain quantum superposition"

# Message 2: AI responds with detailed explanation
"Quantum superposition allows qubits to exist in multiple states..."

# Message 5: Follow-up question
Query: "How does this relate to what you said about superposition?"
Expected: Message 2 (relevance = 1.0)
```

#### Scenario C: OCR Historical Context
```python
# Image 1: Screenshot of climate data
OCR: "Global temperature increase 1.5°C since 1850"

# Image 3: Related claim
Query: "What temperature data did we see earlier?"
Expected: Image 1 OCR text (relevance = 1.0)
```

---

### 2. **Relevance Scoring Methodology**

#### Manual Annotation (Gold Standard)
For each test query, human annotator labels retrieved memories:
- **2 points**: Perfectly relevant (contains answer)
- **1 point**: Partially relevant (related topic)
- **0 points**: Irrelevant (wrong topic)

#### Automated Metrics

**A. Semantic Similarity Score**
```python
# Use same embedding model as memory system
query_embedding = embedding_service.embed_text(query)
retrieved_embedding = embedding_service.embed_text(retrieved_memory)

similarity = cosine_similarity(query_embedding, retrieved_embedding)
# Threshold: similarity > 0.7 = relevant
```

**B. Keyword Overlap (Baseline)**
```python
query_keywords = set(extract_keywords(query))
memory_keywords = set(extract_keywords(retrieved_memory))

overlap = len(query_keywords & memory_keywords) / len(query_keywords)
# Threshold: overlap > 0.4 = relevant
```

**C. LLM-as-Judge (Advanced)**
```python
# Ask LLM to judge relevance
prompt = f"""
Query: {query}
Retrieved Memory: {retrieved_memory}

Is this memory relevant to answering the query?
Rate 0-10 where:
- 0-3: Irrelevant
- 4-6: Partially relevant
- 7-10: Highly relevant
"""
score = llm.generate(prompt) / 10
```

---

### 3. **Test Scenarios Matrix**

| Scenario | Query Type | Expected Behavior | Success Criteria |
|----------|-----------|-------------------|------------------|
| **Exact Recall** | "What did X say in turn Y?" | Retrieve exact turn | Top-1 accuracy = 100% |
| **Semantic Search** | "Arguments about safety" | Retrieve all safety-related turns | Recall > 90% |
| **Temporal Context** | "Recent arguments about..." | Retrieve last 3 relevant turns | Precision > 85% |
| **Cross-Role Search** | "Proponent's economic claims" | Filter by role + topic | Precision > 80% |
| **Negative Test** | "Arguments about blockchain" (not discussed) | No false positives | Precision = 100% |

---

### 4. **Benchmark Implementation Plan**

#### Phase 1: Create Test Harness

```python
# backend/tests/test_rag_benchmark.py

class RAGBenchmark:
    def __init__(self, memory_manager):
        self.memory = memory_manager
        self.test_cases = []
        
    def add_test_case(self, scenario_name, setup_memories, query, expected_memories, relevance_threshold=0.85):
        """
        Args:
            scenario_name: Human-readable test name
            setup_memories: List of (role, content, metadata) to store
            query: Search query string
            expected_memories: List of memory indices that should be retrieved
            relevance_threshold: Minimum relevance score
        """
        self.test_cases.append({
            "name": scenario_name,
            "setup": setup_memories,
            "query": query,
            "expected": expected_memories,
            "threshold": relevance_threshold
        })
    
    def run_benchmark(self):
        results = []
        
        for test_case in self.test_cases:
            # Setup: Store memories
            self.memory.clear()
            stored_ids = []
            for role, content, metadata in test_case["setup"]:
                stored_ids.append(
                    self.memory.add_interaction(role, content, metadata)
                )
            
            # Execute: Search
            retrieved = self.memory.search_memories(
                query=test_case["query"],
                top_k=5
            )
            
            # Evaluate: Calculate metrics
            metrics = self._evaluate_retrieval(
                retrieved=retrieved,
                expected_ids=[stored_ids[i] for i in test_case["expected"]],
                threshold=test_case["threshold"]
            )
            
            results.append({
                "test": test_case["name"],
                "metrics": metrics,
                "passed": metrics["relevance_score"] >= test_case["threshold"]
            })
        
        return self._generate_report(results)
    
    def _evaluate_retrieval(self, retrieved, expected_ids, threshold):
        """Calculate Precision, Recall, F1, and Relevance Score"""
        retrieved_ids = [r.id for r in retrieved]
        
        # Precision: How many retrieved are relevant?
        true_positives = len(set(retrieved_ids) & set(expected_ids))
        precision = true_positives / len(retrieved_ids) if retrieved_ids else 0
        
        # Recall: How many relevant were retrieved?
        recall = true_positives / len(expected_ids) if expected_ids else 0
        
        # F1 Score
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Relevance Score (semantic similarity)
        relevance_scores = [r.score for r in retrieved if r.id in expected_ids]
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "relevance_score": avg_relevance,
            "retrieved_count": len(retrieved_ids),
            "expected_count": len(expected_ids),
            "true_positives": true_positives
        }
    
    def _generate_report(self, results):
        """Generate comprehensive benchmark report"""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r["passed"])
        
        avg_precision = sum(r["metrics"]["precision"] for r in results) / total_tests
        avg_recall = sum(r["metrics"]["recall"] for r in results) / total_tests
        avg_f1 = sum(r["metrics"]["f1_score"] for r in results) / total_tests
        avg_relevance = sum(r["metrics"]["relevance_score"] for r in results) / total_tests
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "pass_rate": passed_tests / total_tests,
                "avg_precision": avg_precision,
                "avg_recall": avg_recall,
                "avg_f1": avg_f1,
                "avg_relevance_score": avg_relevance,
                "target_met": avg_relevance >= 0.85
            },
            "individual_results": results
        }
```

#### Phase 2: Define Test Cases

```python
# backend/tests/rag_test_scenarios.py

def create_debate_test_cases(benchmark):
    """Test cases for debate memory retrieval"""
    
    # Test 1: Exact turn recall
    benchmark.add_test_case(
        scenario_name="Exact Turn Recall",
        setup_memories=[
            ("moderator", "Welcome to the debate on nuclear energy safety.", {"turn": 0}),
            ("proponent", "Nuclear energy is the safest energy source with lowest death rate per TWh.", {"turn": 1}),
            ("opponent", "Nuclear waste remains dangerous for thousands of years.", {"turn": 2}),
            ("proponent", "Modern reactors have passive safety systems.", {"turn": 3}),
        ],
        query="What did the proponent say about safety in turn 1?",
        expected_memories=[1],  # Index of turn 1
        relevance_threshold=0.90
    )
    
    # Test 2: Semantic topic search
    benchmark.add_test_case(
        scenario_name="Topic-Based Retrieval",
        setup_memories=[
            ("proponent", "Nuclear provides 24/7 baseload power unlike solar.", {"turn": 1, "topic": "reliability"}),
            ("opponent", "Solar costs have dropped 90% in the last decade.", {"turn": 2, "topic": "economics"}),
            ("proponent", "France gets 70% of electricity from nuclear with low costs.", {"turn": 3, "topic": "economics"}),
            ("opponent", "Battery storage solves solar intermittency issues.", {"turn": 4, "topic": "reliability"}),
        ],
        query="Arguments about economic costs and affordability",
        expected_memories=[1, 2],  # Turns about economics
        relevance_threshold=0.85
    )
    
    # Test 3: Role-specific filtering
    benchmark.add_test_case(
        scenario_name="Role Filtering",
        setup_memories=[
            ("proponent", "Nuclear has the smallest carbon footprint.", {"turn": 1}),
            ("opponent", "Renewable energy is carbon-free.", {"turn": 2}),
            ("proponent", "Uranium mining has minimal environmental impact.", {"turn": 3}),
            ("opponent", "Wind and solar have no fuel extraction needed.", {"turn": 4}),
        ],
        query="What environmental arguments did the opponent make?",
        expected_memories=[1, 3],  # Opponent's turns
        relevance_threshold=0.85
    )
    
    # Test 4: Temporal recency
    benchmark.add_test_case(
        scenario_name="Recent Context Retrieval",
        setup_memories=[
            ("proponent", "Initial argument about safety.", {"turn": 1}),
            ("opponent", "Initial counter about waste.", {"turn": 2}),
            ("proponent", "Early rebuttal about containment.", {"turn": 3}),
            ("opponent", "Recent argument about Chernobyl.", {"turn": 8}),
            ("proponent", "Latest response about modern designs.", {"turn": 9}),
        ],
        query="Most recent arguments in the debate",
        expected_memories=[3, 4],  # Last 2 turns
        relevance_threshold=0.80
    )
    
    # Test 5: Negative case (no false positives)
    benchmark.add_test_case(
        scenario_name="Irrelevant Query Handling",
        setup_memories=[
            ("proponent", "Nuclear energy discussion.", {"turn": 1}),
            ("opponent", "Counter-argument on nuclear.", {"turn": 2}),
        ],
        query="What was said about cryptocurrency mining?",
        expected_memories=[],  # Should retrieve nothing
        relevance_threshold=0.85
    )

def create_chat_test_cases(benchmark):
    """Test cases for multi-turn chat retrieval"""
    
    # Test 6: Follow-up context
    benchmark.add_test_case(
        scenario_name="Multi-Turn Chat Context",
        setup_memories=[
            ("user", "What is quantum entanglement?", {"type": "question"}),
            ("assistant", "Quantum entanglement is when particles remain connected...", {"type": "answer"}),
            ("user", "Can you give an example?", {"type": "question"}),
            ("assistant", "Imagine two entangled photons...", {"type": "answer"}),
        ],
        query="What did you explain about entanglement earlier?",
        expected_memories=[1],  # First assistant response
        relevance_threshold=0.85
    )
    
    # Test 7: Multi-topic conversation
    benchmark.add_test_case(
        scenario_name="Topic Switching",
        setup_memories=[
            ("user", "Tell me about AI safety.", {"topic": "ai_safety"}),
            ("assistant", "AI safety focuses on alignment...", {"topic": "ai_safety"}),
            ("user", "What about climate change?", {"topic": "climate"}),
            ("assistant", "Climate change is caused by...", {"topic": "climate"}),
            ("user", "Back to AI - what are the risks?", {"topic": "ai_safety"}),
        ],
        query="Previous discussion about AI safety concerns",
        expected_memories=[1],  # First AI safety response
        relevance_threshold=0.85
    )

def create_ocr_test_cases(benchmark):
    """Test cases for OCR image analysis retrieval"""
    
    # Test 8: OCR historical reference
    benchmark.add_test_case(
        scenario_name="OCR Context Recall",
        setup_memories=[
            ("user", "OCR from image: 'COVID-19 vaccine contains microchips'", {"type": "ocr"}),
            ("assistant", "This is misinformation. No vaccines contain microchips.", {"type": "fact_check"}),
            ("user", "OCR from image: 'Vaccine side effects chart'", {"type": "ocr"}),
            ("assistant", "This chart shows normal immune responses...", {"type": "fact_check"}),
        ],
        query="What did we find about vaccine misinformation earlier?",
        expected_memories=[1],  # First fact-check
        relevance_threshold=0.85
    )
```

#### Phase 3: Run Benchmark Suite

```python
# backend/tests/run_rag_benchmark.py

import json
from memory.memory_manager import get_memory_manager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import (
    create_debate_test_cases,
    create_chat_test_cases,
    create_ocr_test_cases
)

def run_full_benchmark():
    """Execute complete RAG benchmark suite"""
    
    # Initialize
    memory = get_memory_manager()
    benchmark = RAGBenchmark(memory)
    
    # Add all test scenarios
    create_debate_test_cases(benchmark)
    create_chat_test_cases(benchmark)
    create_ocr_test_cases(benchmark)
    
    # Run benchmark
    print("🎯 Running RAG Retrieval Benchmark...")
    print(f"Total test cases: {len(benchmark.test_cases)}\n")
    
    results = benchmark.run_benchmark()
    
    # Display results
    print("=" * 60)
    print("📊 BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Tests Run: {results['summary']['total_tests']}")
    print(f"Tests Passed: {results['summary']['passed']}")
    print(f"Pass Rate: {results['summary']['pass_rate']:.1%}")
    print()
    print(f"Average Precision: {results['summary']['avg_precision']:.2%}")
    print(f"Average Recall: {results['summary']['avg_recall']:.2%}")
    print(f"Average F1 Score: {results['summary']['avg_f1']:.2%}")
    print(f"Average Relevance Score: {results['summary']['avg_relevance_score']:.2%}")
    print()
    print(f"🎯 Target (>85% relevance): {'✅ MET' if results['summary']['target_met'] else '❌ NOT MET'}")
    print("=" * 60)
    
    # Individual test results
    print("\n📋 Individual Test Results:")
    for result in results["individual_results"]:
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"\n{status} {result['test']}")
        print(f"  Precision: {result['metrics']['precision']:.2%}")
        print(f"  Recall: {result['metrics']['recall']:.2%}")
        print(f"  Relevance: {result['metrics']['relevance_score']:.2%}")
    
    # Save results to file
    with open("rag_benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n💾 Full results saved to: rag_benchmark_results.json")
    
    return results

if __name__ == "__main__":
    results = run_full_benchmark()
```

---

### 5. **Success Criteria & Thresholds**

#### Primary Metric: **Average Relevance Score**
- **Target**: ≥85%
- **Calculation**: Mean semantic similarity of retrieved memories to query
- **Why**: Directly measures if RAG is finding contextually relevant information

#### Secondary Metrics:

| Metric | Target | Importance |
|--------|--------|------------|
| **Precision** | ≥80% | Avoid noise (false positives) |
| **Recall** | ≥90% | Don't miss relevant memories |
| **F1 Score** | ≥85% | Balance of precision/recall |
| **Pass Rate** | 100% | All test cases meet thresholds |

#### Failure Analysis Triggers:
- Relevance < 70%: **Critical** - RAG is adding noise, not help
- Recall < 80%: **Major** - Missing important context
- False Positive Rate > 20%: **Major** - Confusing AI with irrelevant info

---

### 6. **Optimization Strategies (If Benchmark Fails)**

#### If Relevance Score < 85%:

**A. Tune Embedding Model**
```python
# Try different models
EMBEDDING_OPTIONS = [
    "sentence-transformers/all-MiniLM-L6-v2",  # Current (384 dim, fast)
    "sentence-transformers/all-mpnet-base-v2",  # Better quality (768 dim)
    "BAAI/bge-small-en-v1.5",  # Optimized for retrieval
]
```

**B. Adjust Search Parameters**
```python
# Increase top_k for better recall
top_k_rag = 5  # instead of 2-3

# Add metadata filtering
search_memories(query, top_k=5, filter_metadata={"role": "proponent"})
```

**C. Improve Query Expansion**
```python
# Before search, expand query with synonyms
query = "safety concerns"
expanded = "safety concerns risks dangers hazards nuclear reactor"
```

**D. Re-ranking Strategy**
```python
# Two-stage retrieval:
# 1. Broad search (top_k=10)
# 2. Re-rank with LLM relevance scoring
# 3. Return top-3 after re-ranking
```

#### If Precision Low (Too Many False Positives):

**E. Stricter Similarity Threshold**
```python
# Only retrieve if similarity > 0.75 (instead of 0.5)
MIN_SIMILARITY_THRESHOLD = 0.75
```

**F. Time-Decay Weighting**
```python
# Penalize very old memories
relevance_score = similarity * (1 - 0.1 * age_in_turns)
```

#### If Recall Low (Missing Relevant Memories):

**G. Hybrid Search**
```python
# Combine semantic search + keyword search
semantic_results = vector_store.search(query_embedding)
keyword_results = vector_store.keyword_search(query_terms)
merged = merge_and_deduplicate(semantic_results, keyword_results)
```

---

### 7. **Continuous Monitoring (Production)**

After benchmark passes, implement ongoing monitoring:

```python
# backend/memory/metrics_tracker.py

class RAGMetricsTracker:
    """Track RAG performance in production"""
    
    def log_retrieval(self, query, retrieved_memories, user_feedback=None):
        """
        Args:
            query: Search query
            retrieved_memories: List of RetrievalResult objects
            user_feedback: Optional user rating of relevance (1-5 stars)
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "retrieved_count": len(retrieved_memories),
            "avg_similarity": sum(m.score for m in retrieved_memories) / len(retrieved_memories),
            "user_feedback": user_feedback
        }
        
        # Store in metrics DB or log file
        self.metrics_db.append(metrics)
    
    def generate_weekly_report(self):
        """Aggregate metrics over time"""
        return {
            "avg_retrieval_count": ...,
            "avg_similarity": ...,
            "user_satisfaction": ...,
            "queries_with_no_results": ...
        }
```

---

## 🎯 Implementation Checklist

- [ ] **Week 1**: Implement RAGBenchmark test harness
- [ ] **Week 1**: Create 10+ test scenarios (debate, chat, OCR)
- [ ] **Week 2**: Run initial benchmark, analyze results
- [ ] **Week 2**: Tune parameters if needed (embedding model, top_k, thresholds)
- [ ] **Week 3**: Re-run benchmark, validate >85% target met
- [ ] **Week 3**: Document findings and optimal configuration
- [ ] **Week 4**: Implement production metrics tracking
- [ ] **Ongoing**: Monitor real-world RAG performance

---

## 📈 Expected Outcomes

### If Benchmark Passes (≥85% relevance):
✅ **Proof** that RAG is improving context quality  
✅ **Confidence** to deploy to production  
✅ **Baseline** for future improvements  

### If Benchmark Fails (<85% relevance):
🔧 **Data** to guide optimization (which scenarios fail?)  
🔧 **Direction** for tuning (embeddings? search params?)  
🔧 **Validation** that improvements actually help  

---

## 💡 Key Insights

1. **Ground Truth is Critical**: Hand-crafted test cases where we KNOW the right answer
2. **Multiple Metrics**: Single metric can be gamed; use precision + recall + relevance
3. **Real Scenarios**: Test cases should mirror actual usage (debate turns, chat context)
4. **Continuous Improvement**: Benchmark is not one-time; re-run after every change
5. **User Feedback**: In production, implicit feedback (was memory used?) is gold

---

## 🚀 Next Steps After Benchmark

Once RAG proven at >85%:
1. **Document optimal config** (embedding model, top_k, thresholds)
2. **Deploy to production** with monitoring
3. **Move to Priority 3**: Memory coherence for role reversal
4. **Gather real usage data** to refine further

The benchmark is not just validation - it's your **development loop** for RAG quality.

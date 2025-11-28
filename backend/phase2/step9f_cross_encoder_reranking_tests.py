"""
Step 9f: Cross-Encoder Reranking Tests
========================================

Tests cross-encoder reranking for RAG retrieval improvement.
Compares 4 strategies: baseline (no reranking) + 3 reranking variants.

Expected gains: +1-2pp precision, +1-2pp relevance
Target: ≥76% relevance, ≥34% precision for Alpha-v9 promotion

Author: ATLAS RAG Optimization Team
Date: November 11, 2025
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict, Any

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Now import our modules
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios
from memory.memory_manager import HybridMemoryManager
from phase2.cross_encoder_reranker import CrossEncoderReranker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class RerankingStrategy:
    """Base class for reranking strategies."""
    
    def __init__(self, name: str, description: str, retrieve_k: int, rerank_k: int):
        self.name = name
        self.description = description
        self.retrieve_k = retrieve_k
        self.rerank_k = rerank_k
    
    def apply_reranking(
        self,
        query: str,
        documents: List[Dict],
        reranker: CrossEncoderReranker
    ) -> List[Dict]:
        """Apply reranking strategy. Override in subclasses."""
        raise NotImplementedError


class BaselineStrategy(RerankingStrategy):
    """No reranking - control group."""
    
    def __init__(self):
        super().__init__(
            name='9f-0-baseline',
            description='No reranking (control)',
            retrieve_k=5,
            rerank_k=5
        )
    
    def apply_reranking(self, query: str, documents: List[Dict], reranker: CrossEncoderReranker) -> List[Dict]:
        # Return documents unchanged (no reranking)
        return documents[:self.rerank_k]


class Rerank10Strategy(RerankingStrategy):
    """Retrieve 10, rerank to top 5."""
    
    def __init__(self):
        super().__init__(
            name='9f-1-rerank-10',
            description='Retrieve 10, rerank to top 5',
            retrieve_k=10,
            rerank_k=5
        )
    
    def apply_reranking(self, query: str, documents: List[Dict], reranker: CrossEncoderReranker) -> List[Dict]:
        return reranker.rerank(query, documents, top_k=self.rerank_k)


class Rerank20Strategy(RerankingStrategy):
    """Retrieve 20, rerank to top 5."""
    
    def __init__(self):
        super().__init__(
            name='9f-2-rerank-20',
            description='Retrieve 20, rerank to top 5',
            retrieve_k=20,
            rerank_k=5
        )
    
    def apply_reranking(self, query: str, documents: List[Dict], reranker: CrossEncoderReranker) -> List[Dict]:
        return reranker.rerank(query, documents, top_k=self.rerank_k)


class Rerank30Strategy(RerankingStrategy):
    """Retrieve 30, rerank to top 5."""
    
    def __init__(self):
        super().__init__(
            name='9f-3-rerank-30',
            description='Retrieve 30, rerank to top 5',
            retrieve_k=30,
            rerank_k=5
        )
    
    def apply_reranking(self, query: str, documents: List[Dict], reranker: CrossEncoderReranker) -> List[Dict]:
        return reranker.rerank(query, documents, top_k=self.rerank_k)


def test_reranking_strategy(
    strategy: RerankingStrategy,
    benchmark: RAGBenchmark,
    memory_manager: HybridMemoryManager,
    reranker: CrossEncoderReranker
) -> Dict:
    """
    Test a single reranking strategy.
    
    Args:
        strategy: Reranking strategy to test
        benchmark: RAG benchmark harness
        memory_manager: Memory manager instance
        reranker: Cross-encoder reranker
    
    Returns:
        Test results dictionary
    """
    print(f"\n[TEST] Testing Strategy: {strategy.name}")
    print(f"[DESC] {strategy.description}")
    print(f"[CONFIG] Retrieve K={strategy.retrieve_k}, Rerank K={strategy.rerank_k}")
    
    # Store original search function
    original_search = memory_manager.search_memories
    
    try:
        # Monkey-patch search_memories to apply reranking
        def reranked_search(query: str, top_k: int = 5, **kwargs):
            """Wrapper that applies reranking to search results."""
            # Stage 1: Retrieve more candidates than requested
            retrieve_k = strategy.retrieve_k
            candidates = original_search(query, top_k=retrieve_k, **kwargs)
            
            # Stage 2: Apply reranking strategy
            reranked = strategy.apply_reranking(query, candidates, reranker)
            
            # Return top_k results (reranking may reduce count)
            return reranked[:top_k]
        
        # Apply monkey-patch
        memory_manager.search_memories = reranked_search
        
        # Run benchmark tests
        print(f"[RUN] Running 13 benchmark tests...")
        results = benchmark.run_benchmark(verbose=False)
        
        # Restore original function
        memory_manager.search_memories = original_search
        
        if results is None:
            print(f"[ERROR] Benchmark returned None")
            return None
        
        # Extract metrics
        summary = results.get('summary', {})
        relevance = summary.get('avg_relevance_score', 0) * 100
        precision = summary.get('avg_precision', 0) * 100
        recall = summary.get('avg_recall', 0) * 100
        passed = summary.get('passed', 0)
        
        print(f"[RESULTS] Relevance: {relevance:.2f}%, Precision: {precision:.2f}%, Recall: {recall:.2f}%, Passed: {passed}/13")
        
        return {
            'strategy': strategy.name,
            'description': strategy.description,
            'retrieve_k': strategy.retrieve_k,
            'rerank_k': strategy.rerank_k,
            'results': results
        }
    
    except Exception as e:
        print(f"[ERROR] Error testing {strategy.name}: {e}")
        logger.exception(f"Error in test_reranking_strategy")
        # Restore original function on error
        memory_manager.search_memories = original_search
        return None


def run_step9f_tests():
    """
    Run Step 9f cross-encoder reranking tests.
    
    Tests 4 strategies:
    - 9f-0-baseline: No reranking (control)
    - 9f-1-rerank-10: Retrieve 10, rerank to 5
    - 9f-2-rerank-20: Retrieve 20, rerank to 5
    - 9f-3-rerank-30: Retrieve 30, rerank to 5
    """
    print("=" * 70)
    print("STEP 9f: CROSS-ENCODER RERANKING TESTS")
    print("=" * 70)
    print(f"[START] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Baseline metrics (from validation run)
    print("[BASELINE] Current RAG System Performance:")
    print("   Relevance:  74.78%")
    print("   Precision:  32.95%")
    print("   Recall:     92.31%")
    print("   Tests:      6/13 passing (46.2%)")
    print()
    
    # Alpha-v9 promotion criteria
    print("[TARGET] Alpha-v9 Promotion Criteria:")
    print("   Relevance:  ≥76% (+1.22pp)")
    print("   Precision:  ≥34% (+1.05pp)")
    print("   Recall:     ≥90% (maintain)")
    print("   Tests:      ≥7/13 passing (54%)")
    print()
    
    # Initialize components
    print("[INIT] Initializing RAG system...")
    try:
        memory_manager = HybridMemoryManager()
        print("[OK] Memory manager initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize memory manager: {e}")
        return
    
    print("[INIT] Creating benchmark harness...")
    try:
        benchmark = RAGBenchmark(memory_manager)
        print("[OK] Benchmark harness created")
    except Exception as e:
        print(f"[ERROR] Failed to create benchmark: {e}")
        return
    
    print("[INIT] Loading test scenarios...")
    try:
        load_all_test_scenarios(benchmark)
        print(f"[OK] Loaded {len(benchmark.test_cases)} test scenarios")
    except Exception as e:
        print(f"[ERROR] Failed to load test scenarios: {e}")
        return
    
    print("[INIT] Loading cross-encoder model...")
    try:
        reranker = CrossEncoderReranker(
            model_name='cross-encoder/ms-marco-MiniLM-L6-v2',
            enabled=True,
            batch_size=32,
            verbose=False
        )
        print(f"[OK] Cross-encoder loaded: {reranker.model_name}")
    except Exception as e:
        print(f"[ERROR] Failed to load cross-encoder: {e}")
        return
    
    # Define strategies to test
    print("\n[STRATEGIES] Testing 4 reranking strategies:")
    strategies = [
        BaselineStrategy(),          # Control group
        Rerank10Strategy(),          # Retrieve 2x
        Rerank20Strategy(),          # Retrieve 4x
        Rerank30Strategy(),          # Retrieve 6x
    ]
    
    for i, strategy in enumerate(strategies, 1):
        print(f"   {i}. {strategy.name}: {strategy.description}")
    print()
    
    # Run tests for each strategy
    all_results = []
    for strategy in strategies:
        result = test_reranking_strategy(strategy, benchmark, memory_manager, reranker)
        if result:
            all_results.append(result)
    
    # Analyze results
    print("\n" + "=" * 70)
    print("STEP 9f RESULTS SUMMARY")
    print("=" * 70)
    print()
    
    print(f"{'Strategy':<25} {'Relevance':<12} {'Precision':<12} {'Recall':<10} {'Tests':<8}")
    print("-" * 70)
    
    best_relevance = 0
    best_precision = 0
    best_strategy = None
    
    for result in all_results:
        strategy_name = result['strategy']
        summary = result['results'].get('summary', {})
        
        relevance = summary.get('avg_relevance_score', 0) * 100
        precision = summary.get('avg_precision', 0) * 100
        recall = summary.get('avg_recall', 0) * 100
        passed = summary.get('passed', 0)
        total = summary.get('total', 13)
        
        print(f"{strategy_name:<25} {relevance:>10.2f}% {precision:>10.2f}% {recall:>8.2f}% {passed:>3}/{total}")
        
        # Track best performer
        if relevance > best_relevance or (relevance == best_relevance and precision > best_precision):
            best_relevance = relevance
            best_precision = precision
            best_strategy = result
    
    # Save results to JSON
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = results_dir / f'step9f_results_{timestamp}.json'
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print()
    print(f"[SAVE] Results saved to: {results_file}")
    print()
    
    # Alpha-v9 promotion decision
    print("=" * 70)
    print("ALPHA-v9 PROMOTION DECISION")
    print("=" * 70)
    print()
    
    if best_strategy:
        print(f"[BEST] Best Strategy: {best_strategy['strategy']}")
        print(f"[BEST] {best_strategy['description']}")
        print(f"[BEST] Relevance: {best_relevance:.2f}%")
        print(f"[BEST] Precision: {best_precision:.2f}%")
        print()
        
        # Check promotion criteria
        relevance_met = best_relevance >= 76.0
        precision_met = best_precision >= 34.0
        
        print("[CHECK] Promotion Criteria:")
        print(f"   Relevance ≥76%:   {'[PASS]' if relevance_met else '[FAIL]'} (have {best_relevance:.2f}%)")
        print(f"   Precision ≥34%:   {'[PASS]' if precision_met else '[FAIL]'} (have {best_precision:.2f}%)")
        print()
        
        if relevance_met and precision_met:
            print("[PROMOTE] ✅ ALPHA-v9 CRITERIA MET!")
            print("[PROMOTE] Recommend promoting best strategy to Alpha-v9")
            print()
            print("[NEXT] Actions:")
            print("   1. Save configuration via rag_version_control.py")
            print("   2. Update PHASE2_LOG.md with Step 9f results")
            print("   3. Document cross-encoder settings in config")
            print("   4. Announce Alpha-v9 promotion")
        else:
            print("[NEXT] RECOMMENDATION:")
            if not relevance_met and not precision_met:
                print("   Both metrics below target. Options:")
                print("   - Combine Step 9c (metadata) + Step 9f (reranking)")
                print("   - Proceed to Step 9g (additional techniques)")
            elif not relevance_met:
                print("   Relevance below target. Consider:")
                print("   - Better embedding model (all-mpnet-base-v2)")
                print("   - Query expansion techniques (Step 9d)")
            elif not precision_met:
                print("   Precision below target. Consider:")
                print("   - Fix Step 9c metadata filtering (15-30 min)")
                print("   - Stricter similarity thresholds")
    else:
        print("[ERROR] No valid results to analyze")
    
    print()
    print(f"[COMPLETE] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        run_step9f_tests()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test execution cancelled by user")
    except Exception as e:
        print(f"\n\n[ERROR] Fatal error: {e}")
        logger.exception("Fatal error in run_step9f_tests")

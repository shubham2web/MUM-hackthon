"""
Quick test to verify re-ranking is now working (not silently disabled)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.memory_manager import HybridMemoryManager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios

print("\n🧪 QUICK RE-RANKING VERIFICATION TEST\n")
print("="*70)

# Test 1: Baseline (no re-ranking)
print("\n1️⃣ TEST: Baseline (No Re-ranking)")
print("-" * 70)
os.environ['RERANKER_VECTOR_WEIGHT'] = '1.0'
os.environ['RERANKER_CE_WEIGHT'] = '0.0'

try:
    from memory.reranker import get_reranker
    get_reranker(reset=True)
except:
    pass

memory = HybridMemoryManager(
    long_term_backend="faiss",
    enable_reranking=False  # Explicitly disabled
)

benchmark = RAGBenchmark(memory)
load_all_test_scenarios(benchmark)
results = benchmark.run_benchmark(verbose=False)

baseline_score = results['summary']['avg_relevance_score'] * 100
print(f"\n✅ Baseline Score: {baseline_score:.1f}%")

del memory, benchmark

# Test 2: With re-ranking enabled
print("\n2️⃣ TEST: With Re-Ranking (80/20 hybrid)")
print("-" * 70)
os.environ['RERANKER_VECTOR_WEIGHT'] = '0.2'
os.environ['RERANKER_CE_WEIGHT'] = '0.8'
os.environ['RERANKER_THRESHOLD'] = '0.0'  # No threshold filtering

try:
    from memory.reranker import get_reranker
    get_reranker(reset=True)
except:
    pass

memory = HybridMemoryManager(
    long_term_backend="faiss",
    enable_reranking=True  # ✅ ENABLED
)

# Verify re-ranking is actually enabled
if memory.long_term.enable_reranking and memory.long_term.reranker:
    print("✅ Re-ranking is ACTIVE")
else:
    print("❌ CRITICAL: Re-ranking is DISABLED despite enable_reranking=True!")
    sys.exit(1)

benchmark = RAGBenchmark(memory)
load_all_test_scenarios(benchmark)
results = benchmark.run_benchmark(verbose=False)

reranking_score = results['summary']['avg_relevance_score'] * 100
print(f"\n✅ Re-Ranking Score: {reranking_score:.1f}%")

# Analysis
print("\n" + "="*70)
print("📊 VERIFICATION RESULTS")
print("="*70)
print(f"Baseline (no re-ranking):   {baseline_score:.1f}%")
print(f"With Re-ranking (80/20):     {reranking_score:.1f}%")
print(f"Difference:                  {reranking_score - baseline_score:+.1f} percentage points")
print("="*70)

if baseline_score == reranking_score:
    print("\n❌ IDENTICAL SCORES - Re-ranking may still be broken!")
    print("   This should NOT happen if cross-encoder is actually running.")
elif reranking_score == 0.0:
    print("\n❌ ZERO SCORE - Threshold filtering too aggressive or score normalization issue")
else:
    print("\n✅ DIFFERENT SCORES - Re-ranking harness is working!")
    if reranking_score > baseline_score:
        print(f"   🎉 Re-ranking IMPROVED scores by {reranking_score - baseline_score:.1f} points!")
    else:
        print(f"   ⚠️  Re-ranking DECREASED scores by {abs(reranking_score - baseline_score):.1f} points")
        print("      (May indicate domain mismatch or bad weighting)")

print()

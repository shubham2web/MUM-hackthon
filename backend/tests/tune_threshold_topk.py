"""
Threshold & Top-K Tuning - Phase 1 Quick Wins

This script tunes two critical parameters to improve precision:
1. Similarity threshold (how similar a result must be to include it)
2. Top-K (how many results to return)

Goal: Improve from 60.9% → 72-78% relevance
"""
import sys
import os

# Fix Windows UTF-8 encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from datetime import datetime
from typing import Dict, List
from memory.memory_manager import HybridMemoryManager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios


def run_threshold_topk_experiment(
    threshold: float,
    top_k: int
) -> Dict:
    """
    Run benchmark with specific threshold and top-k values.
    
    Args:
        threshold: Minimum similarity score (0-1)
        top_k: Number of results to return
        
    Returns:
        Experiment results
    """
    print(f"\n{'='*70}")
    print(f"EXPERIMENT: Threshold={threshold:.2f}, Top-K={top_k}")
    print(f"{'='*70}\n")
    
    # Set environment variables
    os.environ['SIMILARITY_THRESHOLD'] = str(threshold)
    os.environ['DEFAULT_TOP_K'] = str(top_k)
    
    # Disable re-ranking (we know it hurts)
    os.environ['ENABLE_RERANKING'] = 'False'
    
    # Create memory manager
    memory = HybridMemoryManager(long_term_backend="faiss")
    
    # Create and run benchmark
    benchmark = RAGBenchmark(memory)
    load_all_test_scenarios(benchmark)
    results = benchmark.run_benchmark(verbose=False)
    
    if results:
        experiment_result = {
            'threshold': threshold,
            'top_k': top_k,
            'metrics': {
                'relevance': results['summary']['avg_relevance_score'] * 100,
                'precision': results['summary']['avg_precision'] * 100,
                'recall': results['summary']['avg_recall'] * 100,
                'f1': results['summary']['avg_f1'] * 100,
                'tests_passed': results['summary']['passed'],
                'pass_rate': results['summary']['pass_rate'] * 100
            },
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"📊 RESULTS:")
        print(f"  Relevance:  {experiment_result['metrics']['relevance']:.1f}%")
        print(f"  Precision:  {experiment_result['metrics']['precision']:.1f}%")
        print(f"  Recall:     {experiment_result['metrics']['recall']:.1f}%")
        print(f"  F1 Score:   {experiment_result['metrics']['f1']:.1f}%")
        
        # Clean up
        del memory
        del benchmark
        
        return experiment_result
    
    return None


def main():
    """Run threshold and top-k tuning suite"""
    
    print("\n🎯 THRESHOLD & TOP-K TUNING - PHASE 1")
    print("Goal: Improve precision to boost relevance from 60.9% → 72-78%\n")
    
    # Define parameter grid
    thresholds = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70]  # Current is 0.45
    top_k_values = [3, 4, 5, 6, 7]  # Current is 5
    
    total_experiments = len(thresholds) * len(top_k_values)
    print(f"Running {total_experiments} experiments...")
    print(f"Thresholds: {thresholds}")
    print(f"Top-K values: {top_k_values}\n")
    
    results = []
    experiment_num = 0
    
    for threshold in thresholds:
        for top_k in top_k_values:
            experiment_num += 1
            print(f"\n[{experiment_num}/{total_experiments}] Testing: threshold={threshold:.2f}, top_k={top_k}")
            
            try:
                result = run_threshold_topk_experiment(threshold, top_k)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"❌ Experiment failed: {e}")
                continue
    
    if not results:
        print("\n❌ No successful experiments")
        return
    
    # Analyze results
    print("\n" + "="*70)
    print("📊 RESULTS ANALYSIS")
    print("="*70 + "\n")
    
    # Sort by relevance
    sorted_by_relevance = sorted(results, key=lambda x: x['metrics']['relevance'], reverse=True)
    
    # Sort by precision
    sorted_by_precision = sorted(results, key=lambda x: x['metrics']['precision'], reverse=True)
    
    # Sort by F1 (balance of precision and recall)
    sorted_by_f1 = sorted(results, key=lambda x: x['metrics']['f1'], reverse=True)
    
    # Top 5 by relevance
    print("🏆 TOP 5 BY RELEVANCE:")
    print(f"{'Rank':<6} {'Threshold':<12} {'Top-K':<8} {'Relevance':<12} {'Precision':<12} {'Recall':<10}")
    print("-" * 70)
    for i, exp in enumerate(sorted_by_relevance[:5], 1):
        print(f"{i:<6} {exp['threshold']:<12.2f} {exp['top_k']:<8} "
              f"{exp['metrics']['relevance']:<12.1f} "
              f"{exp['metrics']['precision']:<12.1f} "
              f"{exp['metrics']['recall']:<10.1f}")
    
    print("\n🎯 TOP 5 BY PRECISION:")
    print(f"{'Rank':<6} {'Threshold':<12} {'Top-K':<8} {'Precision':<12} {'Relevance':<12} {'Recall':<10}")
    print("-" * 70)
    for i, exp in enumerate(sorted_by_precision[:5], 1):
        print(f"{i:<6} {exp['threshold']:<12.2f} {exp['top_k']:<8} "
              f"{exp['metrics']['precision']:<12.1f} "
              f"{exp['metrics']['relevance']:<12.1f} "
              f"{exp['metrics']['recall']:<10.1f}")
    
    print("\n⚖️  TOP 5 BY F1 SCORE (BALANCED):")
    print(f"{'Rank':<6} {'Threshold':<12} {'Top-K':<8} {'F1':<12} {'Relevance':<12} {'Precision':<12}")
    print("-" * 70)
    for i, exp in enumerate(sorted_by_f1[:5], 1):
        print(f"{i:<6} {exp['threshold']:<12.2f} {exp['top_k']:<8} "
              f"{exp['metrics']['f1']:<12.1f} "
              f"{exp['metrics']['relevance']:<12.1f} "
              f"{exp['metrics']['precision']:<12.1f}")
    
    # Best overall
    best = sorted_by_relevance[0]
    print("\n" + "="*70)
    print("🏆 RECOMMENDED CONFIGURATION")
    print("="*70)
    print(f"Threshold: {best['threshold']:.2f}")
    print(f"Top-K:     {best['top_k']}")
    print(f"\nPerformance:")
    print(f"  Relevance:  {best['metrics']['relevance']:.1f}%  (Target: 85%)")
    print(f"  Precision:  {best['metrics']['precision']:.1f}%  (Target: 60%)")
    print(f"  Recall:     {best['metrics']['recall']:.1f}%  (Target: 90%)")
    print(f"  F1 Score:   {best['metrics']['f1']:.1f}%")
    
    # Show improvement
    baseline_relevance = 60.9
    improvement = best['metrics']['relevance'] - baseline_relevance
    gap_to_target = 85.0 - best['metrics']['relevance']
    
    print(f"\n📈 Improvement from baseline: +{improvement:.1f} percentage points")
    print(f"📊 Remaining gap to 85% target: {gap_to_target:.1f} percentage points")
    
    if best['metrics']['relevance'] >= 85.0:
        print("\n✅ TARGET ACHIEVED! 🎉")
    elif best['metrics']['relevance'] >= 72.0:
        print("\n✅ Phase 1 goal achieved (72%+)")
        print("   Next: Proceed to Phase 2 (Query & Metadata optimization)")
    else:
        print("\n⚠️  Phase 1 goal not fully achieved")
        print("   Consider: More aggressive thresholds or model upgrade")
    
    print("="*70 + "\n")
    
    # Save results
    output_file = f"threshold_topk_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            'experiments': results,
            'sorted_by_relevance': sorted_by_relevance[:10],
            'sorted_by_precision': sorted_by_precision[:10],
            'sorted_by_f1': sorted_by_f1[:10],
            'best_config': best
        }, f, indent=2)
    print(f"📄 Full results saved to: {output_file}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Tuning interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Tuning failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

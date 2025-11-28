"""
Fixed Tuning Experiments - Properly reloads memory system between runs

The previous approach had an issue: the LLMReranker was initialized once
and never updated when environment variables changed. This version fixes
that by completely reinitializing the memory system for each experiment.
"""
import sys
import os

# Fix Windows UTF-8 encoding issues
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


def run_single_experiment(
    name: str,
    vector_weight: float,
    cross_encoder_weight: float,
    score_threshold: float = 0.0,
    normalization: str = "minmax"
) -> Dict:
    """
    Run a single tuning experiment with proper reinitialization.
    
    Key fix: Creates fresh memory manager instance for each experiment
    so environment variables take effect.
    """
    print(f"\n{'='*70}")
    print(f"EXPERIMENT: {name}")
    print(f"{'='*70}")
    print(f"Vector Weight:        {vector_weight:.2f}")
    print(f"Cross-Encoder Weight: {cross_encoder_weight:.2f}")
    print(f"Score Threshold:      {score_threshold:.2f}")
    print(f"Normalization:        {normalization}")
    print(f"{'='*70}\n")
    
    # Set environment variables BEFORE creating memory manager
    os.environ['RERANKER_VECTOR_WEIGHT'] = str(vector_weight)
    os.environ['RERANKER_CE_WEIGHT'] = str(cross_encoder_weight)
    os.environ['RERANKER_THRESHOLD'] = str(score_threshold)
    os.environ['RERANKER_NORMALIZATION'] = normalization
    
    # CRITICAL FIX: Reset the reranker singleton so it reads new env vars
    try:
        from memory.reranker import get_reranker
        get_reranker(reset=True)  # Force reinitialization
    except:
        pass
    
    # Create FRESH memory manager (this will initialize reranker with new env vars)
    memory = HybridMemoryManager(
        long_term_backend="faiss",
        enable_reranking=True  # CRITICAL FIX: Enable re-ranking for experiments!
    )
    
    # Create benchmark with this memory instance
    benchmark = RAGBenchmark(memory)
    load_all_test_scenarios(benchmark)
    
    # Run benchmark
    results = benchmark.run_benchmark(verbose=False)
    
    if results:
        experiment_result = {
            'name': name,
            'config': {
                'vector_weight': vector_weight,
                'cross_encoder_weight': cross_encoder_weight,
                'score_threshold': score_threshold,
                'normalization': normalization
            },
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
        
        print(f"\n📊 RESULTS:")
        print(f"  Relevance:  {experiment_result['metrics']['relevance']:.1f}%")
        print(f"  Precision:  {experiment_result['metrics']['precision']:.1f}%")
        print(f"  Recall:     {experiment_result['metrics']['recall']:.1f}%")
        print(f"  F1 Score:   {experiment_result['metrics']['f1']:.1f}%")
        
        # Clean up memory
        del memory
        del benchmark
        
        return experiment_result
    
    return None


def main():
    """Run complete tuning suite with proper reinitialization"""
    
    print("\n🎯 CROSS-ENCODER RE-RANKER TUNING (FIXED)")
    print("Goal: Find optimal configuration for 85%+ relevance\n")
    
    experiments_config = [
        # Baseline
        {'name': 'Baseline (No Re-ranking)', 'vector_weight': 1.0, 'cross_encoder_weight': 0.0},
        
        # Pure cross-encoder
        {'name': 'Pure Cross-Encoder', 'vector_weight': 0.0, 'cross_encoder_weight': 1.0},
        
        # Hybrid blends
        {'name': 'Hybrid: CE Dominant (80/20)', 'vector_weight': 0.2, 'cross_encoder_weight': 0.8},
        {'name': 'Hybrid: Balanced (50/50)', 'vector_weight': 0.5, 'cross_encoder_weight': 0.5},
        {'name': 'Hybrid: Vector Dominant (60/40)', 'vector_weight': 0.6, 'cross_encoder_weight': 0.4},
        
        # With thresholds
        {'name': 'Hybrid (80/20) + Threshold 0.5', 'vector_weight': 0.2, 'cross_encoder_weight': 0.8, 'score_threshold': 0.5},
        {'name': 'Hybrid (80/20) + Threshold 0.7', 'vector_weight': 0.2, 'cross_encoder_weight': 0.8, 'score_threshold': 0.7},
        
        # Alternative normalization
        {'name': 'Hybrid (80/20) + Sigmoid Norm', 'vector_weight': 0.2, 'cross_encoder_weight': 0.8, 'normalization': 'sigmoid'},
    ]
    
    results = []
    
    for config in experiments_config:
        try:
            result = run_single_experiment(**config)
            if result:
                results.append(result)
        except Exception as e:
            print(f"❌ Experiment failed: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Analyze results
    if not results:
        print("\n❌ No successful experiments")
        return
    
    print("\n" + "="*70)
    print("📊 EXPERIMENTS RANKED BY RELEVANCE")
    print("="*70 + "\n")
    
    # Sort by relevance
    sorted_results = sorted(results, key=lambda x: x['metrics']['relevance'], reverse=True)
    
    print(f"{'Rank':<6} {'Experiment':<40} {'Relevance':>10} {'Precision':>10} {'Recall':>10}")
    print("-" * 95)
    
    for i, exp in enumerate(sorted_results, 1):
        print(f"{i:<6} {exp['name']:<40} {exp['metrics']['relevance']:>9.1f}% {exp['metrics']['precision']:>9.1f}% {exp['metrics']['recall']:>9.1f}%")
    
    # Show best
    best = sorted_results[0]
    print("\n" + "="*70)
    print("🏆 BEST CONFIGURATION")
    print("="*70)
    print(f"Experiment: {best['name']}\n")
    print(f"Configuration:")
    print(f"  Vector Weight:        {best['config']['vector_weight']:.2f}")
    print(f"  Cross-Encoder Weight: {best['config']['cross_encoder_weight']:.2f}")
    print(f"  Score Threshold:      {best['config']['score_threshold']:.2f}")
    print(f"\nPerformance:")
    print(f"  Relevance:  {best['metrics']['relevance']:.1f}%  (Target: 85%+)")
    print(f"  Precision:  {best['metrics']['precision']:.1f}%  (Target: 60%+)")
    print(f"  Recall:     {best['metrics']['recall']:.1f}%  (Target: 90%+)")
    
    if best['metrics']['relevance'] >= 85.0:
        print("\n✅ TARGET MET! System ready for production!")
    else:
        gap = 85.0 - best['metrics']['relevance']
        print(f"\n⚠️  Gap to target: {gap:.1f} percentage points")
    
    print("="*70 + "\n")
    
    # Save results
    output_file = f"tuning_results_fixed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(sorted_results, f, indent=2)
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

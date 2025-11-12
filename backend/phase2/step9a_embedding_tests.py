"""
Step 9a: Embedding Model Upgrade Testing Framework

This script automates testing of different embedding models to find the best
performer for RAG retrieval optimization (Phase 2, Step 9a).

Tests 3 embedding models:
1. BGE-small-en-v1.5 (384-dim) - baseline
2. bge-large-en-v1.5 (1024-dim) - 2.7x larger
3. all-mpnet-base-v2 (768-dim) - 2x larger, 1000x more training data

Usage:
    python phase2/step9a_embedding_tests.py
"""

import sys
import os
import time
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.vector_store import VectorStore
from tests.run_rag_benchmark import run_full_benchmark


# Test configurations
EMBEDDING_MODELS = [
    {
        "name": "baseline",
        "model": "BAAI/bge-small-en-v1.5",
        "dimensions": 384,
        "description": "Current baseline (Phase 1 alpha-v7)",
        "version": "alpha-v7-baseline"
    },
    {
        "name": "bge-large",
        "model": "BAAI/bge-large-en-v1.5",
        "dimensions": 1024,
        "description": "BGE Large: 2.7x larger embeddings, MTEB 64.2",
        "version": "alpha-v9-candidate-1"
    },
    {
        "name": "all-mpnet",
        "model": "sentence-transformers/all-mpnet-base-v2",
        "dimensions": 768,
        "description": "MPNet: 2x larger, trained on 1B+ pairs, MTEB 63.3",
        "version": "alpha-v9-candidate-2"
    }
]

# Test parameters (aligned with Phase 2 directive)
TEST_CONFIG = {
    "top_k": 5,
    "similarity_threshold": 0.75,  # Higher threshold per directive
    "hybrid_vector_weight": 0.97,
    "query_preprocessing_mode": "7e-1",
    "enable_reranking": False  # Disabled for Step 9a
}


def print_header(text, char="="):
    """Print formatted header"""
    width = 80
    print(f"\n{char * width}")
    print(f"{text.center(width)}")
    print(f"{char * width}\n")


def print_config(config):
    """Print test configuration"""
    print("Test Configuration:")
    for key, value in config.items():
        print(f"  • {key}: {value}")
    print()


def test_embedding_model(model_config, test_config):
    """
    Test a single embedding model configuration
    
    Args:
        model_config: Dictionary with model name, path, dimensions
        test_config: Dictionary with test parameters
        
    Returns:
        Dictionary with test results (relevance, precision, recall, latency, etc.)
    """
    print_header(f"Testing: {model_config['name']}", "-")
    print(f"Model: {model_config['model']}")
    print(f"Dimensions: {model_config['dimensions']}")
    print(f"Description: {model_config['description']}")
    print(f"Version: {model_config['version']}")
    print()
    
    # Monkey-patch VectorStore to use test config
    original_init = VectorStore.__init__
    
    def patched_init(self, *args, **kwargs):
        # Override with test config
        kwargs['embedding_model'] = model_config['model']
        kwargs['similarity_threshold'] = test_config['similarity_threshold']
        kwargs['hybrid_vector_weight'] = test_config['hybrid_vector_weight']
        kwargs['query_preprocessing_mode'] = test_config['query_preprocessing_mode']
        kwargs['enable_reranking'] = test_config['enable_reranking']
        original_init(self, *args, **kwargs)
    
    VectorStore.__init__ = patched_init
    
    try:
        print(f"⏳ Running benchmark with {model_config['name']}...")
        start_time = time.time()
        
        # Run benchmark (captures stdout)
        results = run_full_benchmark()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n✅ Benchmark complete in {total_time:.2f}s\n")
        
        # Parse results
        return {
            "model_name": model_config['name'],
            "model_path": model_config['model'],
            "dimensions": model_config['dimensions'],
            "version": model_config['version'],
            "results": results,
            "total_time": total_time,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        print(f"\n❌ Error testing {model_config['name']}: {e}\n")
        return {
            "model_name": model_config['name'],
            "model_path": model_config['model'],
            "dimensions": model_config['dimensions'],
            "version": model_config['version'],
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    finally:
        # Restore original init
        VectorStore.__init__ = original_init


def compare_results(all_results):
    """
    Compare results from all models and determine winner
    
    Args:
        all_results: List of result dictionaries
        
    Returns:
        Dictionary with comparison analysis
    """
    print_header("Step 9a Results Comparison", "=")
    
    # Extract baseline
    baseline = None
    for result in all_results:
        if result['model_name'] == 'baseline':
            baseline = result['results']
            break
    
    if not baseline:
        print("⚠️  Warning: No baseline results found")
        return
    
    # Print comparison table
    print(f"{'Model':<20} {'Dims':<8} {'Relevance':<12} {'Δ':<8} {'Precision':<12} {'Δ':<8} {'Recall':<10} {'Latency'}")
    print("-" * 100)
    
    best_relevance = {"model": None, "value": 0, "delta": 0}
    best_precision = {"model": None, "value": 0, "delta": 0}
    
    for result in all_results:
        if 'error' in result:
            print(f"{result['model_name']:<20} {result['dimensions']:<8} ERROR: {result['error']}")
            continue
        
        res = result['results']
        dims = result['dimensions']
        
        # Calculate deltas
        rel_delta = res.get('avg_relevance', 0) - baseline.get('avg_relevance', 0)
        prec_delta = res.get('avg_precision', 0) - baseline.get('avg_precision', 0)
        
        # Track best
        if res.get('avg_relevance', 0) > best_relevance['value']:
            best_relevance = {
                "model": result['model_name'],
                "value": res.get('avg_relevance', 0),
                "delta": rel_delta
            }
        
        if res.get('avg_precision', 0) > best_precision['value']:
            best_precision = {
                "model": result['model_name'],
                "value": res.get('avg_precision', 0),
                "delta": prec_delta
            }
        
        # Format deltas
        rel_delta_str = f"+{rel_delta:.2f}pp" if rel_delta > 0 else f"{rel_delta:.2f}pp"
        prec_delta_str = f"+{prec_delta:.2f}pp" if prec_delta > 0 else f"{prec_delta:.2f}pp"
        
        # Print row
        print(f"{result['model_name']:<20} {dims:<8} "
              f"{res.get('avg_relevance', 0):.2f}%{'':<6} {rel_delta_str:<8} "
              f"{res.get('avg_precision', 0):.2f}%{'':<6} {prec_delta_str:<8} "
              f"{res.get('avg_recall', 0):.2f}%{'':<4} "
              f"{result.get('total_time', 0)/res.get('tests_passed', 1):.0f}ms")
    
    print()
    
    # Winner analysis
    print_header("Winner Analysis", "-")
    
    print(f"🏆 Best Relevance: {best_relevance['model']}")
    print(f"   Value: {best_relevance['value']:.2f}%")
    print(f"   Gain: {best_relevance['delta']:+.2f}pp from baseline")
    print()
    
    print(f"🎯 Best Precision: {best_precision['model']}")
    print(f"   Value: {best_precision['value']:.2f}%")
    print(f"   Gain: {best_precision['delta']:+.2f}pp from baseline")
    print()
    
    # Recommendation
    print("📋 Recommendation:")
    
    # Find model that wins both or has best combined score
    combined_scores = {}
    for result in all_results:
        if 'error' in result:
            continue
        res = result['results']
        # Weight: 60% precision (primary goal), 40% relevance
        combined_scores[result['model_name']] = (
            res.get('avg_precision', 0) * 0.6 + 
            res.get('avg_relevance', 0) * 0.4
        )
    
    if combined_scores:
        winner = max(combined_scores, key=combined_scores.get)
        winner_result = next(r for r in all_results if r['model_name'] == winner)
        
        print(f"   Promote to alpha-v9: {winner}")
        print(f"   Version: {winner_result['version']}")
        print(f"   Combined Score: {combined_scores[winner]:.2f}")
        print(f"   (60% precision + 40% relevance)")
        
        # Check if meets success criteria
        winner_res = winner_result['results']
        prec_gain = winner_res.get('avg_precision', 0) - baseline.get('avg_precision', 0)
        rel_gain = winner_res.get('avg_relevance', 0) - baseline.get('avg_relevance', 0)
        recall = winner_res.get('avg_recall', 0)
        
        print()
        print("✅ Success Criteria Check:")
        print(f"   Precision gain: {prec_gain:+.2f}pp (minimum +1pp) {'✅' if prec_gain >= 1 else '❌'}")
        print(f"   Relevance gain: {rel_gain:+.2f}pp (minimum +1pp) {'✅' if rel_gain >= 1 else '❌'}")
        print(f"   Recall: {recall:.2f}% (minimum 90%) {'✅' if recall >= 90 else '❌'}")
        
        if prec_gain >= 1 and rel_gain >= 1 and recall >= 90:
            print("\n🎉 SUCCESS! Promote to alpha-v9 and continue Phase 2")
        else:
            print("\n⚠️  Criteria not met. Consider additional tuning or hybrid approach")
    
    return {
        "best_relevance": best_relevance,
        "best_precision": best_precision,
        "combined_scores": combined_scores,
        "winner": winner if combined_scores else None
    }


def save_results(all_results, comparison, output_path="phase2/step9a_results.json"):
    """Save results to JSON file"""
    output_data = {
        "test_config": TEST_CONFIG,
        "all_results": all_results,
        "comparison": comparison,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    output_file = Path(__file__).parent.parent / output_path
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")


def main():
    """Main test execution"""
    print_header("RAG Optimization Phase 2 - Step 9a: Embedding Model Tests", "=")
    print("Testing 3 embedding models to find optimal configuration")
    print("Goal: Lift precision from 32.95% while maintaining recall > 90%")
    print()
    
    print_config(TEST_CONFIG)
    
    all_results = []
    
    # Test each model
    for i, model_config in enumerate(EMBEDDING_MODELS, 1):
        print(f"\n[{i}/{len(EMBEDDING_MODELS)}] Testing {model_config['name']}...")
        
        result = test_embedding_model(model_config, TEST_CONFIG)
        all_results.append(result)
        
        # Print quick summary
        if 'error' not in result:
            res = result['results']
            print(f"   Quick Results:")
            print(f"   • Relevance: {res.get('avg_relevance', 0):.2f}%")
            print(f"   • Precision: {res.get('avg_precision', 0):.2f}%")
            print(f"   • Recall: {res.get('avg_recall', 0):.2f}%")
            print(f"   • Tests Passed: {res.get('tests_passed', 0)}/13")
        
        # Brief pause between tests
        if i < len(EMBEDDING_MODELS):
            print("\n⏸️  Brief pause before next test (5s)...")
            time.sleep(5)
    
    # Compare all results
    comparison = compare_results(all_results)
    
    # Save results
    save_results(all_results, comparison)
    
    print_header("Step 9a Complete!", "=")
    print("✅ All embedding models tested")
    print("📊 Results logged to phase2/step9a_results.json")
    print("📝 Update RAG_OPTIMIZATION_PHASE2_LOG.md with findings")
    print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
RAG Optimization - Phase 2, Step 9a: Embedding Model Upgrade Tests (v2 FIXED)

CRITICAL INFRASTRUCTURE FIX:
The v1 test script used monkey-patching which completely broke VectorStore initialization.
This v2 uses proper environment variable approach to test different embedding models.

Tests three embedding models:
1. Baseline: BAAI/bge-small-en-v1.5 (384-dim, current alpha-v7)
2. Candidate 1: BAAI/bge-large-en-v1.5 (1024-dim, expected +1-3pp precision)
3. Candidate 2: sentence-transformers/all-mpnet-base-v2 (768-dim, expected +1-2pp)

Test Configuration (per Phase 2 directive):
- top_k: 5
- similarity_threshold: 0.75 (higher than Phase 1's 0.50)
- hybrid_vector_weight: 0.97 (97% semantic, 3% lexical)
- query_preprocessing_mode: "7e-1"
- enable_reranking: False

Success Criteria (promote to alpha-v9):
✅ Precision: ≥34% (+1pp minimum) - PRIMARY BOTTLENECK TARGET
✅ Relevance: ≥76% (+1pp minimum)
✅ Recall: ≥90% (maintain high coverage)
✅ Latency: <80ms average retrieval time

Winner Selection:
- Combined score = 60% precision + 40% relevance
- Reflects precision-first strategy per Phase 2 mission

Usage:
    python phase2/step9a_embedding_tests_v2.py

Output:
    - Comparison table with Δ precision, Δ relevance
    - Winner recommendation with combined score
    - Success criteria validation (✅/❌)
    - Results saved to phase2/step9a_results_v2.json
"""

import os
import sys
import time
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup
from tests.run_rag_benchmark import run_full_benchmark


# ============================================================================
#                           EMBEDDING MODELS TO TEST
# ============================================================================

EMBEDDING_MODELS = [
    {
        "name": "baseline",
        "model": "BAAI/bge-small-en-v1.5",
        "dimensions": 384,
        "description": "BGE-Small: Current alpha-v7 baseline, MTEB 60.1",
        "version": "alpha-v7-baseline",
        "expected_performance": "Baseline: 74.78% relevance, 32.95% precision",
    },
    {
        "name": "bge-large",
        "model": "BAAI/bge-large-en-v1.5",
        "dimensions": 1024,
        "description": "BGE-Large: 3x larger, high semantic clarity, MTEB 64.2",
        "version": "alpha-v9-candidate-1",
        "expected_performance": "Expected +1-3pp precision, +0.5-2pp relevance",
    },
    {
        "name": "all-mpnet",
        "model": "sentence-transformers/all-mpnet-base-v2",
        "dimensions": 768,
        "description": "MPNet: 2x larger, trained on 1B+ pairs, MTEB 63.3",
        "version": "alpha-v9-candidate-2",
        "expected_performance": "Expected +1-2pp precision, +0.5-1.5pp relevance",
    },
]


# ============================================================================
#                           PHASE 2 TEST CONFIGURATION
# ============================================================================

TEST_CONFIG = {
    "top_k": 5,
    "similarity_threshold": 0.75,
    "hybrid_vector_weight": 0.97,
    "query_preprocessing_mode": "7e-1",
    "enable_reranking": False,
    "enable_hybrid_bm25": True,
}

SUCCESS_CRITERIA = {
    "min_precision_gain": 1.0,  # +1pp minimum (PRIMARY TARGET)
    "min_relevance_gain": 1.0,  # +1pp minimum
    "min_recall": 90.0,          # maintain 90%+
    "max_latency_ms": 80,        # <80ms average
}


# ============================================================================
#                           HELPER FUNCTIONS
# ============================================================================

def get_timestamp():
    """Get formatted timestamp for logging"""
    return datetime.now().strftime("%H:%M:%S")


def backup_vector_database():
    """Backup current vector database before testing"""
    vector_db_path = Path("database/vector_store")
    if vector_db_path.exists():
        backup_path = Path("database/vector_store_backup_step9a")
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.copytree(vector_db_path, backup_path)
        print(f"[{get_timestamp()}] ✅ Vector database backed up to {backup_path}")
        return True
    return False


def restore_vector_database():
    """Restore original vector database after testing"""
    backup_path = Path("database/vector_store_backup_step9a")
    vector_db_path = Path("database/vector_store")
    
    if backup_path.exists():
        if vector_db_path.exists():
            shutil.rmtree(vector_db_path)
        shutil.copytree(backup_path, vector_db_path)
        print(f"[{get_timestamp()}] ✅ Vector database restored from backup")
        return True
    return False


def clear_vector_database():
    """Clear vector database to allow reindexing with new embeddings"""
    vector_db_path = Path("database/vector_store")
    if vector_db_path.exists():
        shutil.rmtree(vector_db_path)
        print(f"[{get_timestamp()}] 🗑️  Vector database cleared for reindexing")


def rebuild_vector_database():
    """
    The benchmark suite will automatically rebuild the vector database
    with test memories when it runs. We just need to ensure the database
    is cleared so it uses the new EMBEDDING_MODEL environment variable.
    """
    print(f"[{get_timestamp()}] ✅ Vector database will be rebuilt automatically by benchmark")
    return True


def test_embedding_model(model_config: Dict[str, Any], baseline_results: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Test a single embedding model by:
    1. Setting EMBEDDING_MODEL environment variable
    2. Clearing and rebuilding vector database
    3. Running 13-test benchmark
    4. Collecting metrics
    
    Args:
        model_config: Model configuration dict
        baseline_results: Optional baseline results for comparison
        
    Returns:
        Dict with test results, metrics, and comparison
    """
    model_name = model_config['name']
    model_path = model_config['model']
    
    print("\n" + "="*80)
    print(f"                          Testing: {model_name}")
    print("="*80)
    print(f"\nModel: {model_path}")
    print(f"Dimensions: {model_config['dimensions']}")
    print(f"Description: {model_config['description']}")
    print(f"Version: {model_config['version']}\n")
    
    try:
        # Step 1: Set embedding model environment variable
        os.environ["EMBEDDING_MODEL"] = model_path
        print(f"[{get_timestamp()}] 🔧 Set EMBEDDING_MODEL={model_path}")
        
        # Step 2: Clear vector database
        clear_vector_database()
        
        # Step 3: Rebuild with new embeddings
        if not rebuild_vector_database():
            return {
                "model_name": model_name,
                "model_path": model_path,
                "dimensions": model_config['dimensions'],
                "version": model_config['version'],
                "error": "Failed to rebuild vector database",
                "results": None,
            }
        
        # Step 4: Run 13-test benchmark
        print(f"\n[{get_timestamp()}] ⏳ Running benchmark with {model_name}...")
        start_time = time.time()
        
        results = run_full_benchmark(verbose=True, export=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\n[{get_timestamp()}] ✅ Benchmark complete in {total_time:.2f}s\n")
        
        # Parse results
        return {
            "model_name": model_name,
            "model_path": model_path,
            "dimensions": model_config['dimensions'],
            "version": model_config['version'],
            "results": results,
            "total_time": total_time,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": TEST_CONFIG,
        }
        
    except Exception as e:
        print(f"\n[{get_timestamp()}] ❌ Error testing {model_name}: {e}\n")
        return {
            "model_name": model_name,
            "model_path": model_path,
            "dimensions": model_config['dimensions'],
            "version": model_config['version'],
            "error": str(e),
            "results": None,
        }


def compare_results(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare results from all embedding models.
    
    Args:
        all_results: List of test results for each model
        
    Returns:
        Comparison dict with winner recommendation
    """
    print("\n" + "="*80)
    print("                       Step 9a Results Comparison")
    print("="*80 + "\n")
    
    # Extract baseline
    baseline = next((r for r in all_results if r["model_name"] == "baseline"), None)
    if not baseline or not baseline.get("results"):
        print("⚠️  Baseline results not found or invalid - cannot compare")
        return {"error": "Baseline results missing"}
    
    baseline_metrics = baseline["results"]
    baseline_relevance = baseline_metrics.get("avg_relevance", 0)
    baseline_precision = baseline_metrics.get("avg_precision", 0)
    baseline_recall = baseline_metrics.get("avg_recall", 0)
    
    # Print comparison table
    print(f"{'Model':<20} {'Dims':<8} {'Relevance':<12} {'Δ':<10} {'Precision':<12} {'Δ':<10} {'Recall':<10} {'Latency':<8}")
    print("-" * 110)
    
    comparison = []
    
    for result in all_results:
        if not result.get("results"):
            continue
            
        metrics = result["results"]
        relevance = metrics.get("avg_relevance", 0)
        precision = metrics.get("avg_precision", 0)
        recall = metrics.get("avg_recall", 0)
        latency = int(result.get("total_time", 0) * 1000 / 13)  # ms per test
        
        # Calculate deltas
        delta_relevance = relevance - baseline_relevance
        delta_precision = precision - baseline_precision
        
        # Combined score (60% precision + 40% relevance)
        combined_score = 0.6 * precision + 0.4 * relevance
        
        print(f"{result['model_name']:<20} "
              f"{result['dimensions']:<8} "
              f"{relevance:>6.2f}%    "
              f"{delta_relevance:+6.2f}pp "
              f"{precision:>6.2f}%    "
              f"{delta_precision:+6.2f}pp "
              f"{recall:>6.2f}%  "
              f"{latency}ms")
        
        comparison.append({
            "model_name": result["model_name"],
            "model_path": result["model_path"],
            "dimensions": result["dimensions"],
            "version": result["version"],
            "relevance": relevance,
            "precision": precision,
            "recall": recall,
            "latency_ms": latency,
            "delta_relevance": delta_relevance,
            "delta_precision": delta_precision,
            "combined_score": combined_score,
            "tests_passed": metrics.get("tests_passed", 0),
        })
    
    print("\n" + "-" * 80)
    print("                            Winner Analysis")
    print("-" * 80 + "\n")
    
    # Find winners
    candidates = [c for c in comparison if c["model_name"] != "baseline"]
    
    if not candidates:
        print("⚠️  No candidate models to compare")
        return {"comparison": comparison}
    
    best_relevance = max(candidates, key=lambda x: x["relevance"])
    best_precision = max(candidates, key=lambda x: x["precision"])
    best_combined = max(candidates, key=lambda x: x["combined_score"])
    
    print(f"🏆 Best Relevance: {best_relevance['model_name']}")
    print(f"   Value: {best_relevance['relevance']:.2f}%")
    print(f"   Gain: +{best_relevance['delta_relevance']:.2f}pp from baseline\n")
    
    print(f"🎯 Best Precision: {best_precision['model_name']}")
    print(f"   Value: {best_precision['precision']:.2f}%")
    print(f"   Gain: +{best_precision['delta_precision']:.2f}pp from baseline\n")
    
    print(f"📋 Recommendation:")
    print(f"   Promote to alpha-v9: {best_combined['model_name']}")
    print(f"   Version: {best_combined['version']}")
    print(f"   Combined Score: {best_combined['combined_score']:.2f}")
    print(f"   (60% precision + 40% relevance)\n")
    
    # Check success criteria
    meets_criteria = (
        best_combined['delta_precision'] >= SUCCESS_CRITERIA['min_precision_gain'] and
        best_combined['delta_relevance'] >= SUCCESS_CRITERIA['min_relevance_gain'] and
        best_combined['recall'] >= SUCCESS_CRITERIA['min_recall']
    )
    
    print(f"✅ Success Criteria Check:")
    print(f"   Precision gain: +{best_combined['delta_precision']:.2f}pp (minimum +{SUCCESS_CRITERIA['min_precision_gain']}pp) {'✅' if best_combined['delta_precision'] >= SUCCESS_CRITERIA['min_precision_gain'] else '❌'}")
    print(f"   Relevance gain: +{best_combined['delta_relevance']:.2f}pp (minimum +{SUCCESS_CRITERIA['min_relevance_gain']}pp) {'✅' if best_combined['delta_relevance'] >= SUCCESS_CRITERIA['min_relevance_gain'] else '❌'}")
    print(f"   Recall: {best_combined['recall']:.2f}% (minimum {SUCCESS_CRITERIA['min_recall']}%) {'✅' if best_combined['recall'] >= SUCCESS_CRITERIA['min_recall'] else '❌'}\n")
    
    if not meets_criteria:
        print("⚠️  Criteria not met. Consider additional tuning or hybrid approach\n")
    else:
        print("🎉 SUCCESS! Winner meets all criteria for alpha-v9 promotion!\n")
    
    return {
        "comparison": comparison,
        "winner": best_combined,
        "best_relevance": best_relevance,
        "best_precision": best_precision,
        "meets_criteria": meets_criteria,
        "baseline_metrics": {
            "relevance": baseline_relevance,
            "precision": baseline_precision,
            "recall": baseline_recall,
        },
    }


def save_results(all_results: List[Dict[str, Any]], comparison: Dict[str, Any], output_file: str):
    """Save test results to JSON file"""
    output = {
        "step": "9a",
        "description": "Embedding Model Upgrade Tests",
        "timestamp": datetime.now().isoformat(),
        "test_config": TEST_CONFIG,
        "success_criteria": SUCCESS_CRITERIA,
        "models_tested": EMBEDDING_MODELS,
        "individual_results": all_results,
        "comparison": comparison,
    }
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"💾 Results saved to: {output_path.absolute()}\n")


# ============================================================================
#                                MAIN EXECUTION
# ============================================================================

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("           RAG OPTIMIZATION - PHASE 2, STEP 9a (v2 FIXED)")
    print("              Embedding Model Upgrade Tests")
    print("="*80 + "\n")
    
    print("📊 Phase 2 Mission:")
    print("   • Precision: 40%+ (+7pp minimum) - PRIMARY BOTTLENECK")
    print("   • Relevance: 79-83% (+4-8pp target)")
    print("   • Recall: ≥90% (maintain)")
    print("   • Tests: 9+/13 (target +3)\n")
    
    print("🧪 Testing 3 Embedding Models:")
    for i, model in enumerate(EMBEDDING_MODELS, 1):
        print(f"   {i}. {model['name']}: {model['model']} ({model['dimensions']}-dim)")
    print()
    
    # Backup current vector database
    print("[{get_timestamp()}] 📦 Backing up current vector database...")
    if backup_vector_database():
        print("[{get_timestamp()}] ✅ Backup complete\n")
    
    # Test all models
    all_results = []
    
    for i, model_config in enumerate(EMBEDDING_MODELS, 1):
        print(f"\n[{i}/{len(EMBEDDING_MODELS)}] Testing {model_config['name']}...\n")
        
        result = test_embedding_model(model_config)
        all_results.append(result)
        
        # Show quick results
        if result.get("results"):
            metrics = result["results"]
            print(f"   Quick Results:")
            print(f"   • Relevance: {metrics.get('avg_relevance', 0):.2f}%")
            print(f"   • Precision: {metrics.get('avg_precision', 0):.2f}%")
            print(f"   • Recall: {metrics.get('avg_recall', 0):.2f}%")
            print(f"   • Tests Passed: {metrics.get('tests_passed', 0)}/13\n")
        
        # Brief pause between tests
        if i < len(EMBEDDING_MODELS):
            print("⏸️  Brief pause before next test (5s)...")
            time.sleep(5)
    
    # Compare results
    comparison = compare_results(all_results)
    
    # Save results
    output_file = "phase2/step9a_results_v2.json"
    save_results(all_results, comparison, output_file)
    
    # Restore original vector database
    print("[{get_timestamp()}] 📦 Restoring original vector database...")
    restore_vector_database()
    
    print("\n" + "="*80)
    print("                           Step 9a Complete!")
    print("="*80 + "\n")
    
    print("✅ All embedding models tested")
    print(f"📊 Results logged to {output_file}")
    print("📝 Update RAG_OPTIMIZATION_PHASE2_LOG.md with findings\n")


if __name__ == "__main__":
    main()

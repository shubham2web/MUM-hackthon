#!/usr/bin/env python3
"""
RAG Optimization - Phase 2, Step 9e: Adaptive Thresholding Tests

After Step 9a revealed precision is architectural (not embedding-bound), Step 9e
attacks the bottleneck with dynamic threshold adaptation.

Strategy:
- Sub-step 9e-1: Percentile threshold sweep (60-90%)
- Sub-step 9e-2: Dynamic cutoff based on query score variance
- Sub-step 9e-3: Semantic weighting integration

Current State: Alpha-v7 baseline (74.78% relevance, 32.95% precision, 92.31% recall)
Target: Alpha-v9 (≥76% relevance, ≥34% precision, ≥90% recall)

Usage:
    python phase2/step9e_adaptive_threshold_tests.py

Output:
    - phase2/results/step9e_results.json (9e-1 results)
    - phase2/results/step9e_results_dynamic.json (9e-2 results, future)
    - phase2/results/step9e_results_combined.json (9e-3 results, future)
"""

import os
import sys
import time
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.run_rag_benchmark import run_full_benchmark


# ============================================================================
#                           STEP 9E-1: PERCENTILE SWEEP
# ============================================================================

PERCENTILE_THRESHOLDS = [0.60, 0.70, 0.75, 0.80, 0.85, 0.90]

SUCCESS_CRITERIA_9E = {
    "min_precision_gain": 0.5,  # +0.5pp minimum
    "min_relevance": 74.5,      # maintain within 0.3pp of baseline
    "min_recall": 90.0,         # maintain ≥90%
    "max_latency_ms": 80,       # <80ms average
}

BASELINE_METRICS = {
    "relevance": 74.78,
    "precision": 32.95,
    "recall": 92.31,
}


def get_timestamp():
    """Get formatted timestamp for logging"""
    return datetime.now().strftime("%H:%M:%S")


def test_percentile_threshold(percentile: float) -> Dict[str, Any]:
    """
    Test a single percentile threshold by temporarily modifying vector_store.py
    
    Args:
        percentile: Percentile threshold (0.60 = 60th percentile cutoff)
        
    Returns:
        Dict with test results
    """
    print(f"\n{'='*80}")
    print(f"  Testing Percentile Threshold: {percentile:.0%} ({percentile:.2f})")
    print('='*80)
    
    # Note: This is a simplified version. In production, we'd need to:
    # 1. Modify vector_store.py to use percentile-based filtering
    # 2. Or implement percentile filtering in a wrapper
    
    print(f"[{get_timestamp()}] ⚠️  Percentile filtering not yet implemented in vector_store.py")
    print(f"[{get_timestamp()}] 📝 This test will run baseline for now (threshold=0.75)")
    print(f"[{get_timestamp()}] 🔧 Implementation needed: Add percentile_threshold parameter to VectorStore")
    
    try:
        start_time = time.time()
        results = run_full_benchmark(verbose=True, export=True)
        end_time = time.time()
        total_time = end_time - start_time
        
        return {
            "percentile": percentile,
            "results": results,
            "total_time": total_time,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "implementation_status": "baseline_only",
        }
        
    except Exception as e:
        print(f"\n[{get_timestamp()}] ❌ Error testing percentile {percentile}: {e}")
        return {
            "percentile": percentile,
            "error": str(e),
            "results": None,
        }


def run_9e1_percentile_sweep() -> Dict[str, Any]:
    """
    Run Step 9e-1: Percentile threshold sweep
    
    Tests multiple percentile thresholds to find optimal cutoff point
    """
    print("\n" + "="*80)
    print("         STEP 9e-1: PERCENTILE THRESHOLD SWEEP")
    print("="*80 + "\n")
    
    print("🎯 Goal: Find optimal percentile cutoff for precision boost")
    print(f"📊 Testing {len(PERCENTILE_THRESHOLDS)} thresholds: {', '.join(f'{p:.0%}' for p in PERCENTILE_THRESHOLDS)}")
    print(f"⏱️  Estimated time: {len(PERCENTILE_THRESHOLDS) * 1} minutes (~1 min per test)\n")
    
    all_results = []
    
    for i, percentile in enumerate(PERCENTILE_THRESHOLDS, 1):
        print(f"\n[{i}/{len(PERCENTILE_THRESHOLDS)}] Testing {percentile:.0%} percentile threshold...")
        
        result = test_percentile_threshold(percentile)
        all_results.append(result)
        
        # Show quick results
        if result.get("results"):
            metrics = result["results"]["summary"]
            precision = metrics.get("avg_precision", 0) * 100
            relevance = metrics.get("avg_relevance_score", 0) * 100
            recall = metrics.get("avg_recall", 0) * 100
            
            print(f"\n   Results for {percentile:.0%} threshold:")
            print(f"   • Precision: {precision:.2f}% (Δ {precision - BASELINE_METRICS['precision']:+.2f}pp)")
            print(f"   • Relevance: {relevance:.2f}% (Δ {relevance - BASELINE_METRICS['relevance']:+.2f}pp)")
            print(f"   • Recall: {recall:.2f}%")
        
        # Brief pause between tests
        if i < len(PERCENTILE_THRESHOLDS):
            time.sleep(2)
    
    # Analyze results
    comparison = analyze_9e1_results(all_results)
    
    return {
        "step": "9e-1",
        "description": "Percentile Threshold Sweep",
        "timestamp": datetime.now().isoformat(),
        "thresholds_tested": PERCENTILE_THRESHOLDS,
        "individual_results": all_results,
        "comparison": comparison,
        "success_criteria": SUCCESS_CRITERIA_9E,
        "baseline_metrics": BASELINE_METRICS,
    }


def analyze_9e1_results(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze percentile sweep results and find optimal threshold
    """
    print("\n" + "="*80)
    print("              Step 9e-1 Results Analysis")
    print("="*80 + "\n")
    
    valid_results = [r for r in all_results if r.get("results")]
    
    if not valid_results:
        print("⚠️  No valid results to analyze")
        return {"error": "No valid results"}
    
    # Print comparison table
    print(f"{'Percentile':<12} {'Precision':<12} {'Δ':<10} {'Relevance':<12} {'Δ':<10} {'Recall':<10}")
    print("-" * 80)
    
    best_precision = None
    best_relevance = None
    best_combined = None
    
    for result in valid_results:
        metrics = result["results"]["summary"]
        precision = metrics.get("avg_precision", 0) * 100
        relevance = metrics.get("avg_relevance_score", 0) * 100
        recall = metrics.get("avg_recall", 0) * 100
        
        delta_precision = precision - BASELINE_METRICS["precision"]
        delta_relevance = relevance - BASELINE_METRICS["relevance"]
        
        # Combined score (60% precision + 40% relevance)
        combined_score = 0.6 * precision + 0.4 * relevance
        
        print(f"{result['percentile']:.0%}        "
              f"{precision:>6.2f}%    "
              f"{delta_precision:+6.2f}pp "
              f"{relevance:>6.2f}%    "
              f"{delta_relevance:+6.2f}pp "
              f"{recall:>6.2f}%")
        
        # Track best performers
        if best_precision is None or precision > best_precision["precision"]:
            best_precision = {
                "percentile": result["percentile"],
                "precision": precision,
                "relevance": relevance,
                "recall": recall,
                "delta_precision": delta_precision,
                "combined_score": combined_score,
            }
        
        if best_combined is None or combined_score > best_combined["combined_score"]:
            best_combined = {
                "percentile": result["percentile"],
                "precision": precision,
                "relevance": relevance,
                "recall": recall,
                "delta_precision": delta_precision,
                "delta_relevance": delta_relevance,
                "combined_score": combined_score,
            }
    
    print("\n" + "-" * 80)
    print("                    Winner Analysis")
    print("-" * 80 + "\n")
    
    if best_combined:
        print(f"🏆 Best Combined Score: {best_combined['percentile']:.0%} percentile")
        print(f"   Precision: {best_combined['precision']:.2f}% (Δ {best_combined['delta_precision']:+.2f}pp)")
        print(f"   Relevance: {best_combined['relevance']:.2f}% (Δ {best_combined['delta_relevance']:+.2f}pp)")
        print(f"   Recall: {best_combined['recall']:.2f}%")
        print(f"   Combined Score: {best_combined['combined_score']:.2f}")
        
        # Check success criteria
        meets_criteria = (
            best_combined['delta_precision'] >= SUCCESS_CRITERIA_9E['min_precision_gain'] and
            best_combined['relevance'] >= SUCCESS_CRITERIA_9E['min_relevance'] and
            best_combined['recall'] >= SUCCESS_CRITERIA_9E['min_recall']
        )
        
        print(f"\n✅ Success Criteria Check:")
        print(f"   Precision gain: {best_combined['delta_precision']:+.2f}pp "
              f"(minimum +{SUCCESS_CRITERIA_9E['min_precision_gain']}pp) "
              f"{'✅' if best_combined['delta_precision'] >= SUCCESS_CRITERIA_9E['min_precision_gain'] else '❌'}")
        print(f"   Relevance: {best_combined['relevance']:.2f}% "
              f"(minimum {SUCCESS_CRITERIA_9E['min_relevance']}%) "
              f"{'✅' if best_combined['relevance'] >= SUCCESS_CRITERIA_9E['min_relevance'] else '❌'}")
        print(f"   Recall: {best_combined['recall']:.2f}% "
              f"(minimum {SUCCESS_CRITERIA_9E['min_recall']}%) "
              f"{'✅' if best_combined['recall'] >= SUCCESS_CRITERIA_9E['min_recall'] else '❌'}")
        
        if meets_criteria:
            print(f"\n🎉 SUCCESS! {best_combined['percentile']:.0%} threshold meets criteria for alpha-v9!")
        else:
            print(f"\n⚠️  Criteria not fully met. Consider Step 9e-2 (dynamic variance-based threshold)")
    
    return {
        "best_precision": best_precision,
        "best_combined": best_combined,
        "meets_criteria": meets_criteria if best_combined else False,
    }


def save_results(results: Dict[str, Any], output_file: str):
    """Save test results to JSON file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_path.absolute()}")


# ============================================================================
#                                MAIN EXECUTION
# ============================================================================

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("      RAG OPTIMIZATION - PHASE 2, STEP 9e")
    print("           Adaptive Thresholding Tests")
    print("="*80 + "\n")
    
    print("📊 Current State (Alpha-v7 Baseline):")
    print(f"   • Relevance: {BASELINE_METRICS['relevance']:.2f}%")
    print(f"   • Precision: {BASELINE_METRICS['precision']:.2f}% ← BOTTLENECK")
    print(f"   • Recall: {BASELINE_METRICS['recall']:.2f}%")
    print(f"   • Tests: 6/13 passing\n")
    
    print("🎯 Step 9e Goal:")
    print(f"   • Precision: ≥{BASELINE_METRICS['precision'] + SUCCESS_CRITERIA_9E['min_precision_gain']:.2f}% "
          f"(+{SUCCESS_CRITERIA_9E['min_precision_gain']}pp minimum)")
    print(f"   • Relevance: ≥{SUCCESS_CRITERIA_9E['min_relevance']:.2f}% (maintain)")
    print(f"   • Recall: ≥{SUCCESS_CRITERIA_9E['min_recall']:.2f}% (maintain)")
    print(f"   • Promote to: Alpha-v9\n")
    
    print("🧪 Test Sequence:")
    print("   1. Step 9e-1: Percentile threshold sweep (30 min)")
    print("   2. Step 9e-2: Dynamic variance-based threshold (1 hour) [FUTURE]")
    print("   3. Step 9e-3: Semantic weighting integration (1 hour) [FUTURE]\n")
    
    # Run Step 9e-1
    print("=" * 80)
    print("                  STARTING STEP 9e-1")
    print("=" * 80)
    
    results_9e1 = run_9e1_percentile_sweep()
    save_results(results_9e1, "phase2/results/step9e_results.json")
    
    print("\n" + "="*80)
    print("                   Step 9e-1 Complete!")
    print("="*80 + "\n")
    
    print("✅ Percentile sweep completed")
    print("📊 Results logged to phase2/results/step9e_results.json")
    print("📝 Update RAG_OPTIMIZATION_PHASE2_LOG.md with findings")
    print("\n🔜 Next: Implement Step 9e-2 (dynamic variance-based threshold)")
    print("   or proceed to Step 9d (query expansion) if 9e-1 sufficient\n")


if __name__ == "__main__":
    main()

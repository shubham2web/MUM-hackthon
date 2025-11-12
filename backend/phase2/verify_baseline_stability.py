#!/usr/bin/env python3
"""
RAG Baseline Stability Verification

This script runs the RAG benchmark multiple times with identical configuration
to verify baseline stability. Required before any parametric optimization experiments.

Success Criteria:
- Relevance variance < 0.1pp across N runs
- All runs show expected baseline ± 0.1pp
- No systematic drift between runs

Usage:
    python phase2/verify_baseline_stability.py --runs 5
    python phase2/verify_baseline_stability.py --runs 10 --expected 74.78

Output:
    - Console: Statistical summary
    - JSON: phase2/results/baseline_stability_report.json
"""

import os
import sys
import time
import json
import argparse
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.run_rag_benchmark import run_full_benchmark


def verify_baseline_stability(
    num_runs: int = 5,
    expected_relevance: float = 74.78,
    variance_threshold: float = 0.1,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run benchmark N times with identical configuration and analyze variance.
    
    Args:
        num_runs: Number of benchmark iterations
        expected_relevance: Expected baseline relevance score (%)
        variance_threshold: Maximum acceptable standard deviation (pp)
        verbose: Print detailed progress
        
    Returns:
        Dict with stability analysis results
    """
    print("=" * 80)
    print("        RAG BASELINE STABILITY VERIFICATION")
    print("=" * 80)
    print()
    print(f"Configuration:")
    print(f"  • Runs: {num_runs}")
    print(f"  • Expected Baseline: {expected_relevance:.2f}%")
    print(f"  • Variance Threshold: {variance_threshold:.2f}pp")
    print(f"  • Test Suite: 13 benchmark tests")
    print()
    print("=" * 80)
    print()
    
    results = []
    run_details = []
    
    for i in range(num_runs):
        print(f"\n[Run {i+1}/{num_runs}] Executing benchmark...")
        print("-" * 80)
        
        start_time = time.time()
        
        try:
            # Run benchmark with consistent settings
            result = run_full_benchmark(verbose=verbose, export=False)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Extract metrics from result['summary'] dict
            summary = result.get('summary', {})
            relevance = summary.get('avg_relevance_score', 0.0) * 100  # Convert 0.7478 → 74.78
            precision = summary.get('avg_precision', 0.0) * 100
            recall = summary.get('avg_recall', 0.0) * 100
            tests_passed = summary.get('passed', 0)
            total_tests = summary.get('total_tests', 0)
            
            results.append(relevance)
            
            run_details.append({
                "run": i + 1,
                "relevance": relevance,
                "precision": precision,
                "recall": recall,
                "tests_passed": tests_passed,
                "total_tests": total_tests,
                "duration_seconds": round(duration, 2),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            print(f"\n✅ Run {i+1} Complete:")
            print(f"   Relevance: {relevance:.2f}%")
            print(f"   Precision: {precision:.2f}%")
            print(f"   Tests Passed: {tests_passed}/{total_tests}")
            print(f"   Duration: {duration:.2f}s")
            
        except Exception as e:
            print(f"\n❌ Run {i+1} Failed: {str(e)}")
            run_details.append({
                "run": i + 1,
                "error": str(e),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            # Don't include failed run in statistics
            continue
    
    print("\n" + "=" * 80)
    print("                    STABILITY ANALYSIS")
    print("=" * 80)
    print()
    
    if len(results) < num_runs:
        print(f"⚠️  Only {len(results)}/{num_runs} runs completed successfully")
        print()
    
    # Calculate statistics
    mean = np.mean(results)
    std_dev = np.std(results, ddof=1)  # Sample standard deviation
    min_val = np.min(results)
    max_val = np.max(results)
    range_val = max_val - min_val
    
    # Deviation from expected baseline
    mean_deviation = mean - expected_relevance
    max_deviation = max(abs(min_val - expected_relevance), 
                        abs(max_val - expected_relevance))
    
    print(f"📊 Relevance Score Statistics:")
    print(f"   Mean:       {mean:.4f}%")
    print(f"   Std Dev:    {std_dev:.4f}pp")
    print(f"   Min:        {min_val:.4f}%")
    print(f"   Max:        {max_val:.4f}%")
    print(f"   Range:      {range_val:.4f}pp")
    print()
    
    print(f"📏 Baseline Deviation:")
    print(f"   Expected:   {expected_relevance:.2f}%")
    print(f"   Mean Dev:   {mean_deviation:+.4f}pp")
    print(f"   Max Dev:    {max_deviation:.4f}pp")
    print()
    
    # Individual run deviations
    print(f"📋 Run-by-Run Deviations:")
    for i, rel in enumerate(results):
        dev = rel - expected_relevance
        status = "✅" if abs(dev) <= variance_threshold else "⚠️"
        print(f"   Run {i+1}: {rel:.4f}% ({dev:+.4f}pp) {status}")
    print()
    
    # Stability verdict
    print("=" * 80)
    print("                    STABILITY VERDICT")
    print("=" * 80)
    print()
    
    is_stable = std_dev < variance_threshold
    is_accurate = abs(mean_deviation) < variance_threshold
    all_within_tolerance = all(abs(r - expected_relevance) <= variance_threshold 
                                for r in results)
    
    print(f"✓ Variance Check: ", end="")
    if is_stable:
        print(f"✅ PASS - StdDev {std_dev:.4f}pp < {variance_threshold:.2f}pp threshold")
    else:
        print(f"❌ FAIL - StdDev {std_dev:.4f}pp ≥ {variance_threshold:.2f}pp threshold")
    
    print(f"✓ Accuracy Check: ", end="")
    if is_accurate:
        print(f"✅ PASS - Mean deviation {mean_deviation:+.4f}pp within ±{variance_threshold:.2f}pp")
    else:
        print(f"❌ FAIL - Mean deviation {mean_deviation:+.4f}pp exceeds ±{variance_threshold:.2f}pp")
    
    print(f"✓ Consistency Check: ", end="")
    if all_within_tolerance:
        print(f"✅ PASS - All runs within ±{variance_threshold:.2f}pp of expected")
    else:
        print(f"❌ FAIL - Some runs exceed ±{variance_threshold:.2f}pp tolerance")
    
    print()
    
    overall_stable = is_stable and is_accurate and all_within_tolerance
    
    if overall_stable:
        print("🎯 OVERALL VERDICT: ✅ BASELINE STABLE")
        print()
        print("   Baseline is deterministic and suitable for parametric optimization.")
        print("   Step 9e (adaptive thresholding) can proceed with valid measurements.")
    else:
        print("🚨 OVERALL VERDICT: ❌ BASELINE UNSTABLE")
        print()
        print("   ⚠️  Parametric optimization experiments (Step 9e) INVALID until fixed.")
        print()
        print("   Recommended Actions:")
        print("   1. Verify FAISS index type (exact vs approximate search)")
        print("   2. Check for state carryover between runs")
        print("   3. Add per-query score logging to identify variance sources")
        print("   4. Consider pivoting to Step 9d (query expansion) while fixing stability")
    
    print()
    print("=" * 80)
    
    # Prepare results summary
    summary = {
        "metadata": {
            "test_date": datetime.now().strftime("%Y-%m-%d"),
            "test_time": datetime.now().strftime("%H:%M:%S"),
            "num_runs_attempted": num_runs,
            "num_runs_completed": len(results),
            "expected_baseline": expected_relevance,
            "variance_threshold": variance_threshold
        },
        "statistics": {
            "mean_relevance": round(mean, 4),
            "std_dev": round(std_dev, 4),
            "min_relevance": round(min_val, 4),
            "max_relevance": round(max_val, 4),
            "range": round(range_val, 4),
            "mean_deviation": round(mean_deviation, 4),
            "max_deviation": round(max_deviation, 4)
        },
        "checks": {
            "variance_check": "PASS" if is_stable else "FAIL",
            "accuracy_check": "PASS" if is_accurate else "FAIL",
            "consistency_check": "PASS" if all_within_tolerance else "FAIL",
            "overall_stable": overall_stable
        },
        "individual_runs": run_details,
        "raw_scores": [round(r, 4) for r in results]
    }
    
    return summary


def save_results(summary: Dict[str, Any], output_dir: str = "phase2/results"):
    """Save stability analysis to JSON"""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"baseline_stability_{timestamp}.json")
    
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"💾 Results saved to: {output_file}")
    print()
    
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Verify RAG baseline stability before parametric optimization"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of benchmark iterations (default: 5)"
    )
    parser.add_argument(
        "--expected",
        type=float,
        default=74.78,
        help="Expected baseline relevance %% (default: 74.78)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="Max acceptable variance in pp (default: 0.1)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed benchmark output"
    )
    
    args = parser.parse_args()
    
    summary = verify_baseline_stability(
        num_runs=args.runs,
        expected_relevance=args.expected,
        variance_threshold=args.threshold,
        verbose=not args.quiet
    )
    
    output_file = save_results(summary)
    
    # Exit code for CI/CD integration
    if summary["checks"]["overall_stable"]:
        print("✅ Baseline stable - parametric optimization approved")
        sys.exit(0)
    else:
        print("❌ Baseline unstable - parametric optimization blocked")
        sys.exit(1)


if __name__ == "__main__":
    main()

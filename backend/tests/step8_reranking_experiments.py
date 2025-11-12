"""
Step 8: Cross-Encoder Reranking Experiments
===========================================

Test lightweight cross-encoder reranking for precision improvement.

Baseline: alpha-v7 (α=0.97 + 7e-1 normalization) = 74.78% relevance, 32.95% precision
Goal: +3-5pp precision via semantic reranking
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


def test_reranking_mode(enabled: bool, fusion_weight: float, label: str):
    """Test a specific reranking configuration"""
    import subprocess
    
    # Set environment variables
    env = os.environ.copy()
    env["ENABLE_RERANKING"] = "true" if enabled else "false"
    env["RERANKER_FUSION_WEIGHT"] = str(fusion_weight)
    
    print(f"\n{'='*70}")
    print(f"Testing: {label}")
    print(f"  Reranking: {enabled}")
    print(f"  Fusion Weight: {fusion_weight} (vector={fusion_weight}, CE={1-fusion_weight})")
    print(f"{'='*70}")
    
    # Run benchmark
    cmd = [sys.executable, str(backend_dir / "tests" / "run_rag_benchmark.py")]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            env=env,
            timeout=120
        )
        
        # Extract metrics from output
        output = result.stdout
        
        # Parse key metrics
        import re
        relevance_match = re.search(r'Average Relevance:\s+([\d.]+)%', output)
        precision_match = re.search(r'Average Precision:\s+([\d.]+)%', output)
        recall_match = re.search(r'Average Recall:\s+([\d.]+)%', output)
        tests_match = re.search(r'Tests Passed:\s+(\d+)', output)
        
        if relevance_match:
            relevance = float(relevance_match.group(1))
            precision = float(precision_match.group(1)) if precision_match else 0
            recall = float(recall_match.group(1)) if recall_match else 0
            tests = int(tests_match.group(1)) if tests_match else 0
            
            print(f"\n📊 Results:")
            print(f"  Relevance:  {relevance:.2f}%")
            print(f"  Precision:  {precision:.2f}%")
            print(f"  Recall:     {recall:.2f}%")
            print(f"  Tests:      {tests}/13")
            
            return {
                "label": label,
                "enabled": enabled,
                "fusion_weight": fusion_weight,
                "relevance": relevance,
                "precision": precision,
                "recall": recall,
                "tests": tests
            }
        else:
            print("⚠️  Could not extract metrics from output")
            return None
            
    except subprocess.TimeoutExpired:
        print("⚠️  Benchmark timed out")
        return None
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return None


def main():
    """Run Step 8 experiments"""
    print("="*70)
    print("STEP 8: CROSS-ENCODER RERANKING EXPERIMENTS")
    print("="*70)
    print()
    print("Baseline: alpha-v7 (74.78% relevance, 32.95% precision)")
    print("Goal: +3-5pp precision via reranking")
    print()
    
    # Test configurations
    experiments = [
        # Baseline
        (False, 0.7, "Baseline (No Reranking)"),
        
        # Reranking with different fusion weights
        (True, 0.5, "Reranking 50/50 (Vector=50%, CE=50%)"),
        (True, 0.6, "Reranking 60/40 (Vector=60%, CE=40%)"),
        (True, 0.7, "Reranking 70/30 (Vector=70%, CE=30%)"),
        (True, 0.8, "Reranking 80/20 (Vector=80%, CE=20%)"),
    ]
    
    results = []
    
    for enabled, fusion_weight, label in experiments:
        result = test_reranking_mode(enabled, fusion_weight, label)
        if result:
            results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print()
    print(f"{'Configuration':<40} {'Relevance':>10} {'Precision':>10} {'Tests':>8}")
    print("-"*70)
    
    baseline = results[0] if results else None
    for r in results:
        delta_rel = f"({r['relevance'] - baseline['relevance']:+.2f})" if baseline else ""
        delta_prec = f"({r['precision'] - baseline['precision']:+.2f})" if baseline else ""
        print(f"{r['label']:<40} {r['relevance']:>8.2f}% {delta_rel:>8} {r['precision']:>8.2f}% {delta_prec:>8} {r['tests']:>3}/13")
    
    print()
    
    # Find best configuration
    if results:
        best = max(results, key=lambda x: x['relevance'])
        print(f"🏆 Best Configuration: {best['label']}")
        print(f"   Relevance:  {best['relevance']:.2f}%")
        print(f"   Precision:  {best['precision']:.2f}%")
        print(f"   Tests:      {best['tests']}/13")


if __name__ == "__main__":
    main()

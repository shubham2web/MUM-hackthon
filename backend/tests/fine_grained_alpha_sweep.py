"""
Fine-Grained Alpha Sweep - Step 5
Test alpha values around the current optimum (0.85) to find subtle improvements
"""

import subprocess
import json
import os
import re
from datetime import datetime
from pathlib import Path

# Test alpha values around current optimum
ALPHA_VALUES = [0.83, 0.85, 0.87, 0.90]

# Known baseline for comparison
BASELINE_ALPHA = 0.85
BASELINE_RELEVANCE = 72.95

def run_benchmark(alpha):
    """Run benchmark with specified alpha value"""
    print(f"\n{'='*70}")
    print(f"Testing alpha = {alpha:.2f} ({int(alpha*100)}% vector, {int((1-alpha)*100)}% lexical)")
    print(f"{'='*70}")
    
    # Set environment variable
    env = os.environ.copy()
    env['HYBRID_VECTOR_WEIGHT'] = str(alpha)
    env['PYTHONIOENCODING'] = 'utf-8'
    
    # Run benchmark
    print("Running benchmark...")
    result = subprocess.run(
        ['python', 'tests/run_rag_benchmark.py'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        env=env
    )
    
    # Parse output
    output = (result.stdout or '') + (result.stderr or '')
    
    # Extract metrics
    metrics = {
        'alpha': alpha,
        'vector_weight': alpha,
        'lexical_weight': 1 - alpha,
        'relevance': None,
        'precision': None,
        'recall': None,
        'f1': None,
        'tests_passed': None
    }
    
    # Parse relevance
    relevance_match = re.search(r'Average Relevance:\s+([\d.]+)%', output)
    if relevance_match:
        metrics['relevance'] = float(relevance_match.group(1))
    
    # Parse precision
    precision_match = re.search(r'Average Precision:\s+([\d.]+)%', output)
    if precision_match:
        metrics['precision'] = float(precision_match.group(1))
    
    # Parse recall
    recall_match = re.search(r'Average Recall:\s+([\d.]+)%', output)
    if recall_match:
        metrics['recall'] = float(recall_match.group(1))
    
    # Parse F1
    f1_match = re.search(r'Average F1 Score:\s+([\d.]+)%', output)
    if f1_match:
        metrics['f1'] = float(f1_match.group(1))
    
    # Parse tests passed
    tests_match = re.search(r'Tests Passed:\s+(\d+)', output)
    if tests_match:
        metrics['tests_passed'] = int(tests_match.group(1))
    
    return metrics

def main():
    """Run fine-grained alpha sweep"""
    
    print("\n" + "="*70)
    print("FINE-GRAINED ALPHA SWEEP - STEP 5")
    print("="*70)
    print(f"Testing alpha values: {ALPHA_VALUES}")
    print(f"Baseline: alpha={BASELINE_ALPHA} → {BASELINE_RELEVANCE}% relevance")
    print("="*70 + "\n")
    
    results = []
    
    for alpha in ALPHA_VALUES:
        try:
            metrics = run_benchmark(alpha)
            results.append(metrics)
            
            # Print immediate results
            if metrics['relevance'] is not None:
                delta = metrics['relevance'] - BASELINE_RELEVANCE
                delta_str = f"{delta:+.2f}%"
                
                print(f"\nResults for alpha={alpha:.2f}:")
                print(f"   Relevance:    {metrics['relevance']:.2f}%")
                print(f"   Precision:    {metrics.get('precision', 0):.2f}%")
                print(f"   Recall:       {metrics.get('recall', 0):.2f}%")
                print(f"   F1 Score:     {metrics.get('f1', 0):.2f}%")
                print(f"   Tests Passed: {metrics.get('tests_passed', 0)}/13")
                print(f"   Delta:        {delta_str}")
            else:
                print(f"\n   ERROR: Could not parse metrics for alpha={alpha:.2f}")
        
        except Exception as e:
            print(f"\n   ERROR running alpha={alpha:.2f}: {e}")
            results.append({
                'alpha': alpha,
                'error': str(e)
            })
    
    # Save results to JSON
    results_file = Path(__file__).parent / 'fine_grained_alpha_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")
    
    # Generate summary table
    print("\n" + "="*70)
    print("FINE-GRAINED ALPHA SWEEP SUMMARY")
    print("="*70)
    print(f"{'Alpha':<8} {'Vector':<8} {'Lexical':<8} {'Relevance':<12} {'Precision':<10} {'F1':<10} {'Tests':<8}")
    print("-"*70)
    
    best_alpha = BASELINE_ALPHA
    best_relevance = BASELINE_RELEVANCE
    
    for r in results:
        if 'error' in r:
            print(f"{r['alpha']:<8.2f} ERROR: {r['error']}")
            continue
        
        alpha = r['alpha']
        vector = f"{int(alpha*100)}%"
        lexical = f"{int((1-alpha)*100)}%"
        relevance = r.get('relevance', 0)
        precision = r.get('precision', 0)
        f1 = r.get('f1', 0)
        tests = r.get('tests_passed', 0)
        
        # Track best
        if relevance > best_relevance:
            best_relevance = relevance
            best_alpha = alpha
        
        # Format delta
        if alpha == BASELINE_ALPHA:
            delta_str = "(BASELINE)"
        else:
            delta = relevance - BASELINE_RELEVANCE
            if delta > 0:
                delta_str = f"(+{delta:.2f}%)"
            else:
                delta_str = f"({delta:.2f}%)"
        
        print(f"{alpha:<8.2f} {vector:<8} {lexical:<8} {relevance:<7.2f}% {delta_str:<12} {precision:<7.2f}% {f1:<7.2f}% {tests:<2}/13")
    
    print("\n" + "="*70)
    print("BEST CONFIGURATION:")
    print(f"   Alpha:        {best_alpha:.2f}")
    print(f"   Relevance:    {best_relevance:.2f}%")
    
    if best_alpha != BASELINE_ALPHA:
        improvement = best_relevance - BASELINE_RELEVANCE
        print(f"   Improvement:  +{improvement:.2f}% vs baseline")
        print(f"\nRECOMMENDATION: Update hybrid_vector_weight to {best_alpha:.2f}")
    else:
        print(f"   Status:       Current alpha={BASELINE_ALPHA:.2f} is optimal")
        print(f"\nRECOMMENDATION: Keep existing alpha={BASELINE_ALPHA:.2f}")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

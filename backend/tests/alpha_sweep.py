"""
Alpha Sweep Experiment - Find optimal vector/lexical weight balance.

Tests alpha values: 0.70, 0.75, 0.80, 0.85
Baseline (alpha=0.75): 71.78% relevance, 5/13 tests
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import subprocess
import json
from typing import Dict, List
import tempfile

# Alpha values to test
ALPHA_VALUES = [0.70, 0.75, 0.80, 0.85]

def run_benchmark(alpha: float) -> Dict:
    """Run benchmark with specified alpha value"""
    # Set environment variable for alpha
    env = os.environ.copy()
    env['HYBRID_VECTOR_WEIGHT'] = str(alpha)
    
    result = subprocess.run(
        ['python', 'tests/run_rag_benchmark.py'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',  # Ignore unicode errors
        cwd=os.path.join(os.path.dirname(__file__), '..'),
        env=env
    )
    
    # Parse output for metrics
    output = (result.stdout or '') + (result.stderr or '')
    
    metrics = {
        'relevance': 0.0,
        'precision': 0.0,
        'recall': 0.0,
        'f1': 0.0,
        'tests_passed': 0
    }
    
    for line in output.split('\n'):
        if 'Average Relevance:' in line:
            metrics['relevance'] = float(line.split(':')[1].strip().rstrip('%'))
        elif 'Average Precision:' in line:
            metrics['precision'] = float(line.split(':')[1].strip().rstrip('%'))
        elif 'Average Recall:' in line:
            metrics['recall'] = float(line.split(':')[1].strip().rstrip('%'))
        elif 'Average F1 Score:' in line:
            metrics['f1'] = float(line.split(':')[1].strip().rstrip('%'))
        elif 'Tests Passed:' in line:
            metrics['tests_passed'] = int(line.split(':')[1].strip().split('/')[0])
    
    return metrics

def main():
    print("="*70)
    print("ALPHA SWEEP EXPERIMENT")
    print("="*70)
    print(f"Testing alpha values: {ALPHA_VALUES}")
    print(f"Baseline (alpha=0.75): 71.78% relevance, 5/13 tests")
    print("="*70)
    print()
    
    results = []
    
    for alpha in ALPHA_VALUES:
        print(f"\n{'='*70}")
        print(f"Testing alpha = {alpha} (vector={alpha:.0%}, lexical={1-alpha:.0%})")
        print(f"{'='*70}")
        
        # Run benchmark with this alpha
        print("Running benchmark...")
        metrics = run_benchmark(alpha)
        
        # Store results
        result = {
            'alpha': alpha,
            'vector_weight': alpha,
            'lexical_weight': 1 - alpha,
            **metrics
        }
        results.append(result)
        
        # Print results
        print(f"\nResults for alpha={alpha}:")
        print(f"   Relevance:    {metrics['relevance']:.2f}%")
        print(f"   Precision:    {metrics['precision']:.2f}%")
        print(f"   Recall:       {metrics['recall']:.2f}%")
        print(f"   F1 Score:     {metrics['f1']:.2f}%")
        print(f"   Tests Passed: {metrics['tests_passed']}/13")
        
        # Compare to baseline
        baseline_relevance = 71.78
        delta = metrics['relevance'] - baseline_relevance
        if delta > 0:
            print(f"   Delta:        +{delta:.2f}% BETTER")
        elif delta < 0:
            print(f"   Delta:        {delta:.2f}% WORSE")
        else:
            print(f"   Delta:        {delta:.2f}% (same)")
    
    # Summary
    print(f"\n\n{'='*70}")
    print("ALPHA SWEEP SUMMARY")
    print(f"{'='*70}")
    print(f"{'Alpha':<8} {'Vector':<8} {'Lexical':<8} {'Relevance':<12} {'Precision':<12} {'F1':<10} {'Tests':<8}")
    print(f"{'-'*70}")
    
    for r in results:
        print(f"{r['alpha']:<8.2f} {r['vector_weight']:<8.0%} {r['lexical_weight']:<8.0%} "
              f"{r['relevance']:<12.2f}% {r['precision']:<12.2f}% {r['f1']:<10.2f}% {r['tests_passed']:<8}/13")
    
    # Find best
    best = max(results, key=lambda x: (x['relevance'], x['f1'], x['tests_passed']))
    print(f"\nBEST CONFIGURATION:")
    print(f"   Alpha:        {best['alpha']}")
    print(f"   Relevance:    {best['relevance']:.2f}%")
    print(f"   Tests Passed: {best['tests_passed']}/13")
    print(f"   F1 Score:     {best['f1']:.2f}%")
    
    # Save results
    results_file = os.path.join(os.path.dirname(__file__), 'alpha_sweep_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")
    
    # Recommendation
    if best['alpha'] == 0.75:
        print(f"\nRECOMMENDATION: Keep baseline alpha=0.75 (no improvement found)")
    else:
        print(f"\nRECOMMENDATION: Switch to alpha={best['alpha']} for +{best['relevance']-71.78:.2f}% gain")

if __name__ == '__main__':
    main()

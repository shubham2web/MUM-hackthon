"""
Step 7b: Alpha × BM25 Grid Search
Test combinations of (alpha, lexical_weight) to find optimal balance
Captures tradeoffs between semantic and lexical signals
"""

import subprocess
import json
import os
import csv
import itertools
from datetime import datetime
from pathlib import Path
import re

# Grid parameters - Step 7b: Fine-grained validation around α=0.95
ALPHAS = [0.93, 0.94, 0.95, 0.96, 0.97]  # 5-point grid: α=0.95 ± 0.02 (Δ=0.01)
# Note: lexical_weight = 1 - alpha, so we're just testing different alphas
# If your system has separate BM25 weighting, adjust accordingly

BASELINE_ALPHA = 0.95  # alpha-v4 baseline
BASELINE_RELEVANCE = 74.07  # alpha-v4 relevance

def run_benchmark_with_config(alpha: float) -> dict:
    """Run benchmark with specified configuration"""
    lexical_weight = 1 - alpha
    
    print(f"\n{'='*70}")
    print(f"Testing: alpha={alpha:.2f} ({int(alpha*100)}% semantic, {int(lexical_weight*100)}% lexical)")
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
        'lexical_weight': lexical_weight,
        'relevance': None,
        'tests_passed': None,
        'precision': None,
        'recall': None,
        'f1': None,
        'timestamp': datetime.now().isoformat()
    }
    
    # Parse with regex
    if match := re.search(r'Average Relevance:\s+([\d.]+)%', output):
        metrics['relevance'] = float(match.group(1))
    if match := re.search(r'Tests Passed:\s+(\d+)', output):
        metrics['tests_passed'] = int(match.group(1))
    if match := re.search(r'Average Precision:\s+([\d.]+)%', output):
        metrics['precision'] = float(match.group(1))
    if match := re.search(r'Average Recall:\s+([\d.]+)%', output):
        metrics['recall'] = float(match.group(1))
    if match := re.search(r'Average F1 Score:\s+([\d.]+)%', output):
        metrics['f1'] = float(match.group(1))
    
    return metrics

def main():
    """Run alpha × lexical grid search"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = log_dir / f"grid_alpha_lexical_{timestamp}.csv"
    json_file = log_dir / f"grid_alpha_lexical_{timestamp}.json"
    
    print("\n" + "="*70)
    print("ALPHA x LEXICAL GRID SEARCH - STEP 7b")
    print("="*70)
    print(f"Testing alphas: {ALPHAS}")
    print(f"Baseline: alpha={BASELINE_ALPHA} -> {BASELINE_RELEVANCE}% relevance")
    print(f"Goal: Find optimal semantic/lexical balance")
    print("="*70 + "\n")
    
    results = []
    
    # Run grid search
    for alpha in ALPHAS:
        try:
            metrics = run_benchmark_with_config(alpha)
            results.append(metrics)
            
            # Print immediate results
            if metrics['relevance'] is not None:
                delta = metrics['relevance'] - BASELINE_RELEVANCE
                delta_str = f"{delta:+.2f}%"
                
                print(f"\nResults for alpha={alpha:.2f}:")
                print(f"   Semantic:     {int(alpha*100)}%")
                print(f"   Lexical:      {int((1-alpha)*100)}%")
                print(f"   Relevance:    {metrics['relevance']:.2f}% ({delta_str})")
                print(f"   Tests Passed: {metrics['tests_passed']}/13")
                print(f"   Precision:    {metrics['precision']:.2f}%")
                print(f"   Recall:       {metrics['recall']:.2f}%")
                print(f"   F1 Score:     {metrics['f1']:.2f}%")
            else:
                print(f"\nERROR: Could not parse metrics for alpha={alpha:.2f}")
        
        except Exception as e:
            print(f"\nERROR running alpha={alpha:.2f}: {e}")
            results.append({
                'alpha': alpha,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    # Save results
    # JSON
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 JSON results saved to: {json_file}")
    
    # CSV
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['alpha', 'vector_weight', 'lexical_weight', 'relevance', 'tests_passed', 
                        'precision', 'recall', 'f1', 'delta_vs_baseline', 'timestamp'])
        
        for r in results:
            if 'error' not in r and r['relevance'] is not None:
                delta = r['relevance'] - BASELINE_RELEVANCE
                writer.writerow([
                    r['alpha'],
                    r['vector_weight'],
                    r['lexical_weight'],
                    r['relevance'],
                    r['tests_passed'],
                    r['precision'],
                    r['recall'],
                    r['f1'],
                    f"{delta:+.2f}",
                    r['timestamp']
                ])
    
    print(f"💾 CSV results saved to: {csv_file}")
    
    # Generate summary
    print("\n" + "="*70)
    print("GRID SEARCH SUMMARY")
    print("="*70)
    print(f"{'Alpha':<8} {'Semantic':<10} {'Lexical':<10} {'Relevance':<12} {'Delta':<12} {'Tests':<8}")
    print("-"*70)
    
    best_alpha = BASELINE_ALPHA
    best_relevance = BASELINE_RELEVANCE
    
    for r in results:
        if 'error' in r or r['relevance'] is None:
            print(f"{r['alpha']:<8.2f} ERROR")
            continue
        
        alpha = r['alpha']
        relevance = r['relevance']
        delta = relevance - BASELINE_RELEVANCE
        tests = r['tests_passed']
        
        # Track best
        if relevance > best_relevance:
            best_relevance = relevance
            best_alpha = alpha
        
        # Format delta
        if alpha == BASELINE_ALPHA:
            delta_str = "(BASE)"
        else:
            delta_str = f"({delta:+.2f}%)"
        
        print(f"{alpha:<8.2f} {int(alpha*100):>3}%       {int((1-alpha)*100):>3}%        "
              f"{relevance:<7.2f}% {delta_str:<12} {tests:<2}/13")
    
    print("\n" + "="*70)
    print("BEST CONFIGURATION:")
    print(f"   Alpha:        {best_alpha:.2f}")
    print(f"   Semantic:     {int(best_alpha*100)}%")
    print(f"   Lexical:      {int((1-best_alpha)*100)}%")
    print(f"   Relevance:    {best_relevance:.2f}%")
    
    if best_alpha != BASELINE_ALPHA:
        improvement = best_relevance - BASELINE_RELEVANCE
        print(f"   Improvement:  +{improvement:.2f}% vs baseline")
        print(f"\nRECOMMENDATION: Update hybrid_vector_weight to {best_alpha:.2f}")
    else:
        print(f"   Status:       Baseline alpha={BASELINE_ALPHA:.2f} remains optimal")
        print(f"\nRECOMMENDATION: Keep hybrid_vector_weight at {BASELINE_ALPHA:.2f}")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

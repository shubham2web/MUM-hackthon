"""
Step 7a: Higher-Alpha Micro-Sweep
Test alpha values [0.90, 0.91, 0.92, 0.93, 0.94, 0.95] to find peak performance
Monotonic trend from Step 5 suggests potential for further gains
"""

import subprocess
import json
import os
import csv
from datetime import datetime
from pathlib import Path
import re

# Test range: extend beyond current optimum (0.90)
ALPHAS = [0.90, 0.91, 0.92, 0.93, 0.94, 0.95]
BASELINE_ALPHA = 0.90
BASELINE_RELEVANCE = 73.51

def run_benchmark_with_alpha(alpha: float) -> dict:
    """Run benchmark with specified alpha value"""
    print(f"\n{'='*70}")
    print(f"Testing alpha = {alpha:.2f} ({int(alpha*100)}% semantic, {int((1-alpha)*100)}% lexical)")
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
    """Run higher-alpha micro-sweep"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = log_dir / f"alpha_micro_sweep_{timestamp}.csv"
    json_file = log_dir / f"alpha_micro_sweep_{timestamp}.json"
    
    print("\n" + "="*70)
    print("HIGHER-ALPHA MICRO-SWEEP - STEP 7a")
    print("="*70)
    print(f"Testing alphas: {ALPHAS}")
    print(f"Baseline: α={BASELINE_ALPHA} → {BASELINE_RELEVANCE}% relevance")
    print(f"Hypothesis: Monotonic trend continues beyond 0.90")
    print("="*70 + "\n")
    
    results = []
    
    # Run sweep
    for alpha in ALPHAS:
        try:
            metrics = run_benchmark_with_alpha(alpha)
            results.append(metrics)
            
            # Print immediate results
            if metrics['relevance'] is not None:
                delta = metrics['relevance'] - BASELINE_RELEVANCE
                delta_str = f"{delta:+.2f}%"
                
                print(f"\n✅ Results for α={alpha:.2f}:")
                print(f"   Relevance:    {metrics['relevance']:.2f}% ({delta_str})")
                print(f"   Tests Passed: {metrics['tests_passed']}/13")
                print(f"   Precision:    {metrics['precision']:.2f}%")
                print(f"   Recall:       {metrics['recall']:.2f}%")
                print(f"   F1 Score:     {metrics['f1']:.2f}%")
            else:
                print(f"\n❌ ERROR: Could not parse metrics for α={alpha:.2f}")
        
        except Exception as e:
            print(f"\n❌ ERROR running α={alpha:.2f}: {e}")
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
        writer.writerow(['alpha', 'relevance', 'tests_passed', 'precision', 'recall', 'f1', 'delta_vs_baseline', 'timestamp'])
        
        for r in results:
            if 'error' not in r and r['relevance'] is not None:
                delta = r['relevance'] - BASELINE_RELEVANCE
                writer.writerow([
                    r['alpha'],
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
    print("MICRO-SWEEP SUMMARY")
    print("="*70)
    print(f"{'Alpha':<8} {'Relevance':<12} {'Delta':<12} {'Tests':<8} {'Precision':<10} {'Recall':<10}")
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
        precision = r['precision']
        recall = r['recall']
        
        # Track best
        if relevance > best_relevance:
            best_relevance = relevance
            best_alpha = alpha
        
        # Format delta
        if alpha == BASELINE_ALPHA:
            delta_str = "(BASELINE)"
        else:
            delta_str = f"({delta:+.2f}%)"
        
        print(f"{alpha:<8.2f} {relevance:<7.2f}% {delta_str:<12} {tests:<2}/13   {precision:<7.2f}% {recall:<7.2f}%")
    
    print("\n" + "="*70)
    print("BEST CONFIGURATION:")
    print(f"   Alpha:        {best_alpha:.2f}")
    print(f"   Relevance:    {best_relevance:.2f}%")
    
    if best_alpha != BASELINE_ALPHA:
        improvement = best_relevance - BASELINE_RELEVANCE
        print(f"   Improvement:  +{improvement:.2f}% vs baseline")
        print(f"\n✅ RECOMMENDATION: Update hybrid_vector_weight to {best_alpha:.2f}")
        print(f"\n📝 Next step:")
        print(f"   python rag_version_control.py save \\")
        print(f"     --version alpha-v4 \\")
        print(f"     --relevance {best_relevance:.2f} \\")
        print(f"     --alpha {best_alpha:.2f} \\")
        print(f'     --notes "Step 7a: Higher-alpha micro-sweep found {best_alpha:.2f} optimal"')
    else:
        print(f"   Status:       Baseline α={BASELINE_ALPHA:.2f} remains optimal")
        print(f"\n✅ RECOMMENDATION: Keep hybrid_vector_weight at {BASELINE_ALPHA:.2f}")
        print(f"   Peak likely reached - consider other optimizations")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

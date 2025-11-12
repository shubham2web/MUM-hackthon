"""
Step 7d: Threshold Tuning - Similarity Cutoff & Top-K Optimization
Goal: Improve precision from 32.95% by filtering low-confidence results
Strategy: Test combinations of similarity threshold and top-k limits
"""

import subprocess
import json
import os
import csv
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, List, Tuple

# Test parameters
SIMILARITY_THRESHOLDS = [0.65, 0.70, 0.75, 0.80, 0.85]  # Similarity score cutoffs
TOP_K_VALUES = [3, 5, 10]  # Number of results to retrieve

# Baseline (alpha-v5)
BASELINE_ALPHA = 0.97
BASELINE_RELEVANCE = 74.30
BASELINE_PRECISION = 32.95
BASELINE_TOP_K = 5  # Current default

def run_benchmark_with_threshold(threshold: float, top_k: int) -> dict:
    """Run benchmark with specified threshold and top-k configuration"""
    
    print(f"\n{'='*70}")
    print(f"Testing: threshold={threshold:.2f}, top_k={top_k}")
    print(f"{'='*70}")
    
    # Set environment variables for configuration
    env = os.environ.copy()
    env['HYBRID_VECTOR_WEIGHT'] = str(BASELINE_ALPHA)  # Keep alpha at 0.97
    env['SIMILARITY_THRESHOLD'] = str(threshold)
    env['TOP_K'] = str(top_k)
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
        'threshold': threshold,
        'top_k': top_k,
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

def phase_1_threshold_sweep() -> List[dict]:
    """Phase 1: Test similarity thresholds at baseline top_k=5"""
    print("\n" + "="*70)
    print("PHASE 1: SIMILARITY THRESHOLD SWEEP")
    print("="*70)
    print(f"Testing thresholds: {SIMILARITY_THRESHOLDS}")
    print(f"Fixed top_k: {BASELINE_TOP_K}")
    print(f"Goal: Find optimal similarity cutoff")
    print("="*70 + "\n")
    
    results = []
    for threshold in SIMILARITY_THRESHOLDS:
        try:
            metrics = run_benchmark_with_threshold(threshold, BASELINE_TOP_K)
            results.append(metrics)
            
            # Print immediate results
            if metrics['relevance'] is not None:
                delta_rel = metrics['relevance'] - BASELINE_RELEVANCE
                delta_prec = metrics['precision'] - BASELINE_PRECISION
                
                print(f"\nResults for threshold={threshold:.2f}:")
                print(f"   Relevance:  {metrics['relevance']:.2f}% ({delta_rel:+.2f}%)")
                print(f"   Precision:  {metrics['precision']:.2f}% ({delta_prec:+.2f}%)")
                print(f"   Recall:     {metrics['recall']:.2f}%")
                print(f"   F1 Score:   {metrics['f1']:.2f}%")
                print(f"   Tests:      {metrics['tests_passed']}/13")
            else:
                print(f"\nERROR: Could not parse metrics for threshold={threshold:.2f}")
        
        except Exception as e:
            print(f"\nERROR running threshold={threshold:.2f}: {e}")
            results.append({
                'threshold': threshold,
                'top_k': BASELINE_TOP_K,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    return results

def phase_2_topk_sweep(best_threshold: float) -> List[dict]:
    """Phase 2: Test top-k values at optimal threshold"""
    print("\n" + "="*70)
    print("PHASE 2: TOP-K SWEEP")
    print("="*70)
    print(f"Testing top_k: {TOP_K_VALUES}")
    print(f"Fixed threshold: {best_threshold:.2f}")
    print(f"Goal: Find optimal result count")
    print("="*70 + "\n")
    
    results = []
    for top_k in TOP_K_VALUES:
        try:
            metrics = run_benchmark_with_threshold(best_threshold, top_k)
            results.append(metrics)
            
            # Print immediate results
            if metrics['relevance'] is not None:
                delta_rel = metrics['relevance'] - BASELINE_RELEVANCE
                delta_prec = metrics['precision'] - BASELINE_PRECISION
                
                print(f"\nResults for top_k={top_k}:")
                print(f"   Relevance:  {metrics['relevance']:.2f}% ({delta_rel:+.2f}%)")
                print(f"   Precision:  {metrics['precision']:.2f}% ({delta_prec:+.2f}%)")
                print(f"   Recall:     {metrics['recall']:.2f}%")
                print(f"   F1 Score:   {metrics['f1']:.2f}%")
                print(f"   Tests:      {metrics['tests_passed']}/13")
            else:
                print(f"\nERROR: Could not parse metrics for top_k={top_k}")
        
        except Exception as e:
            print(f"\nERROR running top_k={top_k}: {e}")
            results.append({
                'threshold': best_threshold,
                'top_k': top_k,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    return results

def save_results(phase: str, results: List[dict]):
    """Save results to JSON and CSV"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = log_dir / f"threshold_tuning_{phase}_{timestamp}.json"
    csv_file = log_dir / f"threshold_tuning_{phase}_{timestamp}.csv"
    
    # Save JSON
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nJSON saved: {json_file}")
    
    # Save CSV
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['threshold', 'top_k', 'relevance', 'precision', 'recall', 
                        'f1', 'tests_passed', 'delta_relevance', 'delta_precision', 'timestamp'])
        
        for r in results:
            if 'error' not in r and r['relevance'] is not None:
                delta_rel = r['relevance'] - BASELINE_RELEVANCE
                delta_prec = r['precision'] - BASELINE_PRECISION
                writer.writerow([
                    r['threshold'],
                    r['top_k'],
                    r['relevance'],
                    r['precision'],
                    r['recall'],
                    r['f1'],
                    r['tests_passed'],
                    f"{delta_rel:+.2f}",
                    f"{delta_prec:+.2f}",
                    r['timestamp']
                ])
    
    print(f"CSV saved: {csv_file}")

def find_best_config(results: List[dict]) -> Tuple[float, int, dict]:
    """Find best configuration by F1 score (precision-recall balance)"""
    best_f1 = 0
    best_config = None
    
    for r in results:
        if 'error' in r or r['f1'] is None:
            continue
        
        if r['f1'] > best_f1:
            best_f1 = r['f1']
            best_config = r
    
    if best_config:
        return best_config['threshold'], best_config['top_k'], best_config
    return None, None, None

def main():
    """Run Step 7d: Threshold Tuning"""
    
    print("\n" + "="*70)
    print("STEP 7d: THRESHOLD TUNING")
    print("="*70)
    print(f"Baseline: alpha={BASELINE_ALPHA}, relevance={BASELINE_RELEVANCE}%")
    print(f"Current precision: {BASELINE_PRECISION}% (LOW - needs improvement)")
    print(f"Current recall: 92.31% (HIGH - maintain this)")
    print(f"Goal: Improve precision without hurting recall/relevance")
    print("="*70 + "\n")
    
    # Phase 1: Threshold sweep
    print("\n[Starting Phase 1: Similarity Threshold Sweep]")
    phase1_results = phase_1_threshold_sweep()
    save_results("phase1_threshold", phase1_results)
    
    # Find best threshold from Phase 1
    best_threshold, _, best_phase1 = find_best_config(phase1_results)
    
    if best_threshold is None:
        print("\nERROR: No valid results from Phase 1. Aborting.")
        return
    
    print("\n" + "="*70)
    print("PHASE 1 COMPLETE - BEST THRESHOLD FOUND")
    print("="*70)
    print(f"Best threshold: {best_threshold:.2f}")
    print(f"Relevance:  {best_phase1['relevance']:.2f}%")
    print(f"Precision:  {best_phase1['precision']:.2f}%")
    print(f"Recall:     {best_phase1['recall']:.2f}%")
    print(f"F1 Score:   {best_phase1['f1']:.2f}%")
    print("="*70 + "\n")
    
    # Phase 2: Top-K sweep at optimal threshold
    print("\n[Starting Phase 2: Top-K Sweep]")
    phase2_results = phase_2_topk_sweep(best_threshold)
    save_results("phase2_topk", phase2_results)
    
    # Find overall best configuration
    all_results = phase1_results + phase2_results
    best_threshold, best_topk, best_overall = find_best_config(all_results)
    
    print("\n" + "="*70)
    print("STEP 7d COMPLETE - OPTIMAL CONFIGURATION FOUND")
    print("="*70)
    print(f"Best threshold:  {best_threshold:.2f}")
    print(f"Best top_k:      {best_topk}")
    print(f"Relevance:       {best_overall['relevance']:.2f}% ({best_overall['relevance'] - BASELINE_RELEVANCE:+.2f}%)")
    print(f"Precision:       {best_overall['precision']:.2f}% ({best_overall['precision'] - BASELINE_PRECISION:+.2f}%)")
    print(f"Recall:          {best_overall['recall']:.2f}%")
    print(f"F1 Score:        {best_overall['f1']:.2f}%")
    print(f"Tests Passed:    {best_overall['tests_passed']}/13")
    
    # Recommendation
    if best_overall['precision'] > BASELINE_PRECISION:
        improvement = best_overall['precision'] - BASELINE_PRECISION
        print(f"\nRECOMMENDATION: Apply threshold={best_threshold:.2f}, top_k={best_topk}")
        print(f"   Precision improvement: +{improvement:.2f}pp")
        print(f"   Save as alpha-v6")
    else:
        print(f"\nNO IMPROVEMENT: Current baseline remains optimal")
        print(f"   Precision unchanged at {BASELINE_PRECISION}%")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

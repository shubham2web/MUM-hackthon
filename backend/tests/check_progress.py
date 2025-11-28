"""
Quick progress checker - shows current status of tuning experiments
"""
import os
import json
import glob
from datetime import datetime

def check_latest_results():
    """Check for most recent results files"""
    
    # Check for tuning results
    tuning_pattern = os.path.join(os.path.dirname(__file__), "tuning_results_*.json")
    tuning_files = glob.glob(tuning_pattern)
    
    # Check for benchmark results (to see individual experiment progress)
    benchmark_pattern = os.path.join(os.path.dirname(__file__), "rag_benchmark_results_*.json")
    benchmark_files = glob.glob(benchmark_pattern)
    
    print("\n" + "="*70)
    print("TUNING PROGRESS CHECK")
    print("="*70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    if tuning_files:
        latest_tuning = max(tuning_files, key=os.path.getmtime)
        print(f"Found tuning results: {os.path.basename(latest_tuning)}")
        
        try:
            with open(latest_tuning, 'r') as f:
                results = json.load(f)
            
            print(f"\nCompleted Experiments: {len(results.get('experiments', []))}/8\n")
            
            for exp in results.get('experiments', []):
                name = exp['name']
                rel = exp['metrics']['relevance']
                prec = exp['metrics']['precision']
                rec = exp['metrics']['recall']
                
                status = "TARGET MET!" if rel >= 85.0 else ""
                print(f"  {name:40s} | Rel: {rel:5.1f}% | Prec: {prec:5.1f}% | Rec: {rec:5.1f}% {status}")
            
            # Show best so far
            if results.get('experiments'):
                best = max(results['experiments'], key=lambda x: x['metrics']['relevance'])
                print(f"\n  Best so far: {best['name']} with {best['metrics']['relevance']:.1f}% relevance")
        
        except Exception as e:
            print(f"Error reading results: {e}")
    
    else:
        print("No tuning_results_*.json files found yet.")
        
        # Show recent benchmark activity
        if benchmark_files:
            recent = sorted(benchmark_files, key=os.path.getmtime)[-3:]
            print(f"\nRecent benchmark runs (last 3):")
            for f in recent:
                mtime = datetime.fromtimestamp(os.path.getmtime(f))
                print(f"  {os.path.basename(f)} - {mtime.strftime('%H:%M:%S')}")
            print("\nExperiments are running... results will appear when complete.")
        else:
            print("\nNo activity detected yet. Waiting for experiments to start...")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    check_latest_results()

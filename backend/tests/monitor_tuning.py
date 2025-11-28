"""
Monitoring script for tuning experiments progress
Checks for output and results periodically
"""
import os
import time
import json
import glob
from datetime import datetime

def check_progress():
    """Check for tuning results files and show progress"""
    results_pattern = os.path.join(
        os.path.dirname(__file__), 
        "tuning_results_*.json"
    )
    
    result_files = glob.glob(results_pattern)
    
    if not result_files:
        return None
    
    # Get most recent results file
    latest_file = max(result_files, key=os.path.getmtime)
    
    try:
        with open(latest_file, 'r') as f:
            results = json.load(f)
        return results
    except:
        return None

def format_progress(results):
    """Format results for display"""
    if not results:
        return "⏳ Waiting for results... Experiments are running.\n"
    
    output = []
    output.append("\n" + "="*70)
    output.append("📊 TUNING PROGRESS UPDATE")
    output.append("="*70)
    output.append(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
    output.append(f"Experiments completed: {len(results.get('experiments', []))}/8")
    output.append("")
    
    # Show completed experiments
    if 'experiments' in results:
        output.append("Completed Experiments:")
        output.append("-"*70)
        
        for exp in results['experiments']:
            name = exp['name']
            relevance = exp['metrics']['relevance']
            precision = exp['metrics']['precision']
            recall = exp['metrics']['recall']
            
            status = "🎯 TARGET MET!" if relevance >= 0.85 else "📊"
            
            output.append(f"{status} {name}")
            output.append(f"   Relevance: {relevance:.1%} | Precision: {precision:.1%} | Recall: {recall:.1%}")
            output.append("")
    
    output.append("="*70)
    return "\n".join(output)

def monitor_loop(interval=30, max_checks=60):
    """
    Monitor tuning progress
    
    Args:
        interval: Seconds between checks
        max_checks: Maximum number of checks before stopping
    """
    print("\n🔍 TUNING MONITOR STARTED")
    print("="*70)
    print(f"Checking for progress every {interval} seconds")
    print("Press Ctrl+C to stop monitoring")
    print("="*70)
    
    checks = 0
    last_exp_count = 0
    
    try:
        while checks < max_checks:
            results = check_progress()
            
            if results:
                current_exp_count = len(results.get('experiments', []))
                
                # Show update if new experiments completed
                if current_exp_count > last_exp_count:
                    print(format_progress(results))
                    last_exp_count = current_exp_count
                    
                    # Check if all 8 experiments are done
                    if current_exp_count >= 8:
                        print("\n✅ ALL EXPERIMENTS COMPLETED!")
                        print("\n🏆 FINAL RESULTS:")
                        
                        # Show ranked results
                        if 'ranked_experiments' in results:
                            print("\nExperiments Ranked by Relevance:")
                            print("-"*70)
                            for i, exp in enumerate(results['ranked_experiments'][:3], 1):
                                print(f"{i}. {exp['name']}: {exp['metrics']['relevance']:.1%}")
                        
                        print("\n📁 Full results saved to:")
                        results_pattern = os.path.join(
                            os.path.dirname(__file__), 
                            "tuning_results_*.json"
                        )
                        result_files = glob.glob(results_pattern)
                        if result_files:
                            latest = max(result_files, key=os.path.getmtime)
                            print(f"   {latest}")
                        
                        break
                elif checks % 4 == 0:  # Show "still running" every 2 minutes
                    print(f"⏳ Still running... ({current_exp_count}/8 completed) - {datetime.now().strftime('%H:%M:%S')}")
            else:
                if checks % 4 == 0:
                    print(f"⏳ Waiting for first experiment to complete... - {datetime.now().strftime('%H:%M:%S')}")
            
            time.sleep(interval)
            checks += 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Monitoring stopped by user")
        print("Note: Tuning experiments are still running in the background")
    
    print("\n" + "="*70)
    print("Monitor stopped. Check tuning_results_*.json for final results.")
    print("="*70 + "\n")

if __name__ == "__main__":
    # Monitor every 30 seconds, up to 60 checks (30 minutes)
    monitor_loop(interval=30, max_checks=60)

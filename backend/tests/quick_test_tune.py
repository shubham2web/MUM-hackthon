"""
Quick test to verify tuning framework works with a single experiment
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.run_tuning_experiments import RerankerTuner

if __name__ == "__main__":
    print("\n🧪 QUICK TUNING TEST")
    print("=" * 70)
    print("Testing framework with single experiment (Baseline)")
    print("=" * 70 + "\n")
    
    tuner = RerankerTuner()
    
    # Run just the baseline experiment
    print(f"Running experiment: Baseline (No Re-ranking)")
    result = tuner.run_experiment(
        name="Baseline (No Re-ranking)",
        vector_weight=1.0,
        cross_encoder_weight=0.0,
        score_threshold=0.0,
        normalization="minmax"
    )
    
    print("\n" + "=" * 70)
    print("📊 RESULT")
    print("=" * 70)
    print(f"Relevance Score: {result['relevance']:.1%}")
    print(f"Precision:       {result['precision']:.1%}")
    print(f"Recall:          {result['recall']:.1%}")
    print(f"F1 Score:        {result['f1']:.1%}")
    print(f"Pass Rate:       {result['pass_rate']:.1%}")
    print("=" * 70 + "\n")
    
    print("✅ Framework test completed successfully!")

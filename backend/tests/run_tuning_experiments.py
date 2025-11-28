"""
Cross-Encoder Tuning Framework

Systematic experiments to find optimal re-ranking configuration:
1. Pure cross-encoder scores
2. Hybrid scoring (vector + cross-encoder blends)
3. Score thresholding
4. Different normalization strategies

Goal: Boost precision from 32.95% to 60-75% while maintaining 92.31% recall
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple
import json

import sys
import os

# Fix Windows UTF-8 encoding issues
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.vector_store import RetrievalResult
from tests.run_rag_benchmark import run_full_benchmark


class RerankerTuner:
    """Experiments to optimize re-ranker configuration"""
    
    def __init__(self):
        self.results = []
    
    def run_experiment(
        self,
        name: str,
        vector_weight: float,
        cross_encoder_weight: float,
        score_threshold: float = 0.0,
        normalization: str = "minmax"
    ) -> Dict:
        """
        Run single tuning experiment.
        
        Args:
            name: Experiment name
            vector_weight: Weight for vector similarity score (0-1)
            cross_encoder_weight: Weight for cross-encoder score (0-1)
            score_threshold: Minimum score to include result (0-1)
            normalization: How to normalize cross-encoder scores
            
        Returns:
            Experiment results dictionary
        """
        print(f"\n{'='*70}")
        print(f"EXPERIMENT: {name}")
        print(f"{'='*70}")
        print(f"Vector Weight:        {vector_weight:.2f}")
        print(f"Cross-Encoder Weight: {cross_encoder_weight:.2f}")
        print(f"Score Threshold:      {score_threshold:.2f}")
        print(f"Normalization:        {normalization}")
        print(f"{'='*70}\n")
        
        # Store experiment config in environment for reranker to use
        os.environ['RERANKER_VECTOR_WEIGHT'] = str(vector_weight)
        os.environ['RERANKER_CE_WEIGHT'] = str(cross_encoder_weight)
        os.environ['RERANKER_THRESHOLD'] = str(score_threshold)
        os.environ['RERANKER_NORMALIZATION'] = normalization
        
        # Run benchmark
        results = run_full_benchmark(verbose=False, export=False)
        
        if results:
            experiment_result = {
                'name': name,
                'config': {
                    'vector_weight': vector_weight,
                    'cross_encoder_weight': cross_encoder_weight,
                    'score_threshold': score_threshold,
                    'normalization': normalization
                },
                'metrics': {
                    'relevance': results['summary']['avg_relevance_score'] * 100,  # Convert to percentage
                    'precision': results['summary']['avg_precision'] * 100,
                    'recall': results['summary']['avg_recall'] * 100,
                    'f1': results['summary']['avg_f1'] * 100,
                    'tests_passed': results['summary']['passed'],
                    'pass_rate': results['summary']['pass_rate'] * 100
                },
                'timestamp': datetime.now().isoformat()
            }
            
            self.results.append(experiment_result)
            
            print(f"\n📊 RESULTS:")
            print(f"  Relevance:  {experiment_result['metrics']['relevance']:.1f}%")
            print(f"  Precision:  {experiment_result['metrics']['precision']:.1f}%")
            print(f"  Recall:     {experiment_result['metrics']['recall']:.1f}%")
            print(f"  F1 Score:   {experiment_result['metrics']['f1']:.1f}%")
            print(f"  Tests Passed: {experiment_result['metrics']['tests_passed']}/13")
            
            return experiment_result
        
        return None
    
    def run_tuning_suite(self):
        """Run complete tuning experiment suite"""
        
        print("\n" + "="*70)
        print("CROSS-ENCODER TUNING SUITE")
        print("="*70)
        print("Running systematic experiments to optimize re-ranking")
        print("Target: 85%+ relevance, 60%+ precision, maintain 90%+ recall")
        print("="*70 + "\n")
        
        experiments = [
            # Baseline: No re-ranking
            {
                'name': 'Baseline (No Re-ranking)',
                'vector_weight': 1.0,
                'cross_encoder_weight': 0.0,
                'score_threshold': 0.0,
                'normalization': 'minmax'
            },
            
            # Test 1: Pure cross-encoder
            {
                'name': 'Pure Cross-Encoder',
                'vector_weight': 0.0,
                'cross_encoder_weight': 1.0,
                'score_threshold': 0.0,
                'normalization': 'minmax'
            },
            
            # Test 2a: Hybrid - Cross-encoder dominant
            {
                'name': 'Hybrid: CE Dominant (80/20)',
                'vector_weight': 0.2,
                'cross_encoder_weight': 0.8,
                'score_threshold': 0.0,
                'normalization': 'minmax'
            },
            
            # Test 2b: Hybrid - Balanced
            {
                'name': 'Hybrid: Balanced (50/50)',
                'vector_weight': 0.5,
                'cross_encoder_weight': 0.5,
                'score_threshold': 0.0,
                'normalization': 'minmax'
            },
            
            # Test 2c: Hybrid - Vector dominant
            {
                'name': 'Hybrid: Vector Dominant (60/40)',
                'vector_weight': 0.6,
                'cross_encoder_weight': 0.4,
                'score_threshold': 0.0,
                'normalization': 'minmax'
            },
            
            # Test 3a: Best hybrid + threshold
            {
                'name': 'Hybrid (80/20) + Threshold 0.5',
                'vector_weight': 0.2,
                'cross_encoder_weight': 0.8,
                'score_threshold': 0.5,
                'normalization': 'minmax'
            },
            
            # Test 3b: Best hybrid + stricter threshold
            {
                'name': 'Hybrid (80/20) + Threshold 0.7',
                'vector_weight': 0.2,
                'cross_encoder_weight': 0.8,
                'score_threshold': 0.7,
                'normalization': 'minmax'
            },
            
            # Test 4: Different normalization
            {
                'name': 'Hybrid (80/20) + Sigmoid Norm',
                'vector_weight': 0.2,
                'cross_encoder_weight': 0.8,
                'score_threshold': 0.0,
                'normalization': 'sigmoid'
            },
        ]
        
        # Run all experiments
        for exp_config in experiments:
            try:
                self.run_experiment(**exp_config)
            except Exception as e:
                print(f"❌ Experiment failed: {e}")
                continue
        
        # Analyze results
        self.analyze_results()
    
    def analyze_results(self):
        """Analyze and compare all experiment results"""
        
        print("\n" + "="*70)
        print("TUNING RESULTS ANALYSIS")
        print("="*70 + "\n")
        
        if not self.results:
            print("No results to analyze")
            return
        
        # Sort by relevance score
        sorted_results = sorted(
            self.results,
            key=lambda x: x['metrics']['relevance'],
            reverse=True
        )
        
        print("📊 EXPERIMENTS RANKED BY RELEVANCE:\n")
        print(f"{'Rank':<6} {'Experiment':<35} {'Relevance':<12} {'Precision':<12} {'Recall':<10} {'F1':<10}")
        print("-" * 95)
        
        for i, result in enumerate(sorted_results, 1):
            name = result['name'][:33]
            rel = result['metrics']['relevance']
            prec = result['metrics']['precision']
            rec = result['metrics']['recall']
            f1 = result['metrics']['f1']
            
            # Highlight if meets target
            marker = "🎯" if rel >= 85.0 else "  "
            
            print(f"{marker} {i:<4} {name:<35} {rel:>6.1f}%      {prec:>6.1f}%      {rec:>6.1f}%   {f1:>6.1f}%")
        
        # Best result
        best = sorted_results[0]
        print("\n" + "="*70)
        print("🏆 BEST CONFIGURATION")
        print("="*70)
        print(f"Experiment: {best['name']}")
        print(f"\nConfiguration:")
        print(f"  Vector Weight:        {best['config']['vector_weight']:.2f}")
        print(f"  Cross-Encoder Weight: {best['config']['cross_encoder_weight']:.2f}")
        print(f"  Score Threshold:      {best['config']['score_threshold']:.2f}")
        print(f"  Normalization:        {best['config']['normalization']}")
        print(f"\nPerformance:")
        print(f"  Relevance:  {best['metrics']['relevance']:.1f}%  (Target: 85%+)")
        print(f"  Precision:  {best['metrics']['precision']:.1f}%  (Target: 60%+)")
        print(f"  Recall:     {best['metrics']['recall']:.1f}%  (Target: 90%+)")
        print(f"  F1 Score:   {best['metrics']['f1']:.1f}%")
        print(f"  Pass Rate:  {best['metrics']['pass_rate']:.1f}%")
        
        # Check if target met
        if best['metrics']['relevance'] >= 85.0:
            print("\n✅ TARGET MET! System ready for production!")
        else:
            gap = 85.0 - best['metrics']['relevance']
            print(f"\n⚠️  Gap to target: {gap:.1f} percentage points")
            print("   Recommendations:")
            print("   - Try more aggressive cross-encoder weights (0.9+)")
            print("   - Test higher thresholds")
            print("   - Consider different cross-encoder model")
        
        print("="*70 + "\n")
        
        # Save results
        output_file = f"tuning_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"📄 Full results saved to: {output_file}\n")


def main():
    """Run tuning suite"""
    
    print("\n🎯 CROSS-ENCODER RE-RANKER TUNING")
    print("Goal: Find optimal configuration for 85%+ relevance\n")
    
    tuner = RerankerTuner()
    tuner.run_tuning_suite()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Tuning interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Tuning failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

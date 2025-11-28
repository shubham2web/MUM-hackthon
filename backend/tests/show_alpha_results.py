import json

results = json.load(open('tests/fine_grained_alpha_results.json'))

print("\n" + "="*70)
print("FINE-GRAINED ALPHA SWEEP RESULTS - STEP 5")
print("="*70)
print(f"{'Alpha':<8} {'Vector':<8} {'Lexical':<8} {'Relevance':<12} {'Delta':<12} {'Tests':<8}")
print("-"*70)

baseline = 72.95
best_alpha = 0.85
best_relevance = baseline

for r in results:
    alpha = r['alpha']
    rel = r['relevance']
    delta = rel - baseline
    tests = r['tests_passed']
    
    if rel > best_relevance:
        best_relevance = rel
        best_alpha = alpha
    
    delta_str = f"{delta:+.2f}%"
    if alpha == 0.85:
        delta_str += " (BASE)"
    
    print(f"{alpha:<8.2f} {int(alpha*100):>3}%     {int((1-alpha)*100):>3}%      {rel:>6.2f}%     {delta_str:<12} {tests}/13")

print("\n" + "="*70)
print("BEST CONFIGURATION:")
print(f"   Alpha:        {best_alpha:.2f} ({int(best_alpha*100)}% semantic, {int((1-best_alpha)*100)}% lexical)")
print(f"   Relevance:    {best_relevance:.2f}%")

improvement = best_relevance - baseline
if improvement > 0:
    print(f"   Improvement:  +{improvement:.2f}% vs baseline (α=0.85)")
    print(f"\n✅ RECOMMENDATION: Update hybrid_vector_weight to {best_alpha:.2f}")
else:
    print(f"   Status:       Baseline α=0.85 remains optimal")
    print(f"\n✅ RECOMMENDATION: Keep hybrid_vector_weight at 0.85")

print("="*70 + "\n")

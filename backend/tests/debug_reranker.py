"""
Debug script to understand why cross-encoder models aren't differentiating.

Tests:
1. What scores does each model return for clearly relevant vs irrelevant pairs?
2. Are scores in expected range?
3. Does the model actually work?
"""
from sentence_transformers import CrossEncoder

def test_model(model_name: str):
    """Test a cross-encoder model with simple examples."""
    print(f"\n{'='*70}")
    print(f"Testing: {model_name}")
    print('='*70)
    
    try:
        model = CrossEncoder(model_name)
        
        # Test cases: query + (relevant doc, irrelevant doc)
        query = "What are the health benefits of exercise?"
        
        pairs = [
            (query, "Regular exercise improves cardiovascular health, strengthens muscles, and boosts mental well-being."),  # VERY RELEVANT
            (query, "Exercise has numerous health benefits including weight management and disease prevention."),  # RELEVANT
            (query, "The weather today is sunny with a chance of rain in the afternoon."),  # IRRELEVANT
            (query, "Python is a popular programming language used for data science and web development."),  # IRRELEVANT
        ]
        
        scores = model.predict(pairs)
        
        print("\nQuery:", query)
        print("\nScores:")
        for (q, doc), score in zip(pairs, scores):
            relevance = "✅ RELEVANT" if score > 0.5 else "❌ IRRELEVANT"
            print(f"  {score:.4f} {relevance}: {doc[:80]}...")
        
        # Check score differentiation
        score_range = max(scores) - min(scores)
        print(f"\nScore Range: {score_range:.4f}")
        if score_range < 0.1:
            print("⚠️  WARNING: Very low score differentiation! Model may not be working correctly.")
        elif score_range > 0.5:
            print("✅ Good score differentiation")
        else:
            print("⚠️  Moderate score differentiation")
            
        return scores
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

if __name__ == "__main__":
    print("\n" + "="*70)
    print("CROSS-ENCODER MODEL DIAGNOSTICS")
    print("="*70)
    
    # Test all three models
    models = [
        "cross-encoder/ms-marco-MiniLM-L-6-v2",  # MS-MARCO (web search)
        "BAAI/bge-reranker-v2-m3",  # BGE reranker
        "cross-encoder/stsb-roberta-large",  # STS-B (semantic similarity)
    ]
    
    results = {}
    for model_name in models:
        scores = test_model(model_name)
        if scores is not None:
            results[model_name] = scores
    
    # Compare models
    if len(results) > 1:
        print("\n" + "="*70)
        print("MODEL COMPARISON")
        print("="*70)
        
        for model_name, scores in results.items():
            score_range = max(scores) - min(scores)
            print(f"\n{model_name}:")
            print(f"  Range: {score_range:.4f}")
            print(f"  Max:   {max(scores):.4f}")
            print(f"  Min:   {min(scores):.4f}")

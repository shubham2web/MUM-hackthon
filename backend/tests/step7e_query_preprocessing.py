"""
Step 7e: Query Preprocessing (Semantic Normalization Layer)
==========================================================

Goal: Improve semantic hit rate without penalizing recall by cleaning
      and enriching input queries BEFORE retrieval.

Strategy:
    7e-1: Basic normalization (lowercase, punctuation, numbers)
    7e-2: Lemmatization/stemming
    7e-3: Synonym expansion via embedding neighbors
    7e-4: Contextual re-weighting (boost key nouns/verbs)
    7e-5: Combined pipeline

Expected: +2-4pp relevance gain without recall loss
Baseline: alpha-v5 (α=0.97, 74.30% relevance, 32.95% precision)
"""

import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from memory.vector_store import VectorStore


# Test cases from original benchmark
TEST_CASES = [
    ("What are the main features of our product?", "product_features.txt"),
    ("How do I reset my password?", "password_reset_guide.txt"),
    ("What is our return policy?", "return_policy.txt"),
    ("Tell me about pricing plans", "pricing_plans.txt"),
    ("How to contact customer support?", "contact_support.txt"),
    ("What are the system requirements?", "system_requirements.txt"),
    ("How do I upgrade my account?", "account_upgrade.txt"),
    ("What payment methods do you accept?", "payment_methods.txt"),
    ("Is there a mobile app available?", "mobile_app_info.txt"),
    ("How to export my data?", "data_export.txt"),
    ("What are the security features?", "security_features.txt"),
    ("How do I cancel my subscription?", "subscription_cancellation.txt"),
    ("What is included in the free trial?", "free_trial_info.txt"),
]


class QueryPreprocessor:
    """Query preprocessing pipeline with multiple normalization stages"""
    
    def __init__(self, mode="baseline"):
        """
        mode: 
            - "baseline": No preprocessing (current behavior)
            - "7e-1": Basic normalization
            - "7e-2": + Lemmatization
            - "7e-3": + Synonym expansion
            - "7e-4": + Contextual re-weighting
            - "7e-5": Full pipeline
        """
        self.mode = mode
        
        # Import NLP libraries only when needed
        if mode in ["7e-2", "7e-3", "7e-4", "7e-5"]:
            try:
                import nltk
                from nltk.stem import WordNetLemmatizer
                from nltk.corpus import wordnet
                
                # Download required NLTK data
                for resource in ['punkt', 'wordnet', 'averaged_perceptron_tagger', 'omw-1.4']:
                    try:
                        nltk.data.find(f'tokenizers/{resource}')
                    except LookupError:
                        nltk.download(resource, quiet=True)
                
                self.lemmatizer = WordNetLemmatizer()
                self.wordnet = wordnet
                self.nltk = nltk
            except ImportError:
                print("⚠️  NLTK not installed. Install with: pip install nltk")
                self.mode = "7e-1"  # Fallback to basic mode
    
    def preprocess(self, query: str) -> str:
        """Apply preprocessing based on mode"""
        if self.mode == "baseline":
            return query
        
        # 7e-1: Basic normalization
        processed = self._basic_normalize(query)
        
        if self.mode == "7e-1":
            return processed
        
        # 7e-2: Lemmatization
        if self.mode in ["7e-2", "7e-3", "7e-4", "7e-5"]:
            processed = self._lemmatize(processed)
        
        if self.mode == "7e-2":
            return processed
        
        # 7e-3: Synonym expansion
        if self.mode in ["7e-3", "7e-4", "7e-5"]:
            processed = self._expand_synonyms(processed)
        
        if self.mode == "7e-3":
            return processed
        
        # 7e-4: Contextual re-weighting
        if self.mode in ["7e-4", "7e-5"]:
            processed = self._contextual_reweight(processed)
        
        return processed
    
    def _basic_normalize(self, query: str) -> str:
        """7e-1: Lowercase, strip punctuation, normalize numbers"""
        # Lowercase
        query = query.lower()
        
        # Normalize numbers (replace specific numbers with generic token)
        query = re.sub(r'\d+', '<NUM>', query)
        
        # Remove excessive punctuation but keep sentence structure
        query = re.sub(r'[?!]{2,}', '?', query)
        query = re.sub(r'\.{2,}', '.', query)
        
        # Strip leading/trailing whitespace
        query = query.strip()
        
        return query
    
    def _lemmatize(self, query: str) -> str:
        """7e-2: Lemmatize words to base forms"""
        # Tokenize
        tokens = self.nltk.word_tokenize(query)
        
        # POS tagging for better lemmatization
        pos_tags = self.nltk.pos_tag(tokens)
        
        # Lemmatize each token
        lemmatized = []
        for word, pos in pos_tags:
            # Convert POS tag to WordNet format
            wn_pos = self._get_wordnet_pos(pos)
            if wn_pos:
                lemmatized.append(self.lemmatizer.lemmatize(word, pos=wn_pos))
            else:
                lemmatized.append(self.lemmatizer.lemmatize(word))
        
        return ' '.join(lemmatized)
    
    def _get_wordnet_pos(self, treebank_tag: str) -> str:
        """Convert treebank POS tag to WordNet POS tag"""
        if treebank_tag.startswith('J'):
            return self.wordnet.ADJ
        elif treebank_tag.startswith('V'):
            return self.wordnet.VERB
        elif treebank_tag.startswith('N'):
            return self.wordnet.NOUN
        elif treebank_tag.startswith('R'):
            return self.wordnet.ADV
        return None
    
    def _expand_synonyms(self, query: str) -> str:
        """7e-3: Add relevant synonyms for key terms"""
        tokens = self.nltk.word_tokenize(query)
        pos_tags = self.nltk.pos_tag(tokens)
        
        expanded = []
        for word, pos in pos_tags:
            expanded.append(word)
            
            # Only expand nouns and verbs
            if pos.startswith('N') or pos.startswith('V'):
                synsets = self.wordnet.synsets(word)
                if synsets:
                    # Get the most common synonym
                    synonyms = set()
                    for syn in synsets[:2]:  # Top 2 synsets
                        for lemma in syn.lemmas()[:2]:  # Top 2 lemmas
                            synonym = lemma.name().replace('_', ' ')
                            if synonym.lower() != word.lower():
                                synonyms.add(synonym)
                    
                    # Add max 2 synonyms
                    for syn in list(synonyms)[:2]:
                        expanded.append(syn)
        
        return ' '.join(expanded)
    
    def _contextual_reweight(self, query: str) -> str:
        """7e-4: Boost key nouns and verbs by repetition"""
        tokens = self.nltk.word_tokenize(query)
        pos_tags = self.nltk.pos_tag(tokens)
        
        reweighted = []
        for word, pos in pos_tags:
            reweighted.append(word)
            
            # Boost important terms (nouns, verbs, adjectives)
            if pos.startswith('N') or pos.startswith('V') or pos.startswith('J'):
                # Repeat key terms to increase semantic weight
                reweighted.append(word)
        
        return ' '.join(reweighted)


def run_benchmark(preprocessor: QueryPreprocessor, vector_store: VectorStore) -> dict:
    """Run full benchmark with given preprocessor"""
    correct = 0
    total_tests = len(TEST_CASES)
    
    results = []
    for query, expected_doc in TEST_CASES:
        # Preprocess query
        processed_query = preprocessor.preprocess(query)
        
        # Retrieve (use search method, not retrieve)
        retrieved_results = vector_store.search(processed_query, top_k=4)
        
        # Check if expected doc is in top results
        is_correct = any(expected_doc in result.metadata.get("source", "") for result in retrieved_results)
        if is_correct:
            correct += 1
        
        results.append({
            "query": query,
            "processed_query": processed_query,
            "expected": expected_doc,
            "retrieved": [result.metadata.get("source", "") for result in retrieved_results],
            "correct": is_correct
        })
    
    relevance = (correct / total_tests) * 100
    return {
        "relevance": relevance,
        "correct": correct,
        "total": total_tests,
        "results": results
    }


def extract_metrics_from_benchmark(output: str) -> dict:
    """Extract metrics from benchmark output"""
    metrics = {}
    
    # Extract relevance
    rel_match = re.search(r'Average Relevance Score:\s+([\d.]+)%', output)
    if rel_match:
        metrics['relevance'] = float(rel_match.group(1))
    
    # Extract precision
    prec_match = re.search(r'Precision:\s+([\d.]+)%', output)
    if prec_match:
        metrics['precision'] = float(prec_match.group(1))
    
    # Extract recall
    rec_match = re.search(r'Recall:\s+([\d.]+)%', output)
    if rec_match:
        metrics['recall'] = float(rec_match.group(1))
    
    # Extract F1
    f1_match = re.search(r'F1 Score:\s+([\d.]+)%', output)
    if f1_match:
        metrics['f1'] = float(f1_match.group(1))
    
    # Extract tests passed
    tests_match = re.search(r'Tests Passed:\s+(\d+)/(\d+)', output)
    if tests_match:
        metrics['tests_passed'] = f"{tests_match.group(1)}/{tests_match.group(2)}"
    
    return metrics


def main():
    """Run Step 7e query preprocessing experiments"""
    print("=" * 70)
    print("Step 7e: Query Preprocessing Experiments")
    print("=" * 70)
    print()
    
    # Initialize vector store and populate test data
    print("📁 Initializing vector store and loading test data...")
    vector_store = VectorStore()
    
    # Populate test data if empty
    try:
        from tests.populate_test_data import populate_test_data
        populate_test_data(vector_store)
        print("✅ Test data loaded")
    except Exception as e:
        print(f"⚠️  Could not load test data: {e}")
        print("   Continuing with existing data...")
    print()
    
    # Baseline (alpha-v5)
    baseline_metrics = {
        "relevance": 74.30,
        "precision": 32.95,
        "recall": 92.31,
        "f1": 47.51,
        "tests_passed": "6/13"
    }
    
    print("📊 Baseline (alpha-v5):")
    print(f"   Relevance: {baseline_metrics['relevance']}%")
    print(f"   Precision: {baseline_metrics['precision']}%")
    print(f"   Recall: {baseline_metrics['recall']}%")
    print(f"   F1: {baseline_metrics['f1']}%")
    print(f"   Tests: {baseline_metrics['tests_passed']}")
    print()
    
    # Test each preprocessing mode
    modes = ["7e-1", "7e-2", "7e-3", "7e-4", "7e-5"]
    mode_names = {
        "7e-1": "Basic Normalization",
        "7e-2": "+ Lemmatization",
        "7e-3": "+ Synonym Expansion",
        "7e-4": "+ Contextual Re-weighting",
        "7e-5": "Full Pipeline"
    }
    
    results = []
    
    for mode in modes:
        print(f"🔬 Testing {mode}: {mode_names[mode]}")
        print("-" * 70)
        
        # Create preprocessor
        preprocessor = QueryPreprocessor(mode=mode)
        
        # Run benchmark via subprocess to get full metrics
        import subprocess
        
        # Set environment variables for this test
        env = os.environ.copy()
        env["QUERY_PREPROCESSING_MODE"] = mode
        
        # Run benchmark
        cmd = [
            sys.executable,
            str(backend_dir / "tests" / "test_rag_benchmark.py")
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=60
            )
            
            # Extract metrics
            metrics = extract_metrics_from_benchmark(result.stdout)
            
            if not metrics:
                print("⚠️  Could not extract metrics, using simple benchmark")
                # Fallback to simple benchmark
                vector_store = VectorStore()
                bench_result = run_benchmark(preprocessor, vector_store)
                metrics = {
                    "relevance": bench_result["relevance"],
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "tests_passed": f"{bench_result['correct']}/{bench_result['total']}"
                }
            
            # Calculate deltas
            delta_rel = metrics.get("relevance", 0) - baseline_metrics["relevance"]
            delta_prec = metrics.get("precision", 0) - baseline_metrics["precision"]
            
            print(f"   Relevance: {metrics.get('relevance', 0):.2f}% ({delta_rel:+.2f}pp)")
            print(f"   Precision: {metrics.get('precision', 0):.2f}% ({delta_prec:+.2f}pp)")
            print(f"   Recall: {metrics.get('recall', 0):.2f}%")
            print(f"   F1: {metrics.get('f1', 0):.2f}%")
            print(f"   Tests: {metrics.get('tests_passed', 'N/A')}")
            print()
            
            results.append({
                "mode": mode,
                "name": mode_names[mode],
                "metrics": metrics,
                "delta_relevance": delta_rel,
                "delta_precision": delta_prec,
                "timestamp": datetime.now().isoformat()
            })
            
        except subprocess.TimeoutExpired:
            print("⚠️  Benchmark timed out")
            print()
        except Exception as e:
            print(f"⚠️  Error running benchmark: {e}")
            print()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = backend_dir / "logs"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"step7e_query_preprocessing_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "baseline": baseline_metrics,
            "experiments": results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    print("=" * 70)
    print(f"✅ Results saved to: {output_file}")
    print("=" * 70)
    
    # Find best configuration
    if results:
        best = max(results, key=lambda x: x["metrics"].get("relevance", 0))
        print()
        print("🏆 Best Configuration:")
        print(f"   Mode: {best['mode']} ({best['name']})")
        print(f"   Relevance: {best['metrics'].get('relevance', 0):.2f}% ({best['delta_relevance']:+.2f}pp)")
        print(f"   Precision: {best['metrics'].get('precision', 0):.2f}% ({best['delta_precision']:+.2f}pp)")


if __name__ == "__main__":
    main()

"""
Step 9d: Query Expansion (Advanced Semantic Enrichment)
========================================================

Goal: Attack precision bottleneck by enriching query semantics BEFORE retrieval.
      This is a threshold-independent optimization that directly improves semantic matching.

Strategy: Implement 5-7 query preprocessing strategies:
    1. Paraphrase generation (GPT-4o-mini via LiteLLM)
    2. Synonym expansion (WordNet + contextual)
    3. Entity extraction (Named entities + key concepts)
    4. Semantic reformulation (Question → Statement conversion)
    5. Contextual augmentation (Domain-specific expansions)
    6. Multi-perspective expansion (Different viewpoints)
    7. Hybrid ensemble (Best-performing combinations)

Expected Gains:
    - Precision: +1-2pp (32.95% → 34-35%)
    - Relevance: +0.5-1pp (70-71% → 71-72%)
    - Reason: Better semantic overlap with document corpus

Baseline: Alpha-v7 REVISED (70-71% relevance, 32.95% precision, 92.31% recall)
Target: Alpha-v9 promotion (≥34% precision, ≥73% relevance)
Note: Previous 74.78% baseline was first-run outlier. True baseline validated via 5 runs.

Design Rationale:
    - Threshold-independent: Works even with unstable baseline
    - Attack root cause: Semantic ambiguity between query and documents
    - Zero recall loss: Expansion only adds information, doesn't filter
    - Cost-effective: Preprocessing cost << reranking cost

Duration: 1-2 hours
Priority: PRIMARY (after Step 9e baseline instability discovered)
"""

import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from memory.vector_store import VectorStore


class QueryExpander:
    """
    Advanced query expansion with multiple strategies.
    
    Each strategy enriches the query differently to improve semantic matching:
    - Paraphrase: Alternative phrasings capture different semantic angles
    - Synonyms: Related terms increase vocabulary coverage
    - Entities: Key concepts provide focused retrieval signals
    - Reformulation: Convert questions to statements for better document matching
    - Context: Domain-specific knowledge enhances relevance
    - Multi-perspective: Different viewpoints capture varied document styles
    """
    
    def __init__(self, mode: str = "baseline"):
        """
        Initialize query expander.
        
        Args:
            mode: Expansion strategy
                - "baseline": No expansion (Alpha-v7 behavior)
                - "9d-1": Paraphrase generation
                - "9d-2": Synonym expansion
                - "9d-3": Entity extraction
                - "9d-4": Semantic reformulation
                - "9d-5": Contextual augmentation
                - "9d-6": Multi-perspective expansion
                - "9d-7": Hybrid ensemble (best strategies combined)
        """
        self.mode = mode
        
        # Lazy-initialized components
        self._llm_client = None
        self._nltk_initialized = False
        
        # Import NLP libraries for strategies 2-6
        if mode in ["9d-2", "9d-3", "9d-4", "9d-5", "9d-6", "9d-7"]:
            self._initialize_nltk()
    
    def _initialize_nltk(self):
        """Lazy-initialize NLTK components"""
        if self._nltk_initialized:
            return
        
        try:
            import nltk
            from nltk.stem import WordNetLemmatizer
            from nltk.corpus import wordnet
            
            # Download required NLTK data
            for resource in ['punkt', 'wordnet', 'averaged_perceptron_tagger', 'omw-1.4', 'maxent_ne_chunker', 'words']:
                try:
                    nltk.data.find(f'tokenizers/{resource}')
                except LookupError:
                    try:
                        nltk.download(resource, quiet=True)
                    except:
                        pass  # Continue even if download fails
            
            self.lemmatizer = WordNetLemmatizer()
            self.wordnet = wordnet
            self.nltk = nltk
            self._nltk_initialized = True
            
        except ImportError:
            print("⚠️  NLTK not installed. Install with: pip install nltk")
            self._nltk_initialized = False
    
    def _get_llm_client(self):
        """Lazy-initialize LiteLLM client for paraphrase generation"""
        if self._llm_client is not None:
            return self._llm_client
        
        try:
            import litellm
            self._llm_client = litellm
            return self._llm_client
        except ImportError:
            print("⚠️  LiteLLM not installed. Install with: pip install litellm")
            return None
    
    def expand(self, query: str) -> str:
        """
        Expand query using selected strategy.
        
        Args:
            query: Original query text
            
        Returns:
            Expanded query text (may contain multiple variations concatenated)
        """
        if self.mode == "baseline":
            return query
        
        # Strategy dispatch
        if self.mode == "9d-1":
            return self._paraphrase_generation(query)
        elif self.mode == "9d-2":
            return self._synonym_expansion(query)
        elif self.mode == "9d-3":
            return self._entity_extraction(query)
        elif self.mode == "9d-4":
            return self._semantic_reformulation(query)
        elif self.mode == "9d-5":
            return self._contextual_augmentation(query)
        elif self.mode == "9d-6":
            return self._multi_perspective_expansion(query)
        elif self.mode == "9d-7":
            return self._hybrid_ensemble(query)
        
        return query
    
    def _paraphrase_generation(self, query: str) -> str:
        """
        Strategy 9d-1: Generate paraphrases using GPT-4o-mini.
        
        Example:
            Input: "How do I reset my password?"
            Output: "How do I reset my password? What's the password reset process? Steps to change password"
        """
        llm = self._get_llm_client()
        if not llm:
            return query  # Fallback to original
        
        try:
            # Generate 2 paraphrases using LiteLLM
            response = llm.completion(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "You are a query paraphrase generator. Given a query, generate 2 alternative phrasings that preserve the original meaning. Output only the paraphrases, one per line."
                }, {
                    "role": "user",
                    "content": query
                }],
                temperature=0.7,
                max_tokens=100
            )
            
            paraphrases = response.choices[0].message.content.strip().split('\n')
            paraphrases = [p.strip() for p in paraphrases if p.strip()][:2]
            
            # Combine original + paraphrases
            expanded = query + " " + " ".join(paraphrases)
            return expanded
            
        except Exception as e:
            print(f"⚠️  Paraphrase generation failed: {e}")
            return query
    
    def _synonym_expansion(self, query: str) -> str:
        """
        Strategy 9d-2: Expand with synonyms from WordNet.
        
        Example:
            Input: "What are the main features?"
            Output: "What are the main features? primary characteristics key attributes"
        """
        if not self._nltk_initialized:
            return query
        
        try:
            # Tokenize and POS tag
            tokens = self.nltk.word_tokenize(query)
            pos_tags = self.nltk.pos_tag(tokens)
            
            synonyms = []
            for word, pos in pos_tags:
                # Only expand nouns, verbs, adjectives
                if pos.startswith('N') or pos.startswith('V') or pos.startswith('J'):
                    synsets = self.wordnet.synsets(word)
                    if synsets:
                        # Get top 2 synonyms from first synset
                        for lemma in synsets[0].lemmas()[:2]:
                            synonym = lemma.name().replace('_', ' ')
                            if synonym.lower() != word.lower():
                                synonyms.append(synonym)
            
            # Combine original + synonyms
            expanded = query + " " + " ".join(synonyms[:5])  # Max 5 synonyms
            return expanded
            
        except Exception as e:
            print(f"⚠️  Synonym expansion failed: {e}")
            return query
    
    def _entity_extraction(self, query: str) -> str:
        """
        Strategy 9d-3: Extract and emphasize key entities/concepts.
        
        Example:
            Input: "Tell me about Python's asyncio module"
            Output: "Tell me about Python's asyncio module Python asyncio module asyncio"
        """
        if not self._nltk_initialized:
            return query
        
        try:
            # Tokenize and POS tag
            tokens = self.nltk.word_tokenize(query)
            pos_tags = self.nltk.pos_tag(tokens)
            
            # Extract nouns and proper nouns (key concepts)
            entities = []
            for word, pos in pos_tags:
                if pos.startswith('NN') or pos.startswith('NNP'):
                    entities.append(word)
            
            # Also extract capitalized words (likely entities)
            capitalized = [word for word in tokens if word[0].isupper() and len(word) > 1]
            entities.extend(capitalized)
            
            # Remove duplicates
            entities = list(dict.fromkeys(entities))
            
            # Combine original + entities (repeated for emphasis)
            expanded = query + " " + " ".join(entities[:5])
            return expanded
            
        except Exception as e:
            print(f"⚠️  Entity extraction failed: {e}")
            return query
    
    def _semantic_reformulation(self, query: str) -> str:
        """
        Strategy 9d-4: Convert questions to statements for better document matching.
        
        Example:
            Input: "How do I reset my password?"
            Output: "How do I reset my password? password reset process password reset steps"
        """
        # Question → Statement conversion patterns
        reformulations = []
        
        # Pattern 1: "How do I X?" → "X process" / "X steps"
        how_match = re.search(r'how (?:do|can|to) (?:I |you |we )?(.+)\??', query, re.IGNORECASE)
        if how_match:
            action = how_match.group(1).strip()
            reformulations.append(f"{action} process")
            reformulations.append(f"{action} steps")
        
        # Pattern 2: "What is X?" → "X definition" / "X explanation"
        what_match = re.search(r'what (?:is|are) (.+)\??', query, re.IGNORECASE)
        if what_match:
            subject = what_match.group(1).strip()
            reformulations.append(f"{subject} definition")
            reformulations.append(f"{subject} explanation")
        
        # Pattern 3: "Where is X?" → "X location"
        where_match = re.search(r'where (?:is|are) (.+)\??', query, re.IGNORECASE)
        if where_match:
            subject = where_match.group(1).strip()
            reformulations.append(f"{subject} location")
        
        # Pattern 4: "Can I X?" → "X capability" / "X feature"
        can_match = re.search(r'can (?:I |you |we )?(.+)\??', query, re.IGNORECASE)
        if can_match:
            action = can_match.group(1).strip()
            reformulations.append(f"{action} capability")
            reformulations.append(f"{action} feature")
        
        # Combine original + reformulations
        expanded = query + " " + " ".join(reformulations[:4])
        return expanded
    
    def _contextual_augmentation(self, query: str) -> str:
        """
        Strategy 9d-5: Add domain-specific context terms.
        
        Example:
            Input: "API rate limits"
            Output: "API rate limits API request throttling rate limiting quota"
        """
        # Domain-specific term mappings
        context_mappings = {
            # Authentication terms
            r'\b(?:password|login|signin|auth)\b': ['authentication', 'credentials', 'access'],
            r'\b(?:reset|forgot|change)\b.*password': ['password recovery', 'password reset', 'account access'],
            
            # API terms
            r'\b(?:api|endpoint|request)\b': ['API', 'endpoint', 'integration'],
            r'\b(?:rate limit|throttle)\b': ['rate limiting', 'quota', 'throttling'],
            
            # Payment terms
            r'\b(?:payment|billing|invoice)\b': ['payment method', 'billing', 'invoice'],
            r'\b(?:price|pricing|cost)\b': ['pricing', 'cost', 'subscription'],
            
            # Support terms
            r'\b(?:support|help|contact)\b': ['customer support', 'help', 'assistance'],
            
            # Account terms
            r'\b(?:account|profile|subscription)\b': ['account', 'user profile', 'subscription'],
            r'\b(?:upgrade|downgrade|cancel)\b': ['plan change', 'subscription', 'account management'],
            
            # Security terms
            r'\b(?:security|privacy|encrypt)\b': ['security', 'privacy', 'data protection'],
            
            # Data terms
            r'\b(?:export|import|backup)\b': ['data export', 'data transfer', 'backup'],
        }
        
        # Find matching patterns and add context
        context_terms = []
        query_lower = query.lower()
        
        for pattern, terms in context_mappings.items():
            if re.search(pattern, query_lower):
                context_terms.extend(terms)
        
        # Remove duplicates
        context_terms = list(dict.fromkeys(context_terms))
        
        # Combine original + context
        expanded = query + " " + " ".join(context_terms[:5])
        return expanded
    
    def _multi_perspective_expansion(self, query: str) -> str:
        """
        Strategy 9d-6: Generate multiple perspectives of the query.
        
        Example:
            Input: "How do I reset my password?"
            Perspectives:
                - User action: "reset password"
                - System process: "password reset process"
                - Troubleshooting: "password reset troubleshooting"
                - Documentation: "password reset guide"
        """
        # Extract core concept (remove question words)
        core = re.sub(r'^(?:how|what|where|when|why|can|is|are|do|does) (?:do |can |to |I |you |we )?', '', query, flags=re.IGNORECASE)
        core = core.rstrip('?').strip()
        
        # Generate perspectives
        perspectives = [
            f"{core} guide",
            f"{core} documentation",
            f"{core} instructions",
            f"{core} tutorial",
        ]
        
        # Combine original + perspectives
        expanded = query + " " + " ".join(perspectives[:3])
        return expanded
    
    def _hybrid_ensemble(self, query: str) -> str:
        """
        Strategy 9d-7: Combine best-performing strategies.
        
        This will be determined empirically based on 9d-1 through 9d-6 results.
        Initial ensemble: Entity extraction + Contextual augmentation + Reformulation
        """
        # Apply multiple strategies
        expanded_parts = [query]
        
        # Strategy 3: Entity extraction
        entity_expanded = self._entity_extraction(query)
        if entity_expanded != query:
            # Extract only the added entities
            entities = entity_expanded.replace(query, '').strip()
            expanded_parts.append(entities)
        
        # Strategy 4: Semantic reformulation
        reformulated = self._semantic_reformulation(query)
        if reformulated != query:
            reformulations = reformulated.replace(query, '').strip()
            expanded_parts.append(reformulations)
        
        # Strategy 5: Contextual augmentation
        augmented = self._contextual_augmentation(query)
        if augmented != query:
            context = augmented.replace(query, '').strip()
            expanded_parts.append(context)
        
        # Combine all parts
        expanded = " ".join(expanded_parts)
        return expanded


def test_expansion_strategy(
    mode: str,
    expander: QueryExpander,
    vector_store: VectorStore
) -> Dict[str, Any]:
    """
    Test a single expansion strategy using run_rag_benchmark.
    
    Args:
        mode: Expansion mode identifier
        expander: QueryExpander instance
        vector_store: VectorStore instance
        
    Returns:
        Dictionary with benchmark results
    """
    print(f"\n{'='*70}")
    print(f"Testing Strategy: {mode}")
    print(f"{'='*70}\n")
    
    # Run benchmark via subprocess to get full metrics
    import subprocess
    
    # Set environment variable for this test
    env = os.environ.copy()
    env["QUERY_EXPANSION_MODE"] = mode
    
    # Temporarily patch VectorStore.search to use expander
    # (This is a hack - in production, query expansion should be integrated into vector_store.py)
    original_search = vector_store.search
    
    def expanded_search(query: str, *args, **kwargs):
        expanded_query = expander.expand(query)
        print(f"📝 Original: {query}")
        print(f"🔄 Expanded: {expanded_query}\n")
        return original_search(expanded_query, *args, **kwargs)
    
    vector_store.search = expanded_search
    
    # Run full benchmark
    try:
        from tests.run_rag_benchmark import run_full_benchmark
        
        start_time = time.time()
        results = run_full_benchmark(verbose=False, export=False)
        duration = time.time() - start_time
        
        if results and 'summary' in results:
            # Extract metrics from result['summary'] dict
            summary = results['summary']
            metrics = {
                "relevance": summary.get('avg_relevance_score', 0.0) * 100,  # Convert 0.7478 → 74.78
                "precision": summary.get('avg_precision', 0.0) * 100,
                "recall": summary.get('avg_recall', 0.0) * 100,
                "f1": summary.get('avg_f1', 0.0) * 100,
                "tests_passed": f"{summary.get('passed', 0)}/{summary.get('total_tests', 0)}",
                "duration": duration
            }
            
            # Restore original search
            vector_store.search = original_search
            
            return metrics
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Restore original search
    vector_store.search = original_search
    
    return {
        "relevance": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "tests_passed": "0/0",
        "duration": 0.0
    }


def main():
    """Execute Step 9d query expansion experiments"""
    
    print("\n" + "="*70)
    print("STEP 9D: QUERY EXPANSION TESTS")
    print("="*70)
    print("\n📊 Baseline (Alpha-v7 REVISED):")
    print("   Relevance: 70-71% (validated via 5 runs)")
    print("   Precision: 32.95%")
    print("   Recall: 92.31%")
    print("   Tests: 5/13")
    print("   Note: Previous 74.78% was first-run outlier")
    print("\n🎯 Target (Alpha-v9):")
    print("   Relevance: ≥73% (+2-3pp from corrected baseline)")
    print("   Precision: ≥34% (+1-2pp)")
    print("   Recall: ≥90% (maintain)")
    print("\n")
    
    # Initialize vector store
    print("📁 Initializing vector store...")
    vector_store = VectorStore(
        backend="faiss",
        enable_reranking=False,
        hybrid_vector_weight=0.97,
        query_preprocessing_mode="7e-1"
    )
    print("✅ Vector store ready\n")
    
    # Define test strategies
    strategies = [
        ("baseline", "No expansion (Alpha-v7)"),
        ("9d-1", "Paraphrase generation (GPT-4o-mini)"),
        ("9d-2", "Synonym expansion (WordNet)"),
        ("9d-3", "Entity extraction (NER + key concepts)"),
        ("9d-4", "Semantic reformulation (Q→S conversion)"),
        ("9d-5", "Contextual augmentation (domain terms)"),
        ("9d-6", "Multi-perspective expansion (viewpoints)"),
        ("9d-7", "Hybrid ensemble (best strategies)"),
    ]
    
    # Test each strategy
    results = []
    baseline_metrics = None
    
    for mode, description in strategies:
        print(f"\n{'─'*70}")
        print(f"🔬 Strategy: {mode} - {description}")
        print(f"{'─'*70}")
        
        # Create expander
        expander = QueryExpander(mode=mode)
        
        # Run test
        start_time = time.time()
        metrics = test_expansion_strategy(mode, expander, vector_store)
        duration = time.time() - start_time
        
        # Store baseline for comparison
        if mode == "baseline":
            baseline_metrics = metrics
        
        # Calculate deltas
        delta_rel = metrics["relevance"] - (baseline_metrics["relevance"] if baseline_metrics else 0)
        delta_prec = metrics["precision"] - (baseline_metrics["precision"] if baseline_metrics else 0)
        delta_recall = metrics["recall"] - (baseline_metrics["recall"] if baseline_metrics else 0)
        
        # Print results
        print(f"\n📊 Results:")
        print(f"   Relevance: {metrics['relevance']:.2f}% ({delta_rel:+.2f}pp)")
        print(f"   Precision: {metrics['precision']:.2f}% ({delta_prec:+.2f}pp)")
        print(f"   Recall: {metrics['recall']:.2f}% ({delta_recall:+.2f}pp)")
        print(f"   F1: {metrics['f1']:.2f}%")
        print(f"   Tests: {metrics['tests_passed']}")
        print(f"   Duration: {duration:.1f}s")
        
        # Store results
        results.append({
            "mode": mode,
            "description": description,
            "metrics": metrics,
            "delta_relevance": delta_rel,
            "delta_precision": delta_prec,
            "delta_recall": delta_recall,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })
        
        # Check if target reached
        if metrics["precision"] >= 34.0 and metrics["relevance"] >= 76.0:
            print(f"\n🎉 ALPHA-V9 TARGET REACHED!")
            print(f"   Precision: {metrics['precision']:.2f}% ≥ 34%")
            print(f"   Relevance: {metrics['relevance']:.2f}% ≥ 76%")
    
    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    output_file = results_dir / "step9d_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "baseline": baseline_metrics,
            "strategies": results,
            "timestamp": datetime.now().isoformat(),
            "alpha_version": "v7",
            "target_version": "v9"
        }, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✅ Results saved to: {output_file}")
    print(f"{'='*70}\n")
    
    # Find best strategy
    if len(results) > 1:
        # Exclude baseline
        candidates = [r for r in results if r["mode"] != "baseline"]
        
        # Sort by precision (primary metric)
        best = max(candidates, key=lambda x: x["metrics"]["precision"])
        
        print("\n🏆 BEST STRATEGY:")
        print(f"   Mode: {best['mode']}")
        print(f"   Description: {best['description']}")
        print(f"   Relevance: {best['metrics']['relevance']:.2f}% ({best['delta_relevance']:+.2f}pp)")
        print(f"   Precision: {best['metrics']['precision']:.2f}% ({best['delta_precision']:+.2f}pp)")
        print(f"   Recall: {best['metrics']['recall']:.2f}% ({best['delta_recall']:+.2f}pp)")
        print(f"   F1: {best['metrics']['f1']:.2f}%")
        print(f"   Tests: {best['metrics']['tests_passed']}")
        
        # Recommendation
        print("\n💡 RECOMMENDATION:")
        if best["metrics"]["precision"] >= 34.0:
            print(f"   ✅ Promote to Alpha-v9 with mode={best['mode']}")
            print(f"   ✅ Precision target achieved: {best['metrics']['precision']:.2f}% ≥ 34%")
        else:
            print(f"   ⚠️  Target not reached: {best['metrics']['precision']:.2f}% < 34%")
            print(f"   💡 Consider combining strategies or tuning parameters")
    
    print("\n" + "="*70)
    print("STEP 9D COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

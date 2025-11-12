"""
Step 9g: Query Expansion with Full RAG Benchmark
==================================================

Goal: Improve relevance scores by expanding queries with semantically related terms
      BEFORE retrieval to capture more relevant documents.

Strategy: Test 5 lightweight query expansion approaches:
    1. Baseline (control - no expansion)
    2. Synonym Expansion (WordNet-based)
    3. Entity Extraction (key concepts)
    4. Contextual Keywords (domain terms)
    5. Simple Reformulation (question → statement)

Expected Gains:
    - Relevance: +3-5pp (70-71% → 73-76%)
    - Precision: +1-2pp (32.95% → 34-35%)
    - Recall: Maintain 92.31%

Current Status:
    - Step 9c delivered: 43.85% precision (EXCEEDS 34% target!) ✅
    - But relevance dropped: 70.25% (BELOW 76% target) ❌
    - This step targets RELEVANCE improvement

Duration: 30-45 minutes (5 strategies × 13 benchmarks = 65 tests)
Priority: PRIMARY - Closes the relevance gap to reach Alpha-v9
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import re

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from memory.memory_manager import get_memory_manager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios


class SimpleQueryExpander:
    """
    Lightweight query expansion without external dependencies.
    
    Uses rule-based methods to enrich queries for better semantic matching.
    """
    
    def __init__(self, strategy: str = "baseline"):
        """
        Args:
            strategy: Expansion approach
                - "baseline": No expansion
                - "synonyms": Add common synonyms
                - "entities": Extract and emphasize key entities
                - "keywords": Add domain-specific context words
                - "reformulate": Convert questions to statements
        """
        self.strategy = strategy
        
        # Common synonym mappings for debate/chat domain
        self.synonym_map = {
            "argument": ["claim", "point", "position", "stance"],
            "opponent": ["adversary", "opposition", "other side", "counterpart"],
            "proponent": ["advocate", "supporter", "defender", "champion"],
            "safety": ["security", "protection", "risk management", "safeguarding"],
            "cost": ["expense", "price", "affordability", "economic impact"],
            "environment": ["ecology", "nature", "ecosystem", "planet"],
            "energy": ["power", "electricity", "fuel"],
            "technology": ["innovation", "advancement", "system", "tools"],
            "debate": ["discussion", "argument", "discourse", "exchange"],
            "evidence": ["proof", "data", "facts", "support"],
            "climate": ["weather", "atmospheric", "environmental conditions"],
            "nuclear": ["atomic", "fission", "reactor"],
            "solar": ["photovoltaic", "sun-powered", "renewable"],
            "misinformation": ["false information", "fake news", "disinformation"],
            "vaccine": ["immunization", "inoculation", "vaccination"],
        }
        
        # Domain context keywords
        self.domain_keywords = {
            "safety": ["hazard", "danger", "secure", "protect"],
            "economic": ["financial", "monetary", "budget", "funding"],
            "environment": ["carbon", "emissions", "sustainable", "green"],
            "technology": ["system", "device", "infrastructure", "capability"],
            "debate": ["rebuttal", "counterargument", "refutation", "defense"],
            "fact-check": ["verify", "authentic", "accurate", "credible"],
        }
    
    def expand(self, query: str) -> str:
        """
        Expand query using selected strategy.
        
        Args:
            query: Original query text
            
        Returns:
            Expanded query (original + enrichment terms)
        """
        if self.strategy == "baseline":
            return query
        elif self.strategy == "synonyms":
            return self._add_synonyms(query)
        elif self.strategy == "entities":
            return self._emphasize_entities(query)
        elif self.strategy == "keywords":
            return self._add_keywords(query)
        elif self.strategy == "reformulate":
            return self._reformulate_query(query)
        
        return query
    
    def _add_synonyms(self, query: str) -> str:
        """Add synonyms for key terms in query."""
        query_lower = query.lower()
        additions = []
        
        for term, synonyms in self.synonym_map.items():
            if term in query_lower:
                # Add 2 most relevant synonyms
                additions.extend(synonyms[:2])
        
        if additions:
            return f"{query} {' '.join(additions)}"
        return query
    
    def _emphasize_entities(self, query: str) -> str:
        """
        Extract and duplicate key entities to boost their importance.
        
        Simple approach: Capitalized words and quoted phrases are entities.
        """
        # Find capitalized words (entities)
        entities = re.findall(r'\b[A-Z][a-z]+\b', query)
        
        # Find quoted phrases
        quoted = re.findall(r'"([^"]+)"', query)
        
        # Combine
        key_terms = list(set(entities + quoted))
        
        if key_terms:
            # Append entities to emphasize them in search
            return f"{query} {' '.join(key_terms)}"
        return query
    
    def _add_keywords(self, query: str) -> str:
        """Add domain-specific context keywords."""
        query_lower = query.lower()
        additions = []
        
        for domain, keywords in self.domain_keywords.items():
            if domain in query_lower:
                # Add 2 related keywords
                additions.extend(keywords[:2])
        
        # Also check for specific patterns
        if "what did" in query_lower or "who said" in query_lower:
            additions.append("statement")
        if "argument" in query_lower:
            additions.extend(["position", "reasoning"])
        if "recent" in query_lower or "latest" in query_lower:
            additions.extend(["current", "newest"])
        
        if additions:
            return f"{query} {' '.join(set(additions))}"
        return query
    
    def _reformulate_query(self, query: str) -> str:
        """
        Convert questions to statement form for better document matching.
        
        Example:
            "What did opponent say about safety?" 
            → "What did opponent say about safety? opponent said safety"
        """
        query_lower = query.lower()
        reformulations = []
        
        # Pattern 1: "What did X say/argue about Y?"
        match = re.search(r'what did ([\w\s]+) (?:say|argue|claim|state) about ([\w\s]+)', query_lower)
        if match:
            subject = match.group(1).strip()
            topic = match.group(2).strip()
            reformulations.append(f"{subject} {topic}")
        
        # Pattern 2: "How does X affect Y?"
        match = re.search(r'how (?:does|do|did) ([\w\s]+) (?:affect|impact|influence) ([\w\s]+)', query_lower)
        if match:
            cause = match.group(1).strip()
            effect = match.group(2).strip()
            reformulations.append(f"{cause} {effect} relationship")
        
        # Pattern 3: "Why is X important?"
        match = re.search(r'why (?:is|are|was|were) ([\w\s]+) (?:important|significant|critical)', query_lower)
        if match:
            topic = match.group(1).strip()
            reformulations.append(f"{topic} importance significance")
        
        # Pattern 4: "Previous/earlier X"
        if "previous" in query_lower or "earlier" in query_lower or "before" in query_lower:
            reformulations.append("historical context")
        
        if reformulations:
            return f"{query} {' '.join(reformulations)}"
        return query


def test_expansion_strategy(strategy_name: str, strategy_desc: str, expander: SimpleQueryExpander) -> Dict[str, Any]:
    """
    Test a query expansion strategy using full RAG benchmark.
    
    Args:
        strategy_name: Strategy identifier (e.g., "9g-1-synonyms")
        strategy_desc: Human-readable description
        expander: QueryExpander instance
        
    Returns:
        Dict with benchmark results
    """
    print(f"\n[TEST] Testing Strategy: {strategy_name}")
    print(f"   Description: {strategy_desc}")
    
    # Initialize memory manager
    print("[INIT] Initializing memory manager...")
    memory_manager = get_memory_manager(long_term_backend="faiss")
    
    # Monkey-patch search_memories to apply query expansion
    original_search = memory_manager.search_memories
    
    def expanded_search(query: str, top_k: int = 5, **kwargs):
        """Wrapper that expands query before searching."""
        expanded_query = expander.expand(query)
        
        # Debug output for first few queries
        if expanded_query != query:
            print(f"   [EXPAND] '{query[:50]}...' → '{expanded_query[:80]}...'")
        
        return original_search(expanded_query, top_k=top_k, **kwargs)
    
    memory_manager.search_memories = expanded_search
    
    try:
        # Create benchmark and load scenarios
        print("[INIT] Loading test scenarios...")
        benchmark = RAGBenchmark(memory_manager)
        load_all_test_scenarios(benchmark)
        print(f"[OK] Loaded {len(benchmark.test_cases)} test scenarios")
        
        # Run benchmark
        print(f"[RUN] Running 13 benchmark tests...")
        results = benchmark.run_benchmark(verbose=False)
        
        # Restore original method
        memory_manager.search_memories = original_search
        
        # Extract metrics
        summary = results.get('summary', {})
        
        print(f"[RESULTS] Relevance: {summary.get('avg_relevance_score', 0)*100:.2f}%, "
              f"Precision: {summary.get('avg_precision', 0)*100:.2f}%, "
              f"Recall: {summary.get('avg_recall', 0)*100:.2f}%, "
              f"Passed: {summary.get('passed', 0)}/{summary.get('total_tests', 13)}")
        
        return {
            'strategy': strategy_name,
            'description': strategy_desc,
            'results': results
        }
    
    except Exception as e:
        print(f"[ERROR] Strategy {strategy_name} failed: {e}")
        memory_manager.search_memories = original_search
        raise


def run_step9g_tests():
    """
    Run all query expansion strategies and compare results.
    """
    print("\n" + "="*70)
    print("STEP 9g: QUERY EXPANSION BENCHMARK")
    print("="*70)
    print("\nObjective: Improve relevance by expanding queries with related terms")
    print("Current Gap: Relevance 70.25% → Target 76% (+5.75pp needed)")
    print("Expected Gain: +3-5pp relevance, +1-2pp precision")
    print("\nTesting 5 strategies (65 total tests)...")
    
    # Define strategies to test
    strategies = [
        ("9g-0-baseline", "No expansion (control)", SimpleQueryExpander("baseline")),
        ("9g-1-synonyms", "Add common synonyms", SimpleQueryExpander("synonyms")),
        ("9g-2-entities", "Emphasize key entities", SimpleQueryExpander("entities")),
        ("9g-3-keywords", "Add domain context", SimpleQueryExpander("keywords")),
        ("9g-4-reformulate", "Question → Statement", SimpleQueryExpander("reformulate")),
    ]
    
    all_results = []
    baseline_metrics = None
    
    for strategy_name, strategy_desc, expander in strategies:
        try:
            result = test_expansion_strategy(strategy_name, strategy_desc, expander)
            all_results.append(result)
            
            # Store baseline for comparison
            if strategy_name == "9g-0-baseline":
                baseline_metrics = result['results']['summary']
        
        except Exception as e:
            print(f"[ERROR] Failed to test {strategy_name}: {e}")
            continue
    
    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"step9g_results_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n[SAVE] Results saved to: {output_file}")
    
    # Print comparison table
    print("\n" + "="*70)
    print("[RESULTS] STEP 9g RESULTS SUMMARY")
    print("="*70)
    print()
    
    print(f"{'Strategy':<25} {'Relevance':<12} {'Precision':<12} {'Recall':<10} {'Tests':<8}")
    print("-"*70)
    
    for result in all_results:
        summary = result['results']['summary']
        strategy = result['strategy']
        rel = summary.get('avg_relevance_score', 0) * 100
        prec = summary.get('avg_precision', 0) * 100
        rec = summary.get('avg_recall', 0) * 100
        passed = summary.get('passed', 0)
        total = summary.get('total_tests', 13)
        
        print(f"{strategy:<25} {rel:>10.2f}% {prec:>10.2f}% {rec:>8.2f}% {passed:>3}/{total:<3}")
    
    # Find best strategy
    print("\n" + "="*70)
    print("[DECISION] ALPHA-v9 PROMOTION DECISION")
    print("="*70)
    
    if len(all_results) > 1:
        # Exclude baseline
        candidates = [r for r in all_results if r['strategy'] != "9g-0-baseline"]
        
        # Sort by relevance (primary metric for Step 9g)
        best = max(candidates, key=lambda x: x['results']['summary'].get('avg_relevance_score', 0))
        best_summary = best['results']['summary']
        
        best_rel = best_summary.get('avg_relevance_score', 0) * 100
        best_prec = best_summary.get('avg_precision', 0) * 100
        best_passed = best_summary.get('passed', 0)
        
        baseline_rel = baseline_metrics.get('avg_relevance_score', 0) * 100
        baseline_prec = baseline_metrics.get('avg_precision', 0) * 100
        
        delta_rel = best_rel - baseline_rel
        delta_prec = best_prec - baseline_prec
        
        print(f"\n[CHECK] Best Relevance: {best_rel:.2f}% ", end="")
        if best_rel >= 76.0:
            print("[PASS] (need >=76%)")
        else:
            print(f"[FAIL] (need >=76%, gap: {76.0 - best_rel:.2f}pp)")
        
        print(f"[CHECK] Best Precision: {best_prec:.2f}% ", end="")
        if best_prec >= 34.0:
            print("[PASS] (need >=34%)")
        else:
            print(f"[FAIL] (need >=34%, gap: {34.0 - best_prec:.2f}pp)")
        
        print(f"[CHECK] Best Strategy: {best['strategy']}")
        print(f"[CHECK] Gains: +{delta_rel:.2f}pp relevance, +{delta_prec:.2f}pp precision")
        
        # Decision
        print("\n[NEXT] RECOMMENDATION:")
        if best_rel >= 76.0 and best_prec >= 34.0:
            print(f"   ✅ PROMOTE TO ALPHA-V9 with {best['strategy']}")
            print(f"   ✅ Both targets achieved!")
        elif best_rel >= 76.0:
            print(f"   ⚠️  Relevance target MET ({best_rel:.2f}% >= 76%)")
            print(f"   ⚠️  But precision gap remains ({best_prec:.2f}% < 34%)")
            print(f"   💡 Combine Step 9c (43.85% precision) + Step 9g ({best['strategy']})")
        elif best_prec >= 34.0:
            print(f"   ⚠️  Precision target MET ({best_prec:.2f}% >= 34%)")
            print(f"   ⚠️  But relevance gap remains ({best_rel:.2f}% < 76%)")
            print(f"   💡 Tune expansion parameters or combine strategies")
        else:
            print(f"   ⚠️  Neither target met")
            print(f"   💡 Consider:")
            print(f"      - Combine Step 9c (precision) + Step 9g (relevance)")
            print(f"      - Tune hybrid search alpha parameter")
            print(f"      - Try ensemble approach")
    
    print("\n[COMPLETE] Step 9g testing complete: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70 + "\n")


if __name__ == "__main__":
    run_step9g_tests()

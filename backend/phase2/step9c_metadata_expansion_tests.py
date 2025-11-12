"""
Step 9c: Metadata Expansion Testing
====================================

**Purpose**: Test metadata-based filtering to bypass semantic ceiling at 70-71% relevance.

**Hypothesis**: Rich metadata filtering can improve precision by 0.5-1pp without improving
              core retrieval quality, by reducing false positives through document characteristics.

**Current Status**:
- Baseline: Alpha-v7 REVISED (70-71% relevance, 32.95% precision, 92.31% recall, 5/13 tests passing)
- Expected Gains: 70-71% → 73% relevance (+2-3pp), 32.95% → 34%+ precision (+1pp)
- Target: ≥34% precision, ≥73% relevance for Alpha-v9 promotion

**Note**: Previous 74.78% baseline was first-run outlier. True baseline validated via 5 runs.

**Testing Strategy**:
We test 7 metadata filtering approaches:
1. 9c-0: Baseline (no metadata filtering) - control group
2. 9c-1: Document type filtering (remove off-topic document types)
3. 9c-2: Role filtering (match query role with document role)
4. 9c-3: Topic filtering (require topic alignment between query and documents)
5. 9c-4: Confidence filtering (threshold at 0.6 for argument strength)
6. 9c-5: Combined filtering (type + role + topic together)
7. 9c-6: Weighted scoring (add confidence + importance to relevance score)

**Metadata Schema**:
- document_type: 'argument', 'question', 'answer', 'evidence', 'summary'
- role: 'pro', 'con', 'neutral', 'moderator'
- topic: main debate subject (e.g., 'climate_change', 'healthcare')
- confidence: argument strength 0.0-1.0
- sentiment: polarity -1.0 to +1.0
- importance: debate relevance 0.0-1.0

**Success Criteria**:
- Best strategy achieves ≥34% precision (+1.05pp from 32.95%)
- Best strategy achieves ≥73% relevance (+2pp from 70-71%)
- Recall maintained ≥90% (currently 92.31%)
- Tests passed +1-2 (from 5/13 to 6-7/13)
"""

import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

# Import core RAG components
from memory.memory_manager import get_memory_manager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios


@dataclass
class MetadataProfile:
    """Extracted metadata profile for a document."""
    document_type: str  # argument, question, answer, evidence, summary
    role: Optional[str]  # pro, con, neutral, moderator
    topic: Optional[str]  # main debate subject
    confidence: float  # argument strength 0.0-1.0
    sentiment: float  # polarity -1.0 to +1.0
    importance: float  # debate relevance 0.0-1.0
    entities: List[str]  # named entities
    source_type: Optional[str]  # expert_testimony, statistics, anecdote, logical_reasoning


class MetadataExtractor:
    """Extract rich metadata from text for filtering."""
    
    def __init__(self):
        """Initialize metadata extraction patterns."""
        # Document type patterns
        self.question_patterns = [
            r'\?$', r'^(?:what|why|how|when|where|who|which|is|are|can|could|would|should|do|does)',
            r'(?:explain|clarify|elaborate)'
        ]
        
        self.answer_patterns = [
            r'^(?:yes|no|because|the answer|i think|in my opinion)',
            r'(?:therefore|thus|hence|so|consequently)'
        ]
        
        self.evidence_patterns = [
            r'(?:according to|research shows|studies indicate|data suggests)',
            r'(?:\d+%|\d+\.\d+%)', r'(?:source:|citation:|reference:)',
            r'(?:published|peer-reviewed|journal)'
        ]
        
        self.summary_patterns = [
            r'^(?:in summary|to summarize|in conclusion|overall)',
            r'(?:key points?|main arguments?|takeaways?)'
        ]
        
        # Role stance patterns
        self.pro_patterns = [
            r'(?:support|agree|favor|benefit|positive|advantage|good|better|should|must)',
            r'(?:important|necessary|essential|valuable|effective)'
        ]
        
        self.con_patterns = [
            r'(?:oppose|disagree|against|harmful|negative|disadvantage|bad|worse|shouldn\'t)',
            r'(?:unnecessary|ineffective|dangerous|problematic|flawed)'
        ]
        
        self.neutral_patterns = [
            r'(?:however|although|on the other hand|both sides|balanced view)',
            r'(?:depends|varies|context|nuanced|complex)'
        ]
        
        # Confidence indicators
        self.high_confidence = [
            r'(?:certainly|definitely|clearly|obviously|undoubtedly|proven|fact)',
            r'(?:\d+% of|majority|consensus|overwhelming|significant)'
        ]
        
        self.low_confidence = [
            r'(?:maybe|perhaps|possibly|might|could|uncertain|unclear)',
            r'(?:speculation|assumption|guess|unclear|ambiguous)'
        ]
        
        # Sentiment lexicon (simple positive/negative word lists)
        self.positive_words = {
            'good', 'great', 'excellent', 'positive', 'beneficial', 'effective',
            'successful', 'important', 'valuable', 'significant', 'strong', 'better',
            'improved', 'advantage', 'benefit', 'support', 'helpful'
        }
        
        self.negative_words = {
            'bad', 'poor', 'negative', 'harmful', 'ineffective', 'failed',
            'unsuccessful', 'insignificant', 'weak', 'worse', 'declined',
            'disadvantage', 'problem', 'issue', 'concern', 'risk'
        }
        
        # Source type patterns
        self.expert_patterns = [
            r'(?:expert|professor|dr\.|phd|researcher|scientist|authority)'
        ]
        
        self.statistics_patterns = [
            r'(?:\d+%|\d+\.\d+%)', r'(?:study|survey|poll|data|statistics|research)'
        ]
        
        self.anecdote_patterns = [
            r'(?:i remember|in my experience|once|story|example|case)'
        ]
    
    def extract_metadata(self, text: str, existing_metadata: Optional[Dict] = None) -> MetadataProfile:
        """Extract comprehensive metadata from text.
        
        Args:
            text: Document text to analyze
            existing_metadata: Existing metadata to preserve/enhance
            
        Returns:
            MetadataProfile with extracted metadata
        """
        text_lower = text.lower()
        
        # Document type classification
        doc_type = self._classify_document_type(text_lower)
        
        # Role detection
        role = self._detect_role(text_lower, existing_metadata)
        
        # Topic extraction (from existing metadata or text)
        topic = self._extract_topic(text_lower, existing_metadata)
        
        # Confidence scoring
        confidence = self._score_confidence(text_lower)
        
        # Sentiment analysis
        sentiment = self._analyze_sentiment(text_lower)
        
        # Importance scoring
        importance = self._score_importance(text, text_lower)
        
        # Entity extraction (basic pattern-based)
        entities = self._extract_entities(text)
        
        # Source type classification
        source_type = self._classify_source(text_lower)
        
        return MetadataProfile(
            document_type=doc_type,
            role=role,
            topic=topic,
            confidence=confidence,
            sentiment=sentiment,
            importance=importance,
            entities=entities,
            source_type=source_type
        )
    
    def _classify_document_type(self, text_lower: str) -> str:
        """Classify document as argument, question, answer, evidence, or summary."""
        # Check patterns in priority order
        if any(re.search(pattern, text_lower) for pattern in self.question_patterns):
            return 'question'
        
        if any(re.search(pattern, text_lower) for pattern in self.summary_patterns):
            return 'summary'
        
        if any(re.search(pattern, text_lower) for pattern in self.evidence_patterns):
            return 'evidence'
        
        if any(re.search(pattern, text_lower) for pattern in self.answer_patterns):
            return 'answer'
        
        # Default to argument if no specific type detected
        return 'argument'
    
    def _detect_role(self, text_lower: str, existing_metadata: Optional[Dict]) -> Optional[str]:
        """Detect stance: pro, con, neutral, or moderator."""
        # Check existing metadata first
        if existing_metadata and 'role' in existing_metadata:
            return existing_metadata['role']
        
        # Pattern-based detection
        pro_count = sum(1 for pattern in self.pro_patterns if re.search(pattern, text_lower))
        con_count = sum(1 for pattern in self.con_patterns if re.search(pattern, text_lower))
        neutral_count = sum(1 for pattern in self.neutral_patterns if re.search(pattern, text_lower))
        
        # If neutral indicators present, likely neutral
        if neutral_count > 0:
            return 'neutral'
        
        # Compare pro vs con indicators
        if pro_count > con_count * 1.5:
            return 'pro'
        elif con_count > pro_count * 1.5:
            return 'con'
        elif pro_count > 0 or con_count > 0:
            return 'neutral'  # Mixed signals
        
        return None  # Cannot determine
    
    def _extract_topic(self, text_lower: str, existing_metadata: Optional[Dict]) -> Optional[str]:
        """Extract main debate topic."""
        # Check existing metadata first
        if existing_metadata and 'debate_id' in existing_metadata:
            return existing_metadata['debate_id']
        
        if existing_metadata and 'topic' in existing_metadata:
            return existing_metadata['topic']
        
        # Basic topic keywords (can be expanded)
        topics = {
            'climate': 'climate_change',
            'warming': 'climate_change',
            'carbon': 'climate_change',
            'healthcare': 'healthcare',
            'medical': 'healthcare',
            'economy': 'economics',
            'economic': 'economics',
            'education': 'education',
            'school': 'education',
            'technology': 'technology',
            'tech': 'technology',
            'ai': 'artificial_intelligence',
            'artificial intelligence': 'artificial_intelligence'
        }
        
        for keyword, topic_name in topics.items():
            if keyword in text_lower:
                return topic_name
        
        return None  # Cannot determine
    
    def _score_confidence(self, text_lower: str) -> float:
        """Score argument confidence 0.0-1.0 based on hedging and certainty language."""
        high_conf_count = sum(1 for pattern in self.high_confidence if re.search(pattern, text_lower))
        low_conf_count = sum(1 for pattern in self.low_confidence if re.search(pattern, text_lower))
        
        # Base confidence
        confidence = 0.5
        
        # Adjust based on indicators
        confidence += high_conf_count * 0.1
        confidence -= low_conf_count * 0.15
        
        # Evidence presence boosts confidence
        if any(re.search(pattern, text_lower) for pattern in self.evidence_patterns):
            confidence += 0.15
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, confidence))
    
    def _analyze_sentiment(self, text_lower: str) -> float:
        """Analyze sentiment polarity -1.0 to +1.0."""
        words = set(text_lower.split())
        
        positive_count = len(words & self.positive_words)
        negative_count = len(words & self.negative_words)
        
        total_sentiment_words = positive_count + negative_count
        
        if total_sentiment_words == 0:
            return 0.0  # Neutral
        
        # Calculate polarity
        polarity = (positive_count - negative_count) / total_sentiment_words
        
        return polarity
    
    def _score_importance(self, text: str, text_lower: str) -> float:
        """Score debate relevance 0.0-1.0 based on document characteristics."""
        importance = 0.5  # Base importance
        
        # Length factor (longer documents often more substantive)
        text_len = len(text)
        if text_len > 500:
            importance += 0.1
        elif text_len < 100:
            importance -= 0.1
        
        # Evidence presence
        if any(re.search(pattern, text_lower) for pattern in self.evidence_patterns):
            importance += 0.15
        
        # Multiple arguments/points
        sentences = text.split('.')
        if len(sentences) > 5:
            importance += 0.1
        
        # Expert references
        if any(re.search(pattern, text_lower) for pattern in self.expert_patterns):
            importance += 0.1
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, importance))
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities using simple pattern matching."""
        entities = []
        
        # Capitalized words (simple NER approximation)
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        # Filter out common non-entities
        stopwords = {'The', 'A', 'An', 'In', 'On', 'At', 'To', 'For', 'Of', 'As', 'By', 'Is', 'Are', 'Was', 'Were'}
        entities = [w for w in words if w not in stopwords]
        
        return list(set(entities))[:10]  # Return top 10 unique entities
    
    def _classify_source(self, text_lower: str) -> Optional[str]:
        """Classify evidence source type."""
        if any(re.search(pattern, text_lower) for pattern in self.expert_patterns):
            return 'expert_testimony'
        
        if any(re.search(pattern, text_lower) for pattern in self.statistics_patterns):
            return 'statistics'
        
        if any(re.search(pattern, text_lower) for pattern in self.anecdote_patterns):
            return 'anecdote'
        
        # Check for logical reasoning indicators
        if any(word in text_lower for word in ['therefore', 'thus', 'hence', 'because', 'since']):
            return 'logical_reasoning'
        
        return None


class MetadataFilterStrategy:
    """Base class for metadata filtering strategies."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.extractor = MetadataExtractor()
    
    def filter_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        metadata_profiles: Dict[str, MetadataProfile]
    ) -> List[Dict[str, Any]]:
        """Filter and rerank results based on metadata.
        
        Args:
            query: Search query
            results: Retrieved documents with scores
            metadata_profiles: Extracted metadata for each document
            
        Returns:
            Filtered and reranked results
        """
        raise NotImplementedError("Subclasses must implement filter_results")


class BaselineStrategy(MetadataFilterStrategy):
    """9c-0: No metadata filtering (control group)."""
    
    def __init__(self):
        super().__init__(
            name="9c-0-baseline",
            description="No metadata filtering (control)"
        )
    
    def filter_results(self, query, results, metadata_profiles):
        """Return results unchanged."""
        return results


class DocumentTypeFilterStrategy(MetadataFilterStrategy):
    """9c-1: Filter by document type relevance."""
    
    def __init__(self):
        super().__init__(
            name="9c-1-doc-type",
            description="Remove off-topic document types"
        )
    
    def filter_results(self, query, results, metadata_profiles):
        """Filter out summary/question documents, prefer arguments/evidence."""
        # Extract query type
        query_lower = query.lower()
        query_is_question = '?' in query or query_lower.startswith(('what', 'why', 'how', 'when', 'where', 'who'))
        
        filtered = []
        for result in results:
            doc_id = result.get('id', '')
            profile = metadata_profiles.get(doc_id)
            
            if not profile:
                filtered.append(result)
                continue
            
            # For questions, prefer answers and evidence
            if query_is_question:
                if profile.document_type in ['answer', 'evidence', 'argument']:
                    filtered.append(result)
            else:
                # For statements, prefer arguments and evidence
                if profile.document_type in ['argument', 'evidence']:
                    filtered.append(result)
        
        return filtered[:len(results)]  # Maintain original result count


class RoleFilterStrategy(MetadataFilterStrategy):
    """9c-2: Filter by role alignment."""
    
    def __init__(self):
        super().__init__(
            name="9c-2-role",
            description="Match query role with document role"
        )
    
    def filter_results(self, query, results, metadata_profiles):
        """Prefer documents matching query's stance."""
        # Extract query role
        query_profile = self.extractor.extract_metadata(query)
        query_role = query_profile.role
        
        if not query_role:
            return results  # Cannot filter without query role
        
        # Separate role-matched and role-neutral documents
        matched = []
        neutral = []
        mismatched = []
        
        for result in results:
            doc_id = result.get('id', '')
            profile = metadata_profiles.get(doc_id)
            
            if not profile or not profile.role:
                neutral.append(result)
            elif profile.role == query_role:
                matched.append(result)
            elif profile.role == 'neutral':
                neutral.append(result)
            else:
                mismatched.append(result)
        
        # Prioritize: matched > neutral > mismatched
        return matched + neutral + mismatched


class TopicFilterStrategy(MetadataFilterStrategy):
    """9c-3: Filter by topic alignment."""
    
    def __init__(self):
        super().__init__(
            name="9c-3-topic",
            description="Require topic alignment"
        )
    
    def filter_results(self, query, results, metadata_profiles):
        """Prefer documents matching query topic."""
        # Extract query topic
        query_profile = self.extractor.extract_metadata(query)
        query_topic = query_profile.topic
        
        if not query_topic:
            return results  # Cannot filter without query topic
        
        # Separate topic-matched and unknown-topic documents
        matched = []
        unknown = []
        
        for result in results:
            doc_id = result.get('id', '')
            profile = metadata_profiles.get(doc_id)
            
            if not profile or not profile.topic:
                unknown.append(result)
            elif profile.topic == query_topic:
                matched.append(result)
        
        # Prioritize: matched > unknown
        return matched + unknown


class ConfidenceFilterStrategy(MetadataFilterStrategy):
    """9c-4: Filter by confidence threshold."""
    
    def __init__(self, threshold: float = 0.6):
        super().__init__(
            name="9c-4-confidence",
            description=f"Threshold at {threshold} argument strength"
        )
        self.threshold = threshold
    
    def filter_results(self, query, results, metadata_profiles):
        """Filter out low-confidence documents."""
        filtered = []
        
        for result in results:
            doc_id = result.get('id', '')
            profile = metadata_profiles.get(doc_id)
            
            # Keep if confidence meets threshold or unknown
            if not profile or profile.confidence >= self.threshold:
                filtered.append(result)
        
        return filtered


class CombinedFilterStrategy(MetadataFilterStrategy):
    """9c-5: Combine type + role + topic filtering."""
    
    def __init__(self):
        super().__init__(
            name="9c-5-combined",
            description="Type + role + topic together"
        )
        self.type_filter = DocumentTypeFilterStrategy()
        self.role_filter = RoleFilterStrategy()
        self.topic_filter = TopicFilterStrategy()
    
    def filter_results(self, query, results, metadata_profiles):
        """Apply all filters sequentially."""
        results = self.type_filter.filter_results(query, results, metadata_profiles)
        results = self.role_filter.filter_results(query, results, metadata_profiles)
        results = self.topic_filter.filter_results(query, results, metadata_profiles)
        return results


class WeightedScoringStrategy(MetadataFilterStrategy):
    """9c-6: Add confidence + importance weights to scores."""
    
    def __init__(self, confidence_weight: float = 0.1, importance_weight: float = 0.1):
        super().__init__(
            name="9c-6-weighted",
            description=f"Add confidence ({confidence_weight}) + importance ({importance_weight}) to scores"
        )
        self.confidence_weight = confidence_weight
        self.importance_weight = importance_weight
    
    def filter_results(self, query, results, metadata_profiles):
        """Rerank results by adding metadata scores."""
        reranked = []
        
        for result in results:
            doc_id = result.get('id', '')
            profile = metadata_profiles.get(doc_id)
            
            # Calculate boosted score
            base_score = result.get('score', 0.0)
            
            if profile:
                metadata_boost = (
                    profile.confidence * self.confidence_weight +
                    profile.importance * self.importance_weight
                )
                new_score = base_score + metadata_boost
            else:
                new_score = base_score
            
            result_copy = result.copy()
            result_copy['score'] = new_score
            reranked.append(result_copy)
        
        # Re-sort by new scores
        reranked.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        return reranked


def test_metadata_strategy(
    strategy: MetadataFilterStrategy,
    memory_manager
) -> Dict[str, Any]:
    """Test a single metadata filtering strategy.
    
    Args:
        strategy: Metadata filtering strategy to test
        memory_manager: Memory manager instance with vector store
        
    Returns:
        Dictionary with benchmark results
    """
    print(f"\n{'='*70}")
    print(f"[TEST] Testing Strategy: {strategy.name}")
    print(f"   Description: {strategy.description}")
    print(f"{'='*70}\n")
    
    # Pre-extract metadata for all documents in vector store
    print("[EXTRACT] Extracting metadata profiles for all documents...")
    metadata_profiles = {}
    
    # Get all document IDs and texts from vector store
    vector_store = memory_manager.long_term  # HybridMemoryManager uses 'long_term' for vector store
    if vector_store and hasattr(vector_store, 'id_to_metadata') and hasattr(vector_store, 'index'):
        num_docs = vector_store.index.ntotal
        print(f"   Found {num_docs} documents in vector store")
        
        if num_docs == 0:
            print("   [WARNING] Vector store is empty - no documents to analyze")
            print("   [NOTE] Benchmark will load test data automatically\n")
        else:
            for doc_id, metadata in vector_store.id_to_metadata.items():
                text = metadata.get('text', '')
                if text:
                    profile = strategy.extractor.extract_metadata(text, metadata)
                    metadata_profiles[doc_id] = profile
            
            print(f"   [OK] Extracted {len(metadata_profiles)} metadata profiles\n")
    
    # Monkey-patch memory manager's search_memories to apply metadata filtering
    original_search_memories = memory_manager.search_memories
    
    def filtered_search_memories(query: str, top_k: int = 5, **kwargs):
        """Wrapper that applies metadata filtering to search results."""
        # Get original results (list of MemoryEntry objects)
        results = original_search_memories(query, top_k=top_k, **kwargs)
        
        # If no filtering strategy (baseline), return as-is
        if strategy.name == "9c-0-baseline":
            return results
        
        # Extract document IDs and refresh metadata profiles if needed
        if vector_store and hasattr(vector_store, 'id_to_metadata'):
            for doc_id, metadata in vector_store.id_to_metadata.items():
                if doc_id not in metadata_profiles:
                    text = metadata.get('text', '')
                    if text:
                        metadata_profiles[doc_id] = strategy.extractor.extract_metadata(text, metadata)
        
        # Convert MemoryEntry objects to dicts for filtering
        # Format expected by filter_results: [{'id': str, 'score': float, 'text': str, ...}, ...]
        results_dicts = []
        for r in results:
            result_dict = {
                'id': r['id'],
                'score': r.get('score', 1.0),
                'text': r['text'],
                'metadata': r.get('metadata', {})
            }
            results_dicts.append(result_dict)
        
        # Apply strategy filtering to dict format
        filtered_dicts = strategy.filter_results(query, results_dicts, metadata_profiles)
        
        # Convert back to MemoryEntry objects (keep original objects where IDs match)
        id_to_entry = {r['id']: r for r in results}
        filtered_results = []
        for filtered_dict in filtered_dicts:
            entry_id = filtered_dict['id']
            if entry_id in id_to_entry:
                filtered_results.append(id_to_entry[entry_id])
        
        return filtered_results
    
    # Replace search_memories method temporarily
    memory_manager.search_memories = filtered_search_memories
    
    try:
        # Create benchmark and load test scenarios
        benchmark = RAGBenchmark(memory_manager)
        load_all_test_scenarios(benchmark)
        
        # Run benchmark
        results = benchmark.run_benchmark(verbose=False)
        
        # Restore original search_memories method
        memory_manager.search_memories = original_search_memories
        
        return {
            'strategy': strategy.name,
            'description': strategy.description,
            'results': results
        }
    
    except Exception as e:
        # Restore original search_memories method on error
        memory_manager.search_memories = original_search_memories
        raise e


def run_step9c_tests():
    """Execute Step 9c metadata expansion testing."""
    # Set UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("\n" + "="*70)
    print("STEP 9c: METADATA EXPANSION TESTING")
    print("="*70)
    print(f"\n[START] Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n[BASELINE] Baseline Performance (Alpha-v7 REVISED):")
    print(f"   - Relevance: 70-71% (validated via 5 runs)")
    print(f"   - Precision: 32.95%")
    print(f"   - Recall: 92.31%")
    print(f"   - Tests Passing: 5/13")
    print(f"\n[TARGET] Target Performance (Alpha-v9):")
    print(f"   - Relevance: >=73% (+2-3pp)")
    print(f"   - Precision: >=34% (+1.05pp)")
    print(f"   - Recall: >=90% (maintain)")
    print(f"   - Tests Passing: 6-7/13 (+1-2 tests)")
    
    # Initialize RAG system
    print(f"\n[INIT] Initializing RAG system...")
    memory = get_memory_manager(long_term_backend="faiss")
    print("[OK] Memory manager initialized\n")
    
    # Define strategies to test
    strategies = [
        BaselineStrategy(),  # Control group
        DocumentTypeFilterStrategy(),
        RoleFilterStrategy(),
        TopicFilterStrategy(),
        ConfidenceFilterStrategy(threshold=0.6),
        CombinedFilterStrategy(),
        WeightedScoringStrategy(confidence_weight=0.1, importance_weight=0.1)
    ]
    
    print(f"\n[STRATEGIES] Testing {len(strategies)} metadata strategies:")
    for i, strategy in enumerate(strategies, 1):
        print(f"   {i}. {strategy.name}: {strategy.description}")
    
    # Run tests for each strategy
    all_results = []
    
    for strategy in strategies:
        try:
            result = test_metadata_strategy(strategy, memory)
            if result:  # Only add if test succeeded
                all_results.append(result)
        except Exception as e:
            print(f"\n[ERROR] Error testing {strategy.name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Analyze results
    print("\n" + "="*70)
    print("[RESULTS] STEP 9c RESULTS SUMMARY")
    print("="*70)
    
    # Save results to file
    results_dir = backend_dir / "phase2" / "results"
    results_dir.mkdir(exist_ok=True)
    
    results_file = results_dir / f"step9c_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n[SAVE] Results saved to: {results_file}")
    
    # Display comparison table
    print(f"\n{'Strategy':<25} {'Relevance':<12} {'Precision':<12} {'Recall':<10} {'Tests':<8}")
    print("-" * 70)
    
    best_relevance = None
    best_precision = None
    best_strategy = None
    
    for result in all_results:
        strategy_name = result['strategy']
        metrics = result['results']
        
        relevance = metrics.get('relevance', 0) * 100
        precision = metrics.get('precision', 0) * 100
        recall = metrics.get('recall', 0) * 100
        tests = metrics.get('tests_passed', 0)
        
        print(f"{strategy_name:<25} {relevance:>10.2f}% {precision:>10.2f}% {recall:>8.2f}% {tests:>6}/13")
        
        # Track best performers
        if best_relevance is None or relevance > best_relevance:
            best_relevance = relevance
        
        if best_precision is None or precision > best_precision:
            best_precision = precision
            best_strategy = strategy_name
    
    # Promotion decision
    print("\n" + "="*70)
    print("[DECISION] ALPHA-v9 PROMOTION DECISION")
    print("="*70)
    
    if not all_results or best_relevance is None or best_precision is None:
        print("\n[ERROR] No valid results to analyze. All strategies failed.")
        print("[NEXT] RECOMMENDATION: Debug vector store initialization")
        print("   - Check memory_manager.long_term is initialized")
        print("   - Verify vector store has documents loaded")
        print("   - Review error messages above for root cause")
        return
    
    meets_relevance = best_relevance >= 73.0
    meets_precision = best_precision >= 34.0
    
    print(f"\n[CHECK] Best Relevance: {best_relevance:.2f}% {'[PASS]' if meets_relevance else '[FAIL] (need >=73%)'}")
    print(f"[CHECK] Best Precision: {best_precision:.2f}% {'[PASS]' if meets_precision else '[FAIL] (need >=34%)'}")
    print(f"[CHECK] Best Strategy: {best_strategy}")
    
    if meets_relevance and meets_precision:
        print(f"\n[PROMOTE] RECOMMENDATION: PROMOTE TO ALPHA-v9")
        print(f"   - Strategy {best_strategy} meets all criteria")
        print(f"   - Save configuration via rag_version_control.py")
        print(f"   - Update Phase 2 log with Step 9c success")
    else:
        print(f"\n[NEXT] RECOMMENDATION: PROCEED TO STEP 9f (CROSS-ENCODER RERANKING)")
        print(f"   - Metadata filtering insufficient (+{best_precision - 32.95:.2f}pp precision)")
        print(f"   - Expected Step 9f gains: +0.5-1pp precision, +1-2pp relevance")
        print(f"   - Combined 9c + 9f should reach Alpha-v9 criteria")
    
    print(f"\n[COMPLETE] Step 9c testing complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_step9c_tests()

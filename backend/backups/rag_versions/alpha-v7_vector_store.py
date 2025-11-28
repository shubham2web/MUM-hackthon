"""
Vector Store for Long-Term Memory (RAG)

Implements semantic search and retrieval using ChromaDB or FAISS.
This is ZONE 2 in the Hybrid Memory System.

Enhancements:
- Hybrid lexical + semantic retrieval via BM25 (precision boost)
- Optional cross-encoder re-ranking (OPTIMIZATION 4)
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple, Literal
from datetime import datetime
import numpy as np
from dataclasses import dataclass, field
import re

from memory.embeddings import get_embedding_service

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - handled gracefully at runtime
    BM25Okapi = None


@dataclass
class MemoryEntry:
    """A single memory entry in long-term storage"""
    id: str
    text: str
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Generate embedding if not provided"""
        if self.embedding is None and self.text:
            embedding_service = get_embedding_service()
            self.embedding = embedding_service.embed_text(self.text)


@dataclass
class RetrievalResult:
    """Result from semantic or hybrid search"""

    id: str
    text: str
    score: float  # Final (possibly hybrid) relevance score (higher = more relevant)
    metadata: Dict[str, Any]
    rank: int  # 1 = most relevant
    vector_score: float = 0.0  # Raw vector similarity score before hybrid blending
    lexical_score: float = 0.0  # Normalized lexical/BM25 score used for hybrid blending


class VectorStore:
    """
    Vector database for long-term memory with semantic search.
    
    Supports two backends:
    1. ChromaDB (persistent, recommended for production)
    2. FAISS (in-memory, fast, good for development)
    """
    
    def __init__(
        self,
        collection_name: str = "atlas_memory",
        backend: Literal["chromadb", "faiss"] = "faiss",
        persist_directory: str = "database/vector_store",
        enable_reranking: bool = False,  # STEP 4 FAILED: HGB hurt performance -2.66% (72.95% → 70.29%) - DISABLED
        enable_hybrid_bm25: bool = True,
        hybrid_vector_weight: float = 0.97,  # STEP 7b OPTIMIZED: Grid search validation found 0.97 = 74.30% relevance (+0.23% vs 0.95, +2.52pp total)
        query_preprocessing_mode: str = "7e-1",  # STEP 7e ALPHA-V7: Basic normalization = 74.78% (+0.48pp gain, zero cost)
    ):
        """
        Initialize vector store.
        
        Args:
            collection_name: Name of the collection/index
            backend: "chromadb" or "faiss"
            persist_directory: Directory for persistent storage
            enable_reranking: Whether to enable LLM re-ranking for better precision
            hybrid_vector_weight: Vector weight in hybrid retrieval (0.85 = 85% semantic, 15% lexical)
            query_preprocessing_mode: Query preprocessing mode ("baseline", "7e-1", "7e-2", "7e-3", "7e-4", "7e-5")
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.collection_name = collection_name
        self.backend = backend
        self.persist_directory = persist_directory
        self.enable_reranking = enable_reranking
        self.enable_hybrid_bm25 = enable_hybrid_bm25 and (BM25Okapi is not None)

        # Allow runtime override via environment variable for quick experimentation
        env_vector_weight = os.getenv("HYBRID_VECTOR_WEIGHT")
        if env_vector_weight is not None:
            try:
                hybrid_vector_weight = float(env_vector_weight)
            except ValueError:
                self.logger.warning("Invalid HYBRID_VECTOR_WEIGHT value: %s", env_vector_weight)
        
        # STEP 7e: Query preprocessing
        env_preprocessing_mode = os.getenv("QUERY_PREPROCESSING_MODE")
        if env_preprocessing_mode is not None:
            query_preprocessing_mode = env_preprocessing_mode
        
        self.query_preprocessing_mode = query_preprocessing_mode
        self._query_preprocessor = None  # Lazy initialization

        # Clamp weights to a sensible range
        hybrid_vector_weight = max(0.0, min(1.0, hybrid_vector_weight))
        self.hybrid_vector_weight = hybrid_vector_weight
        self.hybrid_lexical_weight = 1.0 - self.hybrid_vector_weight

        if enable_hybrid_bm25 and BM25Okapi is None:
            self.logger.warning("rank-bm25 not installed, disabling hybrid lexical retrieval")
            self.enable_hybrid_bm25 = False

        if self.enable_hybrid_bm25:
            self.logger.info(
                "Hybrid retrieval enabled (vector weight=%.2f, lexical weight=%.2f)",
                self.hybrid_vector_weight,
                self.hybrid_lexical_weight,
            )

        # Lazy-initialized BM25 index stores
        self.lexical_ids: List[str] = []
        self.lexical_corpus: List[List[str]] = []
        self.lexical_texts: Dict[str, str] = {}
        self.lexical_metadata: Dict[str, Dict[str, Any]] = {}
        self.bm25 = None
        
        # Get embedding service
        self.embedding_service = get_embedding_service()
        self.dimension = self.embedding_service.get_dimension()
        
        # Initialize HGB Soft Bias Re-ranker (Step 4: Conservative 30% weight)
        self.ltr_reranker = None
        if self.enable_reranking:
            try:
                from memory.ltr_reranker import get_ltr_reranker
                # Step 4: Use HGB model with conservative 0.3 weight (NOT 0.9)
                # final_score = 0.7 * hybrid_score + 0.3 * hgb_probability
                self.ltr_reranker = get_ltr_reranker(
                    model_type="gradient_boosting",  # Use HGB model (79.7% ROC-AUC)
                    rerank_weight=0.3,  # CONSERVATIVE: 30% HGB, 70% hybrid (was 0.9 - too aggressive)
                    model_path=None  # Auto-detect ltr_reranker_gb.joblib
                )
                if self.ltr_reranker and self.ltr_reranker.enable_reranking:
                    self.logger.info("✅ HGB Soft Bias re-ranker initialized (weight=0.3, model=HGB)")
                else:
                    self.logger.warning(f"⚠️ HGB re-ranker not available: enable_reranking={self.ltr_reranker.enable_reranking if self.ltr_reranker else 'None'}")
                    self.enable_reranking = False
            except Exception as e:
                self.logger.error(f"❌ HGB re-ranker failed to load: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.enable_reranking = False
        
        # Initialize Hybrid Fusion Layer (RAG v2.0)
        self.hybrid_fusion = None
        if self.enable_hybrid_bm25:
            try:
                from memory.hybrid_fusion import get_hybrid_fusion
                self.hybrid_fusion = get_hybrid_fusion(
                    default_alpha=0.75,
                    enable_adaptive=True,
                    enable_rrf=False
                )
                self.logger.info("✅ Hybrid Fusion Layer initialized (adaptive alpha enabled)")
            except Exception as e:
                self.logger.warning(f"⚠️ Hybrid Fusion Layer not available, using fixed weights: {e}")
        
        self.logger.info(f"Reranking status: enable_reranking={self.enable_reranking}, ltr_reranker={self.ltr_reranker is not None}")
        
        # Initialize backend
        self.client = None
        self.collection = None
        self.index = None  # For FAISS
        self.id_to_metadata = {}  # For FAISS metadata storage
        
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize the selected vector store backend"""
        try:
            if self.backend == "chromadb":
                self._init_chromadb()
            elif self.backend == "faiss":
                self._init_faiss()
            else:
                raise ValueError(f"Unsupported backend: {self.backend}")
            
            self.logger.info(f"✅ Vector store initialized: {self.backend} (dim={self.dimension})")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.backend}: {e}")
            # Fallback to FAISS if ChromaDB fails
            if self.backend != "faiss":
                self.logger.warning("Falling back to FAISS backend")
                self.backend = "faiss"
                self._init_faiss()
    
    def _get_query_preprocessor(self):
        """Lazy initialization of query preprocessor (Step 7e)"""
        if self._query_preprocessor is None and self.query_preprocessing_mode != "baseline":
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
                
                self._query_preprocessor = {
                    'lemmatizer': WordNetLemmatizer(),
                    'wordnet': wordnet,
                    'nltk': nltk
                }
            except ImportError:
                self.logger.warning("NLTK not installed. Query preprocessing disabled. Install: pip install nltk")
                self.query_preprocessing_mode = "baseline"
        return self._query_preprocessor
    
    def _preprocess_query(self, query: str) -> str:
        """Apply query preprocessing based on mode (Step 7e)"""
        if self.query_preprocessing_mode == "baseline":
            return query
        
        # 7e-1: Basic normalization
        processed = self._basic_normalize_query(query)
        
        if self.query_preprocessing_mode == "7e-1":
            return processed
        
        # Get NLP tools
        preprocessor = self._get_query_preprocessor()
        if not preprocessor:
            return processed  # Fallback to basic if NLTK unavailable
        
        # 7e-2: Lemmatization
        if self.query_preprocessing_mode in ["7e-2", "7e-3", "7e-4", "7e-5"]:
            processed = self._lemmatize_query(processed, preprocessor)
        
        if self.query_preprocessing_mode == "7e-2":
            return processed
        
        # 7e-3: Synonym expansion
        if self.query_preprocessing_mode in ["7e-3", "7e-4", "7e-5"]:
            processed = self._expand_synonyms_query(processed, preprocessor)
        
        if self.query_preprocessing_mode == "7e-3":
            return processed
        
        # 7e-4 & 7e-5: Contextual re-weighting
        if self.query_preprocessing_mode in ["7e-4", "7e-5"]:
            processed = self._contextual_reweight_query(processed, preprocessor)
        
        return processed
    
    def _basic_normalize_query(self, query: str) -> str:
        """7e-1: Basic query normalization"""
        query = query.lower()
        query = re.sub(r'\d+', '<NUM>', query)
        query = re.sub(r'[?!]{2,}', '?', query)
        query = re.sub(r'\.{2,}', '.', query)
        return query.strip()
    
    def _lemmatize_query(self, query: str, preprocessor: dict) -> str:
        """7e-2: Lemmatize query terms"""
        tokens = preprocessor['nltk'].word_tokenize(query)
        pos_tags = preprocessor['nltk'].pos_tag(tokens)
        
        lemmatized = []
        for word, pos in pos_tags:
            wn_pos = self._get_wordnet_pos(pos, preprocessor['wordnet'])
            if wn_pos:
                lemmatized.append(preprocessor['lemmatizer'].lemmatize(word, pos=wn_pos))
            else:
                lemmatized.append(preprocessor['lemmatizer'].lemmatize(word))
        
        return ' '.join(lemmatized)
    
    def _get_wordnet_pos(self, treebank_tag: str, wordnet) -> str:
        """Convert treebank POS tag to WordNet POS"""
        if treebank_tag.startswith('J'):
            return wordnet.ADJ
        elif treebank_tag.startswith('V'):
            return wordnet.VERB
        elif treebank_tag.startswith('N'):
            return wordnet.NOUN
        elif treebank_tag.startswith('R'):
            return wordnet.ADV
        return None
    
    def _expand_synonyms_query(self, query: str, preprocessor: dict) -> str:
        """7e-3: Expand query with synonyms"""
        tokens = preprocessor['nltk'].word_tokenize(query)
        pos_tags = preprocessor['nltk'].pos_tag(tokens)
        
        expanded = []
        for word, pos in pos_tags:
            expanded.append(word)
            
            if pos.startswith('N') or pos.startswith('V'):
                synsets = preprocessor['wordnet'].synsets(word)
                if synsets:
                    synonyms = set()
                    for syn in synsets[:2]:
                        for lemma in syn.lemmas()[:2]:
                            synonym = lemma.name().replace('_', ' ')
                            if synonym.lower() != word.lower():
                                synonyms.add(synonym)
                    
                    for syn in list(synonyms)[:2]:
                        expanded.append(syn)
        
        return ' '.join(expanded)
    
    def _contextual_reweight_query(self, query: str, preprocessor: dict) -> str:
        """7e-4: Boost key nouns/verbs by repetition"""
        tokens = preprocessor['nltk'].word_tokenize(query)
        pos_tags = preprocessor['nltk'].pos_tag(tokens)
        
        reweighted = []
        for word, pos in pos_tags:
            reweighted.append(word)
            
            if pos.startswith('N') or pos.startswith('V') or pos.startswith('J'):
                reweighted.append(word)  # Repeat key terms
        
        return ' '.join(reweighted)
    
    def _init_chromadb(self):
        """Initialize ChromaDB backend"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Create persist directory if needed
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                self.logger.info(f"Loaded existing collection: {self.collection_name}")
            except:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"dimension": self.dimension}
                )
                self.logger.info(f"Created new collection: {self.collection_name}")
            
        except ImportError:
            self.logger.error("chromadb not installed. Install: pip install chromadb")
            raise
    
    def _init_faiss(self):
        """Initialize FAISS backend (in-memory)"""
        try:
            import faiss
            
            # Create FAISS index (L2 distance)
            self.index = faiss.IndexFlatL2(self.dimension)
            
            # Enable ID mapping
            self.index = faiss.IndexIDMap(self.index)
            
            self.id_to_metadata = {}
            
            self.logger.info(f"Created FAISS index with dimension {self.dimension}")
            
        except ImportError:
            self.logger.error("faiss-cpu not installed. Install: pip install faiss-cpu")
            raise

    # ------------------------------------------------------------------
    # Lexical/BM25 hybrid helpers
    # ------------------------------------------------------------------

    def _calculate_adaptive_threshold(self, query: str, base_threshold: float) -> float:
        """
        Adjust similarity threshold based on query complexity.
        
        Strategy:
        - Complex queries (many unique terms) → lower threshold (more recall)
        - Simple queries (few terms) → higher threshold (more precision)
        - Very short queries (< 3 words) → raise threshold to avoid noise
        """
        tokens = self._tokenize(query)
        token_count = len(tokens)
        
        if token_count <= 2:
            # Very short query: raise threshold to avoid false positives
            return min(base_threshold + 0.10, 0.85)
        elif token_count <= 4:
            # Short query: use base threshold
            return base_threshold
        elif token_count <= 8:
            # Medium query: slightly lower threshold for better recall
            return max(base_threshold - 0.05, 0.40)
        else:
            # Long/complex query: lower threshold further
            return max(base_threshold - 0.10, 0.35)

    def _calculate_metadata_boost(self, metadata: Dict[str, Any]) -> float:
        """
        Calculate relevance boost based on metadata signals.
        
        Boosts:
        - Recent content (within last 10 turns): +15%
        - Authoritative roles (researcher, expert): +10%
        - User/assistant interactions: +5%
        """
        boost = 1.0
        
        # Recency boost
        turn = metadata.get('turn', 0)
        if turn > 0:
            # More recent = higher boost (exponential decay)
            recency_factor = min(turn / 100.0, 1.0)
            boost *= (1.0 + 0.15 * (1.0 - recency_factor))
        
        # Role boost
        role = metadata.get('role', '').lower()
        if role in ['researcher', 'expert', 'analyst']:
            boost *= 1.10
        elif role in ['user', 'assistant']:
            boost *= 1.05
        
        return boost

    def _tokenize(self, text: str) -> List[str]:
        """
        Enhanced tokenization for BM25 lexical retrieval.
        
        Improvements:
        - Lowercase normalization
        - Keep alphanumeric and hyphens
        - Filter common stopwords
        - Remove very short tokens (< 2 chars)
        """
        if not text:
            return []
        
        # Extract words (alphanumeric + hyphens)
        tokens = re.findall(r"\b\w+\b", text.lower())
        
        # Simple stopword list for English
        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'will', 'with', 'this', 'but'
        }
        
        # Filter: remove stopwords and very short tokens
        return [t for t in tokens if len(t) >= 2 and t not in stopwords]

    def _rebuild_lexical_index(self) -> None:
        """Rebuild BM25 index from stored lexical texts."""
        if not self.enable_hybrid_bm25:
            return
        self.lexical_ids = []
        self.lexical_corpus = []
        for memory_id, text in self.lexical_texts.items():
            tokens = self._tokenize(text)
            if not tokens:
                continue
            self.lexical_ids.append(memory_id)
            self.lexical_corpus.append(tokens)
        if self.lexical_corpus and BM25Okapi is not None:
            self.bm25 = BM25Okapi(self.lexical_corpus)
        else:
            self.bm25 = None

    def _update_lexical_index(self, memory_id: str, text: str, metadata: Dict[str, Any]) -> None:
        """Add or update a document inside the BM25 index."""
        if not self.enable_hybrid_bm25 or not text:
            return

        # Ensure we do not keep duplicate entries when IDs are reused
        if memory_id in self.lexical_texts:
            self._remove_from_lexical_index(memory_id)

        tokens = self._tokenize(text)
        if not tokens:
            return

        self.lexical_texts[memory_id] = text
        self.lexical_metadata[memory_id] = metadata or {}
        self.lexical_ids.append(memory_id)
        self.lexical_corpus.append(tokens)

        if BM25Okapi is not None:
            self.bm25 = BM25Okapi(self.lexical_corpus)

    def _remove_from_lexical_index(self, memory_id: str) -> None:
        """Remove a document from the BM25 index."""
        if not self.enable_hybrid_bm25:
            return

        if memory_id in self.lexical_texts:
            self.lexical_texts.pop(memory_id, None)
            self.lexical_metadata.pop(memory_id, None)
            # Full rebuild keeps implementation simple and data small
            self._rebuild_lexical_index()

    def _get_memory_from_backend(self, memory_id: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """Fetch text/metadata for a given memory ID."""
        # Prefer lexical cache to avoid backend calls
        if memory_id in self.lexical_texts:
            return self.lexical_texts[memory_id], self.lexical_metadata.get(memory_id, {})

        if self.backend == "chromadb":
            try:
                result = self.collection.get(
                    ids=[memory_id],
                    include=["documents", "metadatas"],
                )
                documents = result.get("documents") or []
                metadatas = result.get("metadatas") or []
                if documents:
                    text = documents[0]
                    metadata = metadatas[0] if metadatas else {}
                    return text, metadata
            except Exception as err:
                self.logger.debug(f"Failed to fetch document {memory_id} from Chroma: {err}")
        elif self.backend == "faiss":
            data = self.id_to_metadata.get(memory_id)
            if data:
                return data.get("text"), data.get("metadata", {})

        return None, {}

    def _blend_vector_and_lexical(
        self,
        query: str,
        vector_results: List[RetrievalResult],
        top_k: int,
    ) -> List[RetrievalResult]:
        """Combine vector retrieval with BM25 lexical scores for higher precision."""

        if not vector_results and not self.enable_hybrid_bm25:
            return []

        results_by_id: Dict[str, RetrievalResult] = {res.id: res for res in vector_results}

        # ------------------------------------------------------------------
        # Compute lexical scores using BM25 (if enabled and available)
        # ------------------------------------------------------------------
        lexical_scores: Dict[str, float] = {}
        lexical_candidates: List[Tuple[str, float]] = []

        # DEBUG: Log BM25 state
        self.logger.debug(f"🔍 BM25 STATE: enable_hybrid_bm25={self.enable_hybrid_bm25}, "
                         f"bm25_initialized={self.bm25 is not None}, "
                         f"lexical_ids_count={len(self.lexical_ids) if self.lexical_ids else 0}, "
                         f"corpus_size={len(self.lexical_corpus) if hasattr(self, 'lexical_corpus') else 0}")

        if self.enable_hybrid_bm25 and self.bm25 and self.lexical_ids:
            tokens = self._tokenize(query)
            self.logger.debug(f"🔍 BM25 TOKENIZE: query='{query[:50]}...' → tokens={tokens[:10] if len(tokens) > 10 else tokens}")
            if tokens:
                try:
                    scores = self.bm25.get_scores(tokens)
                    self.logger.debug(f"🔍 BM25 SCORES: got {len(scores)} scores, min={min(scores) if len(scores) > 0 else 0:.3f}, max={max(scores) if len(scores) > 0 else 0:.3f}")
                    
                    # FIX: BM25Okapi can return negative scores - don't filter them out!
                    # We'll normalize them later in the fusion pipeline
                    for idx, raw_score in enumerate(scores):
                        doc_id = self.lexical_ids[idx]
                        lexical_candidates.append((doc_id, float(raw_score)))
                    
                    self.logger.debug(f"🔍 BM25 CANDIDATES: {len(lexical_candidates)} total candidates (including negative scores)")
                except Exception as err:
                    self.logger.warning(f"BM25 scoring failed: {err}")
                    lexical_candidates = []

        lexical_candidates.sort(key=lambda item: item[1], reverse=True)
        lexical_limit = max(top_k * 2, top_k)
        lexical_candidates = lexical_candidates[:lexical_limit]

        if lexical_candidates:
            # FIX: Handle negative BM25 scores by shifting to [0, max]
            min_lexical = min(item[1] for item in lexical_candidates)
            max_lexical = max(item[1] for item in lexical_candidates)
            
            # Shift and normalize: (score - min) / (max - min) → [0, 1]
            score_range = max_lexical - min_lexical
            
            if score_range > 1e-9:  # Avoid division by zero
                for doc_id, raw_score in lexical_candidates:
                    # Shift to positive and normalize
                    normalized = (raw_score - min_lexical) / score_range
                    lexical_scores[doc_id] = normalized
                    if doc_id not in results_by_id:
                        text, metadata = self._get_memory_from_backend(doc_id)
                        if text:
                            results_by_id[doc_id] = RetrievalResult(
                                id=doc_id,
                                text=text,
                                score=0.0,
                                metadata=metadata,
                                rank=0,
                                vector_score=0.0,
                                lexical_score=normalized,
                            )
                self.logger.debug(f"🔍 BM25 NORMALIZED: min={min_lexical:.3f}, max={max_lexical:.3f}, "
                                 f"range={score_range:.3f}, {len(lexical_scores)} scores normalized")
            else:
                self.logger.warning(f"⚠️ BM25 scores have zero range: all scores identical ({max_lexical:.3f})")

        # ------------------------------------------------------------------
        # Blend vector and lexical signals using ADAPTIVE HYBRID FUSION
        # RAG v2.0: Replaces fixed 75/25 weights with query-aware alpha
        # ------------------------------------------------------------------
        lexical_available = bool(lexical_scores)  # FIX: Define before use
        
        # DEBUG: Log fusion decision factors
        self.logger.info(f"🔍 FUSION DECISION: lexical_available={lexical_available} (lexical_scores count={len(lexical_scores)}), "
                        f"hybrid_fusion_exists={self.hybrid_fusion is not None}, "
                        f"query_len={len(query.split())} words")
        
        if False:  # lexical_available and self.hybrid_fusion:  # DISABLED: Using fixed 75/25 baseline instead
            # Advanced fusion layer (EXPERIMENTAL - currently underperforming baseline)
            self.logger.info(f"✅ HYBRID FUSION ACTIVATED: Processing {len(results_by_id)} candidates with adaptive alpha")
            candidates = []
            for res in results_by_id.values():
                candidates.append({
                    'id': res.id,
                    'text': res.text,
                    'metadata': res.metadata,
                    'vector_score': res.vector_score if res.vector_score > 0 else 0.0,
                    'lexical_score': lexical_scores.get(res.id, res.lexical_score)
                })
            
            # Debug: Log input scores to fusion
            if candidates:
                vec_scores = [c['vector_score'] for c in candidates[:3]]
                lex_scores = [c['lexical_score'] for c in candidates[:3]]
                self.logger.info(f"🔍 INPUT TO FUSION (top 3): vector_scores={vec_scores}, lexical_scores={lex_scores}")
            
            # Apply hybrid fusion pipeline:
            # 1. Normalize scores
            # 2. Compute adaptive alpha based on query
            # 3. Apply metadata boost (recency + authority)
            # 4. Sort by final score
            fused_candidates = self.hybrid_fusion.fuse(
                candidates,
                query,
                apply_metadata=True,
                apply_threshold=False  # We already threshold in search()
            )
            
            # Convert back to RetrievalResult
            blended_results = []
            for i, cand in enumerate(fused_candidates, start=1):
                res = results_by_id[cand['id']]
                old_score = res.score
                res.score = cand.get('final_score', cand.get('hybrid_score', res.score))
                res.lexical_score = cand.get('lexical_norm', res.lexical_score)
                res.rank = i
                blended_results.append(res)
                
                # Log first result to see score transformation
                if i == 1:
                    self.logger.info(f"🔍 FUSION SCORE CHANGE: old={old_score:.4f} → new={res.score:.4f} "
                                   f"(vector_norm={cand.get('vector_norm', 0):.3f}, lexical_norm={cand.get('lexical_norm', 0):.3f}, "
                                   f"hybrid={cand.get('hybrid_score', 0):.3f}, final={cand.get('final_score', 0):.3f}, "
                                   f"alpha={cand.get('alpha_used', 0.75):.2f})")
            
            self.logger.debug(
                f"✅ Hybrid Fusion: {len(vector_results)} vector + {len(lexical_candidates)} lexical → {len(blended_results)} results (adaptive alpha={fused_candidates[0].get('alpha_used', 0.75):.2f})"
            )
        
        else:
            # Fallback to original fixed-weight blending
            if not lexical_available:
                self.logger.warning(f"⚠️ HYBRID FUSION FALLBACK: No lexical candidates (lexical_scores empty)")
            if not self.hybrid_fusion:
                self.logger.warning(f"⚠️ HYBRID FUSION FALLBACK: hybrid_fusion not initialized")
            self.logger.info(f"📊 FALLBACK: Using legacy fixed-weight blending (vector={self.hybrid_vector_weight}, lexical={self.hybrid_lexical_weight})")
            
            vector_values = [res.vector_score for res in results_by_id.values() if res.vector_score > 0]
            min_vector = min(vector_values) if vector_values else 0.0
            max_vector = max(vector_values) if vector_values else 0.0
            vector_span = max_vector - min_vector if max_vector > min_vector else None

            blended_results: List[RetrievalResult] = []

            for res in results_by_id.values():
                raw_vector = res.vector_score if res.vector_score > 0 else 0.0
                if vector_span:
                    vector_norm = (raw_vector - min_vector) / vector_span if raw_vector > 0 else 0.0
                elif max_vector > 0:
                    vector_norm = raw_vector / max_vector if raw_vector > 0 else 0.0
                else:
                    vector_norm = 0.0

                lexical_norm = lexical_scores.get(res.id, res.lexical_score)

                if lexical_available:
                    final_score = (
                        (self.hybrid_vector_weight * vector_norm)
                        + (self.hybrid_lexical_weight * lexical_norm)
                    )
                else:
                    # Preserve original vector behaviour when no lexical signal exists
                    final_score = raw_vector

                # METADATA BOOSTING: Prioritize recent content and specific roles
                boost = self._calculate_metadata_boost(res.metadata)
                final_score = final_score * boost

                res.lexical_score = lexical_norm
                res.score = max(0.0, min(1.0, final_score)) if lexical_available else final_score
                blended_results.append(res)

            blended_results.sort(key=lambda r: r.score, reverse=True)

            for idx, res in enumerate(blended_results, start=1):
                res.rank = idx

            if lexical_available:
                self.logger.debug(
                    "Hybrid retrieval (FIXED) combined %d vector results with %d lexical candidates",
                    len(vector_results),
                    len(lexical_candidates),
                )

        return blended_results[:top_k]
    
    def add_memory(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
        enable_chunking: bool = True,  # PHASE 3: Semantic chunking for long documents
        chunk_threshold: int = 500  # Characters threshold for chunking
    ) -> str:
        """
        Add a memory entry to long-term storage.
        
        PHASE 3: Automatically chunks long documents using semantic similarity
        to preserve coherent sections while maintaining retrieval precision.
        
        Args:
            text: Text content to store
            metadata: Optional metadata (debate_id, role, turn, etc.)
            memory_id: Optional custom ID (auto-generated if not provided)
            enable_chunking: Whether to enable semantic chunking for long texts
            chunk_threshold: Minimum text length (chars) to trigger chunking
            
        Returns:
            ID of the stored memory (or parent chunk ID if chunked)
        """
        if not text or not text.strip():
            self.logger.warning("Attempted to add empty text")
            return None
        
        # PHASE 3: Semantic Chunking for Long Documents
        if enable_chunking and len(text) > chunk_threshold:
            try:
                from memory.chunker import SemanticChunker
                chunker = SemanticChunker(embedding_service=self.embedding_service)
                chunks = chunker.split_text(text)
                
                if len(chunks) > 1:
                    # Generate parent ID
                    parent_id = memory_id or str(uuid.uuid4())
                    
                    self.logger.info(f"Chunked long text ({len(text)} chars) into {len(chunks)} semantic chunks")
                    
                    # Store each chunk with parent reference
                    for i, chunk_text in enumerate(chunks):
                        chunk_id = f"{parent_id}_chunk_{i}"
                        chunk_metadata = (metadata or {}).copy()
                        chunk_metadata['parent_id'] = parent_id
                        chunk_metadata['chunk_index'] = i
                        chunk_metadata['total_chunks'] = len(chunks)
                        chunk_metadata['is_chunk'] = True
                        
                        # Recursively add each chunk (with chunking disabled to avoid infinite loop)
                        self.add_memory(chunk_text, chunk_metadata, chunk_id, enable_chunking=False)
                    
                    return parent_id
            except Exception as e:
                self.logger.warning(f"Semantic chunking failed, storing as single memory: {e}")
                # Fall through to regular storage
        
        # Regular single-memory storage
        # Generate ID if not provided
        if memory_id is None:
            memory_id = str(uuid.uuid4())
        
        # Generate embedding
        embedding = self.embedding_service.embed_text(text)
        
        # Prepare metadata
        full_metadata = metadata or {}
        full_metadata['timestamp'] = datetime.now().isoformat()
        full_metadata['text_length'] = len(text)
        
        # Store in backend
        try:
            if self.backend == "chromadb":
                self.collection.add(
                    ids=[memory_id],
                    embeddings=[embedding.tolist()],
                    documents=[text],
                    metadatas=[full_metadata]
                )
            
            elif self.backend == "faiss":
                # Convert ID to integer for FAISS
                id_int = hash(memory_id) & 0x7FFFFFFF  # Ensure positive 32-bit int
                
                # Add to index
                self.index.add_with_ids(
                    np.array([embedding], dtype=np.float32),
                    np.array([id_int], dtype=np.int64)
                )
                
                # Store metadata separately
                self.id_to_metadata[memory_id] = {
                    'text': text,
                    'metadata': full_metadata,
                    'id_int': id_int
                }
            
            self.logger.debug(f"Added memory: {memory_id[:8]}... ({len(text)} chars)")

            # Maintain lexical/BM25 view for hybrid retrieval
            self._update_lexical_index(memory_id, text, full_metadata)

            return memory_id
            
        except Exception as e:
            self.logger.error(f"Failed to add memory: {e}")
            return None
    
    def add_memories_batch(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        memory_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add multiple memories in batch (more efficient).
        
        Args:
            texts: List of text contents
            metadatas: Optional list of metadata dicts
            memory_ids: Optional list of custom IDs
            
        Returns:
            List of stored memory IDs
        """
        if not texts:
            return []
        
        # Generate IDs if not provided
        if memory_ids is None:
            memory_ids = [str(uuid.uuid4()) for _ in texts]
        
        # Generate embeddings in batch
        embeddings = self.embedding_service.embed_batch(texts)
        
        # Prepare metadatas
        if metadatas is None:
            metadatas = [{} for _ in texts]
        
        for i, meta in enumerate(metadatas):
            meta['timestamp'] = datetime.now().isoformat()
            meta['text_length'] = len(texts[i])
        
        # Store in backend
        try:
            if self.backend == "chromadb":
                self.collection.add(
                    ids=memory_ids,
                    embeddings=[emb.tolist() for emb in embeddings],
                    documents=texts,
                    metadatas=metadatas
                )
            
            elif self.backend == "faiss":
                id_ints = [hash(mid) & 0x7FFFFFFF for mid in memory_ids]
                
                self.index.add_with_ids(
                    np.array(embeddings, dtype=np.float32),
                    np.array(id_ints, dtype=np.int64)
                )
                
                for i, mid in enumerate(memory_ids):
                    self.id_to_metadata[mid] = {
                        'text': texts[i],
                        'metadata': metadatas[i],
                        'id_int': id_ints[i]
                    }
            
            # Refresh lexical index once after batch insert for efficiency
            if self.enable_hybrid_bm25:
                for mid, text, meta in zip(memory_ids, texts, metadatas):
                    self.lexical_texts[mid] = text
                    self.lexical_metadata[mid] = meta
                self._rebuild_lexical_index()

            self.logger.info(f"Added {len(texts)} memories in batch")
            return memory_ids
            
        except Exception as e:
            self.logger.error(f"Failed to add batch memories: {e}")
            return []
    
    def search(
        self,
        query: str,
        top_k: int = 4,
        filter_metadata: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.50  # RESTORED: Back to 0.50 after testing
    ) -> List[RetrievalResult]:
        """
        Semantic search for relevant memories (RAG retrieval).
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"debate_id": "123"})
            similarity_threshold: Minimum similarity score (0-1) to include result
            
        Returns:
            List of RetrievalResult objects ranked by relevance, filtered by threshold
        """
        # Allow runtime override via environment variables for Step 7d threshold tuning
        env_top_k = os.getenv("TOP_K")
        if env_top_k is not None:
            try:
                top_k = int(env_top_k)
            except ValueError:
                self.logger.warning("Invalid TOP_K value: %s", env_top_k)
        
        env_threshold = os.getenv("SIMILARITY_THRESHOLD")
        if env_threshold is not None:
            try:
                similarity_threshold = float(env_threshold)
            except ValueError:
                self.logger.warning("Invalid SIMILARITY_THRESHOLD value: %s", env_threshold)
        if not query or not query.strip():
            self.logger.warning("Empty query provided")
            return []
        
        # STEP 7e: Preprocess query before retrieval
        original_query = query
        query = self._preprocess_query(query)
        
        if self.query_preprocessing_mode != "baseline":
            self.logger.debug(f"Query preprocessing ({self.query_preprocessing_mode}): '{original_query}' -> '{query}'")
        
        # ADAPTIVE THRESHOLD: Lower threshold for complex queries, raise for simple ones
        adaptive_threshold = self._calculate_adaptive_threshold(query, similarity_threshold)
        
        # Generate query embedding (use embed_query for Nomic prefix support)
        query_embedding = self.embedding_service.embed_query(query)
        
        try:
            if self.backend == "chromadb":
                # Standard candidate pool (was: max(40, top_k * 4) for testing)
                n_candidates = top_k * 2  # RESTORED: Back to 2x for baseline comparison
                
                # ChromaDB search
                results = self.collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=n_candidates,
                    where=filter_metadata,  # OPTIMIZATION 2: Metadata filtering
                    include=["documents", "metadatas", "distances"]
                )
                
                # Convert to RetrievalResult objects
                retrieval_results = []
                if results['ids'] and len(results['ids'][0]) > 0:
                    for rank, (id_, text, metadata, distance) in enumerate(
                        zip(results['ids'][0], results['documents'][0], 
                            results['metadatas'][0], results['distances'][0]), 
                        start=1
                    ):
                        # Convert distance to similarity score (0-1)
                        score = 1 / (1 + distance)  # Inverse distance
                        
                        result_obj = RetrievalResult(
                            id=id_,
                            text=text,
                            score=score,
                            metadata=metadata,
                            rank=rank,
                            vector_score=score,
                        )

                        # OPTIMIZATION 1: Apply adaptive similarity threshold filter
                        if score >= adaptive_threshold:
                            retrieval_results.append(result_obj)
                
                # Combine vector similarity with lexical BM25 signals before reranking
                blended_results = self._blend_vector_and_lexical(query, retrieval_results, top_k)

                # OPTIMIZATION 4: Apply LLM re-ranking for precision boost
                if self.enable_reranking and blended_results:
                    try:
                        blended_results = self.reranker.rerank(
                            query=query,
                            results=blended_results,
                            top_k=top_k
                        )
                        self.logger.info(f"LLM re-ranking applied: {len(blended_results)} results after re-ranking")
                    except Exception as e:
                        self.logger.warning(f"Re-ranking failed, using hybrid scores: {e}")
                
                # Return only top_k results after hybrid blending and optional re-ranking
                return blended_results[:top_k]
            
            elif self.backend == "faiss":
                # Standard candidate pool (was: max(40, top_k * 4) for testing)
                k = min(top_k * 2, self.index.ntotal)  # RESTORED: Back to 2x
                if k == 0:
                    return []
                
                distances, id_ints = self.index.search(
                    np.array([query_embedding], dtype=np.float32),
                    k
                )
                
                # Convert to RetrievalResult objects
                retrieval_results = []
                for rank, (distance, id_int) in enumerate(zip(distances[0], id_ints[0]), start=1):
                    # Find original ID
                    memory_id = None
                    for mid, data in self.id_to_metadata.items():
                        if data['id_int'] == id_int:
                            memory_id = mid
                            break
                    
                    if memory_id and memory_id in self.id_to_metadata:
                        data = self.id_to_metadata[memory_id]
                        
                        # OPTIMIZATION 2: Apply metadata filter if provided
                        if filter_metadata:
                            skip = False
                            for key, value in filter_metadata.items():
                                if data['metadata'].get(key) != value:
                                    skip = True
                                    break
                            if skip:
                                continue
                        
                        # Convert L2 distance to similarity score
                        score = 1 / (1 + float(distance))
                        
                        result_obj = RetrievalResult(
                            id=memory_id,
                            text=data['text'],
                            score=score,
                            metadata=data['metadata'],
                            rank=rank,
                            vector_score=score,
                        )

                        # OPTIMIZATION 1: Apply adaptive similarity threshold filter
                        if score >= adaptive_threshold:
                            retrieval_results.append(result_obj)
                
                # Combine vector similarity with lexical BM25 signals before reranking
                blended_results = self._blend_vector_and_lexical(query, retrieval_results, top_k)

                # OPTIMIZATION 4: Apply LTR re-ranking for precision boost (Python 3.13 compatible)
                if self.enable_reranking and self.ltr_reranker and blended_results:
                    self.logger.debug(f"Attempting LTR rerank: enable={self.enable_reranking}, has_model={self.ltr_reranker is not None}, results={len(blended_results)}")
                    try:
                        # Collect BM25 scores
                        bm25_scores = {r.id: r.lexical_score for r in blended_results}
                        
                        # Convert to dict format for reranker (include hybrid_score for RAG v2.0)
                        candidates = [
                            {
                                'id': r.id,
                                'text': r.text,
                                'score': r.score,
                                'metadata': r.metadata,
                                'lexical_score': r.lexical_score,
                                'hybrid_score': r.score,  # Current score is from hybrid fusion
                                'final_score': r.score
                            }
                            for r in blended_results
                        ]
                        
                        # Rerank
                        reranked_candidates = self.ltr_reranker.rerank(
                            query=query,
                            candidates=candidates,
                            top_k=top_k,
                            query_metadata=filter_metadata,
                            bm25_scores=bm25_scores
                        )
                        
                        # Convert back to RetrievalResult
                        blended_results = [
                            RetrievalResult(
                                id=c['id'],
                                text=c['text'],
                                score=c.get('final_score', c['score']),
                                metadata=c['metadata'],
                                rank=i+1,
                                vector_score=c.get('vector_sim', c['score']),
                                lexical_score=c.get('lexical_score', 0.0)
                            )
                            for i, c in enumerate(reranked_candidates)
                        ]
                        
                        self.logger.info(f"✅ LTR re-ranking applied: {len(blended_results)} results reranked")
                    except Exception as e:
                        self.logger.warning(f"LTR re-ranking failed, using hybrid scores: {e}")
                
                # Return only top_k after hybrid blending, threshold filtering, and optional re-ranking
                return blended_results[:top_k]
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []
    
    def get_relevant_context(
        self,
        query: str,
        top_k: int = 4,
        format_style: str = "structured"
    ) -> str:
        """
        Get formatted context string for LLM prompt (ZONE 2).
        
        Args:
            query: Search query
            top_k: Number of relevant memories to retrieve
            format_style: "structured" or "conversational"
            
        Returns:
            Formatted context string
        """
        results = self.search(query, top_k=top_k)
        
        if not results:
            return ""
        
        if format_style == "structured":
            lines = ["--- RELEVANT CONTEXT FROM LONG-TERM MEMORY (RAG) ---"]
            for result in results:
                lines.append(f"\n[Relevance: {result.score:.2f}] {result.text}")
                if result.metadata:
                    role = result.metadata.get('role', 'Unknown')
                    turn = result.metadata.get('turn', 'N/A')
                    lines.append(f"  Source: {role} (Turn {turn})")
            return "\n".join(lines)
        
        elif format_style == "conversational":
            lines = ["RELEVANT CONTEXT:"]
            for result in results:
                lines.append(f"- {result.text}")
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unknown format_style: {format_style}")
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory by ID"""
        try:
            if self.backend == "chromadb":
                self.collection.delete(ids=[memory_id])
            elif self.backend == "faiss":
                if memory_id in self.id_to_metadata:
                    del self.id_to_metadata[memory_id]
                # Note: FAISS doesn't support deletion, would need rebuild

            # Keep lexical index in sync
            self._remove_from_lexical_index(memory_id)
            
            self.logger.debug(f"Deleted memory: {memory_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete memory: {e}")
            return False
    
    def clear_all(self):
        """Clear all memories (use with caution!)"""
        try:
            if self.backend == "chromadb":
                self.client.delete_collection(name=self.collection_name)
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"dimension": self.dimension}
                )
            elif self.backend == "faiss":
                self.index.reset()
                self.id_to_metadata.clear()
            
            # Reset lexical caches as well
            self.lexical_ids.clear()
            self.lexical_corpus.clear()
            self.lexical_texts.clear()
            self.lexical_metadata.clear()
            self.bm25 = None

            self.logger.warning("All memories cleared!")
        except Exception as e:
            self.logger.error(f"Failed to clear memories: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store"""
        try:
            if self.backend == "chromadb":
                count = self.collection.count()
            elif self.backend == "faiss":
                count = self.index.ntotal
            else:
                count = 0
            
            return {
                "backend": self.backend,
                "collection_name": self.collection_name,
                "dimension": self.dimension,
                "total_memories": count,
                "embedding_provider": self.embedding_service.get_provider_info(),
                "hybrid_bm25_enabled": self.enable_hybrid_bm25,
                "hybrid_vector_weight": self.hybrid_vector_weight,
                "lexical_documents": len(self.lexical_ids) if self.enable_hybrid_bm25 else 0,
            }
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {}

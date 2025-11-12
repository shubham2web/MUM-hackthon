"""
Embedding Service for Hybrid Memory System

Generates embeddings for semantic search and RAG retrieval.
Supports multiple embedding providers with fallback.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import List, Optional, Literal
import numpy as np
from dataclasses import dataclass

def _select_default_provider() -> str:
    """Determine the default embedding provider based on environment."""
    env_provider = os.getenv("EMBEDDING_PROVIDER")
    if env_provider:
        return env_provider
    # PyTorch currently lacks stable wheels for Python 3.13+, so default to fastembed
    if sys.version_info >= (3, 13):
        return "fastembed"
    return "sentence-transformers"


# Try multiple embedding providers with fallback
EMBEDDING_PROVIDER = _select_default_provider()  # or "openai"

@dataclass
class EmbeddingResult:
    """Result from embedding generation"""
    embeddings: np.ndarray
    dimension: int
    provider: str
    model: str


class EmbeddingService:
    """
    Unified embedding service with multiple provider support.
    
    Providers:
    1. sentence-transformers (local, free, no API key needed)
    2. OpenAI (requires API key, best quality)
    3. HuggingFace Inference (requires HF token)
    """
    
    def __init__(
        self,
        provider: Literal["sentence-transformers", "openai", "huggingface", "fastembed"] = EMBEDDING_PROVIDER,
        model_name: Optional[str] = None
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.provider = provider
        self.model = None
        self.model_name = model_name
        self.dimension = 384  # Default for sentence-transformers
        
        self._initialize_provider()
    
    def _initialize_provider(self):
        """Initialize the selected embedding provider"""
        try:
            if self.provider == "sentence-transformers":
                self._init_sentence_transformers()
            elif self.provider == "openai":
                self._init_openai()
            elif self.provider == "huggingface":
                self._init_huggingface()
            elif self.provider == "fastembed":
                self._init_fastembed()
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

            self.logger.info(f"✅ Embedding service initialized with {self.provider}")

        except Exception as e:
            self.logger.error(f"Failed to initialize {self.provider}: {e}")

            fallback_order = []
            if self.provider != "fastembed":
                fallback_order.append("fastembed")
            if self.provider != "sentence-transformers":
                fallback_order.append("sentence-transformers")

            for fallback_provider in fallback_order:
                self.logger.warning(f"Falling back to {fallback_provider} embeddings")
                try:
                    self.provider = fallback_provider
                    if fallback_provider == "sentence-transformers":
                        self._init_sentence_transformers()
                    elif fallback_provider == "fastembed":
                        self._init_fastembed()
                    self.logger.info(f"✅ Embedding service initialized with {self.provider}")
                    return
                except Exception as fallback_error:
                    self.logger.error(
                        f"Fallback initialization failed for {fallback_provider}: {fallback_error}"
                    )

            raise
    
    def _init_sentence_transformers(self):
        """Initialize sentence-transformers (local, no API key)"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # OPTIMIZATION 5: Nomic Embed - State-of-the-art with 8192 token context!
            # Why Nomic: 
            # - 8192 token context (vs 512 for BGE) - can embed ENTIRE conversations!
            # - Outperforms OpenAI Ada-002 and text-embedding-3-small
            # - Matryoshka learning: Adjustable dimensions (64-768)
            # - Open source, no API costs
            # - Top performer on MTEB benchmark
            
            # Model options (ordered by performance):
            # 1. BAAI/bge-small-en-v1.5: 384 dim (BASELINE - 71.8% relevance)
            # 2. BAAI/bge-base-en-v1.5: 768 dim (BALANCED - expect ~78-80%)
            # 3. BAAI/bge-large-en-v1.5: 1024 dim (BEST - expect ~82-85%) ⭐
            # 4. sentence-transformers/all-mpnet-base-v2: 768 dim (ALTERNATIVE)
            
            default_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")  # Upgraded: 768-dim, same family
            self.model_name = self.model_name or default_model
            
            # Nomic Embed requires trust_remote_code=True for custom modules
            trust_remote = self.model_name.startswith("nomic-ai/")
            self.model = SentenceTransformer(self.model_name, trust_remote_code=trust_remote)
            self.dimension = self.model.get_sentence_embedding_dimension()
            
            self.logger.info(f"Loaded sentence-transformers model: {self.model_name} (dim={self.dimension})")
            
        except ImportError:
            self.logger.error("sentence-transformers not installed. Install: pip install sentence-transformers")
            raise
    
    def _init_fastembed(self):
        """Initialize fastembed (ONNX runtime, no torch dependency)."""
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            self.logger.error("fastembed not installed. Install: pip install fastembed")
            raise exc

        default_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")  # OPTIMAL: Best performance with current LTR model (74.9% relevance, 79.5% precision)
        self.model_name = self.model_name or default_model

        try:
            self.model = TextEmbedding(model_name=self.model_name)
            # Probe the model once to determine embedding dimension
            sample_vector = next(self.model.embed(["dimension probe"], batch_size=1))
            self.dimension = len(sample_vector)
            self.logger.info(
                f"Loaded fastembed model: {self.model_name} (dim={self.dimension})"
            )
        except Exception as exc:
            self.logger.error(f"Fastembed initialization failed for {self.model_name}: {exc}")
            raise

    def _init_openai(self):
        """Initialize OpenAI embeddings"""
        try:
            import openai
            from core.config import OPENAI_API_KEY
            
            if not OPENAI_API_KEY or OPENAI_API_KEY == "":
                raise ValueError("OPENAI_API_KEY not configured")
            
            openai.api_key = OPENAI_API_KEY
            self.model_name = self.model_name or "text-embedding-3-small"  # 1536 dim
            self.dimension = 1536
            
            self.logger.info(f"OpenAI embeddings configured: {self.model_name}")
            
        except ImportError:
            self.logger.error("openai not installed. Install: pip install openai")
            raise
        except Exception as e:
            self.logger.error(f"OpenAI initialization failed: {e}")
            raise
    
    def _init_huggingface(self):
        """Initialize HuggingFace Inference embeddings"""
        try:
            from huggingface_hub import InferenceClient
            from core.config import HF_TOKENS
            
            if not HF_TOKENS or HF_TOKENS == [""]:
                raise ValueError("HF_TOKENS not configured")
            
            import random
            hf_token = random.choice(HF_TOKENS)
            self.model = InferenceClient(token=hf_token)
            self.model_name = self.model_name or "sentence-transformers/all-MiniLM-L6-v2"
            self.dimension = 384
            
            self.logger.info(f"HuggingFace embeddings configured: {self.model_name}")
            
        except Exception as e:
            self.logger.error(f"HuggingFace initialization failed: {e}")
            raise
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            numpy array of embedding vector
        """
        if not text or not text.strip():
            return np.zeros(self.dimension, dtype=np.float32)
        
        try:
            if self.provider == "sentence-transformers":
                # Nomic Embed requires special prefixes for optimal performance
                if self.model_name.startswith("nomic-ai/"):
                    # Add prefix for document embedding (default)
                    # Query embedding uses different prefix (see search method)
                    text = f"search_document: {text}"
                
                embedding = self.model.encode(text, convert_to_numpy=True)
                return embedding.astype(np.float32)
            
            elif self.provider == "openai":
                import openai
                response = openai.embeddings.create(
                    input=text,
                    model=self.model_name
                )
                return np.array(response.data[0].embedding, dtype=np.float32)
            
            elif self.provider == "huggingface":
                # HuggingFace Inference API for embeddings
                embedding = self.model.feature_extraction(text, model=self.model_name)
                # Take mean pooling if needed
                if isinstance(embedding, list) and len(embedding) > 0:
                    if isinstance(embedding[0], list):
                        # Mean pooling over tokens
                        embedding = np.mean(embedding[0], axis=0)
                    else:
                        embedding = np.array(embedding[0])
                return np.array(embedding, dtype=np.float32)

            elif self.provider == "fastembed":
                embedding = next(self.model.embed([text], batch_size=1))
                return np.array(embedding, dtype=np.float32)
            
        except Exception as e:
            self.logger.error(f"Embedding generation failed: {e}")
            return np.zeros(self.dimension, dtype=np.float32)
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a search query (special handling for Nomic).
        
        Args:
            query: Search query text
            
        Returns:
            numpy array of embedding vector
        """
        if not query or not query.strip():
            return np.zeros(self.dimension, dtype=np.float32)
        
        try:
            if self.provider == "sentence-transformers":
                # Nomic Embed requires 'search_query:' prefix for queries
                if self.model_name.startswith("nomic-ai/"):
                    query = f"search_query: {query}"
                
                embedding = self.model.encode(query, convert_to_numpy=True)
                return embedding.astype(np.float32)
            
            # For other providers, use regular embed_text
            return self.embed_text(query)
            
        except Exception as e:
            self.logger.error(f"Query embedding generation failed: {e}")
            return np.zeros(self.dimension, dtype=np.float32)
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts (batched for efficiency).
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process at once
            
        Returns:
            List of numpy embedding arrays
        """
        if not texts:
            return []
        
        try:
            if self.provider == "sentence-transformers":
                embeddings = self.model.encode(
                    texts,
                    batch_size=batch_size,
                    convert_to_numpy=True,
                    show_progress_bar=len(texts) > 100
                )
                return [emb.astype(np.float32) for emb in embeddings]
            
            elif self.provider == "openai":
                # OpenAI has its own batching
                import openai
                response = openai.embeddings.create(
                    input=texts,
                    model=self.model_name
                )
                return [np.array(item.embedding, dtype=np.float32) for item in response.data]
            
            elif self.provider == "huggingface":
                # Process in batches
                embeddings = []
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    for text in batch:
                        emb = self.embed_text(text)
                        embeddings.append(emb)
                return embeddings

            elif self.provider == "fastembed":
                embeddings = list(self.model.embed(texts, batch_size=batch_size))
                return [np.array(emb, dtype=np.float32) for emb in embeddings]
            
        except Exception as e:
            self.logger.error(f"Batch embedding generation failed: {e}")
            return [np.zeros(self.dimension, dtype=np.float32) for _ in texts]
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension
    
    def get_provider_info(self) -> dict:
        """Get information about current provider"""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "dimension": self.dimension
        }


# Global singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create global embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(provider=EMBEDDING_PROVIDER)
    return _embedding_service

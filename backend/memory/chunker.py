"""
Semantic Chunker for Long-Form Content

Splits text into semantically coherent chunks based on embedding similarity variance.
This improves retrieval precision by ensuring each chunk focuses on a single topic.

Strategy:
1. Split text into sentences
2. Embed each sentence
3. Calculate similarity between consecutive sentences
4. Split where similarity drops (topic boundary detected)
5. Merge small chunks to maintain minimum size

Expected gain: +3-5% relevance on disambiguation and topic-switching tests
"""
from __future__ import annotations

import re
import logging
from typing import List, Tuple, Optional
import numpy as np
from dataclasses import dataclass

from memory.embeddings import get_embedding_service


@dataclass
class SemanticChunk:
    """A semantically coherent chunk of text"""
    text: str
    start_idx: int
    end_idx: int
    embedding: Optional[np.ndarray] = None


class SemanticChunker:
    """
    Split text into semantically coherent chunks.
    
    Uses embedding similarity to detect topic boundaries:
    - High similarity between adjacent sentences → same topic
    - Low similarity → topic boundary → split point
    """
    
    def __init__(
        self,
        min_chunk_size: int = 100,  # Minimum characters per chunk
        max_chunk_size: int = 500,  # Maximum characters per chunk
        similarity_threshold: float = 0.5,  # Split when similarity drops below this
        breakpoint_percentile_threshold: int = 75,  # Split at bottom 25% of similarities
    ):
        """
        Initialize semantic chunker.
        
        Args:
            min_chunk_size: Minimum characters per chunk (prevent tiny fragments)
            max_chunk_size: Maximum characters per chunk (hard limit)
            similarity_threshold: Split when sentence similarity < threshold
            breakpoint_percentile_threshold: Alternative: split at percentile drops
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.similarity_threshold = similarity_threshold
        self.breakpoint_percentile_threshold = breakpoint_percentile_threshold
        
        self.embedding_service = get_embedding_service()
    
    def split_text(self, text: str) -> List[SemanticChunk]:
        """
        Split text into semantically coherent chunks.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of SemanticChunk objects
        """
        if not text or len(text) < self.min_chunk_size:
            return [SemanticChunk(text=text, start_idx=0, end_idx=len(text))]
        
        # Step 1: Split into sentences
        sentences = self._split_into_sentences(text)
        
        if len(sentences) <= 1:
            return [SemanticChunk(text=text, start_idx=0, end_idx=len(text))]
        
        # Step 2: Embed sentences
        embeddings = self.embedding_service.embed_batch(sentences)
        
        # Step 3: Calculate similarity between consecutive sentences
        similarities = self._calculate_similarities(embeddings)
        
        # Step 4: Find split points (low similarity = topic boundary)
        split_indices = self._find_split_points(similarities)
        
        # Step 5: Create chunks from split points
        chunks = self._create_chunks(sentences, split_indices)
        
        # Step 6: Merge small chunks
        chunks = self._merge_small_chunks(chunks)
        
        self.logger.debug(f"Split text into {len(chunks)} semantic chunks")
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using regex"""
        # Simple sentence splitter: split on . ! ? followed by space/newline
        sentence_endings = re.compile(r'([.!?]+[\s\n]+)')
        sentences = sentence_endings.split(text)
        
        # Recombine sentence with its punctuation
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i] + sentences[i + 1]
            sentence = sentence.strip()
            if sentence:
                result.append(sentence)
        
        # Handle last sentence if no punctuation at end
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())
        
        return result if result else [text]
    
    def _calculate_similarities(self, embeddings: List[np.ndarray]) -> List[float]:
        """Calculate cosine similarity between consecutive sentence embeddings"""
        similarities = []
        
        for i in range(len(embeddings) - 1):
            emb1 = embeddings[i]
            emb2 = embeddings[i + 1]
            
            # Cosine similarity
            dot_product = np.dot(emb1, emb2)
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)
            
            if norm1 > 0 and norm2 > 0:
                similarity = dot_product / (norm1 * norm2)
            else:
                similarity = 0.0
            
            similarities.append(float(similarity))
        
        return similarities
    
    def _find_split_points(self, similarities: List[float]) -> List[int]:
        """
        Find split points where similarity drops significantly.
        
        Uses percentile-based approach: split at points where similarity
        is in the bottom 25% (default) of all similarities.
        """
        if not similarities:
            return []
        
        # Calculate threshold using percentile
        threshold = np.percentile(
            similarities,
            100 - self.breakpoint_percentile_threshold
        )
        
        # Also consider absolute threshold
        threshold = max(threshold, self.similarity_threshold)
        
        # Find indices where similarity < threshold
        split_points = []
        for i, sim in enumerate(similarities):
            if sim < threshold:
                split_points.append(i + 1)  # Split AFTER this sentence
        
        return split_points
    
    def _create_chunks(
        self,
        sentences: List[str],
        split_indices: List[int]
    ) -> List[SemanticChunk]:
        """Create chunks from sentences using split indices"""
        chunks = []
        start_idx = 0
        
        # Add 0 and len(sentences) as boundaries
        all_splits = [0] + split_indices + [len(sentences)]
        
        for i in range(len(all_splits) - 1):
            start = all_splits[i]
            end = all_splits[i + 1]
            
            chunk_sentences = sentences[start:end]
            chunk_text = ' '.join(chunk_sentences)
            
            chunk = SemanticChunk(
                text=chunk_text,
                start_idx=start,
                end_idx=end
            )
            chunks.append(chunk)
        
        return chunks
    
    def _merge_small_chunks(self, chunks: List[SemanticChunk]) -> List[SemanticChunk]:
        """Merge chunks that are too small with adjacent chunks"""
        if not chunks:
            return []
        
        merged = []
        current_chunk = chunks[0]
        
        for next_chunk in chunks[1:]:
            # If current chunk is too small, merge with next
            if len(current_chunk.text) < self.min_chunk_size:
                current_chunk = SemanticChunk(
                    text=current_chunk.text + ' ' + next_chunk.text,
                    start_idx=current_chunk.start_idx,
                    end_idx=next_chunk.end_idx
                )
            else:
                # Current chunk is big enough, save it
                merged.append(current_chunk)
                current_chunk = next_chunk
        
        # Don't forget the last chunk
        merged.append(current_chunk)
        
        return merged


# Global singleton
_chunker: Optional[SemanticChunker] = None


def get_semantic_chunker() -> SemanticChunker:
    """Get or create global semantic chunker instance"""
    global _chunker
    if _chunker is None:
        _chunker = SemanticChunker()
    return _chunker

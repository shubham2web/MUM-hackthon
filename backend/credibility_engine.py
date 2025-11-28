"""
Credibility Scoring Engine (CSE) for ATLAS v2.0

This module implements weighted truth scoring combining:
- Source trust ratings
- Cross-time agreement
- Semantic alignment (using sentence transformers)
- Evidence diversity
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
import hashlib

# Enhanced semantic matching with sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    logging.warning("sentence-transformers not installed. Using basic keyword matching. Install with: pip install sentence-transformers")


@dataclass
class Source:
    """Represents an evidence source with trust metrics."""
    url: str
    domain: str
    content: str
    timestamp: datetime
    trust_score: float = 0.5  # Default neutral trust
    bias_flags: List[str] = None
    
    def __post_init__(self):
        if self.bias_flags is None:
            self.bias_flags = []


@dataclass
class CredibilityScore:
    """Complete credibility assessment for a claim."""
    overall_score: float  # 0.0 to 1.0
    source_trust: float
    semantic_alignment: float
    temporal_consistency: float
    evidence_diversity: float
    confidence_level: str  # "High", "Medium", "Low"
    explanation: str
    warnings: List[str]


class CredibilityEngine:
    """
    Weighted truth scoring engine that combines multiple signals:
    1. Source Trust: Domain reputation and historical accuracy
    2. Semantic Alignment: Advanced similarity using sentence transformers
    3. Temporal Consistency: Time-based validation
    4. Evidence Diversity: Multiple independent sources
    """
    
    # Weights for scoring components (must sum to 1.0)
    WEIGHTS = {
        'source_trust': 0.30,
        'semantic_alignment': 0.35,
        'temporal_consistency': 0.15,
        'evidence_diversity': 0.20
    }
    
    # Trusted domain list (can be expanded)
    TRUSTED_DOMAINS = {
        'reuters.com': 0.9,
        'apnews.com': 0.9,
        'bbc.com': 0.85,
        'npr.org': 0.85,
        'economist.com': 0.8,
        'nytimes.com': 0.75,
        'theguardian.com': 0.75,
        'wsj.com': 0.75,
    }
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.semantic_model = None
        
        # Initialize semantic similarity model if available
        if SEMANTIC_AVAILABLE:
            try:
                # Use lightweight but accurate model
                self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.logger.info("✅ Semantic similarity model loaded (sentence-transformers)")
            except Exception as e:
                self.logger.warning(f"Failed to load semantic model: {e}. Falling back to keyword matching.")
                self.semantic_model = None
        else:
            self.logger.info("Using basic keyword matching for semantic alignment")
        
    def calculate_credibility(
        self,
        claim: str,
        sources: List[Source],
        evidence_texts: List[str]
    ) -> CredibilityScore:
        """
        Calculate comprehensive credibility score for a claim.
        
        Args:
            claim: The statement being verified
            sources: List of Source objects with metadata
            evidence_texts: List of extracted evidence snippets
            
        Returns:
            CredibilityScore object with detailed assessment
        """
        warnings = []
        
        # 1. Source Trust Score
        source_trust = self._calculate_source_trust(sources)
        if source_trust < 0.3:
            warnings.append("Low source credibility detected")
        
        # 2. Semantic Alignment (simplified - can be enhanced with embeddings)
        semantic_alignment = self._calculate_semantic_alignment(claim, evidence_texts)
        if semantic_alignment < 0.4:
            warnings.append("Weak evidence-claim alignment")
        
        # 3. Temporal Consistency
        temporal_consistency = self._calculate_temporal_consistency(sources)
        if temporal_consistency < 0.5:
            warnings.append("Temporal inconsistencies detected")
        
        # 4. Evidence Diversity
        evidence_diversity = self._calculate_evidence_diversity(sources)
        if evidence_diversity < 0.3:
            warnings.append("Limited source diversity")
        
        # Calculate weighted overall score
        overall_score = (
            self.WEIGHTS['source_trust'] * source_trust +
            self.WEIGHTS['semantic_alignment'] * semantic_alignment +
            self.WEIGHTS['temporal_consistency'] * temporal_consistency +
            self.WEIGHTS['evidence_diversity'] * evidence_diversity
        )
        
        # Determine confidence level
        if overall_score >= 0.75:
            confidence = "High"
        elif overall_score >= 0.5:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        explanation = self._generate_explanation(
            overall_score, source_trust, semantic_alignment,
            temporal_consistency, evidence_diversity
        )
        
        self.logger.info(f"Credibility Score: {overall_score:.2f} ({confidence} confidence)")
        
        return CredibilityScore(
            overall_score=overall_score,
            source_trust=source_trust,
            semantic_alignment=semantic_alignment,
            temporal_consistency=temporal_consistency,
            evidence_diversity=evidence_diversity,
            confidence_level=confidence,
            explanation=explanation,
            warnings=warnings
        )
    
    def _calculate_source_trust(self, sources: List[Source]) -> float:
        """Calculate average trust score across all sources."""
        if not sources:
            self.logger.warning("No sources provided for trust calculation")
            # Return neutral score instead of 0 when no sources available
            return 0.5
        
        trust_scores = []
        for source in sources:
            # Check if domain is in trusted list
            domain_trust = self.TRUSTED_DOMAINS.get(source.domain, 0.5)
            
            # Apply bias penalties
            bias_penalty = len(source.bias_flags) * 0.1
            adjusted_trust = max(0.0, domain_trust - bias_penalty)
            
            trust_scores.append(adjusted_trust)
        
        return sum(trust_scores) / len(trust_scores)
    
    def _calculate_semantic_alignment(self, claim: str, evidence_texts: List[str]) -> float:
        """
        Calculate how well evidence supports the claim using semantic similarity.
        
        Uses sentence-transformers for advanced semantic matching if available,
        otherwise falls back to keyword-based matching.
        
        Args:
            claim: The statement being verified
            evidence_texts: List of evidence snippets from sources
            
        Returns:
            Alignment score between 0.0 and 1.0
        """
        if not evidence_texts:
            # Return minimal score instead of 0.0 for no evidence
            # This prevents complete score collapse when evidence is unavailable
            self.logger.warning("No evidence texts provided for semantic alignment")
            return 0.3  # Baseline score when no evidence available
        
        # Filter out empty or whitespace-only evidence
        valid_evidence = [e.strip() for e in evidence_texts if e and e.strip()]
        if not valid_evidence:
            self.logger.warning("All evidence texts are empty")
            return 0.3  # Baseline score
        
        # Use advanced semantic matching if model is loaded
        if self.semantic_model is not None:
            return self._semantic_similarity_transformer(claim, valid_evidence)
        else:
            return self._semantic_similarity_keyword(claim, valid_evidence)
    
    def _semantic_similarity_transformer(self, claim: str, evidence_texts: List[str]) -> float:
        """
        Advanced semantic matching using sentence transformers.
        Computes cosine similarity between claim and evidence embeddings.
        """
        try:
            # Encode claim
            claim_embedding = self.semantic_model.encode([claim], convert_to_tensor=False)[0]
            
            # Encode all evidence texts
            evidence_embeddings = self.semantic_model.encode(evidence_texts, convert_to_tensor=False)
            
            # Calculate cosine similarity for each evidence
            similarities = []
            for evidence_embedding in evidence_embeddings:
                # Cosine similarity
                similarity = np.dot(claim_embedding, evidence_embedding) / (
                    np.linalg.norm(claim_embedding) * np.linalg.norm(evidence_embedding)
                )
                # Convert from [-1, 1] to [0, 1]
                similarity = (similarity + 1) / 2
                similarities.append(similarity)
            
            # Return average similarity
            avg_similarity = sum(similarities) / len(similarities)
            
            self.logger.debug(f"Semantic similarity (transformer): {avg_similarity:.3f}")
            return float(avg_similarity)
            
        except Exception as e:
            self.logger.error(f"Error in semantic similarity: {e}")
            return self._semantic_similarity_keyword(claim, evidence_texts)
    
    def _semantic_similarity_keyword(self, claim: str, evidence_texts: List[str]) -> float:
        """
        Fallback keyword-based semantic matching.
        Uses Jaccard similarity with term frequency weighting.
        """
        claim_words = set(claim.lower().split())
        alignments = []
        
        for evidence in evidence_texts:
            evidence_words = set(evidence.lower().split())
            
            # Jaccard similarity
            intersection = len(claim_words.intersection(evidence_words))
            union = len(claim_words.union(evidence_words))
            
            if union > 0:
                similarity = intersection / union
                alignments.append(similarity)
        
        avg_alignment = sum(alignments) / len(alignments) if alignments else 0.0
        self.logger.debug(f"Semantic alignment (keyword): {avg_alignment:.3f}")
        return avg_alignment
    
    def _calculate_temporal_consistency(self, sources: List[Source]) -> float:
        """
        Check if sources are recent and consistent across time.
        """
        if not sources:
            self.logger.warning("No sources provided for temporal consistency")
            # Return moderate score instead of 0 when no temporal data
            return 0.6
        
        # Check recency (sources within last 30 days get higher score)
        now = datetime.now()
        recency_scores = []
        
        for source in sources:
            if source.timestamp:
                days_old = (now - source.timestamp).days
                if days_old <= 30:
                    recency_score = 1.0
                elif days_old <= 90:
                    recency_score = 0.7
                elif days_old <= 365:
                    recency_score = 0.5
                else:
                    recency_score = 0.3
                recency_scores.append(recency_score)
        
        return sum(recency_scores) / len(recency_scores) if recency_scores else 0.5
    
    def _calculate_evidence_diversity(self, sources: List[Source]) -> float:
        """
        Measure diversity of sources (different domains, perspectives).
        """
        if not sources:
            self.logger.warning("No sources provided for diversity calculation")
            # Return low-moderate score instead of 0 when no sources
            return 0.4
        
        # Count unique domains
        unique_domains = len(set(source.domain for source in sources if source.domain))
        
        # If no valid domains, return baseline
        if unique_domains == 0:
            return 0.4
        
        # Normalize by number of sources (diminishing returns)
        diversity_score = min(1.0, unique_domains / max(3, len(sources) * 0.6))
        
        return diversity_score
    
    def _generate_explanation(
        self,
        overall: float,
        trust: float,
        semantic: float,
        temporal: float,
        diversity: float
    ) -> str:
        """Generate human-readable explanation of the score."""
        
        parts = []
        parts.append(f"Overall credibility: {overall:.1%}")
        parts.append(f"Source trustworthiness: {trust:.1%}")
        parts.append(f"Evidence alignment: {semantic:.1%}")
        parts.append(f"Temporal consistency: {temporal:.1%}")
        parts.append(f"Source diversity: {diversity:.1%}")
        
        # Add interpretation
        if overall >= 0.75:
            parts.append("\n✅ This claim is strongly supported by credible evidence.")
        elif overall >= 0.5:
            parts.append("\n⚠️ This claim has moderate support but may need additional verification.")
        else:
            parts.append("\n❌ This claim lacks sufficient credible evidence.")
        
        return " | ".join(parts)


# Standalone function for quick scoring
def score_claim_credibility(
    claim: str,
    sources: List[Dict],
    evidence_texts: List[str]
) -> Dict:
    """
    Convenience function for scoring a claim.
    
    Args:
        claim: Statement to verify
        sources: List of dicts with keys: url, domain, content, timestamp
        evidence_texts: List of evidence snippets
        
    Returns:
        Dict with credibility metrics
    """
    engine = CredibilityEngine()
    
    # Convert dicts to Source objects
    source_objects = [
        Source(
            url=s.get('url', ''),
            domain=s.get('domain', ''),
            content=s.get('content', ''),
            timestamp=s.get('timestamp', datetime.now()),
            trust_score=s.get('trust_score', 0.5),
            bias_flags=s.get('bias_flags', [])
        )
        for s in sources
    ]
    
    score = engine.calculate_credibility(claim, source_objects, evidence_texts)
    
    return {
        'overall_score': score.overall_score,
        'confidence_level': score.confidence_level,
        'source_trust': score.source_trust,
        'semantic_alignment': score.semantic_alignment,
        'temporal_consistency': score.temporal_consistency,
        'evidence_diversity': score.evidence_diversity,
        'explanation': score.explanation,
        'warnings': score.warnings
    }

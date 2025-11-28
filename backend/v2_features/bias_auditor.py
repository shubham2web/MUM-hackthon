"""
Bias Audit System for ATLAS v2.0

Enhanced bias detection and tracking with ledger functionality.
Monitors agent bias, source bias, and maintains transparency logs.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json


class BiasType(Enum):
    """Types of bias that can be detected."""
    CONFIRMATION_BIAS = "confirmation_bias"
    SELECTION_BIAS = "selection_bias"
    ANCHORING_BIAS = "anchoring_bias"
    RECENCY_BIAS = "recency_bias"
    AVAILABILITY_BIAS = "availability_bias"
    FRAMING_BIAS = "framing_bias"
    POLITICAL_BIAS = "political_bias"
    CULTURAL_BIAS = "cultural_bias"
    SOURCE_BIAS = "source_bias"
    LANGUAGE_BIAS = "language_bias"


class BiasSeverity(Enum):
    """Severity levels for detected bias."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class BiasFlag:
    """Represents a detected bias instance."""
    bias_type: BiasType
    severity: BiasSeverity
    description: str
    evidence: str
    source: str  # Which agent/source exhibited this bias
    timestamp: datetime
    confidence: float  # 0-1, how confident the detection is
    context: Dict[str, any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'bias_type': self.bias_type.value,
            'severity': self.severity.name,
            'description': self.description,
            'evidence': self.evidence[:200],  # Truncate for logging
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'confidence': self.confidence,
            'context': self.context
        }
    
    def get_hash(self) -> str:
        """Generate unique hash for this bias flag (for ledger)."""
        data = f"{self.bias_type.value}{self.source}{self.evidence}{self.timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class BiasProfile:
    """Aggregated bias profile for an agent or source."""
    entity_name: str
    entity_type: str  # 'agent', 'source', 'domain'
    total_flags: int = 0
    bias_counts: Dict[BiasType, int] = field(default_factory=dict)
    severity_distribution: Dict[BiasSeverity, int] = field(default_factory=dict)
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    reputation_score: float = 1.0  # Starts at 1.0, decreases with bias
    
    def update_reputation(self):
        """Recalculate reputation score based on bias history."""
        if self.total_flags == 0:
            self.reputation_score = 1.0
            return
        
        # Weighted penalty based on severity
        penalty = 0
        severity_weights = {
            BiasSeverity.LOW: 0.02,
            BiasSeverity.MEDIUM: 0.05,
            BiasSeverity.HIGH: 0.10,
            BiasSeverity.CRITICAL: 0.20
        }
        
        for severity, count in self.severity_distribution.items():
            penalty += count * severity_weights.get(severity, 0.05)
        
        self.reputation_score = max(0.0, 1.0 - penalty)


class BiasAuditor:
    """
    Enhanced bias detection and tracking system.
    
    Features:
    - Real-time bias detection in agent responses
    - Source credibility tracking
    - Bias ledger for transparency
    - Pattern recognition across debates
    - Bias mitigation recommendations
    """
    
    # Bias detection patterns (keyword-based, can be enhanced with ML)
    BIAS_PATTERNS = {
        BiasType.CONFIRMATION_BIAS: [
            'obviously', 'clearly', 'everyone knows', 'it\'s a fact that',
            'undeniable', 'without question'
        ],
        BiasType.POLITICAL_BIAS: [
            'leftist', 'right-wing', 'conservative bias', 'liberal agenda',
            'mainstream media', 'fake news'
        ],
        BiasType.FRAMING_BIAS: [
            'merely', 'just', 'only', 'simply', 'actually',
            'real', 'true', 'honest'
        ],
        BiasType.LANGUAGE_BIAS: [
            'catastrophic', 'disaster', 'crisis', 'emergency',
            'miraculous', 'revolutionary', 'unprecedented'
        ]
    }
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bias_flags: List[BiasFlag] = []
        self.bias_profiles: Dict[str, BiasProfile] = {}
        self.bias_ledger: List[Dict] = []  # Immutable log for transparency
        
    def audit_response(
        self,
        text: str,
        source: str,
        context: Optional[Dict] = None
    ) -> List[BiasFlag]:
        """
        Audit a text response for bias indicators.
        
        Args:
            text: The text to audit
            source: Who/what generated this text
            context: Additional context (role, topic, etc.)
            
        Returns:
            List of detected BiasFlag objects
        """
        detected_flags = []
        text_lower = text.lower()
        
        # Pattern-based detection
        for bias_type, patterns in self.BIAS_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_lower:
                    flag = BiasFlag(
                        bias_type=bias_type,
                        severity=BiasSeverity.MEDIUM,
                        description=f"Detected {bias_type.value} pattern",
                        evidence=self._extract_evidence(text, pattern),
                        source=source,
                        timestamp=datetime.now(),
                        confidence=0.7,
                        context=context or {}
                    )
                    detected_flags.append(flag)
                    self.logger.warning(f"Bias detected in {source}: {bias_type.value}")
        
        # Check for one-sided sourcing
        if context and 'sources' in context:
            source_domains = [s.get('domain', '') for s in context['sources']]
            unique_domains = set(source_domains)
            
            if len(unique_domains) < 2 and len(source_domains) >= 3:
                flag = BiasFlag(
                    bias_type=BiasType.SELECTION_BIAS,
                    severity=BiasSeverity.HIGH,
                    description="Limited source diversity detected",
                    evidence=f"Only {len(unique_domains)} unique sources used",
                    source=source,
                    timestamp=datetime.now(),
                    confidence=0.9,
                    context=context
                )
                detected_flags.append(flag)
        
        # Store flags
        self.bias_flags.extend(detected_flags)
        
        # Update bias profile
        self._update_bias_profile(source, detected_flags)
        
        # Add to ledger
        for flag in detected_flags:
            self._add_to_ledger(flag)
        
        return detected_flags
    
    def _extract_evidence(self, text: str, pattern: str, context_words: int = 10) -> str:
        """Extract surrounding context for detected bias pattern."""
        words = text.split()
        for i, word in enumerate(words):
            if pattern in word.lower():
                start = max(0, i - context_words)
                end = min(len(words), i + context_words + 1)
                return ' '.join(words[start:end])
        return text[:100]  # Fallback
    
    def _update_bias_profile(self, entity: str, flags: List[BiasFlag]):
        """Update bias profile for an entity."""
        if entity not in self.bias_profiles:
            self.bias_profiles[entity] = BiasProfile(
                entity_name=entity,
                entity_type='agent',
                first_seen=datetime.now()
            )
        
        profile = self.bias_profiles[entity]
        profile.total_flags += len(flags)
        profile.last_updated = datetime.now()
        
        for flag in flags:
            # Update bias type counts
            if flag.bias_type not in profile.bias_counts:
                profile.bias_counts[flag.bias_type] = 0
            profile.bias_counts[flag.bias_type] += 1
            
            # Update severity distribution
            if flag.severity not in profile.severity_distribution:
                profile.severity_distribution[flag.severity] = 0
            profile.severity_distribution[flag.severity] += 1
        
        # Recalculate reputation
        profile.update_reputation()
    
    def _add_to_ledger(self, flag: BiasFlag):
        """Add bias flag to immutable ledger."""
        ledger_entry = {
            'hash': flag.get_hash(),
            'timestamp': flag.timestamp.isoformat(),
            'flag': flag.to_dict(),
            'previous_hash': self.bias_ledger[-1]['hash'] if self.bias_ledger else '0' * 16
        }
        self.bias_ledger.append(ledger_entry)
    
    def get_bias_profile(self, entity: str) -> Optional[BiasProfile]:
        """Get bias profile for an entity."""
        return self.bias_profiles.get(entity)
    
    def get_all_profiles(self) -> Dict[str, BiasProfile]:
        """Get all bias profiles."""
        return self.bias_profiles.copy()
    
    def generate_bias_report(self) -> Dict:
        """Generate comprehensive bias report."""
        report = {
            'total_flags': len(self.bias_flags),
            'unique_entities': len(self.bias_profiles),
            'bias_type_distribution': {},
            'severity_distribution': {},
            'entity_profiles': {},
            'ledger_entries': len(self.bias_ledger),
            'timestamp': datetime.now().isoformat()
        }
        
        # Aggregate bias types
        for flag in self.bias_flags:
            bias_name = flag.bias_type.value
            if bias_name not in report['bias_type_distribution']:
                report['bias_type_distribution'][bias_name] = 0
            report['bias_type_distribution'][bias_name] += 1
            
            # Aggregate severity
            severity_name = flag.severity.name
            if severity_name not in report['severity_distribution']:
                report['severity_distribution'][severity_name] = 0
            report['severity_distribution'][severity_name] += 1
        
        # Add entity profiles
        for entity, profile in self.bias_profiles.items():
            report['entity_profiles'][entity] = {
                'total_flags': profile.total_flags,
                'reputation_score': profile.reputation_score,
                'bias_types': {bt.value: count for bt, count in profile.bias_counts.items()},
                'last_updated': profile.last_updated.isoformat() if profile.last_updated else None
            }
        
        return report
    
    def get_mitigation_recommendations(self, entity: str) -> List[str]:
        """
        Get bias mitigation recommendations for an entity.
        
        Args:
            entity: Entity name (agent or source)
            
        Returns:
            List of actionable recommendations
        """
        profile = self.get_bias_profile(entity)
        if not profile:
            return ["No bias profile found for this entity."]
        
        recommendations = []
        
        # Check reputation score
        if profile.reputation_score < 0.7:
            recommendations.append(
                f"⚠️ Low reputation score ({profile.reputation_score:.2f}). "
                "Consider reducing influence weight for this agent."
            )
        
        # Specific bias recommendations
        if BiasType.CONFIRMATION_BIAS in profile.bias_counts:
            recommendations.append(
                "✅ Detected confirmation bias. Recommendation: "
                "Actively seek contradicting evidence and challenge assumptions."
            )
        
        if BiasType.SELECTION_BIAS in profile.bias_counts:
            recommendations.append(
                "✅ Detected selection bias. Recommendation: "
                "Diversify sources and include underrepresented perspectives."
            )
        
        if BiasType.POLITICAL_BIAS in profile.bias_counts:
            recommendations.append(
                "✅ Detected political bias. Recommendation: "
                "Use neutral language and present multiple political viewpoints."
            )
        
        if BiasType.LANGUAGE_BIAS in profile.bias_counts:
            recommendations.append(
                "✅ Detected emotional language. Recommendation: "
                "Use more neutral, factual language without loaded terms."
            )
        
        if not recommendations:
            recommendations.append("✅ Bias profile is acceptable. Continue monitoring.")
        
        return recommendations
    
    def export_ledger(self, filepath: Optional[str] = None) -> str:
        """
        Export bias ledger for transparency and verification.
        
        Args:
            filepath: Optional path to save JSON file
            
        Returns:
            JSON string of ledger
        """
        ledger_json = json.dumps(self.bias_ledger, indent=2)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(ledger_json)
            self.logger.info(f"Bias ledger exported to {filepath}")
        
        return ledger_json
    
    def verify_ledger_integrity(self) -> bool:
        """Verify the integrity of the bias ledger (blockchain-style)."""
        if not self.bias_ledger:
            return True
        
        for i in range(1, len(self.bias_ledger)):
            if self.bias_ledger[i]['previous_hash'] != self.bias_ledger[i-1]['hash']:
                self.logger.error(f"Ledger integrity violation at entry {i}")
                return False
        
        self.logger.info("Bias ledger integrity verified")
        return True
    
    def audit_text(self, text: str, source: str, context: Optional[Dict] = None) -> 'BiasAuditResult':
        """
        Audit text for bias and return structured result.
        
        This is a convenience method that wraps audit_response and returns
        a BiasAuditResult object with flags, score, and recommendations.
        
        Args:
            text: The text to audit
            source: Who/what generated this text
            context: Additional context
            
        Returns:
            BiasAuditResult with flags, score, and recommendations
        """
        flags = self.audit_response(text, source, context)
        
        # Calculate overall bias score (0 = no bias, 1 = heavy bias)
        if not flags:
            overall_score = 0.0
        else:
            severity_weights = {
                BiasSeverity.LOW: 0.1,
                BiasSeverity.MEDIUM: 0.25,
                BiasSeverity.HIGH: 0.5,
                BiasSeverity.CRITICAL: 1.0
            }
            total_weight = sum(severity_weights.get(f.severity, 0.25) for f in flags)
            overall_score = min(1.0, total_weight / 3.0)  # Normalize
        
        # Get recommendations
        recommendations = self.get_mitigation_recommendations(source)
        
        return BiasAuditResult(
            flags=flags,
            overall_score=overall_score,
            recommendations=recommendations,
            source=source
        )


@dataclass
class BiasAuditResult:
    """Result of a bias audit."""
    flags: List[BiasFlag]
    overall_score: float  # 0.0 (no bias) to 1.0 (heavy bias)
    recommendations: List[str]
    source: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "flags": [f.to_dict() for f in self.flags],
            "overall_score": round(self.overall_score, 3),
            "recommendations": self.recommendations,
            "source": self.source,
            "flag_count": len(self.flags)
        }


# Global instance
bias_auditor = BiasAuditor()


def audit_text_for_bias(text: str, source: str, context: Dict = None) -> List[Dict]:
    """
    Quick utility to audit text for bias.
    
    Returns:
        List of bias flags as dicts
    """
    flags = bias_auditor.audit_response(text, source, context)
    return [flag.to_dict() for flag in flags]

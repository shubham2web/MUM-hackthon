"""
Forensic Engine for ATLAS v4.0

This module implements entity background checks, credibility scoring,
and dossier generation for the adversarial fact-verification system.

Responsibilities:
- Named Entity Extraction (People/Organizations)
- Generate background checks using structured queries
- Score sources using authority metrics
- Build Reputation Dossiers
"""
from __future__ import annotations

import logging
import re
import hashlib
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Try to import spaCy for NER, fallback to regex-based extraction
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logging.warning("spaCy not installed. Using regex-based entity extraction. Install with: pip install spacy && python -m spacy download en_core_web_sm")


class EntityType(Enum):
    """Types of entities that can be extracted."""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    MONEY = "money"
    PRODUCT = "product"
    EVENT = "event"
    UNKNOWN = "unknown"


class CredibilityTier(Enum):
    """Credibility tiers for sources and entities."""
    TIER_1 = "tier_1"  # Official docs, Reuters, AP → +40
    TIER_2 = "tier_2"  # Established outlets → +20
    TIER_3 = "tier_3"  # Blogs, independent → +5
    TIER_4 = "tier_4"  # Anonymous, unverified → -20


@dataclass
class Entity:
    """Represents an extracted named entity."""
    name: str
    entity_type: EntityType
    mentions: int = 1
    contexts: List[str] = field(default_factory=list)
    confidence: float = 0.8
    
    def get_id(self) -> str:
        """Generate unique ID for this entity."""
        return hashlib.md5(f"{self.name}:{self.entity_type.value}".encode()).hexdigest()[:12]


@dataclass
class RedFlag:
    """Represents a credibility red flag."""
    flag_type: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    evidence: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BackgroundCheck:
    """Background check result for an entity."""
    entity: Entity
    credibility_score: float  # 0-100
    tier: CredibilityTier
    verified_facts: List[str]
    red_flags: List[RedFlag]
    source_count: int
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "entity_name": self.entity.name,
            "entity_type": self.entity.entity_type.value,
            "credibility_score": self.credibility_score,
            "tier": self.tier.value,
            "verified_facts": self.verified_facts,
            "red_flags": [
                {
                    "type": rf.flag_type,
                    "description": rf.description,
                    "severity": rf.severity
                } for rf in self.red_flags
            ],
            "source_count": self.source_count,
            "last_updated": self.last_updated.isoformat()
        }


@dataclass
class ReputationDossier:
    """
    Complete reputation dossier for analysis.
    
    Structure per PRD:
    {
      "entity": "...",
      "credibility": 0–100,
      "red_flags": [...],
      "history": [...]
    }
    """
    entity_name: str
    entity_type: EntityType
    credibility: float  # 0-100
    red_flags: List[RedFlag]
    history: List[Dict[str, Any]]
    background_checks: List[BackgroundCheck]
    authority_score: float  # Weighted authority score
    summary: str
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Convert to PRD-compliant dictionary format."""
        return {
            "entity": self.entity_name,
            "entity_type": self.entity_type.value,
            "credibility": round(self.credibility, 2),
            "red_flags": [
                {
                    "type": rf.flag_type,
                    "description": rf.description,
                    "severity": rf.severity,
                    "evidence": rf.evidence[:200]
                } for rf in self.red_flags
            ],
            "history": self.history,
            "authority_score": round(self.authority_score, 2),
            "summary": self.summary,
            "background_checks_count": len(self.background_checks),
            "generated_at": self.generated_at.isoformat()
        }


class ForensicEngine:
    """
    Forensic Engine for ATLAS v4.0
    
    Performs:
    1. Named Entity Extraction (NER)
    2. Background checks on entities
    3. Authority scoring for sources
    4. Dossier generation for debate agents
    """
    
    # Authority scoring tiers (per PRD Section 6.1)
    AUTHORITY_SCORES = {
        CredibilityTier.TIER_1: 40,  # Reuters, AP, Official Docs
        CredibilityTier.TIER_2: 20,  # Established outlets
        CredibilityTier.TIER_3: 5,   # Blogs
        CredibilityTier.TIER_4: -20  # Anonymous sources
    }
    
    # Domain-to-tier mapping
    DOMAIN_TIERS = {
        # Tier 1: Wire services, official sources
        'reuters.com': CredibilityTier.TIER_1,
        'apnews.com': CredibilityTier.TIER_1,
        'gov': CredibilityTier.TIER_1,
        'edu': CredibilityTier.TIER_1,
        'who.int': CredibilityTier.TIER_1,
        'un.org': CredibilityTier.TIER_1,
        
        # Tier 2: Established news outlets
        'bbc.com': CredibilityTier.TIER_2,
        'bbc.co.uk': CredibilityTier.TIER_2,
        'nytimes.com': CredibilityTier.TIER_2,
        'washingtonpost.com': CredibilityTier.TIER_2,
        'theguardian.com': CredibilityTier.TIER_2,
        'economist.com': CredibilityTier.TIER_2,
        'wsj.com': CredibilityTier.TIER_2,
        'npr.org': CredibilityTier.TIER_2,
        'pbs.org': CredibilityTier.TIER_2,
        'nature.com': CredibilityTier.TIER_2,
        'science.org': CredibilityTier.TIER_2,
        
        # Tier 3: Blogs, independent media
        'medium.com': CredibilityTier.TIER_3,
        'substack.com': CredibilityTier.TIER_3,
        'wordpress.com': CredibilityTier.TIER_3,
        'blogspot.com': CredibilityTier.TIER_3,
    }
    
    # Red flag patterns
    RED_FLAG_PATTERNS = [
        {
            "pattern": r"(allegedly|unconfirmed|rumor|unverified)",
            "type": "unverified_claim",
            "description": "Contains unverified or alleged information",
            "severity": "medium"
        },
        {
            "pattern": r"(anonymous source|unnamed source|sources say)",
            "type": "anonymous_source",
            "description": "Relies on anonymous or unnamed sources",
            "severity": "medium"
        },
        {
            "pattern": r"(conspiracy|cover-up|hidden truth|they don't want you to know)",
            "type": "conspiracy_language",
            "description": "Contains conspiracy theory language",
            "severity": "high"
        },
        {
            "pattern": r"(fake news|mainstream media lies|deep state)",
            "type": "inflammatory_rhetoric",
            "description": "Contains inflammatory or divisive rhetoric",
            "severity": "high"
        },
        {
            "pattern": r"(miracle cure|100% effective|guaranteed|secret method)",
            "type": "sensationalism",
            "description": "Contains sensationalist or exaggerated claims",
            "severity": "medium"
        },
        {
            "pattern": r"(breaking:|exclusive:|shocking:)",
            "type": "clickbait",
            "description": "Uses clickbait-style headlines",
            "severity": "low"
        }
    ]
    
    def __init__(self, ai_agent=None):
        """
        Initialize the Forensic Engine.
        
        Args:
            ai_agent: Optional AI agent for enhanced background checks
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ai_agent = ai_agent
        self.nlp = None
        
        # Load spaCy model if available
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                self.logger.info("✅ spaCy NER model loaded successfully")
            except OSError:
                self.logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
                self.nlp = None
    
    def extract_entities(self, text: str) -> List[Entity]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of extracted Entity objects
        """
        entities = []
        entity_counts = {}
        
        if self.nlp:
            # Use spaCy NER
            doc = self.nlp(text[:10000])  # Limit to prevent memory issues
            
            for ent in doc.ents:
                entity_type = self._map_spacy_label(ent.label_)
                key = (ent.text.strip(), entity_type)
                
                if key not in entity_counts:
                    entity_counts[key] = {
                        "mentions": 0,
                        "contexts": []
                    }
                
                entity_counts[key]["mentions"] += 1
                # Get surrounding context
                start = max(0, ent.start_char - 50)
                end = min(len(text), ent.end_char + 50)
                context = text[start:end].strip()
                if context and len(entity_counts[key]["contexts"]) < 3:
                    entity_counts[key]["contexts"].append(context)
        else:
            # Fallback: Regex-based extraction
            entity_counts = self._regex_entity_extraction(text)
        
        # Convert to Entity objects
        for (name, entity_type), data in entity_counts.items():
            if len(name) > 2 and data["mentions"] >= 1:  # Filter noise
                entities.append(Entity(
                    name=name,
                    entity_type=entity_type,
                    mentions=data["mentions"],
                    contexts=data["contexts"],
                    confidence=min(0.9, 0.5 + data["mentions"] * 0.1)
                ))
        
        # Sort by mentions (most mentioned first)
        entities.sort(key=lambda e: e.mentions, reverse=True)
        self.logger.info(f"Extracted {len(entities)} entities from text")
        
        return entities[:20]  # Return top 20 entities
    
    def _map_spacy_label(self, label: str) -> EntityType:
        """Map spaCy NER labels to our EntityType enum."""
        mapping = {
            "PERSON": EntityType.PERSON,
            "ORG": EntityType.ORGANIZATION,
            "GPE": EntityType.LOCATION,
            "LOC": EntityType.LOCATION,
            "DATE": EntityType.DATE,
            "MONEY": EntityType.MONEY,
            "PRODUCT": EntityType.PRODUCT,
            "EVENT": EntityType.EVENT,
            "FAC": EntityType.LOCATION,
            "NORP": EntityType.ORGANIZATION,
        }
        return mapping.get(label, EntityType.UNKNOWN)
    
    def _regex_entity_extraction(self, text: str) -> Dict:
        """Fallback regex-based entity extraction."""
        entity_counts = {}
        
        # Pattern for potential proper nouns (capitalized words)
        proper_noun_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        
        # Pattern for organizations (Inc, Corp, Ltd, etc.)
        org_pattern = r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\s+(?:Inc|Corp|Ltd|LLC|Company|Organization|Institute|University|Foundation)\.?)\b'
        
        # Extract organizations
        for match in re.finditer(org_pattern, text):
            name = match.group(1).strip()
            key = (name, EntityType.ORGANIZATION)
            if key not in entity_counts:
                entity_counts[key] = {"mentions": 0, "contexts": []}
            entity_counts[key]["mentions"] += 1
            
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()
            if len(entity_counts[key]["contexts"]) < 3:
                entity_counts[key]["contexts"].append(context)
        
        # Extract proper nouns (potential people/places)
        for match in re.finditer(proper_noun_pattern, text):
            name = match.group(1).strip()
            # Skip common words
            skip_words = {'The', 'This', 'That', 'These', 'Those', 'What', 'When', 'Where', 'Which', 'Who', 'How', 'Why'}
            if name in skip_words or len(name) < 3:
                continue
            
            # Guess type based on context
            entity_type = EntityType.PERSON if len(name.split()) <= 3 else EntityType.UNKNOWN
            key = (name, entity_type)
            
            if key not in entity_counts:
                entity_counts[key] = {"mentions": 0, "contexts": []}
            entity_counts[key]["mentions"] += 1
        
        return entity_counts
    
    def get_domain_tier(self, url: str) -> CredibilityTier:
        """
        Determine the credibility tier for a domain.
        
        Args:
            url: URL or domain string
            
        Returns:
            CredibilityTier enum value
        """
        if not url:
            return CredibilityTier.TIER_4
        
        # Extract domain from URL
        domain = url.lower()
        if '://' in domain:
            domain = domain.split('://')[1]
        domain = domain.split('/')[0]
        domain = domain.replace('www.', '')
        
        # Check exact match
        if domain in self.DOMAIN_TIERS:
            return self.DOMAIN_TIERS[domain]
        
        # Check TLD for government/educational
        if domain.endswith('.gov') or domain.endswith('.gov.uk'):
            return CredibilityTier.TIER_1
        if domain.endswith('.edu') or domain.endswith('.ac.uk'):
            return CredibilityTier.TIER_1
        
        # Check partial matches
        for known_domain, tier in self.DOMAIN_TIERS.items():
            if known_domain in domain:
                return tier
        
        # Default to Tier 3 for unknown sources
        return CredibilityTier.TIER_3
    
    def calculate_authority_score(self, sources: List[Dict]) -> Dict[str, Any]:
        """
        Calculate authority scores for a set of sources.
        
        Per PRD Section 6.1:
        - Tier 1: Reuters/AP/Official Docs → +40
        - Tier 2: Established outlets → +20
        - Tier 3: Blogs → +5
        - Tier 4: Anonymous sources → −20
        
        Args:
            sources: List of source dictionaries with 'url' key
            
        Returns:
            Dict with authority_scores per source and aggregate score
        """
        authority_data = {
            "sources": {},
            "aggregate_score": 0,
            "tier_distribution": {
                "tier_1": 0,
                "tier_2": 0,
                "tier_3": 0,
                "tier_4": 0
            },
            "total_sources": len(sources)
        }
        
        if not sources:
            return authority_data
        
        total_score = 0
        
        for source in sources:
            url = source.get('url', '') or source.get('domain', '')
            tier = self.get_domain_tier(url)
            score = self.AUTHORITY_SCORES[tier]
            
            authority_data["sources"][url] = {
                "tier": tier.value,
                "score": score
            }
            authority_data["tier_distribution"][tier.value] += 1
            total_score += score
        
        # Calculate aggregate (normalized to 0-100)
        if sources:
            max_possible = len(sources) * 40  # If all were Tier 1
            min_possible = len(sources) * -20  # If all were Tier 4
            normalized = ((total_score - min_possible) / (max_possible - min_possible)) * 100
            authority_data["aggregate_score"] = round(normalized, 2)
        
        return authority_data
    
    def detect_red_flags(self, text: str, source_url: str = "") -> List[RedFlag]:
        """
        Detect credibility red flags in text.
        
        Args:
            text: Text to analyze
            source_url: Optional source URL for context
            
        Returns:
            List of detected RedFlag objects
        """
        red_flags = []
        text_lower = text.lower()
        
        for pattern_config in self.RED_FLAG_PATTERNS:
            matches = re.findall(pattern_config["pattern"], text_lower)
            if matches:
                # Get evidence snippet
                match = re.search(pattern_config["pattern"], text_lower)
                if match:
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    evidence = text[start:end]
                else:
                    evidence = matches[0] if matches else ""
                
                red_flags.append(RedFlag(
                    flag_type=pattern_config["type"],
                    description=pattern_config["description"],
                    severity=pattern_config["severity"],
                    evidence=f"...{evidence}..."
                ))
        
        # Check for source-level red flags
        if source_url:
            tier = self.get_domain_tier(source_url)
            if tier == CredibilityTier.TIER_4:
                red_flags.append(RedFlag(
                    flag_type="low_authority_source",
                    description="Source is from an unverified or low-authority domain",
                    severity="medium",
                    evidence=source_url
                ))
        
        return red_flags
    
    def perform_background_check(
        self,
        entity: Entity,
        evidence_bundle: List[Dict]
    ) -> BackgroundCheck:
        """
        Perform a background check on an entity.
        
        Args:
            entity: Entity to check
            evidence_bundle: Available evidence sources
            
        Returns:
            BackgroundCheck result
        """
        self.logger.info(f"Performing background check on: {entity.name}")
        
        verified_facts = []
        all_red_flags = []
        source_mentions = 0
        credibility_scores = []
        
        # Scan evidence for mentions of this entity
        for source in evidence_bundle:
            text = source.get('text', '') or source.get('content', '')
            url = source.get('url', '')
            title = source.get('title', '')
            
            # Check if entity is mentioned
            if entity.name.lower() in text.lower() or entity.name.lower() in title.lower():
                source_mentions += 1
                
                # Get source tier
                tier = self.get_domain_tier(url)
                credibility_scores.append(self.AUTHORITY_SCORES[tier])
                
                # Detect red flags in this mention
                flags = self.detect_red_flags(text, url)
                all_red_flags.extend(flags)
                
                # Extract potential facts (sentences mentioning the entity)
                sentences = re.split(r'[.!?]', text)
                for sentence in sentences:
                    if entity.name.lower() in sentence.lower() and len(sentence) > 20:
                        # Simple fact extraction
                        clean_sentence = sentence.strip()[:200]
                        if clean_sentence and clean_sentence not in verified_facts:
                            verified_facts.append(clean_sentence)
                            if len(verified_facts) >= 5:
                                break
        
        # Calculate credibility score
        if credibility_scores:
            avg_score = sum(credibility_scores) / len(credibility_scores)
            # Normalize to 0-100
            credibility = ((avg_score + 20) / 60) * 100
        else:
            credibility = 50  # Default neutral
        
        # Adjust for red flags
        high_severity_flags = len([f for f in all_red_flags if f.severity in ['high', 'critical']])
        credibility -= high_severity_flags * 10
        credibility = max(0, min(100, credibility))
        
        # Determine tier
        if credibility >= 70:
            tier = CredibilityTier.TIER_1
        elif credibility >= 50:
            tier = CredibilityTier.TIER_2
        elif credibility >= 30:
            tier = CredibilityTier.TIER_3
        else:
            tier = CredibilityTier.TIER_4
        
        return BackgroundCheck(
            entity=entity,
            credibility_score=round(credibility, 2),
            tier=tier,
            verified_facts=verified_facts[:5],
            red_flags=all_red_flags[:10],
            source_count=source_mentions
        )
    
    def generate_dossier(
        self,
        query: str,
        evidence_bundle: List[Dict],
        include_ai_analysis: bool = False
    ) -> ReputationDossier:
        """
        Generate a complete reputation dossier for a query/claim.
        
        This is the main entry point for forensic analysis.
        
        Args:
            query: The claim or topic being analyzed
            evidence_bundle: Available evidence sources
            include_ai_analysis: Whether to use AI for enhanced analysis
            
        Returns:
            ReputationDossier with complete analysis
        """
        self.logger.info(f"Generating forensic dossier for: {query[:100]}...")
        
        # Combine all text for entity extraction
        all_text = query + " "
        for source in evidence_bundle[:10]:
            all_text += source.get('text', '')[:1000] + " "
            all_text += source.get('title', '') + " "
        
        # Extract entities
        entities = self.extract_entities(all_text)
        self.logger.info(f"Found {len(entities)} key entities")
        
        # Perform background checks on top entities
        background_checks = []
        all_red_flags = []
        
        for entity in entities[:5]:  # Top 5 entities
            check = self.perform_background_check(entity, evidence_bundle)
            background_checks.append(check)
            all_red_flags.extend(check.red_flags)
        
        # Calculate authority scores for sources
        authority_data = self.calculate_authority_score(evidence_bundle)
        
        # Build history from evidence
        history = []
        for source in evidence_bundle[:10]:
            history.append({
                "source": source.get('domain', source.get('url', 'Unknown')[:50]),
                "title": source.get('title', 'No title')[:100],
                "authority_tier": self.get_domain_tier(source.get('url', '')).value,
                "timestamp": source.get('timestamp', datetime.now().isoformat())
            })
        
        # Calculate overall credibility
        if background_checks:
            avg_credibility = sum(bc.credibility_score for bc in background_checks) / len(background_checks)
        else:
            avg_credibility = authority_data["aggregate_score"]
        
        # Adjust for red flags
        critical_flags = len([f for f in all_red_flags if f.severity == 'critical'])
        high_flags = len([f for f in all_red_flags if f.severity == 'high'])
        avg_credibility -= (critical_flags * 15 + high_flags * 8)
        avg_credibility = max(0, min(100, avg_credibility))
        
        # Generate summary
        summary = self._generate_summary(
            query=query,
            entities=entities,
            background_checks=background_checks,
            authority_data=authority_data,
            red_flags=all_red_flags
        )
        
        # Determine primary entity
        primary_entity_name = entities[0].name if entities else "Unknown"
        primary_entity_type = entities[0].entity_type if entities else EntityType.UNKNOWN
        
        dossier = ReputationDossier(
            entity_name=primary_entity_name,
            entity_type=primary_entity_type,
            credibility=round(avg_credibility, 2),
            red_flags=all_red_flags[:15],  # Top 15 red flags
            history=history,
            background_checks=background_checks,
            authority_score=authority_data["aggregate_score"],
            summary=summary
        )
        
        self.logger.info(f"✅ Dossier generated: credibility={dossier.credibility}, red_flags={len(dossier.red_flags)}")
        
        return dossier
    
    def _generate_summary(
        self,
        query: str,
        entities: List[Entity],
        background_checks: List[BackgroundCheck],
        authority_data: Dict,
        red_flags: List[RedFlag]
    ) -> str:
        """Generate a human-readable summary of the forensic analysis."""
        
        # Entity summary
        entity_names = [e.name for e in entities[:3]]
        entity_str = ", ".join(entity_names) if entity_names else "No key entities identified"
        
        # Authority summary
        tier_dist = authority_data.get("tier_distribution", {})
        tier_1_count = tier_dist.get("tier_1", 0)
        tier_4_count = tier_dist.get("tier_4", 0)
        
        # Red flag summary
        critical_count = len([f for f in red_flags if f.severity == 'critical'])
        high_count = len([f for f in red_flags if f.severity == 'high'])
        
        # Build summary
        summary_parts = []
        summary_parts.append(f"Forensic analysis identified {len(entities)} key entities: {entity_str}.")
        
        if tier_1_count > 0:
            summary_parts.append(f"{tier_1_count} high-authority sources (Tier 1) support this analysis.")
        
        if tier_4_count > 0:
            summary_parts.append(f"⚠️ {tier_4_count} low-authority sources detected.")
        
        if critical_count > 0 or high_count > 0:
            summary_parts.append(f"🚨 {critical_count + high_count} significant red flags detected ({critical_count} critical, {high_count} high severity).")
        elif len(red_flags) > 0:
            summary_parts.append(f"Minor concerns: {len(red_flags)} low/medium severity flags.")
        else:
            summary_parts.append("No significant credibility concerns detected.")
        
        # Overall assessment
        aggregate = authority_data.get("aggregate_score", 50)
        if aggregate >= 70:
            summary_parts.append("Overall: HIGH confidence in source quality.")
        elif aggregate >= 50:
            summary_parts.append("Overall: MODERATE confidence in source quality.")
        else:
            summary_parts.append("Overall: LOW confidence - verify with additional sources.")
        
        return " ".join(summary_parts)
    
    def analyze_claim(
        self,
        claim: str,
        evidence_bundle: List[Dict]
    ) -> Dict[str, Any]:
        """
        Complete forensic analysis of a claim.
        
        This is the high-level API for the /analyze endpoint.
        
        Args:
            claim: The claim to analyze
            evidence_bundle: Evidence sources
            
        Returns:
            Complete forensic analysis dictionary
        """
        dossier = self.generate_dossier(claim, evidence_bundle)
        authority_scores = self.calculate_authority_score(evidence_bundle)
        
        return {
            "dossier": dossier.to_dict(),
            "authority_scores": authority_scores,
            "entity_count": len(dossier.background_checks),
            "red_flag_count": len(dossier.red_flags),
            "overall_credibility": dossier.credibility,
            "recommendation": self._get_recommendation(dossier.credibility, dossier.red_flags)
        }
    
    def _get_recommendation(self, credibility: float, red_flags: List[RedFlag]) -> str:
        """Generate a recommendation based on forensic analysis."""
        critical_flags = len([f for f in red_flags if f.severity == 'critical'])
        
        if critical_flags > 0:
            return "CAUTION: Critical credibility concerns detected. Verify with official sources."
        elif credibility >= 70:
            return "PROCEED: High-confidence analysis with reliable sources."
        elif credibility >= 50:
            return "VERIFY: Moderate confidence. Cross-reference with additional sources."
        else:
            return "SKEPTICAL: Low confidence. Significant verification needed."


# Singleton instance for easy import
_forensic_engine_instance: Optional[ForensicEngine] = None


def get_forensic_engine(ai_agent=None) -> ForensicEngine:
    """Get or create the forensic engine singleton."""
    global _forensic_engine_instance
    if _forensic_engine_instance is None:
        _forensic_engine_instance = ForensicEngine(ai_agent)
    return _forensic_engine_instance

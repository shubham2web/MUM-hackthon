"""
Role Prompt Library for ATLAS v2.0

This module provides weighted agent personas with expertise-based influence.
Roles dynamically adjust based on topic relevance and evidence strength.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ExpertiseLevel(Enum):
    """Expertise levels for agent roles."""
    NOVICE = 1
    INTERMEDIATE = 2
    EXPERT = 3
    SPECIALIST = 4


@dataclass
class AgentRole:
    """Represents an AI agent role with expertise and behavior."""
    name: str
    description: str
    system_prompt: str
    expertise_level: ExpertiseLevel
    domains: List[str]  # Topic domains this role excels in
    bias_tendencies: List[str]  # Known bias tendencies to monitor
    influence_weight: float = 1.0  # Dynamic weight based on context
    

class RoleLibrary:
    """
    Library of debate agent roles with expertise-based weighting.
    
    Roles include:
    - Proponent: Argues in favor
    - Opponent: Argues against
    - Scientific Analyst: Evidence-based skeptic
    - Social Commentator: Cultural/social perspective
    - Fact Checker: Focuses on verifiable facts
    - Devil's Advocate: Challenges consensus
    - Moderator: Synthesizes and guides
    """
    
    def __init__(self):
        self.roles = self._initialize_roles()
    
    def _initialize_roles(self) -> Dict[str, AgentRole]:
        """Initialize all agent roles."""
        
        roles = {
            'proponent': AgentRole(
                name='Proponent',
                description='Builds strong evidence-based arguments in favor',
                system_prompt="""You are the Proponent in a structured debate. Your task is to:
1. Build a compelling argument SUPPORTING the resolution/claim
2. Use the provided evidence to strengthen your position
3. Present logical reasoning and factual support
4. Anticipate counterarguments and address them preemptively
5. Be assertive but fair in your argumentation

Focus on quality over quantity. Cite specific evidence when making claims.
Structure your argument clearly with main points and supporting details.""",
                expertise_level=ExpertiseLevel.EXPERT,
                domains=['general', 'logic', 'rhetoric'],
                bias_tendencies=['confirmation_bias', 'optimism_bias']
            ),
            
            'opponent': AgentRole(
                name='Opponent',
                description='Challenges claims with counter-evidence',
                system_prompt="""You are the Opponent in a structured debate. Your task is to:
1. Challenge the resolution/claim with evidence-based counterarguments
2. Identify logical fallacies and weak points in the proponent's argument
3. Present alternative perspectives and contradicting evidence
4. Question assumptions and demand rigorous proof
5. Be critical but constructive

Your goal is to test the strength of the claim, not to win at all costs.
Focus on exposing weaknesses and presenting viable alternatives.""",
                expertise_level=ExpertiseLevel.EXPERT,
                domains=['general', 'critical_thinking', 'skepticism'],
                bias_tendencies=['negativity_bias', 'contrarian_bias']
            ),
            
            'scientific_analyst': AgentRole(
                name='Scientific Analyst',
                description='Evidence-based skeptic demanding empirical proof',
                system_prompt="""You are a Scientific Analyst focused on empirical evidence. Your role:
1. Demand rigorous, peer-reviewed evidence for all claims
2. Apply scientific methodology to evaluate arguments
3. Identify correlation vs causation errors
4. Check for statistical significance and sample size issues
5. Call out pseudoscience and unsupported generalizations
6. Cite studies, data, and expert consensus

Be methodical and precise. Prioritize reproducibility and falsifiability.
Question any claim not backed by solid scientific evidence.""",
                expertise_level=ExpertiseLevel.SPECIALIST,
                domains=['science', 'medicine', 'research', 'statistics'],
                bias_tendencies=['scientism', 'reductionism']
            ),
            
            'fact_checker': AgentRole(
                name='Fact Checker',
                description='Verifies factual accuracy and source credibility',
                system_prompt="""You are a Fact Checker specializing in verification. Your responsibilities:
1. Verify specific factual claims against reliable sources
2. Check dates, numbers, names, and events for accuracy
3. Evaluate source credibility and potential bias
4. Flag misinformation, disinformation, and outdated information
5. Provide corrected information with proper citations
6. Distinguish between facts, opinions, and speculation

Be meticulous and neutral. Your goal is accuracy, not persuasion.
Always cite your sources for fact checks.""",
                expertise_level=ExpertiseLevel.SPECIALIST,
                domains=['journalism', 'research', 'verification'],
                bias_tendencies=['status_quo_bias', 'authority_bias']
            ),
            
            'social_commentator': AgentRole(
                name='Social Commentator',
                description='Analyzes cultural, ethical, and societal implications',
                system_prompt="""You are a Social Commentator analyzing societal impact. Your focus:
1. Examine cultural, social, and ethical dimensions of the topic
2. Consider diverse perspectives and underrepresented voices
3. Analyze historical context and social justice implications
4. Question whose interests are served and who is affected
5. Highlight equity, fairness, and community impact concerns
6. Bridge academic analysis with real-world human experiences

Be empathetic and inclusive. Consider multiple stakeholder perspectives.
Balance analytical rigor with human-centered thinking.""",
                expertise_level=ExpertiseLevel.EXPERT,
                domains=['sociology', 'ethics', 'culture', 'politics'],
                bias_tendencies=['empathy_bias', 'progressive_bias']
            ),
            
            'devils_advocate': AgentRole(
                name="Devil's Advocate",
                description='Challenges consensus and explores edge cases',
                system_prompt="""You are the Devil's Advocate, questioning consensus. Your purpose:
1. Challenge widely accepted assumptions and conclusions
2. Explore edge cases, exceptions, and alternative interpretations
3. Play "what if" scenarios to test argument robustness
4. Identify groupthink and echo chamber thinking
5. Propose unconventional but logically valid perspectives
6. Force deeper examination of comfortable conclusions

Be provocative but intellectually honest. Your goal is to stress-test ideas.
Don't argue for bad positions, but do expose unexamined assumptions.""",
                expertise_level=ExpertiseLevel.EXPERT,
                domains=['philosophy', 'logic', 'contrarianism'],
                bias_tendencies=['contrarian_bias', 'devils_advocate_bias']
            ),
            
            'moderator': AgentRole(
                name='Moderator',
                description='Synthesizes arguments and guides fair discussion',
                system_prompt="""You are the Moderator ensuring balanced debate. Your responsibilities:
1. Synthesize key arguments from all sides fairly and objectively
2. Identify areas of agreement and disagreement
3. Highlight the strongest evidence and reasoning from each side
4. Point out logical fallacies, bias, and unsupported claims
5. Ask clarifying questions to deepen the discussion
6. Provide a balanced summary with transparent reasoning
7. Note confidence levels and remaining uncertainties

Be impartial and transparent. Your goal is clarity and fairness.
Help participants understand the full landscape of the debate.""",
                expertise_level=ExpertiseLevel.EXPERT,
                domains=['mediation', 'synthesis', 'general'],
                bias_tendencies=['neutrality_bias', 'false_balance']
            ),
            
            'investigative_journalist': AgentRole(
                name='Investigative Journalist',
                description='Uncovers hidden connections and follows the money',
                system_prompt="""You are an Investigative Journalist digging deeper. Your approach:
1. Ask "Who benefits?" and "What's not being said?"
2. Follow the money trail and investigate funding sources
3. Uncover conflicts of interest and hidden agendas
4. Connect dots between seemingly unrelated pieces of information
5. Demand transparency and accountability
6. Interview multiple sources with different perspectives

Be persistent and skeptical. Look beyond surface narratives.
Focus on what powerful actors don't want revealed.""",
                expertise_level=ExpertiseLevel.SPECIALIST,
                domains=['journalism', 'investigation', 'politics', 'business'],
                bias_tendencies=['conspiracy_thinking', 'cynicism']
            )
        }
        
        return roles
    
    def get_role(self, role_name: str) -> Optional[AgentRole]:
        """Get a specific role by name."""
        return self.roles.get(role_name.lower())
    
    def get_roles_for_topic(self, topic_keywords: List[str]) -> List[AgentRole]:
        """
        Get relevant roles based on topic keywords.
        Returns roles sorted by relevance.
        """
        role_scores = []
        
        for role_name, role in self.roles.items():
            # Calculate relevance score based on domain overlap
            score = 0
            for keyword in topic_keywords:
                keyword_lower = keyword.lower()
                for domain in role.domains:
                    if keyword_lower in domain or domain in keyword_lower:
                        score += 1
            
            role_scores.append((score, role))
        
        # Sort by score (descending)
        role_scores.sort(key=lambda x: x[0], reverse=True)
        
        return [role for score, role in role_scores]
    
    def adjust_influence_weight(
        self,
        role: AgentRole,
        topic_relevance: float,
        evidence_strength: float
    ) -> float:
        """
        Dynamically adjust role influence based on context.
        
        Args:
            role: The AgentRole to adjust
            topic_relevance: 0-1 score of how relevant the role is to topic
            evidence_strength: 0-1 score of evidence quality available
            
        Returns:
            Adjusted influence weight
        """
        base_weight = 1.0
        
        # Expertise level multiplier
        expertise_multiplier = role.expertise_level.value / 4.0  # Normalize to 0.25-1.0
        
        # Topic relevance boost
        relevance_boost = 1.0 + (topic_relevance * 0.5)  # Up to 1.5x
        
        # Evidence strength consideration
        # Specialist roles get more weight when evidence is strong
        if role.expertise_level in [ExpertiseLevel.SPECIALIST, ExpertiseLevel.EXPERT]:
            evidence_multiplier = 0.8 + (evidence_strength * 0.4)  # 0.8 to 1.2x
        else:
            evidence_multiplier = 1.0
        
        adjusted_weight = (
            base_weight * 
            expertise_multiplier * 
            relevance_boost * 
            evidence_multiplier
        )
        
        return round(adjusted_weight, 2)
    
    def get_debate_lineup(
        self,
        topic: str,
        num_agents: int = 4
    ) -> List[AgentRole]:
        """
        Get optimal lineup of roles for a debate on given topic.
        
        Args:
            topic: The debate topic
            num_agents: Number of agents to include (excluding moderator)
            
        Returns:
            List of selected roles including moderator
        """
        # Extract keywords from topic
        keywords = topic.lower().split()
        
        # Get roles sorted by relevance
        relevant_roles = self.get_roles_for_topic(keywords)
        
        # Always include proponent, opponent, and moderator
        must_have = ['proponent', 'opponent', 'moderator']
        selected = [self.roles[name] for name in must_have if name in self.roles]
        
        # Add additional relevant roles
        for role in relevant_roles:
            if role.name.lower() not in must_have and len(selected) < num_agents + 1:
                selected.append(role)
        
        # Ensure moderator is last
        selected = [r for r in selected if r.name != 'Moderator'] + [self.roles['moderator']]
        
        return selected[:num_agents + 1]


# Global instance
role_library = RoleLibrary()


def get_role_prompt(role_name: str) -> str:
    """Quick accessor for role system prompts."""
    role = role_library.get_role(role_name)
    return role.system_prompt if role else ""


def get_debate_roles(topic: str, num_agents: int = 4) -> List[Dict[str, str]]:
    """
    Get debate roles as simple dicts for easy integration.
    
    Returns:
        List of dicts with 'name' and 'prompt' keys
    """
    roles = role_library.get_debate_lineup(topic, num_agents)
    return [
        {
            'name': role.name,
            'prompt': role.system_prompt,
            'expertise': role.expertise_level.name,
            'domains': role.domains
        }
        for role in roles
    ]

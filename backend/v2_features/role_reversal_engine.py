"""
Role Reversal Engine for ATLAS v2.0

Implements role switching and convergence mechanics to reduce bias
and test argument strength from multiple perspectives.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReversalRound:
    """Represents a single role reversal round."""
    round_number: int
    timestamp: datetime
    role_assignments: Dict[str, str]  # agent_id -> role_name
    arguments: Dict[str, str]  # agent_id -> argument_text
    convergence_score: float  # 0-1, how much positions converged


@dataclass
class ConvergenceMetrics:
    """Tracks convergence across reversal rounds."""
    initial_divergence: float
    final_divergence: float
    convergence_rate: float
    stable_consensus: bool
    consensus_position: Optional[str]
    minority_positions: List[str]


class RoleReversalEngine:
    """
    Manages role reversal debates where agents switch positions
    to test argument strength and reduce confirmation bias.
    
    Process:
    1. Initial debate with assigned roles
    2. Role reversal: Proponent becomes Opponent, etc.
    3. Agents argue from new perspective
    4. Convergence analysis: Do positions move toward truth?
    5. Synthesis of strongest arguments from all perspectives
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rounds_history: List[ReversalRound] = []
        
    def create_reversal_map(
        self,
        current_roles: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Create role reversal mapping.
        
        Args:
            current_roles: Dict of agent_id -> role_name
            
        Returns:
            New role assignments after reversal
        """
        reversal_map = {}
        
        # Define role opposites
        opposites = {
            'proponent': 'opponent',
            'opponent': 'proponent',
            'scientific_analyst': 'social_commentator',
            'social_commentator': 'scientific_analyst',
            'fact_checker': 'devils_advocate',
            'devils_advocate': 'fact_checker',
            'investigative_journalist': 'fact_checker',
            'moderator': 'moderator'  # Moderator stays neutral
        }
        
        for agent_id, current_role in current_roles.items():
            reversed_role = opposites.get(current_role, current_role)
            reversal_map[agent_id] = reversed_role
            self.logger.info(f"Agent {agent_id}: {current_role} → {reversed_role}")
        
        return reversal_map
    
    async def conduct_reversal_round(
        self,
        round_number: int,
        topic: str,
        reversed_roles: Dict[str, str],
        previous_arguments: Dict[str, str],
        evidence: List[str],
        ai_agent  # AiAgent instance
    ) -> ReversalRound:
        """
        Conduct a single role reversal round.
        
        Args:
            round_number: Which reversal round this is
            topic: Debate topic
            reversed_roles: New role assignments
            previous_arguments: Arguments from previous round
            evidence: Available evidence
            ai_agent: AI agent instance for generating responses
            
        Returns:
            ReversalRound object with results
        """
        import asyncio
        self.logger.info(f"Starting Reversal Round {round_number}")
        
        new_arguments = {}
        
        for agent_id, new_role in reversed_roles.items():
            # Build prompt for reversed perspective
            previous_arg = previous_arguments.get(agent_id, "")
            
            prompt = self._build_reversal_prompt(
                topic=topic,
                new_role=new_role,
                previous_argument=previous_arg,
                evidence=evidence
            )
            
            # Generate argument from new perspective using AI agent
            try:
                response_text = ""
                for chunk in ai_agent.stream(
                    user_message=prompt,
                    system_prompt=f"You are now playing the role of {new_role}. Argue from this perspective.",
                    max_tokens=300  # Reduced from 400 to speed up
                ):
                    response_text += chunk
                
                new_arguments[agent_id] = response_text
                self.logger.info(f"Generated reversal argument for {agent_id} as {new_role}")
                
                # Add small delay between calls to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error generating reversal argument: {e}")
                new_arguments[agent_id] = f"[Error: Could not generate argument for {new_role}]"
        
        # Calculate convergence
        convergence_score = self._calculate_convergence(
            previous_arguments,
            new_arguments
        )
        
        round_result = ReversalRound(
            round_number=round_number,
            timestamp=datetime.now(),
            role_assignments=reversed_roles,
            arguments=new_arguments,
            convergence_score=convergence_score
        )
        
        self.rounds_history.append(round_result)
        return round_result
    
    def _build_reversal_prompt(
        self,
        topic: str,
        new_role: str,
        previous_argument: str,
        evidence: List[str]
    ) -> str:
        """Build prompt for role reversal round."""
        
        evidence_str = "\n".join([f"- {e}" for e in evidence[:5]])
        
        prompt = f"""
ROLE REVERSAL CHALLENGE

Topic: {topic}

Your Previous Argument:
{previous_argument}

Your New Role: {new_role}

Now, you must argue from the OPPOSITE perspective. This is not about winning, 
but about stress-testing arguments and discovering truth through dialectic.

Task:
1. Identify the strongest counterarguments to your previous position
2. Use the evidence below to build a compelling case from this new perspective
3. Be intellectually honest - find genuine weaknesses in your old argument
4. Don't strawman your previous self - engage with the best version of that argument

Available Evidence:
{evidence_str}

Provide your argument from this new perspective:
"""
        return prompt
    
    def _calculate_convergence(
        self,
        round1_arguments: Dict[str, str],
        round2_arguments: Dict[str, str]
    ) -> float:
        """
        Calculate convergence score between two rounds.
        Higher score = more convergence toward common position.
        
        Simplified version using word overlap.
        Can be enhanced with semantic embeddings.
        """
        if not round1_arguments or not round2_arguments:
            return 0.0
        
        # Get all unique words from both rounds
        all_round1_words = set()
        all_round2_words = set()
        
        for arg in round1_arguments.values():
            all_round1_words.update(arg.lower().split())
        
        for arg in round2_arguments.values():
            all_round2_words.update(arg.lower().split())
        
        # Calculate overlap (Jaccard similarity)
        intersection = len(all_round1_words.intersection(all_round2_words))
        union = len(all_round1_words.union(all_round2_words))
        
        convergence = intersection / union if union > 0 else 0.0
        
        return convergence
    
    def analyze_convergence(
        self,
        rounds: List[ReversalRound]
    ) -> ConvergenceMetrics:
        """
        Analyze convergence patterns across multiple reversal rounds.
        
        Args:
            rounds: List of ReversalRound objects
            
        Returns:
            ConvergenceMetrics with analysis
        """
        if len(rounds) < 2:
            return ConvergenceMetrics(
                initial_divergence=1.0,
                final_divergence=1.0,
                convergence_rate=0.0,
                stable_consensus=False,
                consensus_position=None,
                minority_positions=[]
            )
        
        initial_divergence = 1.0 - rounds[0].convergence_score
        final_divergence = 1.0 - rounds[-1].convergence_score
        
        # Calculate convergence rate (how fast positions converged)
        convergence_rate = (initial_divergence - final_divergence) / len(rounds)
        
        # Check for stable consensus (last 2 rounds similar)
        stable_consensus = (
            len(rounds) >= 2 and
            abs(rounds[-1].convergence_score - rounds[-2].convergence_score) < 0.1
        )
        
        # Extract consensus and minority positions (simplified)
        consensus_position = "Positions converged toward nuanced middle ground" if stable_consensus else None
        minority_positions = []
        
        metrics = ConvergenceMetrics(
            initial_divergence=initial_divergence,
            final_divergence=final_divergence,
            convergence_rate=convergence_rate,
            stable_consensus=stable_consensus,
            consensus_position=consensus_position,
            minority_positions=minority_positions
        )
        
        self.logger.info(f"Convergence Analysis: {convergence_rate:.2f} rate, Stable: {stable_consensus}")
        
        return metrics
    
    def synthesize_post_reversal(
        self,
        topic: str,
        all_rounds: List[ReversalRound],
        convergence: ConvergenceMetrics
    ) -> str:
        """
        Synthesize final insights after role reversal process.
        
        Args:
            topic: Original debate topic
            all_rounds: All reversal rounds
            convergence: Convergence analysis
            
        Returns:
            Synthesis text with insights
        """
        synthesis_parts = []
        
        synthesis_parts.append(f"# Role Reversal Analysis: {topic}\n")
        
        synthesis_parts.append(f"\n## Convergence Metrics")
        synthesis_parts.append(f"- Initial Divergence: {convergence.initial_divergence:.2%}")
        synthesis_parts.append(f"- Final Divergence: {convergence.final_divergence:.2%}")
        synthesis_parts.append(f"- Convergence Rate: {convergence.convergence_rate:.3f} per round")
        synthesis_parts.append(f"- Stable Consensus Reached: {'Yes' if convergence.stable_consensus else 'No'}")
        
        if convergence.stable_consensus and convergence.consensus_position:
            synthesis_parts.append(f"\n## Consensus Position")
            synthesis_parts.append(convergence.consensus_position)
        
        synthesis_parts.append(f"\n## Key Insights")
        synthesis_parts.append("Role reversal revealed:")
        
        if convergence.convergence_rate > 0.1:
            synthesis_parts.append("✅ Strong convergence - arguments moved toward common truth")
        elif convergence.convergence_rate > 0:
            synthesis_parts.append("⚠️ Modest convergence - some agreement but divergence remains")
        else:
            synthesis_parts.append("❌ No convergence - fundamental disagreement persists")
        
        synthesis_parts.append(f"\n## Rounds Conducted: {len(all_rounds)}")
        for round_obj in all_rounds:
            synthesis_parts.append(
                f"- Round {round_obj.round_number}: "
                f"Convergence {round_obj.convergence_score:.2%}"
            )
        
        return "\n".join(synthesis_parts)
    
    def get_reversal_history(self) -> List[ReversalRound]:
        """Get history of all reversal rounds."""
        return self.rounds_history.copy()
    
    def clear_history(self):
        """Clear reversal history."""
        self.rounds_history.clear()
        self.logger.info("Reversal history cleared")


# Utility function for quick role reversal
def reverse_debate_roles(
    current_debate_state: Dict[str, any]
) -> Dict[str, str]:
    """
    Quick utility to reverse roles in a debate.
    
    Args:
        current_debate_state: Dict with 'agents' key containing agent->role mapping
        
    Returns:
        New role assignments
    """
    engine = RoleReversalEngine()
    current_roles = current_debate_state.get('agents', {})
    return engine.create_reversal_map(current_roles)

"""
ATLAS v2.0 Integration Module

Orchestrates the new v2.0 features:
- Credibility Scoring Engine
- Role Library with weighted personas
- Role Reversal Engine
- Enhanced Bias Auditor

This module provides high-level APIs for the enhanced debate system.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

# Import v2.0 modules
from v2_features.credibility_engine import CredibilityEngine, Source, CredibilityScore
from v2_features.role_library import RoleLibrary, AgentRole
from v2_features.role_reversal_engine import RoleReversalEngine, ReversalRound, ConvergenceMetrics
from v2_features.bias_auditor import BiasAuditor, BiasFlag, BiasProfile

# Import existing modules
from core.ai_agent import AiAgent
from services.pro_scraper import get_diversified_evidence


class ATLASv2:
    """
    Main orchestrator for ATLAS v2.0 enhanced debate system.
    
    Capabilities:
    - Multi-agent debates with weighted expertise
    - Credibility scoring for claims
    - Role reversal for bias reduction
    - Comprehensive bias auditing
    - Transparent provenance tracking
    """
    
    def __init__(self, model_name: str = "llama3"):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize components
        self.credibility_engine = CredibilityEngine()
        self.role_library = RoleLibrary()
        self.reversal_engine = RoleReversalEngine()
        self.bias_auditor = BiasAuditor()
        self.ai_agent = AiAgent(model_name=model_name)
        
        self.logger.info("ATLAS v2.0 initialized with enhanced features")
    
    async def analyze_claim_v2(
        self,
        claim: str,
        num_agents: int = 4,
        enable_reversal: bool = True,
        reversal_rounds: int = 1
    ) -> Dict[str, Any]:
        """
        Complete ATLAS v2.0 analysis pipeline.
        
        Args:
            claim: The claim/topic to analyze
            num_agents: Number of debate agents
            enable_reversal: Whether to conduct role reversal
            reversal_rounds: Number of reversal iterations
            
        Returns:
            Comprehensive analysis with credibility, debate, bias audit
        """
        self.logger.info(f"Starting ATLAS v2.0 analysis: {claim}")
        start_time = datetime.now()
        
        # Step 1: Gather Evidence
        self.logger.info("Step 1: Gathering diversified evidence...")
        # get_diversified_evidence is async, so just await it directly
        evidence_articles = await get_diversified_evidence(claim, num_results=10)
        
        evidence_texts = [article.get('text', '') or article.get('summary', '') 
                         for article in evidence_articles if article.get('text') or article.get('summary')]
        sources = [
            Source(
                url=article.get('url', ''),
                domain=article.get('domain', ''),
                content=article.get('text', '') or article.get('summary', ''),
                timestamp=datetime.now(),
                trust_score=0.7  # Default trust score
            )
            for article in evidence_articles
        ]
        
        # Step 2: Credibility Scoring
        self.logger.info("Step 2: Calculating credibility score...")
        credibility = self.credibility_engine.calculate_credibility(
            claim=claim,
            sources=sources,
            evidence_texts=evidence_texts
        )
        
        # Step 3: Select Debate Roles
        self.logger.info("Step 3: Selecting optimal debate roles...")
        debate_roles = self.role_library.get_debate_lineup(claim, num_agents)
        
        # Step 4: Initial Debate Round
        self.logger.info("Step 4: Conducting initial debate...")
        initial_debate = await self._conduct_debate_round(
            topic=claim,
            roles=debate_roles,
            evidence=evidence_texts,
            round_name="Initial"
        )
        
        # Step 5: Role Reversal (if enabled)
        reversal_results = []
        convergence_metrics = None
        
        if enable_reversal and reversal_rounds > 0:
            self.logger.info(f"Step 5: Conducting {reversal_rounds} role reversal rounds...")
            
            current_roles = {agent['name']: agent['role'] for agent in initial_debate['agents']}
            previous_args = {agent['name']: agent['argument'] for agent in initial_debate['agents']}
            
            for i in range(reversal_rounds):
                reversed_roles = self.reversal_engine.create_reversal_map(current_roles)
                
                # Conduct reversal round (now async)
                reversal_round = await self.reversal_engine.conduct_reversal_round(
                    round_number=i + 1,
                    topic=claim,
                    reversed_roles=reversed_roles,
                    previous_arguments=previous_args,
                    evidence=evidence_texts,
                    ai_agent=self.ai_agent
                )
                
                reversal_results.append({
                    'round': i + 1,
                    'convergence_score': reversal_round.convergence_score,
                    'role_assignments': reversal_round.role_assignments
                })
                
                current_roles = reversed_roles
                previous_args = reversal_round.arguments
            
            # Analyze convergence
            convergence_metrics = self.reversal_engine.analyze_convergence(
                self.reversal_engine.get_reversal_history()
            )
        
        # Step 6: Bias Audit
        self.logger.info("Step 6: Conducting bias audit...")
        bias_report = self._audit_debate_bias(initial_debate, sources)
        
        # Step 7: Generate Synthesis
        self.logger.info("Step 7: Generating synthesis...")
        synthesis = self._generate_synthesis_v2(
            claim=claim,
            credibility=credibility,
            debate=initial_debate,
            reversal_results=reversal_results,
            convergence=convergence_metrics,
            bias_report=bias_report
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        self.logger.info(f"ATLAS v2.0 analysis complete in {duration:.2f}s")
        
        return {
            'claim': claim,
            'timestamp': start_time.isoformat(),
            'duration_seconds': duration,
            'credibility_score': {
                'overall': credibility.overall_score,
                'confidence_level': credibility.confidence_level,
                'source_trust': credibility.source_trust,
                'semantic_alignment': credibility.semantic_alignment,
                'temporal_consistency': credibility.temporal_consistency,
                'evidence_diversity': credibility.evidence_diversity,
                'explanation': credibility.explanation,
                'warnings': credibility.warnings
            },
            'evidence': {
                'total_sources': len(sources),
                'sources': [
                    {
                        'url': s.url,
                        'domain': s.domain,
                        'trust_score': s.trust_score
                    }
                    for s in sources[:10]
                ]
            },
            'debate': initial_debate,
            'role_reversal': {
                'enabled': enable_reversal,
                'rounds': reversal_results,
                'convergence': {
                    'initial_divergence': convergence_metrics.initial_divergence if convergence_metrics else None,
                    'final_divergence': convergence_metrics.final_divergence if convergence_metrics else None,
                    'convergence_rate': convergence_metrics.convergence_rate if convergence_metrics else None,
                    'stable_consensus': convergence_metrics.stable_consensus if convergence_metrics else False
                } if convergence_metrics else None
            },
            'bias_audit': bias_report,
            'synthesis': synthesis
        }
    
    async def _conduct_debate_round(
        self,
        topic: str,
        roles: List[AgentRole],
        evidence: List[str],
        round_name: str = "Debate"
    ) -> Dict[str, Any]:
        """Conduct a single debate round with given roles."""
        
        evidence_context = "\n".join([f"- {e[:200]}" for e in evidence[:5]])
        
        agents_output = []
        
        for role in roles:
            if role.name == "Moderator":
                continue  # Handle moderator last
            
            # Build prompt for this role
            prompt = f"""
Topic: {topic}

Your Role: {role.name}
{role.description}

Available Evidence:
{evidence_context}

Provide your analysis:
"""
            
            # Generate response
            try:
                # Run streaming in thread pool to avoid blocking
                def collect_stream():
                    result = ""
                    for chunk in self.ai_agent.stream(
                        user_message=prompt,
                        system_prompt=role.system_prompt,
                        max_tokens=500
                    ):
                        result += chunk
                    return result
                
                response_text = await asyncio.to_thread(collect_stream)
                
                # Audit for bias
                bias_flags = self.bias_auditor.audit_response(
                    text=response_text,
                    source=role.name,
                    context={'topic': topic, 'role': role.name}
                )
                
                agents_output.append({
                    'name': role.name,
                    'role': role.name,
                    'argument': response_text,
                    'expertise_level': role.expertise_level.name,
                    'domains': role.domains,
                    'bias_flags': [flag.to_dict() for flag in bias_flags]
                })
                
            except Exception as e:
                self.logger.error(f"Error generating response for {role.name}: {e}")
                agents_output.append({
                    'name': role.name,
                    'role': role.name,
                    'argument': f"[Error generating response: {str(e)}]",
                    'expertise_level': role.expertise_level.name,
                    'domains': role.domains,
                    'bias_flags': []
                })
        
        return {
            'round_name': round_name,
            'topic': topic,
            'agents': agents_output,
            'timestamp': datetime.now().isoformat()
        }
    
    def _audit_debate_bias(
        self,
        debate: Dict[str, Any],
        sources: List[Source]
    ) -> Dict[str, Any]:
        """Audit debate for bias patterns."""
        
        # Get all bias profiles
        profiles = self.bias_auditor.get_all_profiles()
        
        # Generate recommendations
        recommendations = {}
        for agent in debate['agents']:
            agent_name = agent['name']
            recs = self.bias_auditor.get_mitigation_recommendations(agent_name)
            recommendations[agent_name] = recs
        
        # Generate comprehensive report
        report = self.bias_auditor.generate_bias_report()
        report['recommendations'] = recommendations
        
        return report
    
    def _generate_synthesis_v2(
        self,
        claim: str,
        credibility: CredibilityScore,
        debate: Dict[str, Any],
        reversal_results: List[Dict],
        convergence: Optional[ConvergenceMetrics],
        bias_report: Dict[str, Any]
    ) -> str:
        """Generate comprehensive synthesis with v2.0 insights."""
        
        parts = []
        
        parts.append(f"# ATLAS v2.0 Analysis: {claim}\n")
        
        # Credibility Assessment
        parts.append("## Credibility Assessment")
        parts.append(f"**Overall Score:** {credibility.overall_score:.1%} ({credibility.confidence_level} Confidence)")
        parts.append(f"**Source Trust:** {credibility.source_trust:.1%}")
        parts.append(f"**Evidence Alignment:** {credibility.semantic_alignment:.1%}")
        parts.append(f"**Temporal Consistency:** {credibility.temporal_consistency:.1%}")
        parts.append(f"**Source Diversity:** {credibility.evidence_diversity:.1%}")
        
        if credibility.warnings:
            parts.append("\n**Warnings:**")
            for warning in credibility.warnings:
                parts.append(f"- ⚠️ {warning}")
        
        # Debate Summary
        parts.append("\n## Debate Insights")
        parts.append(f"Participants: {', '.join([a['name'] for a in debate['agents']])}")
        
        # Role Reversal Results
        if reversal_results:
            parts.append("\n## Role Reversal Analysis")
            if convergence:
                parts.append(f"- Initial Divergence: {convergence.initial_divergence:.1%}")
                parts.append(f"- Final Divergence: {convergence.final_divergence:.1%}")
                parts.append(f"- Convergence Rate: {convergence.convergence_rate:.3f}")
                parts.append(f"- Consensus Reached: {'✅ Yes' if convergence.stable_consensus else '❌ No'}")
        
        # Bias Summary
        parts.append("\n## Bias Audit")
        parts.append(f"- Total Bias Flags: {bias_report['total_flags']}")
        parts.append(f"- Entities Monitored: {bias_report['unique_entities']}")
        
        if bias_report.get('bias_type_distribution'):
            parts.append("\n**Most Common Biases:**")
            sorted_biases = sorted(
                bias_report['bias_type_distribution'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            for bias_type, count in sorted_biases:
                parts.append(f"- {bias_type}: {count} instances")
        
        # Final Verdict
        parts.append("\n## Final Verdict")
        if credibility.overall_score >= 0.75:
            parts.append("✅ **HIGHLY CREDIBLE** - Strong evidence supports this claim")
        elif credibility.overall_score >= 0.5:
            parts.append("⚠️ **MODERATELY CREDIBLE** - Mixed evidence, exercise caution")
        else:
            parts.append("❌ **LOW CREDIBILITY** - Insufficient or contradictory evidence")
        
        return "\n".join(parts)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get status of all v2.0 components."""
        return {
            'credibility_engine': 'operational',
            'role_library': f"{len(self.role_library.roles)} roles available",
            'reversal_engine': f"{len(self.reversal_engine.rounds_history)} rounds conducted",
            'bias_auditor': f"{len(self.bias_auditor.bias_flags)} flags tracked",
            'ai_agent': 'operational',
            'version': '2.0'
        }


# Global instance for easy import - lazy loaded
_atlas_v2_instance = None

def get_atlas_v2():
    """Get or create the global ATLAS v2 instance (lazy initialization)"""
    global _atlas_v2_instance
    if _atlas_v2_instance is None:
        _atlas_v2_instance = ATLASv2()
    return _atlas_v2_instance

# For backward compatibility
atlas_v2 = None  # Will be initialized on first use

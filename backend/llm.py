# backend/llm.py
"""
LLM helper for evidence-constrained reply generation.

This module provides functions to generate assistant responses that are
strictly constrained to the provided evidence, with proper citation markers.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an assistant that must answer ONLY using the provided evidence items. "
    "Cite evidence by index like [1], [2]. If evidence is insufficient, reply 'Inconclusive based on available sources.' "
    "Do not hallucinate or invent facts. Keep the answer succinct (<= 3 sentences) and include a 1-sentence recommendation when possible."
)

DEFAULT_MODEL = os.getenv('LLM_MODEL', 'gpt-4o-mini')


def format_evidence_for_prompt(evidence_bundle: List[Dict]) -> str:
    """Format evidence bundle into a numbered list for LLM prompt."""
    out = []
    for i, ev in enumerate(evidence_bundle, start=1):
        title = ev.get('title') or ev.get('domain') or f"Source {i}"
        domain = ev.get('domain') or ''
        authority = int(round((ev.get('authority') or 0) * 100))
        snippet = ev.get('snippet') or ev.get('summary') or ev.get('text', '')[:200]
        out.append(f"{i}) {title} — {domain} — authority {authority}% — {snippet}")
    return "\n".join(out)


def llm_generate_evidence_based_reply(
    claim: str,
    evidence_bundle: List[Dict],
    analysis: Optional[Dict] = None
) -> str:
    """
    Generate an evidence-constrained reply using LLM.
    
    Args:
        claim: The user's claim or query
        evidence_bundle: List of evidence items with url, title, domain, authority, snippet
        analysis: Optional analysis result from verdict engine
    
    Returns:
        Assistant text with citation markers like [1], [2]
    """
    evidence_text = format_evidence_for_prompt(evidence_bundle)
    system = SYSTEM_PROMPT
    user_msg = (
        f"User claim: {claim}\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        "Task: Using ONLY the evidence above, write a concise answer (<=3 sentences). "
        "Cite evidence indices inline like [1]. Then add a one-sentence recommendation. "
        "If evidence insufficient, say 'Inconclusive based on available sources.'"
    )

    # Try to use available LLM providers
    try:
        # Try Groq first (fastest)
        from core.ai_agent import AiAgent
        agent = AiAgent(
            name="EvidenceAssistant",
            role_prompt="You answer questions using ONLY provided evidence. Cite sources as [1], [2].",
            provider="groq"
        )
        response = agent.generate_response_sync(
            f"{system}\n\n{user_msg}",
            temperature=0.0
        )
        if response and len(response) > 10:
            return response.strip()
    except Exception as e:
        logger.warning(f"Groq LLM failed: {e}")
    
    try:
        # Try HuggingFace
        from core.ai_agent import AiAgent
        agent = AiAgent(
            name="EvidenceAssistant",
            role_prompt="You answer questions using ONLY provided evidence. Cite sources as [1], [2].",
            provider="huggingface"
        )
        response = agent.generate_response_sync(
            f"{system}\n\n{user_msg}",
            temperature=0.0
        )
        if response and len(response) > 10:
            return response.strip()
    except Exception as e:
        logger.warning(f"HuggingFace LLM failed: {e}")

    # Fallback: simple deterministic template if no LLM available
    logger.info("Using deterministic fallback for evidence-based reply")
    return _deterministic_fallback(claim, evidence_bundle, analysis)


def _deterministic_fallback(
    claim: str,
    evidence_bundle: List[Dict],
    analysis: Optional[Dict] = None
) -> str:
    """
    Generate a deterministic reply when LLM is unavailable.
    Uses the analysis result and evidence to construct a response.
    """
    if not evidence_bundle:
        return "Inconclusive based on available sources."
    
    # Get verdict from analysis if available
    verdict_text = "mixed signals"
    confidence = 50
    if analysis:
        verdict = analysis.get('verdict') or analysis.get('final_verdict', {}).get('verdict', '')
        if verdict:
            verdict_text = verdict.lower()
        conf = analysis.get('confidence_pct') or analysis.get('confidence_score', 50)
        if isinstance(conf, (int, float)):
            confidence = int(conf)
    
    # Build citation string from top evidence
    top_count = min(3, len(evidence_bundle))
    top_indices = [f"[{i+1}]" for i in range(top_count)]
    citations = ', '.join(top_indices)
    
    # Build response based on verdict
    if 'true' in verdict_text or 'verified' in verdict_text:
        summary = f"Based on the available evidence ({citations}), this claim appears to be supported with {confidence}% confidence."
    elif 'false' in verdict_text or 'misleading' in verdict_text:
        summary = f"Based on the available evidence ({citations}), this claim appears to be unsupported or misleading with {confidence}% confidence."
    else:
        summary = f"Evidence ({citations}) suggests {verdict_text} regarding this claim ({confidence}% confidence)."
    
    recommendation = "Recommendation: Verify with primary official sources or authoritative outlets before drawing conclusions."
    
    return f"{summary} {recommendation}"


def generate_debate_summary(
    claim: str,
    pro_arguments: List[str],
    opp_arguments: List[str],
    evidence_bundle: List[Dict],
    verdict: Dict
) -> str:
    """
    Generate a summary of a debate between pro and opponent agents.
    
    Args:
        claim: The claim being debated
        pro_arguments: Arguments supporting the claim
        opp_arguments: Arguments opposing the claim
        evidence_bundle: Evidence used in the debate
        verdict: Final verdict from verdict engine
    
    Returns:
        Summary text with citation markers
    """
    # Format evidence citations
    evidence_refs = []
    for i, ev in enumerate(evidence_bundle[:5], start=1):
        domain = ev.get('domain', 'unknown')
        evidence_refs.append(f"[{i}] {domain}")
    
    verdict_text = verdict.get('verdict', 'INCONCLUSIVE')
    confidence = verdict.get('confidence_pct', verdict.get('confidence_score', 50))
    
    summary = (
        f"**Verdict: {verdict_text}** ({confidence}% confidence)\n\n"
        f"**Key Supporting Points:**\n"
    )
    
    for i, arg in enumerate(pro_arguments[:2], 1):
        summary += f"- {arg[:200]}...\n" if len(arg) > 200 else f"- {arg}\n"
    
    summary += f"\n**Key Counter-Points:**\n"
    for i, arg in enumerate(opp_arguments[:2], 1):
        summary += f"- {arg[:200]}...\n" if len(arg) > 200 else f"- {arg}\n"
    
    summary += f"\n**Sources:** {', '.join(evidence_refs)}"
    
    return summary

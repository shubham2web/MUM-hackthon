# backend/utils/explanation.py
"""
NLP Explanation Generator for ATLAS Verdicts

Generates deterministic, auditable natural-language explanations from structured
background + verdict data. Does NOT use raw LLM chain-of-thought.

Output format:
- short: 1-2 sentence verdict summary
- detailed: 3-6 sentence explanation with evidence, agents, scores, and recommendations
"""

from typing import Dict, List, Any
import math


def _top_evidence_items(evidence_provenance: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
    """Get top evidence items sorted by authority score."""
    if not evidence_provenance:
        return []
    # deterministically sort by authority, domain, title
    items = sorted(
        evidence_provenance, 
        key=lambda e: (-float(e.get("authority", e.get("score", 0)) or 0), e.get("domain", ""), e.get("title", ""))
    )
    return items[:top_k]


def _format_evidence_short(ev: Dict[str, Any]) -> str:
    """Format a single evidence item for display (≤200 chars)."""
    title = ev.get("title") or ev.get("domain") or "Unknown source"
    # Truncate title if too long
    if len(title) > 60:
        title = title[:57] + "..."
    domain = ev.get("domain") or ""
    auth_pct = int(round(float(ev.get("authority", ev.get("score", 0)) or 0) * 100))
    return f"{title} ({domain}, {auth_pct}%)"


def generate_nlp_explanation(
    claim: str, 
    verdict: Dict[str, Any], 
    background: Dict[str, Any], 
    max_sentences: int = 5
) -> Dict[str, str]:
    """
    Generate a deterministic, auditable natural-language explanation from structured background + verdict.
    
    Args:
        claim: The original claim being analyzed
        verdict: Verdict dict with verdict, confidence_pct, recommendation, etc.
        background: Background report with evidence_provenance, agents, score_breakdown, audit
        max_sentences: Maximum sentences in detailed explanation
    
    Returns:
        {
            "short": "<1-2 sentence summary>",
            "detailed": "<3-6 sentences / bullets>"
        }
    """
    # Defensive defaults
    background = background or {}
    verdict = verdict or {}
    
    evidence = background.get("evidence_provenance", []) or []
    agents = background.get("agents", {}) or {}
    score = background.get("score_breakdown", {}) or {}
    audit = background.get("audit", {}) or {}

    verdict_label = verdict.get("verdict") or verdict.get("label") or "UNKNOWN"
    
    # Confidence: try multiple sources
    confidence_pct = None
    if isinstance(verdict.get("confidence_pct"), (int, float)):
        confidence_pct = int(round(verdict.get("confidence_pct")))
    elif isinstance(verdict.get("confidence"), (int, float)):
        confidence_pct = int(round(float(verdict.get("confidence")) * 100))
    elif score.get("combined_confidence") is not None:
        confidence_pct = int(round(float(score.get("combined_confidence", 0)) * 100))
    
    # Short summary
    if confidence_pct is not None:
        short = f"Verdict: {verdict_label}. Confidence: {confidence_pct}%."
    else:
        short = f"Verdict: {verdict_label}."

    # Build detailed explanation deterministically
    parts = []

    # 1) Top evidence used
    top_evs = _top_evidence_items(evidence, top_k=3)
    if top_evs:
        ev_texts = [_format_evidence_short(e) for e in top_evs]
        parts.append(f"The conclusion is primarily supported by {len(top_evs)} sources: " + "; ".join(ev_texts) + ".")
    else:
        parts.append("No external evidence items were available to support or refute the claim.")

    # 2) Agent findings (short summaries)
    agent_summaries = []
    agent_names = [
        "factual_analyst", "forensic_agent", "bias_auditor", 
        "source_critic", "evidence_synthesizer", "proponent", "opponent"
    ]
    for agent_name in agent_names:
        a = agents.get(agent_name) or agents.get(agent_name.replace("_", ""), {})
        if a and a.get("summary"):
            # Keep deterministic order by agent_name
            display_name = agent_name.replace('_', ' ').title()
            summary = a.get("summary", "")
            # Truncate long summaries
            if len(summary) > 100:
                summary = summary[:97] + "..."
            agent_summaries.append(f"{display_name}: {summary}")
    
    if agent_summaries:
        parts.append("Agent findings: " + " | ".join(agent_summaries[:3]) + ".")  # Max 3 agents

    # 3) Score rationale
    auth_avg = score.get("authority_avg")
    ecount = score.get("evidence_count", len(evidence))
    if auth_avg is not None:
        parts.append(
            f"The system combined {ecount} evidence items (average authority {int(round(float(auth_avg) * 100))}%) "
            "to compute the confidence using a probabilistic aggregation."
        )
    elif ecount > 0:
        parts.append(f"The system used {ecount} evidence items to reach this conclusion.")

    # 4) Contradictions or bias signals
    bias_notes = []
    
    # Check bias auditor signals
    ba = agents.get("bias_auditor") or {}
    if ba:
        sigs = ba.get("signals") or ba.get("bias_signals") or []
        if sigs:
            summarized = []
            for s in sigs[:2]:  # Top 2 signals
                t = s.get("type") or s.get("signal") or "bias"
                sev = s.get("severity")
                if sev is not None:
                    summarized.append(f"{t} (severity {round(float(sev), 2)})")
                else:
                    summarized.append(t)
            bias_notes.append("Detected signals: " + ", ".join(summarized))
    
    # Check for contradictions
    contradictions = score.get("contradictions")
    if contradictions:
        bias_notes.append(f"Contradictions found: {len(contradictions)} items.")
    
    if bias_notes:
        parts.append("Notes: " + "; ".join(bias_notes) + ".")

    # 5) Final recommendation
    rec = verdict.get("recommendation") or audit.get("notes")
    if rec:
        # Truncate long recommendations
        if len(rec) > 150:
            rec = rec[:147] + "..."
        parts.append("Recommendation: " + rec)

    # Assemble detailed explanation with sentence limit
    detailed = " ".join(parts)
    
    # Enforce sentence cap (naive split)
    sentences = [s.strip() for s in detailed.split(".") if s.strip()]
    detailed_trimmed = ". ".join(sentences[:max_sentences]) + (". " if sentences else "")
    
    # Attach fingerprint for audit
    fingerprint = audit.get("deterministic_hash") if audit else None
    if fingerprint:
        detailed_trimmed += f"(Fingerprint: {fingerprint[:12]})."

    return {
        "short": short,
        "detailed": detailed_trimmed
    }


def generate_simple_explanation(verdict: Dict[str, Any], evidence_count: int = 0) -> Dict[str, str]:
    """
    Generate a simpler explanation when full background data is not available.
    
    Args:
        verdict: Verdict dict with verdict, confidence_pct, recommendation
        evidence_count: Number of evidence items used
    
    Returns:
        {"short": "...", "detailed": "..."}
    """
    verdict = verdict or {}
    verdict_label = verdict.get("verdict") or "UNKNOWN"
    confidence_pct = verdict.get("confidence_pct") or verdict.get("confidence")
    
    if isinstance(confidence_pct, float) and confidence_pct <= 1:
        confidence_pct = int(round(confidence_pct * 100))
    elif confidence_pct is not None:
        confidence_pct = int(round(confidence_pct))
    
    # Short
    if confidence_pct is not None:
        short = f"Verdict: {verdict_label}. Confidence: {confidence_pct}%."
    else:
        short = f"Verdict: {verdict_label}."
    
    # Detailed
    parts = [short]
    
    if evidence_count > 0:
        parts.append(f"Analysis based on {evidence_count} evidence sources.")
    else:
        parts.append("Limited evidence was available for analysis.")
    
    summary = verdict.get("summary")
    if summary:
        if len(summary) > 150:
            summary = summary[:147] + "..."
        parts.append(summary)
    
    rec = verdict.get("recommendation")
    if rec:
        if len(rec) > 150:
            rec = rec[:147] + "..."
        parts.append(f"Recommendation: {rec}")
    
    detailed = " ".join(parts)
    
    return {
        "short": short,
        "detailed": detailed
    }

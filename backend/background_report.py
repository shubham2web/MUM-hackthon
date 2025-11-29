# backend/background_report.py
"""
Safe Background Reasoning Report Generator

Produces structured, auditable background reports for judges/auditors.
Contains NO internal chain-of-thought or model tokens — only:
- Pipeline trace with timing
- Evidence provenance
- Agent summaries
- Score breakdown with calculation
- Audit fingerprint

PRD-compliant: exposes actionable reasoning without private model internals.
"""

import time
import hashlib
import datetime
from typing import Dict, List, Any, Optional

VERSION = "v4.1.3-rag-adapter"


def now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class TimingTracker:
    """
    Simple timing tracker for pipeline stages.
    Usage:
        tracker = TimingTracker()
        tracker.start("scraping")
        # ... do scraping ...
        tracker.end("scraping", "fetched 6 urls")
    """
    def __init__(self):
        self.timings: Dict[str, Dict] = {}
        self._starts: Dict[str, float] = {}
    
    def start(self, step: str):
        self._starts[step] = time.time()
    
    def end(self, step: str, msg: str = ""):
        if step in self._starts:
            elapsed_ms = int((time.time() - self._starts[step]) * 1000)
            self.timings[step] = {"msg": msg, "ms": elapsed_ms}
            del self._starts[step]
    
    def add(self, step: str, msg: str, ms: int):
        """Manually add a timing entry."""
        self.timings[step] = {"msg": msg, "ms": ms}
    
    def get_stats(self) -> Dict[str, Dict]:
        return self.timings


def make_background_report(
    claim: str,
    evidence_bundle: List[Dict[str, Any]],
    agents_outputs: Optional[Dict[str, Dict]] = None,
    timing_stats: Optional[Dict[str, Dict]] = None,
    score_values: Optional[Dict[str, Any]] = None,
    version: str = VERSION
) -> Dict[str, Any]:
    """
    Generate a safe, auditable background report.
    
    Args:
        claim: The original claim/query
        evidence_bundle: List of evidence items with url, domain, authority, snippet, etc.
        agents_outputs: Dict of agent name -> {summary, claims, used_evidence}
        timing_stats: Dict of step -> {msg, ms}
        score_values: Dict with combined_confidence and other scores
        version: Version string for audit trail
    
    Returns:
        Safe background report dict ready for JSON serialization
    """
    agents_outputs = agents_outputs or {}
    timing_stats = timing_stats or {}
    score_values = score_values or {}
    
    # Build trace timeline
    trace = []
    for step, data in timing_stats.items():
        trace.append({
            "step": step,
            "msg": data.get("msg", ""),
            "took_ms": data.get("ms", 0)
        })
    
    # Build evidence provenance (safe fields only)
    evidence_provenance = []
    for ev in evidence_bundle:
        ev_id = ev.get("id") or ev.get("url_hash", "")[:8] or f"e{len(evidence_provenance)+1}"
        evidence_provenance.append({
            "id": ev_id,
            "title": ev.get("title", "Unknown"),
            "url": ev.get("url", ""),
            "domain": ev.get("domain", ""),
            "authority": round(float(ev.get("authority", 0)), 2),
            "method": ev.get("extraction_method") or ev.get("method", "unknown"),
            "snippet": (ev.get("snippet") or ev.get("summary") or "")[:200],
            "fetch_time": ev.get("fetched_at") or now_iso(),
            "cache_hit": bool(ev.get("cache_hit", False))
        })
    
    # Build safe agent summaries (no internal reasoning)
    agents_safe = {}
    for name, out in agents_outputs.items():
        # Truncate evidence IDs to 8 chars for readability
        used_ev = out.get("used_evidence", [])
        used_ev_safe = [e[:8] if isinstance(e, str) and len(e) > 8 else e for e in used_ev]
        
        agents_safe[name] = {
            "summary": out.get("summary", ""),
            "claims": out.get("claims", []),
            "used_evidence": used_ev_safe
        }
    
    # Build score breakdown with formula (transparent calculation)
    authority_values = [ev.get("authority", 0) for ev in evidence_bundle]
    authority_avg = sum(authority_values) / max(1, len(authority_values))
    
    score_breakdown = {
        "authority_avg": round(authority_avg, 2),
        "evidence_count": len(evidence_bundle),
        "combined_confidence": round(score_values.get("combined_confidence", 0), 2),
        "calculation": "1 - product(1 - auth_i * relevance_i)",
        "values": [
            {
                "id": ev.get("id") or ev.get("url_hash", "")[:8] or f"e{i+1}",
                "auth": round(ev.get("authority", 0), 2),
                "relevance": round(ev.get("relevance", 1.0), 2)
            }
            for i, ev in enumerate(evidence_bundle)
        ]
    }
    
    # Generate deterministic fingerprint for audit
    evidence_ids = sorted([p["id"] for p in evidence_provenance])
    fingerprint_input = f"{claim}|{'|'.join(evidence_ids)}|{version}"
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()
    
    audit = {
        "version": version,
        "deterministic_hash": fingerprint,
        "timestamp": now_iso(),
        "notes": "No raw model tokens or chain-of-thought included."
    }
    
    return {
        "trace": trace,
        "evidence_provenance": evidence_provenance,
        "agents": agents_safe,
        "score_breakdown": score_breakdown,
        "audit": audit
    }


def extract_agent_summary(agent_response: Dict, agent_name: str) -> Dict:
    """
    Extract safe summary from agent response.
    Removes any internal reasoning, keeps only summary and evidence references.
    """
    return {
        "summary": agent_response.get("summary", ""),
        "claims": agent_response.get("claims", agent_response.get("points", [])),
        "used_evidence": agent_response.get("citations", agent_response.get("used_evidence", []))
    }


# Export
__all__ = [
    'make_background_report',
    'TimingTracker',
    'extract_agent_summary',
    'VERSION'
]

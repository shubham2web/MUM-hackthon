# verdict_engine.py
"""
Neutral Verdict Engine for ATLAS v4.1

- Accepts extracted claims, evidence bundle, bias report, forensic dossier.
- Produces a neutral verdict JSON conforming to PRD v4.1 schema.
- Uses safe deterministic heuristics + optional LLM summarizer hooks.
- Includes schema validation & helpful logs.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import math

logger = logging.getLogger("verdict_engine")
logger.setLevel(logging.INFO)

# ---------- Configuration / thresholds ----------
VERIFIED_THRESHOLD = 75
DEBUNKED_THRESHOLD = 35
MAX_SUMMARY_CHARS = 800

# ---------- Helpers ----------
def safe_mean(values: List[float], default: float = 0.5) -> float:
    vals = [v for v in values if v is not None]
    if not vals:
        return default
    return sum(vals) / len(vals)

def clamp_0_100(v: float) -> float:
    return max(0.0, min(100.0, v))

# ---------- Pluggable hook: LLM summarizer ----------
def llm_summarize(text: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """
    Hook to replace with an LLM summarizer when available.
    Currently returns text truncated to max_chars.
    """
    if not text:
        return ""
    return text[:max_chars]

# ---------- Core functions ----------
def summarize_evidence(evidence_bundle: List[Dict[str, Any]]) -> str:
    # take top authoritative snippets and summarise (LLM hook)
    try:
        tops = sorted(evidence_bundle, key=lambda e: e.get("authority", 0.5), reverse=True)[:4]
        snippets = " ".join([e.get("snippet") or e.get("excerpt") or "" for e in tops]).strip()
        return llm_summarize(snippets)
    except Exception as e:
        logger.exception("summarize_evidence failed")
        return ""

def compute_alignment_score(evidence_bundle: List[Dict[str, Any]]) -> float:
    # base alignment: mean of authority scores (0..1) * 100
    if not evidence_bundle:
        return 50.0
    scores = [float(e.get("authority", 0.5)) for e in evidence_bundle]
    return clamp_0_100(safe_mean(scores) * 100.0)

def compute_bias_penalty(bias_report: Optional[Dict[str, Any]]) -> float:
    # bias_report expected: {"flags": [{"type":..., "severity":0-1}, ...], "overall_score":0-1}
    if not bias_report:
        return 0.0
    overall = float(bias_report.get("overall_score", 0.0))
    # penalty scaled 0..30 points depending on severity
    return clamp_0_100(overall * 30.0)

def compute_forensic_penalty(forensic_dossier: Optional[Dict[str, Any]]) -> float:
    # If dossier shows high red_flags severity, reduce confidence
    if not forensic_dossier:
        return 0.0
    entities = forensic_dossier.get("entities", [])
    if not entities:
        return 0.0
    # average inverse reputation (0..1) scaled to 0..15
    reputations = []
    for ent in entities:
        rep = float(ent.get("reputation_score", 0.5))
        reputations.append(1.0 - rep)
    avg_inv = safe_mean(reputations, default=0.0)
    return clamp_0_100(avg_inv * 15.0)

def classify_verdict(score: float) -> str:
    if score >= VERIFIED_THRESHOLD:
        return "VERIFIED"
    if score <= DEBUNKED_THRESHOLD:
        return "DEBUNKED"
    return "COMPLEX"

def build_key_evidence(evidence_bundle: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    try:
        return sorted(evidence_bundle, key=lambda e: e.get("authority", 0.5), reverse=True)[:limit]
    except Exception:
        return evidence_bundle[:limit]

# ---------- Public API ----------
def decide_verdict(
    claims: List[str],
    evidence_bundle: List[Dict[str, Any]],
    bias_report: Optional[Dict[str, Any]] = None,
    forensic_dossier: Optional[Dict[str, Any]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns verdict JSON:
    {
      verdict, confidence (0..1), confidence_pct, summary, key_evidence,
      contradictions, forensic_dossier, bias_signals, recommendation, raw_evidence_count, timestamp
    }
    """
    try:
        alignment = compute_alignment_score(evidence_bundle)  # 0..100
        bias_penalty = compute_bias_penalty(bias_report)      # 0..30
        forensic_penalty = compute_forensic_penalty(forensic_dossier) # 0..15

        # base score influenced by alignment largely
        base = alignment
        score = clamp_0_100(base - bias_penalty - forensic_penalty)

        # small adjustment for number of evidence items (more = slightly more confidence)
        n = len(evidence_bundle) if evidence_bundle is not None else 0
        if n >= 3:
            score = clamp_0_100(score + min(5, math.log1p(n) * 2.0))

        verdict_label = classify_verdict(score)
        summary_text = summarize_evidence(evidence_bundle) or (claims[0] if claims else "")

        result = {
            "verdict": verdict_label,
            "confidence": round(score / 100.0, 3),
            "confidence_pct": int(round(score)),
            "summary": summary_text,
            "key_evidence": build_key_evidence(evidence_bundle),
            "contradictions": extra_context.get("contradictions", []) if extra_context else [],
            "forensic_dossier": forensic_dossier or {"entities": []},
            "bias_signals": bias_report.get("flags", []) if bias_report else [],
            "recommendation": "Cross-check with primary official sources." if verdict_label != "VERIFIED" else "Primary corroboration present; monitor for updates.",
            "raw_evidence_count": n,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # final validation: ensure no Proponent/Opponent fields
        text_blob = (result.get("summary","") + " " + str(result.get("recommendation",""))).lower()
        if "proponent" in text_blob or "opponent" in text_blob:
            logger.warning("Proponent/Opponent tokens found in generated summary - sanitizing")
            result["summary"] = result["summary"].replace("Proponent", "").replace("Opponent", "")

        return result
    except Exception as e:
        logger.exception("decide_verdict failed")
        # graceful fallback verdict
        return {
            "verdict": "COMPLEX",
            "confidence": 0.25,
            "confidence_pct": 25,
            "summary": "Verdict engine failed to compute a stable verdict; please check logs.",
            "key_evidence": evidence_bundle[:3] if evidence_bundle else [],
            "contradictions": [],
            "forensic_dossier": forensic_dossier or {"entities": []},
            "bias_signals": bias_report.get("flags", []) if bias_report else [],
            "recommendation": "Manual review required.",
            "raw_evidence_count": len(evidence_bundle) if evidence_bundle else 0,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

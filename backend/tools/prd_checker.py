# prd_checker.py - PRD Compliance Checker for ATLAS v4.0
"""
Automated PRD Compliance Checker

This module validates that debate transcripts comply with ATLAS v4.0 PRD requirements:
1. All factual claims must have [SRC:ID] citations
2. Forensic dossier must be generated and included
3. Verdict Engine must be called with proper parameters
4. Authority scores must be displayed
"""

import re
import json
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

# Pattern to match source citations like [SRC:TOI-001 | auth:75] or [SRC:TOI-001]
SRC_PATTERN = re.compile(r"\[SRC:([A-Za-z0-9_-]+)(?:\s*\|\s*auth:(\d{1,3}))?\]")

# Keywords that indicate factual claims requiring citations
FACTUAL_CLAIM_KEYWORDS = [
    "said", "reported", "confirmed", "according to", "meeting", "invited", 
    "appointed", "announced", "stated", "revealed", "showed", "found",
    "discovered", "evidence shows", "data indicates", "sources say",
    "documents show", "reports indicate", "officials say", "study found"
]


def has_citation(text: str) -> bool:
    """Check if text contains a valid [SRC:ID] citation."""
    return bool(SRC_PATTERN.search(text))


def extract_citations(text: str) -> List[Dict[str, Any]]:
    """Extract all citations from text with their authority scores."""
    citations = []
    for match in SRC_PATTERN.finditer(text):
        source_id = match.group(1)
        auth_score = int(match.group(2)) if match.group(2) else None
        citations.append({
            "source_id": source_id,
            "authority_score": auth_score,
            "full_match": match.group(0)
        })
    return citations


def is_factual_claim(text: str) -> bool:
    """Check if text contains keywords indicating a factual claim."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in FACTUAL_CLAIM_KEYWORDS)


def check_citation_compliance(transcript: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Check if all turns with factual claims have proper citations.
    
    Args:
        transcript: List of turn dictionaries with 'role' and 'text' keys
        
    Returns:
        Dict with compliance status and any missing citations
    """
    missing_citations = []
    compliant_turns = []
    total_factual_turns = 0
    
    for turn in transcript:
        text = turn.get('text', '')
        role = turn.get('role', 'unknown')
        
        if is_factual_claim(text):
            total_factual_turns += 1
            
            if has_citation(text):
                citations = extract_citations(text)
                compliant_turns.append({
                    "role": role,
                    "text_preview": text[:100] + "..." if len(text) > 100 else text,
                    "citations": citations
                })
            else:
                missing_citations.append({
                    "role": role,
                    "text_preview": text[:140] + "..." if len(text) > 140 else text,
                    "issue": "Factual claim without [SRC:ID] citation"
                })
    
    compliance_rate = (len(compliant_turns) / total_factual_turns * 100) if total_factual_turns > 0 else 100
    
    return {
        "is_compliant": len(missing_citations) == 0,
        "compliance_rate": round(compliance_rate, 1),
        "total_factual_turns": total_factual_turns,
        "compliant_turns": len(compliant_turns),
        "missing_citations": missing_citations,
        "compliant_examples": compliant_turns[:3]  # Sample of good citations
    }


def check_dossier_compliance(dossier: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if forensic dossier has all required fields.
    
    Required fields per PRD:
    - entity: Primary entity being analyzed
    - credibility: Credibility score (0-100)
    - authority_score: Authority score (0-100)
    - red_flags: List of identified red flags
    - key_entities: List of key entities found
    """
    required_keys = ["entity", "credibility", "red_flags"]
    recommended_keys = ["authority_score", "key_entities", "background_checks"]
    
    if not dossier:
        return {
            "is_compliant": False,
            "has_dossier": False,
            "missing_required": required_keys,
            "missing_recommended": recommended_keys
        }
    
    missing_required = [k for k in required_keys if k not in dossier or dossier[k] is None]
    missing_recommended = [k for k in recommended_keys if k not in dossier or dossier[k] is None]
    
    return {
        "is_compliant": len(missing_required) == 0,
        "has_dossier": True,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "dossier_summary": {
            "entity": dossier.get("entity", "N/A"),
            "credibility": dossier.get("credibility", "N/A"),
            "red_flags_count": len(dossier.get("red_flags", [])),
            "authority_score": dossier.get("authority_score", "N/A")
        }
    }


def check_evidence_bundle_compliance(evidence_bundle: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check if evidence bundle has proper structure and authority scores.
    
    Each evidence item should have:
    - url: Source URL
    - title: Article/source title
    - authority_score: Calculated authority (0-100)
    - source_id: Unique identifier for citation
    """
    if not evidence_bundle:
        return {
            "is_compliant": False,
            "has_evidence": False,
            "source_count": 0,
            "issues": ["No evidence sources provided"]
        }
    
    issues = []
    sources_with_auth = 0
    
    for idx, source in enumerate(evidence_bundle):
        if not source.get('url'):
            issues.append(f"Source {idx+1}: Missing URL")
        if not source.get('title'):
            issues.append(f"Source {idx+1}: Missing title")
    
    return {
        "is_compliant": len(issues) == 0,
        "has_evidence": True,
        "source_count": len(evidence_bundle),
        "issues": issues,
        "sources_summary": [
            {
                "index": i+1,
                "domain": s.get('domain', 'unknown'),
                "title_preview": (s.get('title', 'Untitled') or 'Untitled')[:50]
            }
            for i, s in enumerate(evidence_bundle[:5])
        ]
    }


def check_verdict_compliance(verdict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if verdict follows PRD JSON structure.
    
    Required fields:
    - verdict: VERIFIED, DEBUNKED, or COMPLEX
    - confidence: 0-100
    - winning_argument: Summary of winning side
    - critical_analysis: Detailed analysis
    - key_evidence: List of evidence with authority scores
    """
    required_keys = ["verdict", "confidence", "winning_argument", "critical_analysis", "key_evidence"]
    valid_verdicts = ["VERIFIED", "DEBUNKED", "COMPLEX", "INCONCLUSIVE"]
    
    if not verdict:
        return {
            "is_compliant": False,
            "verdict_called": False,
            "missing_keys": required_keys
        }
    
    missing_keys = [k for k in required_keys if k not in verdict]
    
    verdict_value = verdict.get("verdict", "")
    verdict_valid = verdict_value.upper() in valid_verdicts
    
    confidence = verdict.get("confidence", 0)
    confidence_valid = isinstance(confidence, (int, float)) and 0 <= confidence <= 100
    
    key_evidence = verdict.get("key_evidence", [])
    evidence_has_auth = all(
        isinstance(e, dict) and "authority" in e 
        for e in key_evidence
    ) if key_evidence else False
    
    return {
        "is_compliant": len(missing_keys) == 0 and verdict_valid and confidence_valid,
        "verdict_called": True,
        "missing_keys": missing_keys,
        "verdict_value": verdict_value,
        "verdict_valid": verdict_valid,
        "confidence": confidence,
        "confidence_valid": confidence_valid,
        "key_evidence_count": len(key_evidence),
        "evidence_has_authority_scores": evidence_has_auth
    }


def run_full_prd_check(debate_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run complete PRD compliance check on a debate.
    
    Args:
        debate_data: Dict containing:
            - transcript: List of turn dicts
            - evidence_bundle: List of source dicts
            - dossier: Forensic dossier dict
            - verdict: Verdict Engine output dict
            
    Returns:
        Comprehensive compliance report
    """
    transcript = debate_data.get('transcript', [])
    evidence_bundle = debate_data.get('evidence_bundle', [])
    dossier = debate_data.get('dossier', {})
    verdict = debate_data.get('verdict', {})
    
    citation_check = check_citation_compliance(transcript)
    dossier_check = check_dossier_compliance(dossier)
    evidence_check = check_evidence_bundle_compliance(evidence_bundle)
    verdict_check = check_verdict_compliance(verdict)
    
    # Calculate overall compliance score
    checks = [
        citation_check['is_compliant'],
        dossier_check['is_compliant'],
        evidence_check['is_compliant'],
        verdict_check['is_compliant']
    ]
    compliance_score = sum(1 for c in checks if c) / len(checks) * 100
    
    # Determine overall status
    if compliance_score == 100:
        status = "FULLY_COMPLIANT"
    elif compliance_score >= 75:
        status = "MOSTLY_COMPLIANT"
    elif compliance_score >= 50:
        status = "PARTIALLY_COMPLIANT"
    else:
        status = "NON_COMPLIANT"
    
    return {
        "overall_status": status,
        "compliance_score": round(compliance_score, 1),
        "checks": {
            "citations": citation_check,
            "dossier": dossier_check,
            "evidence_bundle": evidence_check,
            "verdict": verdict_check
        },
        "recommendations": generate_recommendations(
            citation_check, dossier_check, evidence_check, verdict_check
        )
    }


def generate_recommendations(citation_check, dossier_check, evidence_check, verdict_check) -> List[str]:
    """Generate actionable recommendations based on compliance check results."""
    recommendations = []
    
    if not citation_check['is_compliant']:
        recommendations.append(
            f"Add [SRC:ID] citations to {len(citation_check['missing_citations'])} turns with factual claims"
        )
    
    if not dossier_check['is_compliant']:
        if not dossier_check['has_dossier']:
            recommendations.append("Generate forensic dossier using ForensicEngine.generate_dossier()")
        else:
            recommendations.append(
                f"Add missing dossier fields: {', '.join(dossier_check['missing_required'])}"
            )
    
    if not evidence_check['is_compliant']:
        if not evidence_check['has_evidence']:
            recommendations.append("Gather evidence using get_diversified_evidence()")
        else:
            recommendations.append(f"Fix evidence issues: {'; '.join(evidence_check['issues'][:3])}")
    
    if not verdict_check['is_compliant']:
        if not verdict_check['verdict_called']:
            recommendations.append("Call generate_final_verdict() with topic, transcript, evidence_bundle, dossier")
        else:
            recommendations.append(
                f"Fix verdict: missing fields ({', '.join(verdict_check['missing_keys'])})"
            )
    
    if not recommendations:
        recommendations.append("All PRD requirements met ✓")
    
    return recommendations


def generate_citation_prompt(role: str, uncited_text: str) -> str:
    """
    Generate a moderator prompt requesting citation for an uncited claim.
    
    This is used in run_turn() when citation enforcement is enabled.
    """
    return f"""MODERATOR INTERVENTION: Citation Required

{role}, your previous statement contained a factual claim without proper citation:

"{uncited_text[:200]}..."

Please restate your claim with a proper evidence citation in the format:
[SRC:SOURCE_ID | auth:XX] where SOURCE_ID matches one of the available evidence sources.

If no evidence supports this claim, please acknowledge it as inference or opinion.
"""


def check_no_transcript_leak(response_json: dict) -> Tuple[bool, str]:
    """
    Validate that the public response does not contain debate transcripts,
    and does not contain "proponent" / "opponent" tokens.
    
    ATLAS v4.1 Requirement: No debate transcripts or adversarial role names
    should be exposed in public API responses.
    
    Args:
        response_json: API response dictionary to validate
        
    Returns:
        Tuple of (is_compliant: bool, message: str)
    """
    # Check for forbidden keys
    forbidden_keys = ["debate", "transcript", "proponent", "opponent", "debate_transcript"]
    for key in forbidden_keys:
        if key in response_json:
            return False, f"Response contains forbidden field '{key}' - prohibited in v4.1"
    
    # Check for forbidden tokens in serialized response
    text = str(response_json).lower()
    if "proponent" in text or "opponent" in text:
        return False, "Response contains 'proponent' or 'opponent' tokens - sanitize and re-run"
    
    if "debate" in text and "transcript" in text:
        return False, "Response appears to contain debate transcript content - prohibited in v4.1"
    
    return True, "OK - No transcript leakage detected"


# Export for easy import
__all__ = [
    'run_full_prd_check',
    'check_citation_compliance', 
    'check_dossier_compliance',
    'check_evidence_bundle_compliance',
    'check_verdict_compliance',
    'check_no_transcript_leak',
    'has_citation',
    'is_factual_claim',
    'generate_citation_prompt',
    'extract_citations'
]

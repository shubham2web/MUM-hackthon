# backend/explanation_engine.py
"""
4-Line Reasoning Summary Engine

Generates clear, readable summaries for every verdict:
1. What we found (evidence review)
2. What it means (analysis)
3. Why the confidence score is what it is
4. Why this verdict classification was chosen
"""

def build_reasoning_summary(claim, evidence, verdict, confidence):
    """
    Build a 4-line reasoning summary for verdict explanation.
    
    Args:
        claim: The original claim being verified
        evidence: List of evidence items (each with 'authority' score)
        verdict: The verdict string (VERIFIED, DEBUNKED, COMPLEX, etc.)
        confidence: Confidence percentage (0-100)
    
    Returns:
        dict with:
            - summary_4_lines: list of 4 explanation lines
            - short: 2-sentence summary
            - detailed: full 4-line explanation
    """
    # Ensure evidence is a list
    if evidence is None:
        evidence = []
    
    # 1. Evidence summary - What we found
    if len(evidence) == 0:
        line1 = "No strong evidence was found online for this claim."
    elif len(evidence) == 1:
        line1 = "Only one relevant source was found, limiting verification strength."
    elif len(evidence) <= 3:
        line1 = f"{len(evidence)} evidence sources were located and analyzed."
    else:
        line1 = f"{len(evidence)} evidence sources were located and thoroughly analyzed."

    # 2. Evidence quality - What it means
    avg_auth = 0
    if len(evidence) > 0:
        # Handle different authority field names
        auth_values = []
        for e in evidence:
            auth = e.get("authority", e.get("authority_score", e.get("score", 0)))
            if isinstance(auth, (int, float)):
                auth_values.append(auth)
        if auth_values:
            avg_auth = int(sum(auth_values) / len(auth_values))

    if avg_auth < 35:
        line2 = "The available evidence has weak credibility or unclear authority."
    elif avg_auth < 60:
        line2 = "The sources have moderate authority but lack consistent details."
    elif avg_auth < 80:
        line2 = "The sources have reasonably strong authority and consistent information."
    else:
        line2 = "The sources have high authority with strong corroborating details."

    # 3. Confidence justification - Why this confidence score
    if confidence < 40:
        line3 = "Confidence is low because information is limited or contradictory."
    elif confidence < 60:
        line3 = "Confidence is moderate due to partial or ambiguous evidence."
    elif confidence < 80:
        line3 = "Confidence is higher due to stronger and more consistent evidence."
    else:
        line3 = "Confidence is high because multiple reliable sources agree."

    # 4. Contextual verdict explanation - More intelligent and specific
    verdict_upper = (verdict or "").upper()
    if verdict_upper in ("VERIFIED", "TRUE"):
        line4 = "The evidence aligns strongly with the claim with no major contradictions detected."
    elif verdict_upper in ("DEBUNKED", "FALSE"):
        line4 = "The claim is contradicted by available evidence or lacks factual grounding."
    elif verdict_upper == "COMPLEX":
        # More nuanced COMPLEX verdict explanation
        if len(evidence) <= 1:
            line4 = "With limited sources and unclear details, the claim remains ambiguous."
        elif avg_auth < 40:
            line4 = "The claim lacks clarity due to low-authority or uncertain evidence."
        else:
            line4 = "The claim is partially supported but still contains inconsistencies."
    elif verdict_upper == "INCONCLUSIVE":
        line4 = "Insufficient evidence exists to make a definitive determination."
    else:
        line4 = "The claim requires further investigation for a conclusive verdict."

    return {
        "summary_4_lines": [line1, line2, line3, line4],
        "short": f"{line1} {line2}",
        "detailed": f"{line1}\n{line2}\n{line3}\n{line4}"
    }


def get_reasoning_for_verdict(verdict_obj, evidence_list, claim=""):
    """
    Convenience wrapper that extracts values from a verdict object.
    
    Args:
        verdict_obj: Dict with 'verdict' and 'confidence_pct' keys
        evidence_list: List of evidence items
        claim: The original claim
    
    Returns:
        Reasoning summary dict
    """
    verdict = verdict_obj.get("verdict", "COMPLEX") if isinstance(verdict_obj, dict) else str(verdict_obj)
    confidence = verdict_obj.get("confidence_pct", 50) if isinstance(verdict_obj, dict) else 50
    
    return build_reasoning_summary(
        claim=claim,
        evidence=evidence_list,
        verdict=verdict,
        confidence=confidence
    )

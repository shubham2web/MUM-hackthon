"""
Debate Helper Functions

This module contains helper functions for debate generation including:
- Stance determination
- Final verdict generation
- Evidence/transcript formatting
- Forensic dossier formatting
"""

import json
import logging
import re
from typing import Optional

from core.ai_agent import AiAgent
from core.config import ROLE_PROMPTS


def determine_debate_stances(topic: str, evidence_bundle: list) -> dict:
    """
    Analyzes the topic and evidence to provide specific stance instructions
    for Proponent and Opponent to avoid generic arguments.
    
    Args:
        topic: The debate topic
        evidence_bundle: List of evidence articles
        
    Returns:
        Dict with 'proponent_stance' and 'opponent_stance' keys
    """
    try:
        # Create a concise evidence summary
        evidence_summary = "\n".join([
            f"- {art.get('title', 'Unknown')}: {art.get('description', '')[:150]}"
            for art in evidence_bundle[:5]
        ]) if evidence_bundle else "No specific evidence available."
        
        stance_prompt = f"""Given this debate topic: "{topic}"

And this evidence:
{evidence_summary}

Provide specific, concrete stances for both sides of the debate. Avoid generic arguments.

For the PROPONENT side, identify:
- The strongest factual claims they should make
- Specific evidence types they should prioritize
- 2-3 concrete talking points

For the OPPONENT side, identify:
- The strongest counter-arguments based on the evidence
- Specific weaknesses to exploit in the proponent's likely arguments
- 2-3 concrete rebuttal points

Keep each stance to 2-3 sentences. Be specific and tactical."""

        ai_agent = AiAgent()
        response = ai_agent.call_blocking(
            user_message=stance_prompt,
            system_prompt="You are a debate strategy analyst. Provide clear, specific strategic guidance.",
            max_tokens=500
        )
        
        # Parse the response to extract stances
        response_text = response.text
        
        # Simple heuristic parsing - look for proponent and opponent sections
        proponent_stance = "Focus on evidence-based arguments that support the resolution."
        opponent_stance = "Challenge the resolution with counter-evidence and logical rebuttals."
        
        if "proponent" in response_text.lower():
            # Extract text after "proponent" keyword
            parts = response_text.lower().split("opponent")
            if len(parts) > 1:
                proponent_part = parts[0].split("proponent")[-1].strip()
                opponent_part = parts[1].strip()
                proponent_stance = proponent_part[:400] if len(proponent_part) > 0 else proponent_stance
                opponent_stance = opponent_part[:400] if len(opponent_part) > 0 else opponent_stance
        
        logging.info(f"✅ Generated debate stances for topic: {topic}")
        return {
            "proponent_stance": proponent_stance,
            "opponent_stance": opponent_stance
        }
        
    except Exception as e:
        logging.error(f"Failed to determine debate stances: {e}")
        # Return default stances if analysis fails
        return {
            "proponent_stance": "Build a strong, evidence-based argument in favor of the resolution.",
            "opponent_stance": "Challenge the resolution with counter-evidence and logical analysis."
        }


def generate_final_verdict(topic: str, transcript: str, evidence_bundle: list, dossier: Optional[dict] = None) -> dict:
    """
    Generates a final verdict by sending the debate transcript to the 'judge' role.
    Uses call_blocking (not streaming) to ensure complete JSON response.
    
    PRD Compliance:
    - Returns verdict (VERIFIED/DEBUNKED/COMPLEX)
    - Returns confidence_score (0-100)
    - Returns winning_argument
    - Returns key_evidence with authority scores
    - Returns discounted_sources (low-credibility sources that were deprioritized)
    
    Args:
        topic: The debate topic
        transcript: Full debate transcript
        evidence_bundle: List of evidence sources
        dossier: Optional forensic dossier dict
        
    Returns:
        Dict with verdict, confidence_score, winning_argument, critical_analysis, key_evidence
    """
    try:
        # Truncate transcript to last 6000 characters to avoid token limits
        truncated_transcript = transcript[-6000:] if len(transcript) > 6000 else transcript
        
        # Add marker if truncated
        if len(transcript) > 6000:
            truncated_transcript = "[Earlier content truncated for analysis]\n\n" + truncated_transcript
        
        # Create detailed evidence context with authority scores
        evidence_context = "\n\n=== EVIDENCE SOURCES WITH AUTHORITY SCORES ===\n"
        for i, art in enumerate(evidence_bundle[:10], 1):
            url = art.get('url', 'N/A')
            domain = art.get('domain', '')
            if not domain and url:
                try:
                    domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                except:
                    domain = "unknown"
            
            # Calculate authority score
            if any(t in domain.lower() for t in ['reuters', 'ap', '.gov', '.edu']):
                auth_score = 85
            elif any(t in domain.lower() for t in ['bbc', 'nytimes', 'theguardian', 'washingtonpost', 'timesofindia']):
                auth_score = 75
            elif any(t in domain.lower() for t in ['medium', 'substack', 'blog']):
                auth_score = 45
            else:
                auth_score = 55
            
            source_id = f"{domain.split('.')[0].upper()[:3]}-{i:03d}"
            evidence_context += f"[SRC:{source_id} | auth:{auth_score}] {art.get('title', 'Unknown')[:60]} - {domain}\n"
        
        # Add dossier summary if available
        dossier_context = ""
        if dossier:
            dossier_context = f"""

=== FORENSIC DOSSIER SUMMARY ===
Overall Credibility: {dossier.get('credibility', 'N/A')}/100
Red Flags: {len(dossier.get('red_flags', []))}
Authority Score: {dossier.get('authority_score', 'N/A')}/100
"""
        
        judge_input = f"""DEBATE TOPIC: {topic}

{truncated_transcript}
{evidence_context}
{dossier_context}

VERDICT REQUIREMENTS:
1. Assess which debater made better use of CITED evidence
2. Discount arguments that lacked proper [SRC:ID] citations
3. Weight high-authority sources (auth:70+) more heavily
4. Note any discounted sources (low authority or red-flagged)

Render your final verdict now in the required JSON format."""
        
        # Use call_blocking to get complete response
        ai_agent = AiAgent()
        judge_prompt = ROLE_PROMPTS.get("judge", "You are a fact-checking judge. Provide a verdict in JSON format.")
        
        logging.info("🔍 Generating final verdict from judge...")
        response = ai_agent.call_blocking(
            user_message=judge_input,
            system_prompt=judge_prompt,
            max_tokens=1000
        )
        
        response_text = response.text.strip()
        logging.info(f"Judge raw response: {response_text[:200]}...")
        
        # Extract JSON using regex (handles cases where model adds extra text)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(0)
            verdict_data = json.loads(json_str)
            
            # Validate required fields
            required_fields = ["verdict", "confidence_score", "winning_argument", "critical_analysis", "key_evidence"]
            if all(field in verdict_data for field in required_fields):
                logging.info(f"✅ Final verdict generated: {verdict_data.get('verdict')} (confidence: {verdict_data.get('confidence_score')}%)")
                return verdict_data
            else:
                logging.error(f"Missing required fields in verdict JSON: {verdict_data.keys()}")
                raise ValueError("Incomplete verdict data")
        else:
            logging.error(f"No JSON found in judge response: {response_text}")
            raise ValueError("Could not extract JSON from judge response")
            
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse judge verdict JSON: {e}")
        return {
            "verdict": "COMPLEX",
            "confidence_score": 0,
            "winning_argument": "Unable to determine due to parsing error",
            "critical_analysis": "The verdict system encountered a technical error processing the debate.",
            "key_evidence": []
        }
    except Exception as e:
        logging.error(f"Error generating final verdict: {e}", exc_info=True)
        return {
            "verdict": "COMPLEX",
            "confidence_score": 0,
            "winning_argument": "Unable to determine due to system error",
            "critical_analysis": f"An error occurred during verdict generation: {str(e)}",
            "key_evidence": []
        }


def get_recent_transcript(transcript: str, max_chars: int = 3000) -> str:
    """
    Keep only the most recent portion of the transcript to avoid payload size issues.
    
    Args:
        transcript: Full debate transcript
        max_chars: Maximum characters to keep
        
    Returns:
        Truncated transcript string
    """
    if len(transcript) <= max_chars:
        return transcript
    
    # Keep the last max_chars characters
    truncated = transcript[-max_chars:]
    
    # Find the first complete section marker to avoid cutting mid-sentence
    markers = ["---", "Debate ID:", "Topic:"]
    for marker in markers:
        pos = truncated.find(marker)
        if pos > 0 and pos < 500:  # If we find a marker near the start
            return "...[earlier debate content truncated]...\n\n" + truncated[pos:]
    
    return "...[earlier debate content truncated]...\n\n" + truncated


def format_evidence_bundle(evidence_bundle: list, forensic_engine=None) -> str:
    """
    Format evidence bundle with source IDs, authority scores, and metadata.
    This creates a structured evidence reference for debaters to cite.
    
    Args:
        evidence_bundle: List of evidence source dicts
        forensic_engine: Optional forensic engine for authority scoring
        
    Returns:
        Formatted string like:
        [SRC:TOI-001 | auth:75] Times of India: "Article title..." (2025-11-29)
    """
    if not evidence_bundle:
        return "[NO EVIDENCE AVAILABLE]"
    
    formatted_sources = []
    
    for idx, source in enumerate(evidence_bundle[:10]):
        url = source.get('url', '')
        domain = source.get('domain', '')
        
        # Extract domain if not present
        if not domain and url:
            try:
                domain = url.split("//")[-1].split("/")[0].replace("www.", "")
            except:
                domain = "unknown"
        
        # Generate source ID (short hash)
        source_id = f"{domain.split('.')[0].upper()[:3]}-{idx+1:03d}"
        
        # Calculate authority score
        authority_score = 50  # Default
        if forensic_engine:
            try:
                tier = forensic_engine.get_domain_tier(url)
                authority_score = {
                    'tier_1': 85,
                    'tier_2': 70,
                    'tier_3': 45,
                    'tier_4': 25
                }.get(tier.value, 50)
            except:
                pass
        else:
            # Simple domain-based scoring
            if any(t in domain.lower() for t in ['reuters', 'ap', '.gov', '.edu']):
                authority_score = 85
            elif any(t in domain.lower() for t in ['bbc', 'nytimes', 'theguardian', 'washingtonpost', 'timesofindia']):
                authority_score = 75
            elif any(t in domain.lower() for t in ['medium', 'substack', 'blog']):
                authority_score = 45
        
        # Get title and snippet
        title = source.get('title', 'Untitled') or 'Untitled'
        title = title[:80] if title else 'Untitled'
        text_snippet = (source.get('text', '') or '')[:150].replace('\n', ' ').strip()
        
        # Handle date - can be None
        published_raw = source.get('published_at') or source.get('fetched_at') or 'Unknown date'
        published = published_raw[:10] if isinstance(published_raw, str) else 'Unknown date'
        
        formatted_sources.append(
            f"[SRC:{source_id} | auth:{authority_score}] {domain}: \"{title}\" ({published})\n"
            f"   Summary: {text_snippet}..."
        )
    
    return "\n\n".join(formatted_sources)


def format_forensic_dossier(dossier) -> str:
    """
    Format forensic dossier for injection into debate context.
    
    Args:
        dossier: Forensic dossier object or dict
        
    Returns:
        Formatted dossier string
    """
    if not dossier:
        return "[NO FORENSIC DOSSIER AVAILABLE]"
    
    try:
        dossier_dict = dossier.to_dict() if hasattr(dossier, 'to_dict') else dossier
        
        sections = [
            "=== FORENSIC INTELLIGENCE BRIEFING ===",
            f"Primary Entity: {dossier_dict.get('entity', 'Unknown')}",
            f"Entity Type: {dossier_dict.get('entity_type', 'unknown')}",
            f"Credibility Score: {dossier_dict.get('credibility', 'N/A')}/100",
            f"Authority Score: {dossier_dict.get('authority_score', 'N/A')}/100",
            "",
            "RED FLAGS DETECTED:"
        ]
        
        red_flags = dossier_dict.get('red_flags', [])
        if red_flags:
            for rf in red_flags[:5]:
                sections.append(f"  ⚠ [{rf.get('severity', 'unknown').upper()}] {rf.get('description', 'No description')}")
        else:
            sections.append("  ✓ No critical red flags detected")
        
        sections.append("")
        sections.append("SOURCE HISTORY:")
        history = dossier_dict.get('history', [])
        for h in history[:5]:
            sections.append(f"  • {h.get('source', 'Unknown')}: {h.get('title', 'No title')[:50]}...")
        
        sections.append("")
        sections.append(f"SUMMARY: {dossier_dict.get('summary', 'No summary available')[:300]}")
        sections.append("=== END FORENSIC BRIEFING ===")
        
        return "\n".join(sections)
    except Exception as e:
        logging.warning(f"Failed to format forensic dossier: {e}")
        return "[FORENSIC DOSSIER FORMAT ERROR]"

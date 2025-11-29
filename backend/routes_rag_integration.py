# backend/routes_rag_integration.py
"""
RAG Integration Routes for ATLAS v4.1.3

Provides /rag/analyze and /rag/debate endpoints that integrate:
- Web scraping via pro_scraper
- RAG adapter for evidence processing
- Deterministic verdict engine
- LLM evidence-constrained reply generation
- Safe background reasoning reports (PRD-compliant)

These routes are designed to work alongside existing /analyze routes.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional

from quart import Blueprint, request, jsonify

# Import background report generator
try:
    from background_report import make_background_report, TimingTracker, extract_agent_summary
    BACKGROUND_REPORT_AVAILABLE = True
except ImportError:
    BACKGROUND_REPORT_AVAILABLE = False
    logging.warning("Background report module not available")

# Import scraper
try:
    from services.pro_scraper import get_diversified_evidence
    SCRAPER_AVAILABLE = True
except ImportError as e:
    SCRAPER_AVAILABLE = False
    logging.warning(f"Pro scraper not available: {e}")

# Import RAG adapter
try:
    from rag.adapter import process_scraper_results, build_evidence_prompt
    RAG_ADAPTER_AVAILABLE = True
except ImportError as e:
    RAG_ADAPTER_AVAILABLE = False
    process_scraper_results = None
    logging.warning(f"RAG adapter not available: {e}")

# Import verdict engine
try:
    from verdict_engine import decide_verdict, classify_verdict, build_key_evidence
    VERDICT_ENGINE_AVAILABLE = True
except ImportError:
    try:
        from backend.verdict_engine import decide_verdict, classify_verdict, build_key_evidence
        VERDICT_ENGINE_AVAILABLE = True
    except ImportError as e:
        VERDICT_ENGINE_AVAILABLE = False
        decide_verdict = None
        classify_verdict = None
        build_key_evidence = None
        logging.warning(f"Verdict engine not available: {e}")

# Import LLM helper
try:
    from llm import llm_generate_evidence_based_reply
    LLM_HELPER_AVAILABLE = True
except ImportError as e:
    LLM_HELPER_AVAILABLE = False
    logging.warning(f"LLM helper not available: {e}")

# Import agents for debate
try:
    from core.ai_agent import AiAgent
    AGENTS_AVAILABLE = True
except ImportError:
    AGENTS_AVAILABLE = False

# Import NLP explanation generator
try:
    from utils.explanation import generate_nlp_explanation, generate_simple_explanation
    NLP_EXPLANATION_AVAILABLE = True
except ImportError:
    try:
        from backend.utils.explanation import generate_nlp_explanation, generate_simple_explanation
        NLP_EXPLANATION_AVAILABLE = True
    except ImportError:
        NLP_EXPLANATION_AVAILABLE = False
        logging.warning("NLP explanation module not available")

# Import 4-line reasoning summary engine
try:
    from explanation_engine import build_reasoning_summary, get_reasoning_for_verdict
    REASONING_ENGINE_AVAILABLE = True
except ImportError:
    try:
        from backend.explanation_engine import build_reasoning_summary, get_reasoning_for_verdict
        REASONING_ENGINE_AVAILABLE = True
    except ImportError:
        REASONING_ENGINE_AVAILABLE = False
        logging.warning("Reasoning engine not available")

logger = logging.getLogger(__name__)

# Create blueprint
rag_bp = Blueprint('rag', __name__, url_prefix='/rag')


async def scrape_for_query(query: str, num_results: int = 10) -> List[Dict]:
    """
    Scrape web for evidence related to query.
    Returns list of {url, domain, text, score, snippet} dicts.
    """
    if not SCRAPER_AVAILABLE:
        logger.warning("Scraper not available, returning empty evidence")
        return []
    
    try:
        evidence = await asyncio.wait_for(
            get_diversified_evidence(query, num_results=num_results),
            timeout=60.0
        )
        return evidence or []
    except asyncio.TimeoutError:
        logger.warning("Evidence scraping timed out")
        return []
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return []


def run_agent_proponent(claim: str, evidence_bundle: List[Dict]) -> Dict:
    """Run proponent agent that argues FOR the claim with thinking trace."""
    if not AGENTS_AVAILABLE:
        return {"role": "proponent", "arguments": [], "summary": "Agent unavailable", "thinking": ""}
    
    try:
        agent = AiAgent()
        
        evidence_text = "\n".join([
            f"[{i+1}] {ev.get('domain', '')}: {ev.get('snippet', ev.get('text', '')[:200])}"
            for i, ev in enumerate(evidence_bundle[:5])
        ])
        
        system_prompt = (
            "You are a proponent arguing that the claim is TRUE. "
            "Use ONLY the provided evidence to support your arguments. "
            "Cite evidence by number like [1], [2]."
        )
        
        # Enhanced prompt to capture thinking
        user_message = f"""Claim: {claim}

Evidence:
{evidence_text}

First, in <thinking> tags, explain your step-by-step reasoning process:
- What evidence is most relevant?
- How does each piece connect to the claim?
- What's the strongest argument strategy?

Then provide 2-3 concise arguments supporting this claim using the evidence.

Format:
<thinking>
[Your reasoning process here]
</thinking>

Arguments:
[Your arguments here with citations]"""
        
        response = agent.call_blocking(user_message=user_message, system_prompt=system_prompt, max_tokens=1024)
        response_text = response.text if response else ""
        
        # Parse thinking from response
        thinking = ""
        arguments = response_text
        if response_text and "<thinking>" in response_text and "</thinking>" in response_text:
            start = response_text.find("<thinking>") + len("<thinking>")
            end = response_text.find("</thinking>")
            thinking = response_text[start:end].strip()
            # Get arguments part (after </thinking>)
            arguments = response_text[end + len("</thinking>"):].strip()
            # Remove "Arguments:" prefix if present
            if arguments.lower().startswith("arguments:"):
                arguments = arguments[len("arguments:"):].strip()
        
        return {
            "role": "proponent",
            "arguments": [arguments] if arguments else [],
            "summary": arguments[:200] if arguments else "No arguments generated",
            "thinking": thinking
        }
    except Exception as e:
        logger.error(f"Proponent agent failed: {e}")
        return {"role": "proponent", "arguments": [], "summary": f"Error: {e}", "thinking": ""}


def run_agent_opponent(claim: str, evidence_bundle: List[Dict]) -> Dict:
    """Run opponent agent that argues AGAINST the claim with thinking trace."""
    if not AGENTS_AVAILABLE:
        return {"role": "opponent", "arguments": [], "summary": "Agent unavailable", "thinking": ""}
    
    try:
        agent = AiAgent()
        
        evidence_text = "\n".join([
            f"[{i+1}] {ev.get('domain', '')}: {ev.get('snippet', ev.get('text', '')[:200])}"
            for i, ev in enumerate(evidence_bundle[:5])
        ])
        
        system_prompt = (
            "You are an opponent arguing that the claim is FALSE or MISLEADING. "
            "Use ONLY the provided evidence to support your counter-arguments. "
            "Cite evidence by number like [1], [2]."
        )
        
        # Enhanced prompt to capture thinking
        user_message = f"""Claim: {claim}

Evidence:
{evidence_text}

First, in <thinking> tags, explain your step-by-step reasoning process:
- What evidence contradicts the claim?
- What weaknesses or gaps exist?
- What's the strongest counter-argument strategy?

Then provide 2-3 concise arguments against this claim using the evidence.

Format:
<thinking>
[Your reasoning process here]
</thinking>

Arguments:
[Your arguments here with citations]"""
        
        response = agent.call_blocking(user_message=user_message, system_prompt=system_prompt, max_tokens=1024)
        response_text = response.text if response else ""
        
        # Parse thinking from response
        thinking = ""
        arguments = response_text
        if response_text and "<thinking>" in response_text and "</thinking>" in response_text:
            start = response_text.find("<thinking>") + len("<thinking>")
            end = response_text.find("</thinking>")
            thinking = response_text[start:end].strip()
            # Get arguments part (after </thinking>)
            arguments = response_text[end + len("</thinking>"):].strip()
            # Remove "Arguments:" prefix if present
            if arguments.lower().startswith("arguments:"):
                arguments = arguments[len("arguments:"):].strip()
        
        return {
            "role": "opponent",
            "arguments": [arguments] if arguments else [],
            "summary": arguments[:200] if arguments else "No arguments generated",
            "thinking": thinking
        }
    except Exception as e:
        logger.error(f"Opponent agent failed: {e}")
        return {"role": "opponent", "arguments": [], "summary": f"Error: {e}", "thinking": ""}


@rag_bp.route("/analyze", methods=["POST"])
async def analyze():
    """
    RAG-powered analysis endpoint.
    
    Request body:
        {"query": "claim text"} or {"text": "claim text"}
    
    Response:
        {
            "assistant": "Evidence-constrained reply with [1], [2] citations",
            "analysis": {...verdict engine output...},
            "evidence": [...evidence bundle...]
        }
    """
    try:
        payload = await request.json or {}
        claim = payload.get("query") or payload.get("text") or ""
        
        if not claim:
            return jsonify({"error": "no query provided"}), 400
        
        logger.info(f"RAG analyze: {claim[:100]}...")
        
        # 1) Get candidate evidence via scraper
        scraped = await scrape_for_query(claim)
        logger.info(f"Scraped {len(scraped)} evidence items")
        
        # 2) Process through RAG adapter (normalize, dedupe, summarize)
        if RAG_ADAPTER_AVAILABLE and process_scraper_results:
            evidence_bundle = process_scraper_results(scraped)
        else:
            evidence_bundle = scraped
        logger.info(f"Evidence bundle: {len(evidence_bundle)} items after processing")
        
        # 3) Run deterministic verdict engine
        analysis = {}
        if VERDICT_ENGINE_AVAILABLE and decide_verdict:
            try:
                analysis = decide_verdict(
                    claim=claim,
                    evidence_bundle=evidence_bundle,
                    bias_report=None,
                    forensic_dossier=None
                )
            except Exception as e:
                logger.error(f"Verdict engine error: {e}")
                analysis = {
                    "verdict": "INCONCLUSIVE",
                    "confidence_pct": 50,
                    "summary": "Unable to determine verdict"
                }
        else:
            analysis = {
                "verdict": "INCONCLUSIVE",
                "confidence_pct": 50,
                "summary": "Verdict engine not available"
            }
        
        # 4) Generate evidence-constrained assistant reply
        if LLM_HELPER_AVAILABLE:
            assistant = llm_generate_evidence_based_reply(claim, evidence_bundle, analysis)
        else:
            # Fallback template
            if evidence_bundle:
                citations = ', '.join([f"[{i+1}]" for i in range(min(3, len(evidence_bundle)))])
                assistant = f"Based on available evidence ({citations}), the claim requires further verification. Recommendation: Check authoritative sources."
            else:
                assistant = "Inconclusive based on available sources."
        
        # 5) Generate NLP explanation
        nlp_explanation = None
        if NLP_EXPLANATION_AVAILABLE:
            try:
                nlp_explanation = generate_simple_explanation(analysis, len(evidence_bundle))
            except Exception as e:
                logger.error(f"NLP explanation generation failed: {e}")
        
        return jsonify({
            "assistant": assistant,
            "analysis": analysis,
            "evidence": evidence_bundle,
            "nlp_explanation": nlp_explanation
        })
        
    except Exception as e:
        logger.error(f"RAG analyze error: {e}")
        return jsonify({"error": str(e)}), 500


@rag_bp.route("/debate", methods=["POST"])
async def debate():
    """
    RAG-powered debate endpoint with pro/opponent agents, process trace, and background report.
    
    Request body:
        {"claim": "claim text"}
    
    Response:
        {
            "trace": [...process steps for thinking animation...],
            "pro": {...proponent output...},
            "opp": {...opponent output...},
            "verdict": {...verdict engine output...},
            "evidence": [...evidence bundle...],
            "background": {...safe background reasoning report...}
        }
    """
    try:
        payload = await request.json or {}
        claim = payload.get("claim") or payload.get("query") or payload.get("text") or ""
        
        if not claim:
            return jsonify({"error": "no claim provided"}), 400
        
        logger.info(f"RAG debate: {claim[:100]}...")
        
        # Initialize timing tracker for background report
        timing = {}
        
        # Process trace for "thinking" visualization (high-level steps only, PRD-safe)
        process_trace = [
            {"step": "scraping", "message": "🔍 Collecting relevant sources and evidence..."},
            {"step": "evaluating_evidence", "message": "📊 Evaluating credibility and summarizing evidence..."},
            {"step": "constructing_pro", "message": "✅ Constructing the proponent's argument from evidence..."},
            {"step": "constructing_opp", "message": "❌ Constructing the opponent's argument from evidence..."},
            {"step": "finalizing", "message": "⚖️ Comparing arguments and computing neutral verdict..."}
        ]
        
        # 1) Gather evidence with timing
        t0 = time.time()
        scraped = await scrape_for_query(claim)
        timing["scraping"] = {"msg": f"fetched {len(scraped)} sources", "ms": int((time.time() - t0) * 1000)}
        
        # 2) Process through RAG adapter with timing
        t0 = time.time()
        if RAG_ADAPTER_AVAILABLE and process_scraper_results:
            evidence_bundle = process_scraper_results(scraped)
        else:
            evidence_bundle = scraped
        timing["normalize"] = {"msg": f"processed {len(evidence_bundle)} evidence items", "ms": int((time.time() - t0) * 1000)}
        
        # 3) Run debate agents with timing
        t0 = time.time()
        pro = run_agent_proponent(claim, evidence_bundle)
        timing["proponent"] = {"msg": "constructed proponent arguments", "ms": int((time.time() - t0) * 1000)}
        
        t0 = time.time()
        opp = run_agent_opponent(claim, evidence_bundle)
        timing["opponent"] = {"msg": "constructed opponent arguments", "ms": int((time.time() - t0) * 1000)}
        
        # 4) Run verdict engine with agent outputs and timing
        t0 = time.time()
        verdict = {}
        if VERDICT_ENGINE_AVAILABLE and decide_verdict:
            try:
                verdict = decide_verdict(
                    claims=[claim],  # claims is a list
                    evidence_bundle=evidence_bundle,
                    bias_report=None,
                    forensic_dossier=None
                )
                # Add agent summaries to verdict
                verdict["pro_summary"] = pro.get("summary", "")
                verdict["opp_summary"] = opp.get("summary", "")
            except Exception as e:
                logger.error(f"Verdict engine error in debate: {e}")
                verdict = {
                    "verdict": "INCONCLUSIVE",
                    "confidence_pct": 50,
                    "summary": "Unable to determine verdict"
                }
        else:
            verdict = {
                "verdict": "INCONCLUSIVE",
                "confidence_pct": 50,
                "summary": "Verdict engine not available"
            }
        timing["verdict"] = {"msg": f"computed verdict: {verdict.get('verdict', 'UNKNOWN')}", "ms": int((time.time() - t0) * 1000)}
        
        # 5) Generate safe background report (PRD-compliant, no chain-of-thought)
        background = None
        if BACKGROUND_REPORT_AVAILABLE:
            try:
                # Build agent outputs for background report
                agents_outputs = {
                    "proponent": {
                        "summary": pro.get("summary", ""),
                        "claims": pro.get("arguments", pro.get("points", [])),
                        "used_evidence": [f"e{i+1}" for i in range(min(3, len(evidence_bundle)))]
                    },
                    "opponent": {
                        "summary": opp.get("summary", ""),
                        "claims": opp.get("arguments", opp.get("points", [])),
                        "used_evidence": [f"e{i+1}" for i in range(min(3, len(evidence_bundle)))]
                    }
                }
                
                # Score values from verdict
                score_values = {
                    "combined_confidence": verdict.get("confidence_pct", 50) / 100.0
                }
                
                background = make_background_report(
                    claim=claim,
                    evidence_bundle=evidence_bundle,
                    agents_outputs=agents_outputs,
                    timing_stats=timing,
                    score_values=score_values
                )
            except Exception as e:
                logger.error(f"Background report generation failed: {e}")
                background = None
        
        # 6) Generate NLP explanation from structured data
        nlp_explanation = None
        if NLP_EXPLANATION_AVAILABLE:
            try:
                nlp_explanation = generate_nlp_explanation(claim, verdict, background)
            except Exception as e:
                logger.error(f"NLP explanation generation failed: {e}")
                # Fallback to simple explanation
                try:
                    nlp_explanation = generate_simple_explanation(verdict, len(evidence_bundle))
                except:
                    pass
        
        # 7) Generate 4-line reasoning summary
        explanation = None
        if REASONING_ENGINE_AVAILABLE:
            try:
                confidence_pct = verdict.get("confidence_pct", 50) if isinstance(verdict, dict) else 50
                verdict_str = verdict.get("verdict", "COMPLEX") if isinstance(verdict, dict) else str(verdict)
                explanation = build_reasoning_summary(
                    claim=claim,
                    evidence=evidence_bundle,
                    verdict=verdict_str,
                    confidence=confidence_pct
                )
            except Exception as e:
                logger.error(f"Reasoning summary generation failed: {e}")
        
        return jsonify({
            "trace": process_trace,
            "pro": pro,
            "opp": opp,
            "verdict": verdict,
            "evidence": evidence_bundle,
            "background": background,
            "nlp_explanation": nlp_explanation,
            "explanation": explanation
        })
        
    except Exception as e:
        logger.error(f"RAG debate error: {e}")
        return jsonify({"error": str(e)}), 500


@rag_bp.route("/health", methods=["GET"])
async def health():
    """Health check for RAG integration."""
    return jsonify({
        "status": "ok",
        "scraper_available": SCRAPER_AVAILABLE,
        "rag_adapter_available": RAG_ADAPTER_AVAILABLE,
        "verdict_engine_available": VERDICT_ENGINE_AVAILABLE,
        "llm_helper_available": LLM_HELPER_AVAILABLE,
        "agents_available": AGENTS_AVAILABLE
    })

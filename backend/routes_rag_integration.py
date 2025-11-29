# backend/routes_rag_integration.py
"""
RAG Integration Routes for ATLAS v4.1.3

Provides /rag/analyze and /rag/debate endpoints that integrate:
- Web scraping via pro_scraper
- RAG adapter for evidence processing
- Deterministic verdict engine
- LLM evidence-constrained reply generation

These routes are designed to work alongside existing /analyze routes.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Any, Optional

from quart import Blueprint, request, jsonify

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

logger = logging.getLogger(__name__)

# Create blueprint
rag_bp = Blueprint('rag', __name__, url_prefix='/rag')


async def scrape_for_query(query: str, max_results: int = 10) -> List[Dict]:
    """
    Scrape web for evidence related to query.
    Returns list of {url, domain, text, score, snippet} dicts.
    """
    if not SCRAPER_AVAILABLE:
        logger.warning("Scraper not available, returning empty evidence")
        return []
    
    try:
        evidence = await asyncio.wait_for(
            get_diversified_evidence(query, max_results=max_results),
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
    """Run proponent agent that argues FOR the claim."""
    if not AGENTS_AVAILABLE:
        return {"role": "proponent", "arguments": [], "summary": "Agent unavailable"}
    
    try:
        agent = AiAgent(
            name="Proponent",
            role_prompt=(
                "You are a proponent arguing that the claim is TRUE. "
                "Use ONLY the provided evidence to support your arguments. "
                "Cite evidence by number like [1], [2]."
            ),
            provider="groq"
        )
        
        evidence_text = "\n".join([
            f"[{i+1}] {ev.get('domain', '')}: {ev.get('snippet', ev.get('text', '')[:200])}"
            for i, ev in enumerate(evidence_bundle[:5])
        ])
        
        prompt = f"Claim: {claim}\n\nEvidence:\n{evidence_text}\n\nProvide 2-3 concise arguments supporting this claim using the evidence."
        
        response = agent.generate_response_sync(prompt, temperature=0.1)
        
        return {
            "role": "proponent",
            "arguments": [response] if response else [],
            "summary": response[:200] if response else "No arguments generated"
        }
    except Exception as e:
        logger.error(f"Proponent agent failed: {e}")
        return {"role": "proponent", "arguments": [], "summary": f"Error: {e}"}


def run_agent_opponent(claim: str, evidence_bundle: List[Dict]) -> Dict:
    """Run opponent agent that argues AGAINST the claim."""
    if not AGENTS_AVAILABLE:
        return {"role": "opponent", "arguments": [], "summary": "Agent unavailable"}
    
    try:
        agent = AiAgent(
            name="Opponent",
            role_prompt=(
                "You are an opponent arguing that the claim is FALSE or MISLEADING. "
                "Use ONLY the provided evidence to support your counter-arguments. "
                "Cite evidence by number like [1], [2]."
            ),
            provider="groq"
        )
        
        evidence_text = "\n".join([
            f"[{i+1}] {ev.get('domain', '')}: {ev.get('snippet', ev.get('text', '')[:200])}"
            for i, ev in enumerate(evidence_bundle[:5])
        ])
        
        prompt = f"Claim: {claim}\n\nEvidence:\n{evidence_text}\n\nProvide 2-3 concise arguments against this claim using the evidence."
        
        response = agent.generate_response_sync(prompt, temperature=0.1)
        
        return {
            "role": "opponent",
            "arguments": [response] if response else [],
            "summary": response[:200] if response else "No arguments generated"
        }
    except Exception as e:
        logger.error(f"Opponent agent failed: {e}")
        return {"role": "opponent", "arguments": [], "summary": f"Error: {e}"}


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
        
        return jsonify({
            "assistant": assistant,
            "analysis": analysis,
            "evidence": evidence_bundle
        })
        
    except Exception as e:
        logger.error(f"RAG analyze error: {e}")
        return jsonify({"error": str(e)}), 500


@rag_bp.route("/debate", methods=["POST"])
async def debate():
    """
    RAG-powered debate endpoint with pro/opponent agents.
    
    Request body:
        {"claim": "claim text"}
    
    Response:
        {
            "pro": {...proponent output...},
            "opp": {...opponent output...},
            "verdict": {...verdict engine output...},
            "evidence": [...evidence bundle...]
        }
    """
    try:
        payload = await request.json or {}
        claim = payload.get("claim") or payload.get("query") or payload.get("text") or ""
        
        if not claim:
            return jsonify({"error": "no claim provided"}), 400
        
        logger.info(f"RAG debate: {claim[:100]}...")
        
        # 1) Gather evidence
        scraped = await scrape_for_query(claim)
        
        # 2) Process through RAG adapter
        if RAG_ADAPTER_AVAILABLE and process_scraper_results:
            evidence_bundle = process_scraper_results(scraped)
        else:
            evidence_bundle = scraped
        
        # 3) Run debate agents
        pro = run_agent_proponent(claim, evidence_bundle)
        opp = run_agent_opponent(claim, evidence_bundle)
        
        # 4) Run verdict engine with agent outputs
        verdict = {}
        if VERDICT_ENGINE_AVAILABLE and decide_verdict:
            try:
                verdict = decide_verdict(
                    claim=claim,
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
        
        return jsonify({
            "pro": pro,
            "opp": opp,
            "verdict": verdict,
            "evidence": evidence_bundle
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

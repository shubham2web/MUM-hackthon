"""
ATLAS v4.0 Full Analysis Pipeline API

This module implements the complete analysis endpoint as per PRD:
RAG → Web Scraper → OCR → Credibility → Forensic → Debate → Verdict

Routes:
- /analyze: Full pipeline analysis
- /analyze/quick: Quick analysis (no debate)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from quart import Blueprint, request, jsonify, Response

# Core imports
from core.ai_agent import AiAgent
from core.config import DEFAULT_MODEL, ROLE_PROMPTS
from core.utils import compute_advanced_analytics, format_sse
from services.pro_scraper import get_diversified_evidence

# V2 Features
try:
    from v2_features.forensic_engine import get_forensic_engine, ForensicEngine
    from v2_features.credibility_engine import CredibilityEngine, Source
    from v2_features.bias_auditor import BiasAuditor
    from v2_features.role_library import RoleLibrary
    V2_FEATURES_AVAILABLE = True
except ImportError as e:
    V2_FEATURES_AVAILABLE = False
    logging.warning(f"⚠️ V2 Features not fully available: {e}")

# Memory system
try:
    from memory.memory_manager import get_memory_manager
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# Create blueprint
analyze_bp = Blueprint('analyze', __name__, url_prefix='/analyze')

# Logger
logger = logging.getLogger(__name__)


class ATLASAnalysisPipeline:
    """
    Complete ATLAS v4.0 Analysis Pipeline.
    
    Pipeline Flow (per PRD Section 3):
    1. RAG Retrieval
    2. Web Scraping
    3. OCR (if applicable)
    4. Credibility Scoring
    5. Forensic Analysis
    6. Debate Generation
    7. Verdict Generation
    """
    
    def __init__(self):
        self.ai_agent = AiAgent()
        self.forensic_engine = get_forensic_engine() if V2_FEATURES_AVAILABLE else None
        self.credibility_engine = CredibilityEngine() if V2_FEATURES_AVAILABLE else None
        self.bias_auditor = BiasAuditor() if V2_FEATURES_AVAILABLE else None
        self.role_library = RoleLibrary() if V2_FEATURES_AVAILABLE else None
        self.memory = get_memory_manager() if MEMORY_AVAILABLE else None
        
        logger.info(f"✅ ATLAS Pipeline initialized (v2_features={V2_FEATURES_AVAILABLE}, memory={MEMORY_AVAILABLE})")
    
    async def run_full_analysis(
        self,
        query: str,
        enable_debate: bool = True,
        enable_forensics: bool = True,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the complete analysis pipeline.
        
        Args:
            query: The claim/topic to analyze
            enable_debate: Whether to run full debate
            enable_forensics: Whether to run forensic analysis
            session_id: Optional session ID for memory
            
        Returns:
            Complete analysis result dictionary
        """
        analysis_id = str(uuid.uuid4())
        start_time = time.time()
        
        result = {
            "analysis_id": analysis_id,
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "pipeline_stages": {},
            "final_verdict": None,
            "metadata": {
                "model_used": DEFAULT_MODEL,
                "v2_features_enabled": V2_FEATURES_AVAILABLE,
                "memory_enabled": MEMORY_AVAILABLE
            }
        }
        
        # Setup memory if available
        if self.memory and session_id:
            self.memory.set_debate_context(session_id)
        
        try:
            # ============================================
            # STAGE 1: RAG + Web Evidence Gathering
            # ============================================
            logger.info(f"📚 Stage 1: Gathering evidence for: {query[:100]}...")
            rag_start = time.time()
            
            evidence_bundle = await self._gather_evidence(query)
            
            result["pipeline_stages"]["rag_retrieval"] = {
                "status": "completed",
                "duration_ms": round((time.time() - rag_start) * 1000),
                "sources_found": len(evidence_bundle),
                "sources": [
                    {
                        "title": e.get("title", "Unknown"),
                        "url": e.get("url", ""),
                        "domain": e.get("domain", "")
                    } for e in evidence_bundle[:10]
                ]
            }
            
            # ============================================
            # STAGE 2: Credibility Scoring
            # ============================================
            logger.info("🔍 Stage 2: Running credibility analysis...")
            cred_start = time.time()
            
            credibility_result = self._run_credibility_analysis(query, evidence_bundle)
            
            result["pipeline_stages"]["credibility"] = {
                "status": "completed",
                "duration_ms": round((time.time() - cred_start) * 1000),
                **credibility_result
            }
            
            # ============================================
            # STAGE 3: Forensic Analysis
            # ============================================
            if enable_forensics and self.forensic_engine:
                logger.info("🔬 Stage 3: Running forensic analysis...")
                forensic_start = time.time()
                
                forensic_result = self.forensic_engine.analyze_claim(query, evidence_bundle)
                
                result["pipeline_stages"]["forensics"] = {
                    "status": "completed",
                    "duration_ms": round((time.time() - forensic_start) * 1000),
                    **forensic_result
                }
            else:
                result["pipeline_stages"]["forensics"] = {"status": "skipped"}
            
            # ============================================
            # STAGE 4: Build Evidence Bundle (PRD Format)
            # ============================================
            evidence_bundle_formatted = self._format_evidence_bundle(
                evidence_bundle,
                credibility_result,
                forensic_result if enable_forensics else None
            )
            
            result["evidence_bundle"] = evidence_bundle_formatted
            
            # ============================================
            # STAGE 5: Debate (if enabled)
            # ============================================
            if enable_debate:
                logger.info("⚔️ Stage 5: Running adversarial debate...")
                debate_start = time.time()
                
                debate_result = await self._run_debate(
                    query,
                    evidence_bundle,
                    forensic_result.get("dossier") if enable_forensics else None
                )
                
                result["pipeline_stages"]["debate"] = {
                    "status": "completed",
                    "duration_ms": round((time.time() - debate_start) * 1000),
                    "rounds": debate_result.get("rounds", 0),
                    "transcript_length": len(debate_result.get("transcript", ""))
                }
                result["debate_transcript"] = debate_result.get("transcript", "")
            else:
                result["pipeline_stages"]["debate"] = {"status": "skipped"}
                debate_result = {"transcript": ""}
            
            # ============================================
            # STAGE 6: Final Verdict
            # ============================================
            logger.info("⚖️ Stage 6: Generating final verdict...")
            verdict_start = time.time()
            
            final_verdict = await self._generate_verdict(
                query,
                evidence_bundle,
                debate_result.get("transcript", ""),
                credibility_result,
                forensic_result if enable_forensics else None
            )
            
            result["pipeline_stages"]["verdict"] = {
                "status": "completed",
                "duration_ms": round((time.time() - verdict_start) * 1000)
            }
            result["final_verdict"] = final_verdict
            
            # ============================================
            # STAGE 7: Bias Audit (Post-Analysis)
            # ============================================
            if self.bias_auditor and enable_debate:
                logger.info("🎭 Stage 7: Running bias audit...")
                bias_result = self._run_bias_audit(debate_result.get("transcript", ""))
                result["pipeline_stages"]["bias_audit"] = {
                    "status": "completed",
                    **bias_result
                }
            
            # Final metadata
            result["metadata"]["total_duration_ms"] = round((time.time() - start_time) * 1000)
            result["metadata"]["status"] = "success"
            
            logger.info(f"✅ Analysis complete: {final_verdict.get('verdict', 'UNKNOWN')} (confidence: {final_verdict.get('confidence_score', 0)}%)")
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            result["metadata"]["status"] = "error"
            result["metadata"]["error"] = str(e)
            result["final_verdict"] = {
                "verdict": "ERROR",
                "confidence_score": 0,
                "critical_analysis": f"Analysis failed: {str(e)}",
                "winning_argument": "Unable to determine",
                "key_evidence": []
            }
        
        return result
    
    async def _gather_evidence(self, query: str) -> List[Dict]:
        """Gather evidence from RAG + web scraping."""
        try:
            evidence_bundle = await asyncio.wait_for(
                get_diversified_evidence(query),
                timeout=60.0
            )
            return evidence_bundle or []
        except asyncio.TimeoutError:
            logger.warning("Evidence gathering timed out")
            return []
        except Exception as e:
            logger.error(f"Evidence gathering failed: {e}")
            return []
    
    def _run_credibility_analysis(
        self,
        claim: str,
        evidence_bundle: List[Dict]
    ) -> Dict[str, Any]:
        """Run credibility scoring on sources."""
        if not self.credibility_engine:
            return {
                "overall_score": 0.5,
                "confidence_level": "Medium",
                "warnings": ["Credibility engine not available"]
            }
        
        try:
            # Convert evidence to Source objects
            sources = []
            evidence_texts = []
            
            for ev in evidence_bundle[:10]:
                url = ev.get("url", "")
                domain = ev.get("domain", "")
                if not domain and url:
                    domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                
                source = Source(
                    url=url,
                    domain=domain,
                    content=ev.get("text", "")[:2000],
                    timestamp=datetime.now()
                )
                sources.append(source)
                evidence_texts.append(ev.get("text", "")[:1000])
            
            # Calculate credibility
            cred_score = self.credibility_engine.calculate_credibility(
                claim=claim,
                sources=sources,
                evidence_texts=evidence_texts
            )
            
            return {
                "overall_score": round(cred_score.overall_score, 3),
                "source_trust": round(cred_score.source_trust, 3),
                "semantic_alignment": round(cred_score.semantic_alignment, 3),
                "temporal_consistency": round(cred_score.temporal_consistency, 3),
                "evidence_diversity": round(cred_score.evidence_diversity, 3),
                "confidence_level": cred_score.confidence_level,
                "explanation": cred_score.explanation,
                "warnings": cred_score.warnings
            }
            
        except Exception as e:
            logger.error(f"Credibility analysis failed: {e}")
            return {
                "overall_score": 0.5,
                "confidence_level": "Unknown",
                "warnings": [f"Analysis error: {str(e)}"]
            }
    
    def _format_evidence_bundle(
        self,
        evidence: List[Dict],
        credibility: Dict,
        forensics: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Format evidence bundle per PRD specification.
        
        PRD Format:
        {
          "extracted_text": "",
          "sources": [...],
          "authority": {...},
          "ocr": [...],
          "chunks": [...]
        }
        """
        # Combine extracted text
        extracted_text = "\n\n".join([
            f"[{ev.get('title', 'Unknown')}]\n{ev.get('text', '')[:500]}"
            for ev in evidence[:5]
        ])
        
        # Authority scores from forensics or credibility
        authority = {}
        if forensics and "authority_scores" in forensics:
            authority = forensics["authority_scores"]
        else:
            authority = {
                "aggregate_score": credibility.get("overall_score", 0.5) * 100,
                "source_count": len(evidence)
            }
        
        return {
            "extracted_text": extracted_text[:5000],
            "sources": [
                {
                    "title": ev.get("title", "Unknown"),
                    "url": ev.get("url", ""),
                    "domain": ev.get("domain", ""),
                    "summary": ev.get("summary", ev.get("text", "")[:200])
                } for ev in evidence[:10]
            ],
            "authority": authority,
            "ocr": [],  # Will be populated if OCR was used
            "chunks": [ev.get("text", "")[:500] for ev in evidence[:5]],
            "total_sources": len(evidence)
        }
    
    async def _run_debate(
        self,
        topic: str,
        evidence_bundle: List[Dict],
        dossier: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Run adversarial debate with Proponent, Opponent, and Moderator.
        
        Returns:
            Dict with transcript and metadata
        """
        loop = asyncio.get_running_loop()
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=4)
        
        transcript = f"=== DEBATE TOPIC: {topic} ===\n\n"
        
        # Build evidence context
        evidence_context = "\n".join([
            f"- {ev.get('title', 'Source')}: {ev.get('text', '')[:200]}..."
            for ev in evidence_bundle[:3]
        ])
        
        # Add dossier context if available
        dossier_context = ""
        if dossier:
            dossier_context = f"\n\nForensic Analysis:\n- Credibility: {dossier.get('credibility', 'N/A')}/100\n- Red Flags: {len(dossier.get('red_flags', []))}\n"
        
        try:
            # Get role prompts
            proponent_prompt = ROLE_PROMPTS.get("proponent", "You are the Proponent. Argue in favor.")
            opponent_prompt = ROLE_PROMPTS.get("opponent", "You are the Opponent. Argue against.")
            moderator_prompt = ROLE_PROMPTS.get("moderator", "You are the Moderator. Synthesize the debate.")
            
            # Round 1: Opening Statements
            transcript += "--- ROUND 1: OPENING STATEMENTS ---\n\n"
            
            # Proponent opening
            proponent_input = f"Topic: {topic}\n\nEvidence:\n{evidence_context}{dossier_context}\n\nProvide your opening statement supporting this claim."
            
            def get_proponent_opening():
                response = ""
                for chunk in self.ai_agent.stream(
                    user_message=proponent_input,
                    system_prompt=proponent_prompt,
                    max_tokens=400
                ):
                    response += chunk
                return response
            
            proponent_response = await loop.run_in_executor(executor, get_proponent_opening)
            transcript += f"[PROPONENT]\n{proponent_response}\n\n"
            
            # Opponent opening
            opponent_input = f"Topic: {topic}\n\nEvidence:\n{evidence_context}{dossier_context}\n\nProponent's argument:\n{proponent_response[:500]}\n\nProvide your opening statement challenging this claim."
            
            def get_opponent_opening():
                response = ""
                for chunk in self.ai_agent.stream(
                    user_message=opponent_input,
                    system_prompt=opponent_prompt,
                    max_tokens=400
                ):
                    response += chunk
                return response
            
            opponent_response = await loop.run_in_executor(executor, get_opponent_opening)
            transcript += f"[OPPONENT]\n{opponent_response}\n\n"
            
            # Round 2: Rebuttals
            transcript += "--- ROUND 2: REBUTTALS ---\n\n"
            
            # Proponent rebuttal
            rebuttal_input = f"The opponent argued:\n{opponent_response[:500]}\n\nProvide your rebuttal."
            
            def get_proponent_rebuttal():
                response = ""
                for chunk in self.ai_agent.stream(
                    user_message=rebuttal_input,
                    system_prompt=proponent_prompt + "\n\nFocus on addressing the opponent's specific points.",
                    max_tokens=300
                ):
                    response += chunk
                return response
            
            proponent_rebuttal = await loop.run_in_executor(executor, get_proponent_rebuttal)
            transcript += f"[PROPONENT REBUTTAL]\n{proponent_rebuttal}\n\n"
            
            # Opponent rebuttal
            opp_rebuttal_input = f"The proponent's rebuttal:\n{proponent_rebuttal[:500]}\n\nProvide your counter-rebuttal."
            
            def get_opponent_rebuttal():
                response = ""
                for chunk in self.ai_agent.stream(
                    user_message=opp_rebuttal_input,
                    system_prompt=opponent_prompt + "\n\nFocus on final compelling arguments.",
                    max_tokens=300
                ):
                    response += chunk
                return response
            
            opponent_rebuttal = await loop.run_in_executor(executor, get_opponent_rebuttal)
            transcript += f"[OPPONENT REBUTTAL]\n{opponent_rebuttal}\n\n"
            
            # Round 3: Moderator Synthesis
            transcript += "--- MODERATOR SYNTHESIS ---\n\n"
            
            synthesis_input = f"""Topic: {topic}

Proponent's main argument: {proponent_response[:300]}...
Opponent's main argument: {opponent_response[:300]}...
Proponent's rebuttal: {proponent_rebuttal[:200]}...
Opponent's rebuttal: {opponent_rebuttal[:200]}...

Provide a balanced synthesis of this debate, identifying the strongest points from each side."""
            
            def get_synthesis():
                response = ""
                for chunk in self.ai_agent.stream(
                    user_message=synthesis_input,
                    system_prompt=moderator_prompt,
                    max_tokens=400
                ):
                    response += chunk
                return response
            
            synthesis = await loop.run_in_executor(executor, get_synthesis)
            transcript += f"[MODERATOR]\n{synthesis}\n\n"
            
            return {
                "transcript": transcript,
                "rounds": 3,
                "participants": ["proponent", "opponent", "moderator"]
            }
            
        except Exception as e:
            logger.error(f"Debate generation failed: {e}")
            return {
                "transcript": transcript + f"\n[ERROR: Debate interrupted - {str(e)}]",
                "rounds": 0,
                "error": str(e)
            }
    
    async def _generate_verdict(
        self,
        topic: str,
        evidence_bundle: List[Dict],
        debate_transcript: str,
        credibility: Dict,
        forensics: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Generate final verdict based on all analysis.
        
        PRD Output Format:
        {
          "verdict": "VERIFIED / DEBUNKED / COMPLEX",
          "confidence": 0–100,
          "winning_argument": "...",
          "critical_analysis": "...",
          "key_evidence": [...]
        }
        """
        loop = asyncio.get_running_loop()
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=2)
        
        # Build comprehensive context
        evidence_summary = "\n".join([
            f"- {ev.get('title', 'Source')}: {ev.get('text', '')[:150]}..."
            for ev in evidence_bundle[:5]
        ])
        
        credibility_summary = f"""
Credibility Analysis:
- Overall Score: {credibility.get('overall_score', 0.5):.2f}
- Source Trust: {credibility.get('source_trust', 0.5):.2f}
- Confidence Level: {credibility.get('confidence_level', 'Unknown')}
- Warnings: {', '.join(credibility.get('warnings', [])) or 'None'}
"""
        
        forensic_summary = ""
        if forensics:
            forensic_summary = f"""
Forensic Analysis:
- Credibility Score: {forensics.get('dossier', {}).get('credibility', 'N/A')}/100
- Red Flags: {forensics.get('red_flag_count', 0)}
- Authority Score: {forensics.get('authority_scores', {}).get('aggregate_score', 'N/A')}
- Recommendation: {forensics.get('recommendation', 'N/A')}
"""
        
        verdict_prompt = f"""You are the Chief Fact-Checker rendering a final verdict. Analyze ALL evidence and arguments.

CLAIM/TOPIC: {topic}

EVIDENCE:
{evidence_summary}

{credibility_summary}
{forensic_summary}

DEBATE TRANSCRIPT:
{debate_transcript[-3000:] if debate_transcript else 'No debate conducted'}

---

Based on this comprehensive analysis, render your final verdict.

VERDICT CRITERIA:
- VERIFIED: Evidence strongly supports the claim with high confidence
- DEBUNKED: Evidence contradicts or disproves the claim
- COMPLEX: Evidence is mixed, nuanced, or insufficient for a clear determination

You MUST respond with valid JSON in this exact format:
{{
  "verdict": "VERIFIED" or "DEBUNKED" or "COMPLEX",
  "confidence_score": 0-100,
  "winning_argument": "The strongest argument that decided the verdict",
  "critical_analysis": "Detailed reasoning for this verdict",
  "key_evidence": ["Evidence 1", "Evidence 2", "Evidence 3"]
}}

Respond ONLY with the JSON object, no other text."""
        
        judge_system_prompt = ROLE_PROMPTS.get("judge", """You are an impartial fact-checking judge. 
Your role is to render fair, evidence-based verdicts. 
Be rigorous, cite specific evidence, and avoid speculation.
Always respond with properly formatted JSON.""")
        
        try:
            def get_verdict():
                response = self.ai_agent.call_blocking(
                    user_message=verdict_prompt,
                    system_prompt=judge_system_prompt,
                    max_tokens=600
                )
                return response.text.strip()
            
            response_text = await loop.run_in_executor(executor, get_verdict)
            
            # Parse JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                verdict_data = json.loads(json_match.group(0))
                
                # Validate and normalize
                verdict_data["verdict"] = verdict_data.get("verdict", "COMPLEX").upper()
                if verdict_data["verdict"] not in ["VERIFIED", "DEBUNKED", "COMPLEX"]:
                    verdict_data["verdict"] = "COMPLEX"
                
                verdict_data["confidence_score"] = min(100, max(0, int(verdict_data.get("confidence_score", 50))))
                
                return verdict_data
            else:
                raise ValueError("No JSON found in response")
                
        except Exception as e:
            logger.error(f"Verdict generation failed: {e}")
            return {
                "verdict": "COMPLEX",
                "confidence_score": 30,
                "winning_argument": "Unable to reach a definitive conclusion",
                "critical_analysis": f"Verdict generation encountered an error: {str(e)}. Based on available evidence, the claim requires further verification.",
                "key_evidence": []
            }
    
    def _run_bias_audit(self, transcript: str) -> Dict[str, Any]:
        """Run bias detection on debate transcript."""
        if not self.bias_auditor:
            return {"status": "skipped", "reason": "Bias auditor not available"}
        
        try:
            # Use the bias auditor to analyze the transcript
            audit_result = self.bias_auditor.audit_text(
                text=transcript,
                source="debate_transcript"
            )
            
            return {
                "bias_flags": [flag.to_dict() for flag in audit_result.flags[:10]],
                "bias_count": len(audit_result.flags),
                "overall_bias_score": audit_result.overall_score,
                "recommendations": audit_result.recommendations[:5]
            }
        except Exception as e:
            logger.error(f"Bias audit failed: {e}")
            return {"status": "error", "error": str(e)}


# Create singleton pipeline instance
_pipeline_instance: Optional[ATLASAnalysisPipeline] = None


def get_pipeline() -> ATLASAnalysisPipeline:
    """Get or create the analysis pipeline singleton."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = ATLASAnalysisPipeline()
    return _pipeline_instance


# ============================================
# API ROUTES
# ============================================

@analyze_bp.route('', methods=['POST'])
@analyze_bp.route('/', methods=['POST'])
async def full_analysis():
    """
    Full ATLAS v4.0 analysis endpoint.
    
    Request JSON:
    {
        "query": "The claim or topic to analyze",
        "enable_debate": true,  // Optional, default true
        "enable_forensics": true,  // Optional, default true
        "session_id": "optional-session-id"
    }
    
    Returns complete analysis with verdict.
    """
    try:
        data = await request.get_json()
        
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"error": "Missing 'query' parameter"}), 400
        
        enable_debate = data.get("enable_debate", True)
        enable_forensics = data.get("enable_forensics", True)
        session_id = data.get("session_id")
        
        logger.info(f"🚀 Starting full analysis: {query[:100]}...")
        
        pipeline = get_pipeline()
        result = await pipeline.run_full_analysis(
            query=query,
            enable_debate=enable_debate,
            enable_forensics=enable_forensics,
            session_id=session_id
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Analysis endpoint error: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500


@analyze_bp.route('/quick', methods=['POST'])
async def quick_analysis():
    """
    Quick analysis without full debate.
    
    Runs: RAG → Credibility → Forensics → Quick Verdict
    Faster but less thorough than full analysis.
    """
    try:
        data = await request.get_json()
        
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"error": "Missing 'query' parameter"}), 400
        
        logger.info(f"⚡ Starting quick analysis: {query[:100]}...")
        
        pipeline = get_pipeline()
        result = await pipeline.run_full_analysis(
            query=query,
            enable_debate=False,  # Skip debate for quick analysis
            enable_forensics=True,
            session_id=data.get("session_id")
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Quick analysis error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@analyze_bp.route('/stream', methods=['POST'])
async def stream_analysis():
    """
    Streaming analysis endpoint.
    Returns Server-Sent Events (SSE) for real-time updates.
    """
    try:
        data = await request.get_json()
        
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"error": "Missing 'query' parameter"}), 400
        
        async def generate():
            pipeline = get_pipeline()
            
            # Stage updates
            yield format_sse({"stage": "starting", "message": "Initializing analysis..."}, "stage")
            
            # Run each stage and yield updates
            yield format_sse({"stage": "evidence", "message": "Gathering evidence..."}, "stage")
            evidence = await pipeline._gather_evidence(query)
            yield format_sse({"stage": "evidence_complete", "sources": len(evidence)}, "stage")
            
            yield format_sse({"stage": "credibility", "message": "Analyzing credibility..."}, "stage")
            cred_result = pipeline._run_credibility_analysis(query, evidence)
            yield format_sse({"stage": "credibility_complete", "score": cred_result.get("overall_score")}, "stage")
            
            if pipeline.forensic_engine:
                yield format_sse({"stage": "forensics", "message": "Running forensic analysis..."}, "stage")
                forensic_result = pipeline.forensic_engine.analyze_claim(query, evidence)
                yield format_sse({"stage": "forensics_complete"}, "stage")
            else:
                forensic_result = None
            
            yield format_sse({"stage": "debate", "message": "Running adversarial debate..."}, "stage")
            debate_result = await pipeline._run_debate(query, evidence, forensic_result.get("dossier") if forensic_result else None)
            yield format_sse({"stage": "debate_complete"}, "stage")
            
            yield format_sse({"stage": "verdict", "message": "Generating final verdict..."}, "stage")
            verdict = await pipeline._generate_verdict(query, evidence, debate_result.get("transcript", ""), cred_result, forensic_result)
            
            yield format_sse(verdict, "final_verdict")
            yield format_sse({"message": "Analysis complete"}, "end")
        
        return Response(generate(), mimetype="text/event-stream")
        
    except Exception as e:
        logger.error(f"Stream analysis error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@analyze_bp.route('/health', methods=['GET'])
async def health_check():
    """Check analysis pipeline health."""
    return jsonify({
        "status": "ok",
        "v2_features": V2_FEATURES_AVAILABLE,
        "memory_system": MEMORY_AVAILABLE,
        "components": {
            "forensic_engine": get_pipeline().forensic_engine is not None,
            "credibility_engine": get_pipeline().credibility_engine is not None,
            "bias_auditor": get_pipeline().bias_auditor is not None
        }
    })

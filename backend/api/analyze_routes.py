"""
ATLAS v4.1.1 Full Analysis Pipeline API with RAG Integration

This module implements the complete analysis endpoint as per PRD:
RAG Evidence Module → Claim Parser → Agents → Verdict Engine → Response

Routes:
- /analyze: Full pipeline analysis with RAG
- /analyze/quick: Quick analysis (no debate)

v4.1.1 Changes:
- Integrated Hybrid RAG (BM25 + Embedding) for evidence retrieval
- RAG runs BEFORE agents for factual grounding
- No debate transcripts exposed (PRD compliant)
- Latency target: 4-8 seconds per verdict
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

# RAG Evidence Module (v4.1.3)
try:
    from rag.evidence_retriever import get_rag_retriever, RAGEvidenceRetriever
    from rag.adapter import (
        process_scraper_results,
        build_evidence_prompt,
        format_assistant_with_citations
    )
    RAG_AVAILABLE = True
    logging.info("✅ RAG Evidence Module loaded (v4.1.3)")
except ImportError as e:
    RAG_AVAILABLE = False
    process_scraper_results = None
    build_evidence_prompt = None
    format_assistant_with_citations = None
    logging.warning(f"⚠️ RAG Evidence Module not available: {e}")

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
            # STAGE 3: Forensic Analysis (Entity Background + Dossier)
            # ============================================
            forensic_result = None
            forensic_dossier = None
            if enable_forensics and self.forensic_engine:
                logger.info("🔬 Stage 3: Running forensic analysis (entity extraction + dossier generation)...")
                forensic_start = time.time()
                
                # Run complete forensic analysis
                forensic_result = self.forensic_engine.analyze_claim(query, evidence_bundle)
                
                # Extract dossier for use in debate
                if forensic_result and "dossier" in forensic_result:
                    forensic_dossier = forensic_result["dossier"]
                    logger.info(f"✅ Forensic dossier generated: credibility={forensic_dossier.get('credibility', 'N/A')}, red_flags={forensic_dossier.get('red_flags', [])}")
                
                result["pipeline_stages"]["forensics"] = {
                    "status": "completed",
                    "duration_ms": round((time.time() - forensic_start) * 1000),
                    "entity_count": forensic_result.get("entity_count", 0) if forensic_result else 0,
                    "red_flag_count": forensic_result.get("red_flag_count", 0) if forensic_result else 0,
                    "overall_credibility": forensic_result.get("overall_credibility", 0) if forensic_result else 0,
                    "recommendation": forensic_result.get("recommendation", "N/A") if forensic_result else "N/A"
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
                logger.info("⚔️ Stage 5: Running adversarial debate with forensic dossier...")
                debate_start = time.time()
                
                # Pass forensic dossier to debate (per PRD Section 2.3)
                debate_result = await self._run_debate(
                    query,
                    evidence_bundle,
                    forensic_dossier  # Pass the dossier object/dict
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
        Format evidence bundle per ATLAS v4.0 PRD specification (Section 2.2).
        
        PRD Format:
        {
          "sources": [...],
          "authority_scores": {...},
          "cleaned_text": "...",
          "raw_metadata": {...}
        }
        """
        # Clean and combine text from all sources
        cleaned_text_parts = []
        for ev in evidence[:10]:
            text = ev.get('text', '') or ev.get('summary', '')
            if text:
                # Basic cleaning: remove extra whitespace, normalize
                cleaned = ' '.join(text.split())
                cleaned_text_parts.append(cleaned[:1000])  # Limit per source
        
        cleaned_text = "\n\n".join(cleaned_text_parts)
        
        # Authority scores per PRD Section 6.1
        authority_scores = {}
        if forensics and "authority_scores" in forensics:
            authority_scores = forensics["authority_scores"]
        else:
            # Calculate from evidence domains
            tier_counts = {"tier_1": 0, "tier_2": 0, "tier_3": 0, "tier_4": 0}
            for ev in evidence:
                domain = ev.get('domain', '')
                url = ev.get('url', '')
                if not domain and url:
                    try:
                        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                    except:
                        pass
                
                # Simple tier detection
                if any(t in domain.lower() for t in ['reuters', 'ap', '.gov', '.edu']):
                    tier_counts["tier_1"] += 1
                elif any(t in domain.lower() for t in ['bbc', 'nytimes', 'theguardian', 'washingtonpost']):
                    tier_counts["tier_2"] += 1
                elif any(t in domain.lower() for t in ['medium', 'substack', 'blog']):
                    tier_counts["tier_3"] += 1
                else:
                    tier_counts["tier_4"] += 1
            
            authority_scores = {
                "tier_distribution": tier_counts,
                "aggregate_score": credibility.get("overall_score", 0.5) * 100,
                "source_count": len(evidence),
                "tier_1_weight": tier_counts["tier_1"] * 40,
                "tier_2_weight": tier_counts["tier_2"] * 20,
                "tier_3_weight": tier_counts["tier_3"] * 5,
                "tier_4_penalty": tier_counts["tier_4"] * -20
            }
        
        # Format sources with authority information
        formatted_sources = []
        for ev in evidence[:10]:
            domain = ev.get('domain', '')
            url = ev.get('url', '')
            if not domain and url:
                try:
                    domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                except:
                    domain = "unknown"
            
            formatted_sources.append({
                "title": ev.get("title", "Unknown"),
                "url": url,
                "domain": domain,
                "summary": ev.get("summary", ev.get("text", "")[:200]),
                "text": ev.get("text", "")[:500],  # Include text for reference
                "published_at": ev.get("published_at"),
                "fetched_at": ev.get("fetched_at")
            })
        
        # Raw metadata for debugging/advanced use
        raw_metadata = {
            "total_sources": len(evidence),
            "credibility_overall": credibility.get("overall_score", 0.5),
            "credibility_level": credibility.get("confidence_level", "Unknown"),
            "forensics_enabled": forensics is not None,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "sources": formatted_sources,
            "authority_scores": authority_scores,
            "cleaned_text": cleaned_text[:10000],  # Limit total text
            "raw_metadata": raw_metadata
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
        
        # Add dossier context if available (per PRD Section 2.3)
        dossier_context = ""
        if dossier:
            # Format dossier per PRD specification
            if isinstance(dossier, dict):
                credibility = dossier.get('credibility', 'N/A')
                red_flags = dossier.get('red_flags', [])
                entity = dossier.get('entity', 'Unknown')
                authority_score = dossier.get('authority_score', 'N/A')
                
                dossier_context = f"""
=== FORENSIC DOSSIER (Entity Background Check) ===
Primary Entity: {entity}
Credibility Score: {credibility}/100
Authority Score: {authority_score}/100
Red Flags Detected: {len(red_flags)}

RED FLAGS:
"""
                for rf in red_flags[:5]:  # Top 5 red flags
                    rf_type = rf.get('type', 'Unknown') if isinstance(rf, dict) else getattr(rf, 'flag_type', 'Unknown')
                    rf_desc = rf.get('description', '')[:150] if isinstance(rf, dict) else getattr(rf, 'description', '')[:150]
                    rf_severity = rf.get('severity', 'unknown') if isinstance(rf, dict) else getattr(rf, 'severity', 'unknown')
                    dossier_context += f"  ⚠ [{rf_severity.upper()}] {rf_type}: {rf_desc}\n"
                
                dossier_context += "\n=== END FORENSIC DOSSIER ===\n\n"
            else:
                # Handle dossier object
                dossier_context = f"\n\nForensic Analysis:\n- Credibility: {getattr(dossier, 'credibility', 'N/A')}/100\n- Red Flags: {len(getattr(dossier, 'red_flags', []))}\n"
        
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
    ATLAS v4.1.1 Neutral Verdict Analysis Endpoint with RAG Integration.
    
    Pipeline: RAG Evidence Module → Claim Parser → Agents → Verdict Engine → Response
    
    Request JSON:
    {
        "query": "The claim or topic to analyze",
        "url": "optional URL to analyze",
        "text": "optional article text",
        "enable_forensics": true,  // Optional, default true
        "session_id": "optional-session-id"
    }
    
    Returns neutral verdict with RAG-sourced evidence (NO proponent/opponent/debate fields).
    """
    start_time = time.time()
    
    try:
        # Import verdict engine
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from verdict_engine import decide_verdict
        from agents.factual_analyst import FactualAnalyst
        from agents.evidence_synthesizer import EvidenceSynthesizer
        from agents.forensic_agent import ForensicAgent
        from agents.bias_auditor_agent import BiasAuditorAgent
        
        data = await request.get_json()
        
        query = data.get("query", "").strip()
        url = data.get("url", "").strip()
        text = data.get("text", "").strip()
        
        if not query and not url and not text:
            return jsonify({"error": "Missing 'query', 'url', or 'text' parameter"}), 400
        
        # Use query as primary, fallback to text
        article_text = query or text
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"🚀 Starting ATLAS v4.1.1 analysis (RAG-enabled): {article_text[:100]}...")
        
        # ============================================
        # STEP 1: RAG Evidence Module (NEW in v4.1.1)
        # Runs FIRST to provide factual grounding
        # ============================================
        rag_start = time.time()
        evidence_bundle = []
        rag_metrics = {}
        
        if RAG_AVAILABLE:
            try:
                rag_retriever = get_rag_retriever()
                evidence_bundle = await asyncio.wait_for(
                    rag_retriever.retrieve_evidence(article_text),
                    timeout=8.0  # 8 second RAG timeout
                )
                rag_metrics = rag_retriever.get_metrics()
                logger.info(f"📚 RAG retrieved {len(evidence_bundle)} evidence items in {rag_metrics.get('last_latency_ms', 0)}ms")
            except asyncio.TimeoutError:
                logger.warning("RAG retrieval timed out, falling back to web scraping")
                evidence_bundle = []
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}, falling back to web scraping")
                evidence_bundle = []
        
        # Fallback to web scraping if RAG didn't return results
        if not evidence_bundle:
            logger.info("📡 Falling back to web scraping for evidence...")
            pipeline = get_pipeline()
            evidence_bundle = await pipeline._gather_evidence(article_text)
            # Normalize to RAG format
            evidence_bundle = [
                {
                    "title": ev.get("title", "Unknown"),
                    "url": ev.get("url", ""),
                    "snippet": (ev.get("text", "") or ev.get("summary", ""))[:200],
                    "authority": ev.get("authority", 0.5),
                    "source_type": "News",
                    "domain": ev.get("domain", "")
                }
                for ev in evidence_bundle
            ]
        
        rag_duration_ms = int((time.time() - rag_start) * 1000)
        
        # ============================================
        # STEP 2: Claim Extraction (FactualAnalyst)
        # ============================================
        fa = FactualAnalyst()
        claims = fa.extract_claims(article_text)
        logger.info(f"📋 Extracted {len(claims)} claims")
        
        # ============================================
        # STEP 3: Evidence Enrichment (EvidenceSynthesizer)
        # ============================================
        synth = EvidenceSynthesizer()
        evidence_bundle_enriched = synth.enrich(evidence_bundle)
        
        # ============================================
        # STEP 4: Bias Analysis (BiasAuditorAgent)
        # ============================================
        ba = BiasAuditorAgent()
        bias_report = ba.audit_text(article_text)
        
        # ============================================
        # STEP 5: Forensic Analysis (ForensicAgent)
        # ============================================
        # Extract named entities for forensic analysis
        named_entities = []
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            doc = nlp(article_text[:5000])  # Limit text for NER
            named_entities = [
                {"name": ent.text, "type": ent.label_}
                for ent in doc.ents
                if ent.label_ in ["PERSON", "ORG", "GPE", "LOC"]
            ][:10]  # Limit to 10 entities
        except Exception as e:
            logger.debug(f"NER extraction not available: {e}")
        
        forensic_agent = ForensicAgent()
        forensic_dossier = forensic_agent.build_dossier(named_entities)
        
        # ============================================
        # STEP 6: Contradiction Detection (placeholder)
        # ============================================
        contradictions = []  # TODO: implement contradiction_engine
        extra_context = {"contradictions": contradictions}
        
        # ============================================
        # STEP 7: Verdict Engine (NO DEBATE)
        # ============================================
        verdict_json = decide_verdict(
            claims=claims,
            evidence_bundle=evidence_bundle_enriched,
            bias_report=bias_report,
            forensic_dossier=forensic_dossier,
            extra_context=extra_context
        )
        
        # Add metadata
        verdict_json["analysis_id"] = analysis_id
        verdict_json["request_url"] = url if url else None
        verdict_json["query"] = article_text[:200]
        
        # Add RAG metrics to response
        verdict_json["rag_metrics"] = {
            "evidence_count": len(evidence_bundle),
            "latency_ms": rag_duration_ms,
            "avg_authority": rag_metrics.get("last_avg_authority", 0) if rag_metrics else (
                sum(e.get("authority", 0.5) for e in evidence_bundle) / len(evidence_bundle) if evidence_bundle else 0
            ),
            "rag_enabled": RAG_AVAILABLE
        }
        
        # Total latency
        total_latency_ms = int((time.time() - start_time) * 1000)
        verdict_json["total_latency_ms"] = total_latency_ms
        
        # ============================================
        # STEP 8: Persist to DB (non-blocking)
        # ============================================
        try:
            from database.db_manager import db_manager
            await db_manager.analysis.insert_one({
                "_id": analysis_id,
                "verdict": verdict_json,
                "created_at": verdict_json.get("timestamp")
            })
        except Exception as e:
            logger.warning(f"Failed to persist analysis result: {e}")
        
        logger.info(
            f"✅ Verdict generated: {verdict_json.get('verdict')} "
            f"({verdict_json.get('confidence_pct')}%) "
            f"[latency={total_latency_ms}ms, evidence={len(evidence_bundle)}]"
        )
        
        # Return ONLY neutral verdict (no debate transcript)
        return jsonify(verdict_json), 200
        
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

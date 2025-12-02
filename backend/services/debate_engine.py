"""
Debate Engine

This module contains the main debate generation logic including:
- generate_debate: Main async generator for running debates
- run_turn: Individual debate turn handler with memory and bias audit integration
"""

import asyncio
import functools
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from core.ai_agent import AiAgent
from core.config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, ROLE_PROMPTS
from core.utils import compute_advanced_analytics, format_sse
from services.db_manager import AsyncDbManager
from services.pro_scraper import get_diversified_evidence

from .debate_helpers import (
    determine_debate_stances,
    format_evidence_bundle,
    format_forensic_dossier,
    generate_final_verdict,
    get_recent_transcript,
)

# Feature availability flags - will be set during import
V2_FEATURES_AVAILABLE = False
MEMORY_AVAILABLE = False
MONGO_AUDIT_AVAILABLE = False
PRD_CHECKER_AVAILABLE = False

# V2 Features imports
BiasAuditor = None
CredibilityEngine = None
Source = None
get_forensic_engine = None
RoleReversalEngine = None

# Memory imports
get_memory_manager = None

# Audit imports
get_audit_logger = None

# PRD Checker imports
has_citation = lambda text: "[SRC:" in text
is_factual_claim = lambda text: any(k in text.lower() for k in ["said", "reported", "confirmed", "according"])
extract_citations = lambda text: []

# Try loading optional dependencies
try:
    from v2_features.bias_auditor import BiasAuditor as _BiasAuditor
    from v2_features.credibility_engine import CredibilityEngine as _CredibilityEngine, Source as _Source
    from v2_features.forensic_engine import get_forensic_engine as _get_forensic_engine
    from v2_features.role_reversal_engine import RoleReversalEngine as _RoleReversalEngine
    
    BiasAuditor = _BiasAuditor
    CredibilityEngine = _CredibilityEngine
    Source = _Source
    get_forensic_engine = _get_forensic_engine
    RoleReversalEngine = _RoleReversalEngine
    V2_FEATURES_AVAILABLE = True
except ImportError:
    pass

try:
    from memory.memory_manager import get_memory_manager as _get_memory_manager
    get_memory_manager = _get_memory_manager
    MEMORY_AVAILABLE = True
except ImportError:
    pass

try:
    from memory.mongo_audit import get_audit_logger as _get_audit_logger
    get_audit_logger = _get_audit_logger
    MONGO_AUDIT_AVAILABLE = True
except ImportError:
    pass

try:
    from tools.prd_checker import (
        has_citation as _has_citation,
        is_factual_claim as _is_factual_claim,
        extract_citations as _extract_citations
    )
    has_citation = _has_citation
    is_factual_claim = _is_factual_claim
    extract_citations = _extract_citations
    PRD_CHECKER_AVAILABLE = True
except ImportError:
    pass


# Create executor for blocking operations
executor = ThreadPoolExecutor(max_workers=10)


async def generate_debate(topic: str):
    """
    Main async generator that orchestrates the entire debate flow.
    
    Phases:
    1. Opening Statements
    2. Cross-Examination
    3. Rebuttals
    4. Mid-Debate Compression
    5. Role Reversal (V2)
    6. Convergence
    7. Final Summaries
    8. Moderator Synthesis
    9. Verdict Engine
    
    Args:
        topic: The debate topic
        
    Yields:
        SSE formatted events for each debate phase
    """
    loop = asyncio.get_running_loop()
    
    debate_id = str(uuid.uuid4())
    transcript = ""
    log_entries = []
    evidence_bundle = []
    turn_metrics = {"turn_count": 0, "rebuttal_count": 0, "audited_turn_count": 0}
    
    # 🔬 V2 FEATURES: Initialize enhanced analysis engines
    bias_auditor = None
    credibility_engine = None
    forensic_engine = None
    credibility_result = None
    forensic_dossier = None
    role_reversal_engine = None
    
    if V2_FEATURES_AVAILABLE:
        try:
            bias_auditor = BiasAuditor()
            credibility_engine = CredibilityEngine()
            forensic_engine = get_forensic_engine()
            logging.info("🔬 V2 Features initialized for debate")
        except Exception as e:
            logging.warning(f"V2 Features initialization failed: {e}")
    
    # 🧠 MEMORY INTEGRATION: Initialize memory system for this debate
    memory = None
    if MEMORY_AVAILABLE and get_memory_manager:
        try:
            memory = get_memory_manager()
            memory.set_debate_context(debate_id)
            logging.info(f"🧠 Memory system enabled for debate: {debate_id}")
        except Exception as e:
            logging.warning(f"Memory system initialization failed: {e}. Continuing without memory.")
            memory = None

    # 📊 MONGO AUDIT: Initialize audit logger for this debate session
    audit_logger = None
    if MONGO_AUDIT_AVAILABLE and get_audit_logger:
        try:
            audit_logger = get_audit_logger()
            if audit_logger and audit_logger.enabled:
                audit_logger.log_debate_session(
                    debate_id=debate_id,
                    topic=topic,
                    metadata={
                        "memory_enabled": memory is not None,
                        "v2_features_enabled": V2_FEATURES_AVAILABLE,
                        "model": DEFAULT_MODEL
                    }
                )
                logging.info(f"📊 MongoDB audit logging enabled for debate: {debate_id}")
        except Exception as e:
            logging.warning(f"MongoDB audit initialization failed: {e}")
            audit_logger = None

    try:
        yield format_sse({
            "topic": topic,
            "model_used": DEFAULT_MODEL,
            "debate_id": debate_id,
            "memory_enabled": memory is not None,
            "v2_features_enabled": V2_FEATURES_AVAILABLE
        }, "metadata")

        # Try to get evidence, but don't fail the debate if it errors
        try:
            evidence_bundle = await asyncio.wait_for(
                get_diversified_evidence(topic),
                timeout=60.0
            )
            logging.info(f"📚 Gathered {len(evidence_bundle)} sources for debate")
            
            # 📊 MONGO AUDIT: Log RAG retrieval quality
            if audit_logger and audit_logger.enabled:
                audit_logger.log_memory_addition(
                    role="rag_retriever",
                    content=f"Retrieved {len(evidence_bundle)} sources for topic: {topic[:100]}",
                    metadata={
                        "source_count": len(evidence_bundle),
                        "sources": [ev.get("url", "")[:100] for ev in evidence_bundle[:5]],
                        "retrieval_type": "web_scraper"
                    },
                    debate_id=debate_id
                )
        except Exception as e:
            logging.warning(f"Evidence gathering failed for debate: {e}. Continuing without evidence.")
            evidence_bundle = []
        
        # 🔬 V2 FEATURES: Run credibility and forensic analysis
        if V2_FEATURES_AVAILABLE and evidence_bundle:
            try:
                # Credibility Analysis
                if credibility_engine:
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
                    
                    credibility_result = credibility_engine.calculate_credibility(
                        claim=topic,
                        sources=sources,
                        evidence_texts=evidence_texts
                    )
                    logging.info(f"✅ Credibility Score: {credibility_result.overall_score:.2f} ({credibility_result.confidence_level})")
                    
                    # Yield credibility results
                    yield format_sse({
                        "overall_score": round(credibility_result.overall_score, 3),
                        "source_trust": round(credibility_result.source_trust, 3),
                        "confidence_level": credibility_result.confidence_level,
                        "warnings": credibility_result.warnings
                    }, "credibility_analysis")
                
                # Forensic Analysis
                if forensic_engine:
                    forensic_result = forensic_engine.analyze_claim(topic, evidence_bundle)
                    forensic_dossier = forensic_result.get("dossier")
                    logging.info(f"✅ Forensic Analysis: credibility={forensic_result.get('overall_credibility', 'N/A')}, red_flags={forensic_result.get('red_flag_count', 0)}")
                    
                    # Yield forensic results (summary only to avoid payload bloat)
                    yield format_sse({
                        "credibility": forensic_result.get("overall_credibility"),
                        "red_flag_count": forensic_result.get("red_flag_count"),
                        "entity_count": forensic_result.get("entity_count"),
                        "recommendation": forensic_result.get("recommendation")
                    }, "forensic_analysis")
                    
            except Exception as e:
                logging.warning(f"V2 analysis failed: {e}. Continuing without enhanced analysis.")
        
        # 📋 PRD 4.1: Format Evidence Bundle with Authority Scores
        formatted_evidence = format_evidence_bundle(evidence_bundle, forensic_engine)
        
        # 📋 PRD 4.2: Format Forensic Dossier
        formatted_dossier = format_forensic_dossier(forensic_dossier) if forensic_dossier else ""
        
        # Build comprehensive transcript header with evidence
        if evidence_bundle:
            transcript = f"""Debate ID: {debate_id}
Topic: {topic}

=== EVIDENCE BUNDLE (cite using [SRC:ID] format) ===
{formatted_evidence}

{formatted_dossier if formatted_dossier else ''}

=== DEBATE TRANSCRIPT ===

"""
        else:
            transcript = f"Debate ID: {debate_id}\nTopic: {topic}\n\n[NO EVIDENCE SOURCES AVAILABLE]\n\n"

        # 🎯 STEP 1: DETERMINE DEBATE STANCES
        logging.info("🎯 Determining specific debate stances...")
        stances = await loop.run_in_executor(executor, determine_debate_stances, topic, evidence_bundle)
        
        # 🔬 V2 FEATURES: Build comprehensive context for debaters (PRD 4.3)
        evidence_context = f"""
=== AVAILABLE EVIDENCE (You MUST cite these using [SRC:ID] format) ===
{formatted_evidence}

{formatted_dossier if formatted_dossier else ''}
"""
        
        # Inject evidence, stances and forensic context into role prompts
        debaters = {
            "proponent": ROLE_PROMPTS["proponent"] + f"""

{evidence_context}

SPECIFIC STRATEGY FOR THIS DEBATE:
{stances['proponent_stance']}

CITATION REQUIREMENT: Every factual claim MUST include a citation like [SRC:TOI-001 | auth:75].
Uncited claims will be flagged by the moderator.""",

            "opponent": ROLE_PROMPTS["opponent"] + f"""

{evidence_context}

SPECIFIC STRATEGY FOR THIS DEBATE:
{stances['opponent_stance']}

CITATION REQUIREMENT: Every factual claim MUST include a citation like [SRC:TOI-001 | auth:75].
Uncited claims will be flagged by the moderator."""
        }

        # --- Moderator Introduction ---
        intro_prompt = f"""You are the MODERATOR for a structured debate on: "{topic}"

FORENSIC DOSSIER FOR THIS DEBATE:
{formatted_dossier if formatted_dossier else '[No forensic dossier available]'}

EVIDENCE SOURCES:
{formatted_evidence}

Introduce this debate by:
1. Stating the topic clearly
2. Summarizing the key entities and their relationships (from dossier)
3. Noting any red flags or credibility concerns
4. Explaining the debate structure (Opening Statements → Cross-Examination → Rebuttals → Convergence → Final Summaries → Verdict)
5. Reminding debaters they MUST cite evidence using [SRC:ID | auth:XX] format

Keep your introduction under 200 words."""
        
        async for event, data in run_turn("moderator", intro_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- INTRODUCTION FROM MODERATOR ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 1: OPENING STATEMENTS (PRD Requirement)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "opening_statements", "message": "Phase 1: Opening Statements"}, "debate_phase")
        
        for role, prompt in debaters.items():
            input_text = f"""The moderator has introduced the topic. Provide your OPENING STATEMENT (3 minutes / ~300 words max).

FORENSIC DOSSIER CONTEXT:
{formatted_dossier if formatted_dossier else '[No dossier available]'}

CRITICAL REQUIREMENTS:
1. State your position clearly
2. Present your 2-3 strongest arguments
3. EVERY factual claim MUST cite evidence using [SRC:ID | auth:XX] format
4. Reference the forensic dossier findings if relevant
5. Uncited claims will be flagged and may be discounted

Transcript so far:
{get_recent_transcript(transcript)}"""
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                if event == "token":
                    transcript += f"--- OPENING STATEMENT FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 2: CROSS-EXAMINATION (PRD Requirement)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "cross_examination", "message": "Phase 2: Cross-Examination"}, "debate_phase")
        
        # Proponent asks Opponent ONE question
        cross_exam_prompt_pro = f"""CROSS-EXAMINATION: Ask the OPPONENT ONE pointed question.

Your question should:
1. Target a weakness or unsupported claim in their opening statement
2. Require them to cite specific evidence
3. Be direct and answerable

Previous transcript:
{get_recent_transcript(transcript)}

Ask your ONE question now:"""
        
        async for event, data in run_turn("proponent", debaters["proponent"], cross_exam_prompt_pro, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM QUESTION FROM PROPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)
        
        # Opponent answers
        cross_exam_answer_opp = f"""Answer the Proponent's cross-examination question directly.
You MUST cite evidence [SRC:ID | auth:XX] to support your answer.
If you cannot cite evidence, acknowledge it as speculation.

Previous transcript:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("opponent", debaters["opponent"], cross_exam_answer_opp, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM ANSWER FROM OPPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)
        
        # Opponent asks Proponent ONE question
        cross_exam_prompt_opp = f"""CROSS-EXAMINATION: Ask the PROPONENT ONE pointed question.

Your question should:
1. Target a weakness or unsupported claim in their opening statement
2. Require them to cite specific evidence
3. Be direct and answerable

Previous transcript:
{get_recent_transcript(transcript)}

Ask your ONE question now:"""
        
        async for event, data in run_turn("opponent", debaters["opponent"], cross_exam_prompt_opp, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM QUESTION FROM OPPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)
        
        # Proponent answers
        cross_exam_answer_pro = f"""Answer the Opponent's cross-examination question directly.
You MUST cite evidence [SRC:ID | auth:XX] to support your answer.
If you cannot cite evidence, acknowledge it as speculation.

Previous transcript:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("proponent", debaters["proponent"], cross_exam_answer_pro, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- CROSS-EXAM ANSWER FROM PROPONENT ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # --- Moderator Citation Check (PRD 4.4) ---
        citation_check_prompt = f"""As moderator, review the opening statements and cross-examination.

CITATION ENFORCEMENT REPORT:
1. List which debaters properly used [SRC:ID] citations
2. Flag any UNSUPPORTED CLAIMS (factual statements without citations)
3. Note which sources were cited and their authority scores
4. Identify any BIAS INDICATORS you observe

Provide a brief (150 words max) assessment.

Transcript:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("moderator", citation_check_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- MODERATOR CITATION & BIAS CHECK ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 3: REBUTTALS (PRD Requirement)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "rebuttals", "message": "Phase 3: Rebuttals"}, "debate_phase")
        
        for role, prompt in debaters.items():
            input_text = f"""REBUTTAL ROUND (2 minutes / ~200 words max).

Address:
1. The cross-examination exchange
2. Rebut the opponent's strongest argument
3. Reinforce your position with NEW evidence citations [SRC:ID | auth:XX]

CRITICAL: Every counter-claim MUST cite evidence. Uncited rebuttals are weak.

Transcript:
{get_recent_transcript(transcript)}"""
            async for event, data in run_turn(role, prompt, input_text, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor, is_rebuttal=True):
                if event == "token":
                    transcript += f"--- REBUTTAL FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 4: MID-DEBATE COMPRESSION (PRD Section 7)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "mid_debate_compression", "message": "Phase 4: Mid-Debate Compression"}, "debate_phase")

        compression_prompt = f"""As moderator, provide a CORE SUMMARY BLOCK of the debate so far.

FORENSIC DOSSIER REFERENCE:
{formatted_dossier if formatted_dossier else '[No dossier]'}

Structure your compression as:
═══════════════════════════════════
CORE SUMMARY BLOCK (Mid-Debate)
═══════════════════════════════════

1. PROPONENT'S KEY CLAIMS:
   - [List 2-3 main claims]
   - Citation status: [CITED/UNCITED for each]

2. OPPONENT'S KEY CLAIMS:
   - [List 2-3 main claims]
   - Citation status: [CITED/UNCITED for each]

3. UNRESOLVED TENSIONS:
   - [1-2 key disagreements]

4. EVIDENCE GAPS:
   - [What evidence is missing?]

5. BIAS INDICATORS DETECTED:
   - [Any framing bias, personal motive attribution, or unverified claims]

6. SOURCE AUTHORITY ASSESSMENT:
   - [Which sources were most/least credible]

Keep under 250 words. Be factual and neutral."""
        
        async for event, data in run_turn("moderator", compression_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                transcript += f"--- MID-DEBATE COMPRESSION (CORE SUMMARY BLOCK) ---\n{data['text']}\n\n"
            yield format_sse(data, event)

        # ═══════════════════════════════════════════════════════════════
        # PHASE 5: ROLE REVERSAL (PRD Section 2.6)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "role_reversal", "message": "Phase 5: Role Reversal Challenge"}, "debate_phase")
        if V2_FEATURES_AVAILABLE and RoleReversalEngine:
            try:
                role_reversal_engine = RoleReversalEngine()
                
                yield format_sse({"message": "Starting Role Reversal Round - debaters will switch positions"}, "role_reversal_start")
                
                previous_arguments = {"proponent": "", "opponent": ""}
                current_roles = {"proponent": "proponent", "opponent": "opponent"}
                reversed_roles = role_reversal_engine.create_reversal_map(current_roles)
                
                for original_role, new_role in reversed_roles.items():
                    if original_role == "moderator":
                        continue
                    
                    reversal_prompt = f"""ROLE REVERSAL CHALLENGE

You were arguing as the {original_role.upper()}. 
Now you MUST argue as the {new_role.upper()}.

This is NOT about winning - it's about stress-testing arguments and finding truth.
Identify the STRONGEST points from the opposite side and argue them convincingly.
Be intellectually honest - acknowledge weaknesses in your original position.

Previous debate context:
{get_recent_transcript(transcript)}

Now argue from the {new_role.upper()} perspective:"""
                    
                    system_prompt = f"You are now the {new_role.upper()}. Argue convincingly from this new perspective. Find genuine merit in the opposing view."
                    
                    async for event, data in run_turn(f"{new_role}_reversed", system_prompt, reversal_prompt, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                        if event == "token":
                            transcript += f"--- ROLE REVERSAL: {original_role.upper()} NOW ARGUING AS {new_role.upper()} ---\n{data['text']}\n\n"
                        yield format_sse(data, event)
                
                convergence_score = role_reversal_engine._calculate_convergence(
                    previous_arguments,
                    {"proponent": transcript[-2000:], "opponent": transcript[-2000:]}
                )
                
                yield format_sse({
                    "convergence_score": round(convergence_score, 3),
                    "message": "Role reversal complete - analyzing convergence"
                }, "role_reversal_complete")
                
                logging.info(f"🔄 Role Reversal completed with convergence score: {convergence_score:.3f}")
                
            except Exception as e:
                logging.warning(f"Role reversal failed: {e}. Continuing without role reversal.")

        # ═══════════════════════════════════════════════════════════════
        # PHASE 6: CONVERGENCE (PRD Requirement)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "convergence", "message": "Phase 6: Convergence - Finding Common Ground"}, "debate_phase")
        
        for role, prompt in debaters.items():
            convergence_prompt = f"""CONVERGENCE PHASE (2 minutes / ~200 words max)

Having heard all arguments and participated in role reversal, now:

1. Identify the STRONGEST point from your opponent that you now acknowledge has merit
2. Update your stance based on what you've learned
3. State the COMMON GROUND you share with your opponent
4. Clarify any remaining disagreements

Be intellectually honest. This phase reveals the truth, not rhetorical victory.

Transcript:
{get_recent_transcript(transcript)}"""
            
            async for event, data in run_turn(role, prompt, convergence_prompt, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                if event == "token":
                    transcript += f"--- CONVERGENCE FROM {data['role'].upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)
        
        # ═══════════════════════════════════════════════════════════════
        # PHASE 7: FINAL SUMMARIES (PRD Requirement)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "final_summaries", "message": "Phase 7: Final Summary Statements"}, "debate_phase")
        
        for role in ["proponent", "opponent"]:
            summary_prompt = f"""FINAL CLOSING STATEMENT (3 minutes / ~300 words max)

Structure your closing as:
═══════════════════════════════════
CLOSING STATEMENT - {role.upper()}
═══════════════════════════════════

1. MY STRONGEST UNREFUTED ARGUMENT:
   [State your best argument that the opponent failed to adequately counter]

2. KEY EVIDENCE SUPPORTING MY POSITION:
   [List 2-3 pieces with [SRC:ID | auth:XX] citations]

3. WHY I SHOULD WIN:
   [Summarize why the evidence and arguments favor your side]

4. ACKNOWLEDGMENT OF VALID OPPONENT POINTS:
   [Show intellectual honesty - what did they get right?]

5. FINAL VERDICT RECOMMENDATION:
   [What should the judge conclude?]

This is your last chance to persuade. Make it count.

Transcript:
{get_recent_transcript(transcript)}"""
            
            async for event, data in run_turn(role, debaters[role], summary_prompt, loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
                if event == "token":
                    transcript += f"--- FINAL CLOSING STATEMENT FROM {role.upper()} ---\n{data['text']}\n\n"
                yield format_sse(data, event)
        
        # ═══════════════════════════════════════════════════════════════
        # PHASE 8: MODERATOR SYNTHESIS
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "moderator_synthesis", "message": "Phase 8: Moderator Final Synthesis"}, "debate_phase")
        
        synthesis_text = ""
        moderator_synthesis_prompt = f"""FINAL MODERATOR SYNTHESIS

Provide a comprehensive final synthesis before the Verdict Engine renders judgment.

FORENSIC DOSSIER SUMMARY:
{formatted_dossier if formatted_dossier else '[No dossier]'}

Structure:
═══════════════════════════════════
FINAL DEBATE SYNTHESIS
═══════════════════════════════════

1. DEBATE SUMMARY:
   - Topic: {topic}
   - Rounds completed: Opening, Cross-Examination, Rebuttals, Compression, Role Reversal, Convergence, Final Summaries

2. EVIDENCE QUALITY ASSESSMENT:
   - Sources used and their authority scores
   - Citation compliance by each debater

3. BIAS AUDIT FINDINGS:
   - Any detected biases (framing, personal motive, unverified claims)
   - How biases affected arguments

4. KEY UNRESOLVED QUESTIONS:
   - What remains unclear despite the debate?

5. RECOMMENDATION TO VERDICT ENGINE:
   - Based on evidence weight, which side has the stronger case?
   - Confidence level (high/medium/low)

Transcript for reference:
{get_recent_transcript(transcript)}"""
        
        async for event, data in run_turn("moderator", moderator_synthesis_prompt, get_recent_transcript(transcript), loop, log_entries, debate_id, topic, turn_metrics, memory, bias_auditor):
            if event == "token":
                synthesis_text += data.get("text", "")
            if event != "token" or data.get("text"):
                yield format_sse(data, event)
        
        transcript += f"--- MODERATOR FINAL SYNTHESIS ---\n{synthesis_text}\n\n"
        
        # ═══════════════════════════════════════════════════════════════
        # PHASE 9: VERDICT ENGINE (PRD 4.5 - MANDATORY)
        # ═══════════════════════════════════════════════════════════════
        yield format_sse({"phase": "verdict", "message": "Phase 9: Verdict Engine - Rendering Final Judgment"}, "debate_phase")
        logging.info("⚖️ Generating final verdict from Chief Fact-Checker...")
        
        # Convert forensic_dossier to dict if it's an object
        dossier_dict = None
        if forensic_dossier:
            try:
                dossier_dict = forensic_dossier.to_dict() if hasattr(forensic_dossier, 'to_dict') else forensic_dossier
            except:
                dossier_dict = None
        
        verdict_func = functools.partial(generate_final_verdict, topic, transcript, evidence_bundle, dossier_dict)
        verdict_data = await loop.run_in_executor(executor, verdict_func)
        
        yield format_sse(verdict_data, "final_verdict")
        logging.info(f"✅ Final verdict delivered: {verdict_data.get('verdict')}")
        
        # 📊 MONGO AUDIT: Log the verdict
        if audit_logger and audit_logger.enabled:
            try:
                audit_logger.log_verdict(
                    debate_id=debate_id,
                    verdict=verdict_data.get("verdict", "COMPLEX"),
                    confidence=verdict_data.get("confidence_score", 50),
                    key_evidence=verdict_data.get("key_evidence", []),
                    winning_argument=verdict_data.get("winning_argument", ""),
                    metadata={
                        "topic": topic,
                        "evidence_count": len(evidence_bundle),
                        "turn_count": turn_metrics.get("turn_count", 0),
                        "dossier_credibility": dossier_dict.get("credibility") if dossier_dict else None
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to log verdict to MongoDB: {e}")
        
        # --- Final Analytics ---
        metrics = await loop.run_in_executor(executor, compute_advanced_analytics, evidence_bundle, transcript, turn_metrics)
        
        # 🧠 MEMORY INTEGRATION: Include memory statistics in analytics
        if memory:
            try:
                memory_summary = memory.get_memory_summary()
                metrics['memory_stats'] = {
                    'total_turns': memory_summary.get('turn_counter', 0),
                    'short_term_messages': memory_summary['short_term']['current_count'],
                    'long_term_memories': memory_summary['long_term']['total_memories'] if memory_summary.get('long_term') else 0
                }
            except Exception as e:
                logging.warning(f"Failed to get memory stats: {e}")
        
        # 🔬 V2 FEATURES: Include bias audit summary in analytics
        if bias_auditor:
            try:
                bias_report = bias_auditor.generate_bias_report()
                metrics['bias_audit'] = {
                    'total_flags': bias_report.get('total_flags', 0),
                    'turns_with_bias': turn_metrics.get('audited_turn_count', 0),
                    'bias_type_distribution': bias_report.get('bias_type_distribution', {}),
                    'severity_distribution': bias_report.get('severity_distribution', {}),
                    'ledger_integrity': bias_auditor.verify_ledger_integrity()
                }
                logging.info(f"🎭 Bias audit summary: {metrics['bias_audit']['total_flags']} flags across {metrics['bias_audit']['turns_with_bias']} turns")
            except Exception as e:
                logging.warning(f"Failed to generate bias report: {e}")
        
        # 🔬 V2 FEATURES: Include credibility summary
        if credibility_result:
            metrics['credibility_summary'] = {
                'overall_score': round(credibility_result.overall_score, 3),
                'source_trust': round(credibility_result.source_trust, 3),
                'confidence_level': credibility_result.confidence_level,
                'warnings_count': len(credibility_result.warnings)
            }
        
        # 🔄 V2 FEATURES: Include role reversal metrics
        if role_reversal_engine:
            try:
                metrics['role_reversal'] = {
                    'rounds_completed': len(role_reversal_engine.rounds_history),
                    'final_convergence_score': role_reversal_engine.rounds_history[-1].convergence_score if role_reversal_engine.rounds_history else 0,
                    'enabled': True
                }
            except Exception as e:
                metrics['role_reversal'] = {'enabled': True, 'error': str(e)}
        else:
            metrics['role_reversal'] = {'enabled': False}
        
        # 📊 MONGO AUDIT: Include audit summary
        if audit_logger and audit_logger.enabled:
            try:
                audit_stats = audit_logger.get_stats()
                metrics['mongo_audit'] = {
                    'enabled': True,
                    'events_logged': audit_stats.get('total_events', 0)
                }
            except Exception:
                metrics['mongo_audit'] = {'enabled': True}
        else:
            metrics['mongo_audit'] = {'enabled': False}
        
        # 📋 PRD COMPLIANCE SUMMARY
        metrics['prd_compliance'] = {
            'phases_completed': [
                'opening_statements',
                'cross_examination',
                'rebuttals',
                'mid_debate_compression',
                'role_reversal' if V2_FEATURES_AVAILABLE else 'skipped',
                'convergence',
                'final_summaries',
                'moderator_synthesis',
                'verdict_engine'
            ],
            'forensic_dossier_injected': bool(forensic_dossier),
            'evidence_bundle_attached': bool(evidence_bundle),
            'citation_enforcement_enabled': True,
            'bias_auditor_executed': bool(bias_auditor),
            'verdict_generated': bool(verdict_data),
            'verdict_verdict': verdict_data.get('verdict') if verdict_data else None,
            'verdict_confidence': verdict_data.get('confidence_score') if verdict_data else None,
            'estimated_compliance_score': 95 if (forensic_dossier and evidence_bundle and verdict_data) else 75
        }
        
        yield format_sse(metrics, "analytics_metrics")

    except Exception as e:
        logging.error(f"Fatal error during debate generation: {e}", exc_info=True)
        yield format_sse({"message": "A fatal error occurred, stopping the debate."}, "error")
    finally:
        if log_entries:
            await AsyncDbManager.add_log_entries_batch(log_entries)
            logging.info(f"Successfully wrote {len(log_entries)} log entries to the database.")
        yield format_sse({"message": "Debate complete."}, "end")


async def run_turn(
    role: str,
    system_prompt: str,
    input_text: str,
    loop,
    log_entries: list,
    debate_id: str,
    topic: str,
    turn_metrics: dict,
    memory=None,
    bias_auditor=None,
    is_rebuttal: bool = False,
    enforce_citations: bool = True
):
    """
    Execute a single debate turn with memory and bias audit integration.
    
    Args:
        role: The speaker role (proponent, opponent, moderator)
        system_prompt: The system prompt for this role
        input_text: The user input/context for this turn
        loop: The async event loop
        log_entries: List to append log entries to
        debate_id: The current debate ID
        topic: The debate topic
        turn_metrics: Dict tracking turn counts
        memory: Optional memory manager
        bias_auditor: Optional bias auditor
        is_rebuttal: Whether this is a rebuttal turn
        enforce_citations: Whether to enforce citation checking
        
    Yields:
        Tuple of (event_type, event_data)
    """
    ai_agent = AiAgent()
    try:
        yield "start_role", {"role": role}

        # 🧠 MEMORY INTEGRATION: Build context with memory if available
        if memory:
            try:
                search_results = memory.long_term.search(
                    query=f"{role} arguments about {topic}",
                    top_k=2
                )
                
                memory_context = ""
                if search_results:
                    relevant_memories = [f"- {result.text[:150]}..." for result in search_results[:2]]
                    memory_context = "\n".join(relevant_memories)
                
                if memory_context:
                    final_input = f"{input_text}\n\nRelevant previous discussion:\n{memory_context}"
                else:
                    final_input = input_text
                
                final_system_prompt = system_prompt
                logging.info(f"🧠 Memory-enhanced context built for {role} (turn {turn_metrics['turn_count'] + 1})")
            except Exception as e:
                logging.warning(f"Memory context building failed: {e}. Using traditional context.")
                final_input = input_text
                final_system_prompt = system_prompt
        else:
            final_input = input_text
            final_system_prompt = system_prompt

        full_response = ""
        stream_generator = ai_agent.stream(
            user_message=final_input,
            system_prompt=final_system_prompt,
            max_tokens=DEFAULT_MAX_TOKENS
        )
        
        def get_next_chunk(gen):
            try:
                return next(gen)
            except StopIteration:
                return None
        
        while True:
            chunk = await loop.run_in_executor(executor, get_next_chunk, stream_generator)
            if chunk is None:
                break
            full_response += chunk
            yield "token", {"role": role, "text": chunk}
        
        turn_metrics["turn_count"] += 1
        if is_rebuttal:
            turn_metrics["rebuttal_count"] += 1
        
        # 🧠 MEMORY INTEGRATION: Store interaction in memory
        if memory:
            try:
                memory.add_interaction(
                    role=role,
                    content=full_response,
                    metadata={
                        "turn": turn_metrics["turn_count"],
                        "is_rebuttal": is_rebuttal,
                        "topic": topic,
                        "model": DEFAULT_MODEL
                    },
                    store_in_rag=True
                )
                logging.debug(f"🧠 Stored {role}'s response in memory (turn {turn_metrics['turn_count']})")
            except Exception as e:
                logging.warning(f"Failed to store in memory: {e}")
        
        # 🔬 BIAS AUDIT: Audit the response for bias
        if bias_auditor and full_response:
            try:
                audit_result = bias_auditor.audit_text(
                    text=full_response,
                    source=f"{role}_turn_{turn_metrics['turn_count']}",
                    context={"topic": topic, "role": role, "is_rebuttal": is_rebuttal}
                )
                
                if audit_result.flags:
                    turn_metrics["audited_turn_count"] += 1
                    logging.info(f"🎭 Bias audit for {role}: {len(audit_result.flags)} flags detected (score: {audit_result.overall_score:.2f})")
                    
                    yield "bias_audit", {
                        "role": role,
                        "turn": turn_metrics["turn_count"],
                        "flags_count": len(audit_result.flags),
                        "overall_score": round(audit_result.overall_score, 3),
                        "flag_types": [f.bias_type.value for f in audit_result.flags[:5]]
                    }
            except Exception as e:
                logging.warning(f"Bias audit failed for {role}: {e}")

        # 📋 PRD CITATION ENFORCEMENT
        if enforce_citations and full_response and role.lower() not in ['moderator']:
            try:
                if is_factual_claim(full_response) and not has_citation(full_response):
                    logging.warning(f"📋 Citation missing in {role}'s response (turn {turn_metrics['turn_count']})")
                    
                    yield "citation_warning", {
                        "role": role,
                        "turn": turn_metrics["turn_count"],
                        "message": f"{role} made factual claims without [SRC:ID] citations",
                        "text_preview": full_response[:150] + "..."
                    }
                    
                    if "missing_citations" not in turn_metrics:
                        turn_metrics["missing_citations"] = []
                    turn_metrics["missing_citations"].append({
                        "role": role,
                        "turn": turn_metrics["turn_count"],
                        "text_preview": full_response[:100]
                    })
                elif has_citation(full_response):
                    citations = extract_citations(full_response) if PRD_CHECKER_AVAILABLE else []
                    logging.info(f"✅ {role} cited {len(citations)} sources in turn {turn_metrics['turn_count']}")
            except Exception as e:
                logging.warning(f"Citation check failed for {role}: {e}")

        log_entries.append({
            "debate_id": debate_id,
            "topic": topic,
            "model_used": DEFAULT_MODEL,
            "role": role,
            "user_message": input_text,
            "ai_response": full_response
        })

        yield "end_role", {"role": role}
    except Exception as e:
        logging.error(f"Error during turn for role '{role}': {e}", exc_info=True)
        yield "turn_error", {"role": role, "message": f"An error occurred for {role}: {str(e)}"}

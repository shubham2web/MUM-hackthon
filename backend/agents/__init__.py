# agents/__init__.py
"""
Internal agents for ATLAS v4.1 reasoning pipeline.

Agents are used **internally** for multi-agent reasoning and should never be exposed
as Proponent/Opponent to end users.
"""

from .factual_analyst import FactualAnalyst
from .evidence_synthesizer import EvidenceSynthesizer
from .source_critic import SourceCritic
from .forensic_agent import ForensicAgent
from .bias_auditor_agent import BiasAuditorAgent
from .risk_assessor import RiskAssessor

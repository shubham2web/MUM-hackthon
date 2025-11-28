"""
MongoDB Audit Logger - Phase 3 Advanced Memory Features

Optional MongoDB integration for logging memory operations, debate events,
and audit trails. Provides persistence and analytics beyond the RAG vector store.

This module is OPTIONAL - memory system works without MongoDB.
Set MONGODB_URI in .env to enable.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Optional MongoDB dependency
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.warning("pymongo not installed. MongoDB audit logging disabled.")


class MongoAuditLogger:
    """
    Audit logger for memory operations using MongoDB.
    
    Logs:
    - Memory additions (with embeddings metadata)
    - Role reversals
    - Consistency checks
    - Debate session events
    
    Collections:
    - memory_events: All memory operations
    - debate_sessions: Debate metadata
    - consistency_alerts: Contradiction warnings
    """
    
    def __init__(self, connection_uri: Optional[str] = None):
        """
        Initialize MongoDB audit logger.
        
        Args:
            connection_uri: MongoDB connection string (e.g., mongodb://localhost:27017)
                           If None, reads from MONGODB_URI env variable
        """
        self.enabled = False
        self.client = None
        self.db = None
        
        if not MONGODB_AVAILABLE:
            logger.info("MongoDB audit logging unavailable (pymongo not installed)")
            return
        
        # Get connection URI
        uri = connection_uri or os.getenv('MONGODB_URI')
        
        if not uri:
            logger.info("MongoDB audit logging disabled (no MONGODB_URI configured)")
            return
        
        try:
            # Connect to MongoDB
            self.client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            
            # Test connection
            self.client.admin.command('ping')
            
            # Get database
            db_name = os.getenv('MONGODB_DATABASE', 'atlas_memory')
            self.db = self.client[db_name]
            
            # Create indexes
            self._create_indexes()
            
            self.enabled = True
            logger.info(f"✅ MongoDB audit logging enabled (database: {db_name})")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"MongoDB connection failed: {e}. Audit logging disabled.")
            self.enabled = False
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e}")
            self.enabled = False
    
    def _create_indexes(self):
        """Create indexes for efficient queries"""
        if not self.enabled:
            return
        
        try:
            # Memory events indexes
            self.db.memory_events.create_index([("debate_id", 1), ("timestamp", -1)])
            self.db.memory_events.create_index([("role", 1)])
            self.db.memory_events.create_index([("event_type", 1)])
            
            # Debate sessions indexes
            self.db.debate_sessions.create_index([("debate_id", 1)], unique=True)
            self.db.debate_sessions.create_index([("created_at", -1)])
            
            # Consistency alerts indexes
            self.db.consistency_alerts.create_index([("debate_id", 1), ("timestamp", -1)])
            self.db.consistency_alerts.create_index([("role", 1)])
            
        except Exception as e:
            logger.error(f"Error creating MongoDB indexes: {e}")
    
    def log_memory_addition(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        debate_id: Optional[str] = None,
        memory_id: Optional[str] = None
    ):
        """Log when memory is added to the system"""
        if not self.enabled:
            return
        
        try:
            event = {
                "event_type": "memory_added",
                "debate_id": debate_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "memory_id": memory_id,
                "timestamp": datetime.utcnow()
            }
            
            self.db.memory_events.insert_one(event)
            logger.debug(f"Logged memory addition: {role} - {content[:50]}...")
            
        except Exception as e:
            logger.error(f"Error logging memory addition: {e}")
    
    def log_role_reversal(
        self,
        current_role: str,
        previous_role: str,
        debate_id: Optional[str] = None,
        previous_args_count: int = 0
    ):
        """Log when agent switches roles"""
        if not self.enabled:
            return
        
        try:
            event = {
                "event_type": "role_reversal",
                "debate_id": debate_id,
                "current_role": current_role,
                "previous_role": previous_role,
                "previous_args_count": previous_args_count,
                "timestamp": datetime.utcnow()
            }
            
            self.db.memory_events.insert_one(event)
            logger.debug(f"Logged role reversal: {previous_role} → {current_role}")
            
        except Exception as e:
            logger.error(f"Error logging role reversal: {e}")
    
    def log_consistency_check(
        self,
        role: str,
        new_statement: str,
        has_inconsistencies: bool,
        consistency_score: float,
        warnings: List[str],
        debate_id: Optional[str] = None
    ):
        """Log consistency check results"""
        if not self.enabled:
            return
        
        try:
            event = {
                "event_type": "consistency_check",
                "debate_id": debate_id,
                "role": role,
                "new_statement": new_statement,
                "has_inconsistencies": has_inconsistencies,
                "consistency_score": consistency_score,
                "warnings": warnings,
                "timestamp": datetime.utcnow()
            }
            
            self.db.memory_events.insert_one(event)
            
            # If inconsistencies found, also log to alerts collection
            if has_inconsistencies:
                alert = {
                    "debate_id": debate_id,
                    "role": role,
                    "statement": new_statement,
                    "consistency_score": consistency_score,
                    "warnings": warnings,
                    "timestamp": datetime.utcnow()
                }
                self.db.consistency_alerts.insert_one(alert)
            
            logger.debug(f"Logged consistency check: {role} - inconsistencies={has_inconsistencies}")
            
        except Exception as e:
            logger.error(f"Error logging consistency check: {e}")
    
    def log_debate_session(
        self,
        debate_id: str,
        topic: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log debate session creation"""
        if not self.enabled:
            return
        
        try:
            session = {
                "debate_id": debate_id,
                "topic": topic,
                "metadata": metadata or {},
                "created_at": datetime.utcnow(),
                "status": "active"
            }
            
            # Upsert (update if exists, insert if not)
            self.db.debate_sessions.update_one(
                {"debate_id": debate_id},
                {"$set": session},
                upsert=True
            )
            
            logger.debug(f"Logged debate session: {debate_id}")
            
        except Exception as e:
            logger.error(f"Error logging debate session: {e}")
    
    def get_debate_history(self, debate_id: str) -> List[Dict[str, Any]]:
        """Get all events for a debate session"""
        if not self.enabled:
            return []
        
        try:
            events = list(
                self.db.memory_events
                .find({"debate_id": debate_id})
                .sort("timestamp", 1)
            )
            
            # Convert ObjectId to string for JSON serialization
            for event in events:
                event['_id'] = str(event['_id'])
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting debate history: {e}")
            return []
    
    def get_consistency_alerts(
        self,
        debate_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent consistency alerts"""
        if not self.enabled:
            return []
        
        try:
            query = {}
            if debate_id:
                query['debate_id'] = debate_id
            
            alerts = list(
                self.db.consistency_alerts
                .find(query)
                .sort("timestamp", -1)
                .limit(limit)
            )
            
            # Convert ObjectId to string
            for alert in alerts:
                alert['_id'] = str(alert['_id'])
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting consistency alerts: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics"""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            total_events = self.db.memory_events.count_documents({})
            total_sessions = self.db.debate_sessions.count_documents({})
            total_alerts = self.db.consistency_alerts.count_documents({})
            
            # Get event type breakdown
            event_types = list(
                self.db.memory_events.aggregate([
                    {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
                ])
            )
            
            return {
                "enabled": True,
                "total_events": total_events,
                "total_sessions": total_sessions,
                "total_alerts": total_alerts,
                "event_types": {e['_id']: e['count'] for e in event_types}
            }
            
        except Exception as e:
            logger.error(f"Error getting audit stats: {e}")
            return {"enabled": True, "error": str(e)}
    
    def log_rag_retrieval(
        self,
        debate_id: str,
        query: str,
        results_count: int,
        top_scores: List[float],
        retrieval_method: str = "hybrid",
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log RAG retrieval quality metrics (PRD Section 2.1).
        
        Args:
            debate_id: The debate session ID
            query: The query used for retrieval
            results_count: Number of results returned
            top_scores: Relevance scores of top results
            retrieval_method: Type of retrieval (hybrid, semantic, keyword)
            latency_ms: Retrieval latency in milliseconds
            metadata: Additional metadata
        """
        if not self.enabled:
            return
        
        try:
            event = {
                "event_type": "rag_retrieval",
                "debate_id": debate_id,
                "query": query[:500],  # Truncate long queries
                "results_count": results_count,
                "top_scores": top_scores[:10],  # Top 10 scores
                "avg_score": sum(top_scores) / len(top_scores) if top_scores else 0,
                "retrieval_method": retrieval_method,
                "latency_ms": latency_ms,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow()
            }
            
            self.db.memory_events.insert_one(event)
            logger.debug(f"Logged RAG retrieval: {results_count} results, avg_score={event['avg_score']:.3f}")
            
        except Exception as e:
            logger.error(f"Error logging RAG retrieval: {e}")
    
    def log_verdict(
        self,
        debate_id: str,
        verdict: str,
        confidence: float,
        key_evidence: List[str],
        winning_argument: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log final verdict (PRD Section 2.6).
        
        Args:
            debate_id: The debate session ID
            verdict: VERIFIED, DEBUNKED, or COMPLEX
            confidence: Confidence score 0-100
            key_evidence: List of key evidence points
            winning_argument: The winning argument summary
            metadata: Additional metadata
        """
        if not self.enabled:
            return
        
        try:
            event = {
                "event_type": "verdict",
                "debate_id": debate_id,
                "verdict": verdict,
                "confidence": confidence,
                "key_evidence": key_evidence[:5],  # Top 5 evidence
                "winning_argument": winning_argument[:1000],
                "metadata": metadata or {},
                "timestamp": datetime.utcnow()
            }
            
            self.db.memory_events.insert_one(event)
            
            # Also update the debate session with verdict
            self.db.debate_sessions.update_one(
                {"debate_id": debate_id},
                {"$set": {
                    "verdict": verdict,
                    "confidence": confidence,
                    "completed_at": datetime.utcnow(),
                    "status": "completed"
                }}
            )
            
            logger.debug(f"Logged verdict: {verdict} (confidence={confidence})")
            
        except Exception as e:
            logger.error(f"Error logging verdict: {e}")
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# Global instance (lazy initialization)
_audit_logger: Optional[MongoAuditLogger] = None


def get_audit_logger() -> MongoAuditLogger:
    """Get or create the global audit logger instance"""
    global _audit_logger
    
    if _audit_logger is None:
        _audit_logger = MongoAuditLogger()
    
    return _audit_logger

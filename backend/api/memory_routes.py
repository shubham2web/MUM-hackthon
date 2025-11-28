"""
API Routes for Hybrid Memory System

Provides REST endpoints for memory management and diagnostics.
"""
from __future__ import annotations

import logging
from typing import Optional
from quart import Blueprint, request, jsonify

from memory.memory_manager import get_memory_manager

# Create blueprint
memory_bp = Blueprint('memory', __name__, url_prefix='/memory')
logger = logging.getLogger(__name__)


@memory_bp.route('/status', methods=['GET'])
async def get_memory_status():
    """
    Get current memory system status and statistics.
    
    GET /memory/status
    
    Returns:
        {
            "status": "ok",
            "memory_summary": {...},
            "rag_enabled": true
        }
    """
    try:
        memory_manager = get_memory_manager()
        summary = memory_manager.get_memory_summary()
        
        return jsonify({
            "status": "ok",
            "memory_summary": summary,
            "rag_enabled": memory_manager.enable_rag
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting memory status: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/search', methods=['POST'])
async def search_memories():
    """
    Search long-term memory with semantic similarity.
    
    POST /memory/search
    Body: {
        "query": "What was discussed about climate change?",
        "top_k": 10,
        "filter": {"role": "proponent"}  // optional
    }
    
    Returns:
        {
            "results": [
                {
                    "id": "...",
                    "text": "...",
                    "score": 0.85,
                    "rank": 1,
                    "metadata": {...}
                }
            ],
            "query": "...",
            "count": 10
        }
    """
    try:
        data = await request.get_json()
        query = data.get('query')
        
        if not query:
            return jsonify({"error": "Missing 'query' field"}), 400
        
        top_k = data.get('top_k', 10)
        filter_metadata = data.get('filter')
        
        memory_manager = get_memory_manager()
        
        if not memory_manager.enable_rag:
            return jsonify({"error": "RAG is not enabled"}), 503
        
        results = memory_manager.search_memories(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
        
        return jsonify({
            "results": results,
            "query": query,
            "count": len(results)
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/context', methods=['POST'])
async def build_context():
    """
    Build 4-zone context payload for a given task.
    
    POST /memory/context
    Body: {
        "system_prompt": "You are...",
        "current_task": "Analyze this claim...",
        "query": "What evidence supports this?",  // optional
        "top_k_rag": 4,
        "use_short_term": true,
        "use_long_term": true
    }
    
    Returns:
        {
            "context_payload": "...",
            "zones_included": ["zone1", "zone2", "zone3", "zone4"],
            "token_estimate": 1234
        }
    """
    try:
        data = await request.get_json()
        
        system_prompt = data.get('system_prompt', '')
        current_task = data.get('current_task', '')
        
        if not current_task:
            return jsonify({"error": "Missing 'current_task' field"}), 400
        
        query = data.get('query')
        top_k_rag = data.get('top_k_rag', 4)
        use_short_term = data.get('use_short_term', True)
        use_long_term = data.get('use_long_term', True)
        
        memory_manager = get_memory_manager()
        
        context_payload = memory_manager.build_context_payload(
            system_prompt=system_prompt,
            current_task=current_task,
            query=query,
            top_k_rag=top_k_rag,
            use_short_term=use_short_term,
            use_long_term=use_long_term
        )
        
        # Estimate tokens (rough: ~4 chars per token)
        token_estimate = len(context_payload) // 4
        
        zones_included = ["zone1", "zone4"]  # Always included
        if use_long_term and memory_manager.enable_rag:
            zones_included.append("zone2")
        if use_short_term and len(memory_manager.short_term) > 0:
            zones_included.append("zone3")
        
        return jsonify({
            "context_payload": context_payload,
            "zones_included": zones_included,
            "token_estimate": token_estimate
        }), 200
        
    except Exception as e:
        logger.error(f"Error building context: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/add', methods=['POST'])
async def add_interaction():
    """
    Add an interaction to memory system.
    
    POST /memory/add
    Body: {
        "role": "proponent",
        "content": "I believe that...",
        "metadata": {"custom": "data"},
        "store_in_rag": true
    }
    
    Returns:
        {
            "success": true,
            "result": {
                "role": "proponent",
                "turn": 5,
                "short_term": "added",
                "long_term": "uuid..."
            }
        }
    """
    try:
        data = await request.get_json()
        
        role = data.get('role')
        content = data.get('content')
        
        if not role or not content:
            return jsonify({"error": "Missing 'role' or 'content'"}), 400
        
        metadata = data.get('metadata')
        store_in_rag = data.get('store_in_rag', True)
        
        memory_manager = get_memory_manager()
        
        result = memory_manager.add_interaction(
            role=role,
            content=content,
            metadata=metadata,
            store_in_rag=store_in_rag
        )
        
        return jsonify({
            "success": True,
            "result": result
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding interaction: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/clear', methods=['POST'])
async def clear_memory():
    """
    Clear memory (short-term, long-term, or both).
    
    POST /memory/clear
    Body: {
        "target": "short_term" | "long_term" | "all"
    }
    
    Returns:
        {
            "success": true,
            "message": "Memory cleared",
            "target": "all"
        }
    """
    try:
        data = await request.get_json()
        target = data.get('target', 'short_term')
        
        memory_manager = get_memory_manager()
        
        if target == 'short_term':
            memory_manager.clear_short_term()
        elif target == 'long_term':
            memory_manager.clear_long_term()
        elif target == 'all':
            memory_manager.clear_all_memory()
        else:
            return jsonify({"error": f"Invalid target: {target}"}), 400
        
        return jsonify({
            "success": True,
            "message": f"{target.replace('_', '-')} memory cleared",
            "target": target
        }), 200
        
    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/debate/start', methods=['POST'])
async def start_debate():
    """
    Initialize memory for a new debate session.
    
    POST /memory/debate/start
    Body: {
        "debate_id": "debate_123",
        "clear_previous": false
    }
    
    Returns:
        {
            "success": true,
            "debate_id": "debate_123",
            "message": "Debate context initialized"
        }
    """
    try:
        data = await request.get_json()
        debate_id = data.get('debate_id')
        
        if not debate_id:
            return jsonify({"error": "Missing 'debate_id'"}), 400
        
        clear_previous = data.get('clear_previous', False)
        
        memory_manager = get_memory_manager()
        
        if clear_previous:
            memory_manager.clear_short_term()
        
        memory_manager.set_debate_context(debate_id)
        
        return jsonify({
            "success": True,
            "debate_id": debate_id,
            "message": "Debate context initialized"
        }), 200
        
    except Exception as e:
        logger.error(f"Error starting debate: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/export', methods=['GET'])
async def export_memory():
    """
    Export memory state for debugging/persistence.
    
    GET /memory/export
    
    Returns:
        {
            "debate_id": "...",
            "turn_counter": 10,
            "short_term": {...},
            "timestamp": "..."
        }
    """
    try:
        memory_manager = get_memory_manager()
        state = memory_manager.export_memory_state()
        
        return jsonify(state), 200
        
    except Exception as e:
        logger.error(f"Error exporting memory: {e}")
        return jsonify({"error": str(e)}), 500


# Health check for memory system
@memory_bp.route('/health', methods=['GET'])
async def memory_health():
    """Check if memory system is operational"""
    try:
        memory_manager = get_memory_manager()
        return jsonify({
            "status": "healthy",
            "rag_enabled": memory_manager.enable_rag,
            "short_term_size": len(memory_manager.short_term)
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


# -----------------------------
# PHASE 2: Role Reversal Support
# -----------------------------

@memory_bp.route('/role/history', methods=['POST'])
async def get_role_history():
    """
    Get all historical memories for a specific role.
    
    POST /memory/role/history
    Body: {
        "role": "proponent",
        "debate_id": "debate_123"  // optional
    }
    
    Returns:
        {
            "role": "proponent",
            "memories": [...],
            "count": 10
        }
    """
    try:
        data = await request.get_json()
        role = data.get('role')
        
        if not role:
            return jsonify({"error": "Missing 'role' field"}), 400
        
        debate_id = data.get('debate_id')
        
        memory_manager = get_memory_manager()
        history = memory_manager.get_role_history(role, debate_id)
        
        return jsonify({
            "role": role,
            "memories": history,
            "count": len(history)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting role history: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/role/reversal', methods=['POST'])
async def build_role_reversal_context():
    """
    Build specialized context for role reversal scenarios.
    
    POST /memory/role/reversal
    Body: {
        "current_role": "opponent",
        "previous_role": "proponent",
        "system_prompt": "You are now the opponent...",
        "current_task": "Argue against renewable energy...",
        "debate_id": "debate_123"  // optional
    }
    
    Returns:
        {
            "context_payload": "...",
            "previous_arguments_count": 5,
            "role_switch": "proponent → opponent"
        }
    """
    try:
        data = await request.get_json()
        
        current_role = data.get('current_role')
        previous_role = data.get('previous_role')
        system_prompt = data.get('system_prompt', '')
        current_task = data.get('current_task', '')
        
        if not current_role or not previous_role:
            return jsonify({
                "error": "Missing 'current_role' or 'previous_role' field"
            }), 400
        
        if not current_task:
            return jsonify({"error": "Missing 'current_task' field"}), 400
        
        debate_id = data.get('debate_id')
        
        memory_manager = get_memory_manager()
        
        # Get previous arguments count
        previous_args = memory_manager.get_role_history(previous_role, debate_id)
        
        # Build role reversal context
        context_payload = memory_manager.build_role_reversal_context(
            current_role=current_role,
            previous_role=previous_role,
            system_prompt=system_prompt,
            current_task=current_task,
            debate_id=debate_id
        )
        
        return jsonify({
            "context_payload": context_payload,
            "previous_arguments_count": len(previous_args),
            "role_switch": f"{previous_role} → {current_role}",
            "token_estimate": len(context_payload) // 4
        }), 200
        
    except Exception as e:
        logger.error(f"Error building role reversal context: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/consistency/check', methods=['POST'])
async def check_consistency():
    """
    Check for potential contradictions in a role's statements.
    
    POST /memory/consistency/check
    Body: {
        "role": "proponent",
        "new_statement": "Actually, fossil fuels are better...",
        "debate_id": "debate_123",  // optional
        "threshold": 0.3  // optional, similarity threshold
    }
    
    Returns:
        {
            "has_inconsistencies": true,
            "consistency_score": 0.6,
            "warnings": ["Potential contradiction with Turn 3: ..."],
            "related_statements": [...]
        }
    """
    try:
        data = await request.get_json()
        
        role = data.get('role')
        new_statement = data.get('new_statement')
        
        if not role:
            return jsonify({"error": "Missing 'role' field"}), 400
        
        if not new_statement:
            return jsonify({"error": "Missing 'new_statement' field"}), 400
        
        debate_id = data.get('debate_id')
        threshold = data.get('threshold', 0.3)
        
        memory_manager = get_memory_manager()
        
        result = memory_manager.detect_memory_inconsistencies(
            role=role,
            new_statement=new_statement,
            debate_id=debate_id,
            threshold=threshold
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error checking consistency: {e}")
        return jsonify({"error": str(e)}), 500


# -----------------------------
# PHASE 3: Advanced Features (Diagnostics & Optimization)
# -----------------------------

@memory_bp.route('/diagnostics', methods=['GET'])
async def get_diagnostics():
    """
    Get memory system diagnostics and performance metrics.
    
    GET /memory/diagnostics
    
    Returns:
        {
            "memory_usage": {...},
            "performance": {...},
            "audit_stats": {...}  // if MongoDB enabled
        }
    """
    try:
        memory_manager = get_memory_manager()
        
        # Basic diagnostics
        diagnostics = {
            "memory_usage": {
                "short_term_messages": len(memory_manager.short_term),
                "short_term_window": memory_manager.short_term.window_size,
                "rag_enabled": memory_manager.enable_rag
            },
            "debate_context": {
                "current_debate_id": memory_manager.current_debate_id,
                "turn_counter": memory_manager.turn_counter
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add long-term memory stats if RAG is enabled
        if memory_manager.enable_rag and memory_manager.vector_store:
            try:
                # Get collection stats from vector store
                collection_info = memory_manager.vector_store.collection.get()
                diagnostics["long_term_memory"] = {
                    "total_memories": len(collection_info['ids']) if collection_info else 0,
                    "backend": memory_manager.vector_store.backend
                }
            except Exception as e:
                logger.warning(f"Could not get long-term memory stats: {e}")
        
        # Add MongoDB audit stats if available
        try:
            from memory.mongo_audit import get_audit_logger
            audit_logger = get_audit_logger()
            
            if audit_logger.enabled:
                diagnostics["audit_stats"] = audit_logger.get_stats()
        except Exception as e:
            logger.debug(f"MongoDB audit stats unavailable: {e}")
        
        return jsonify(diagnostics), 200
        
    except Exception as e:
        logger.error(f"Error getting diagnostics: {e}")
        return jsonify({"error": str(e)}), 500


@memory_bp.route('/optimize', methods=['POST'])
async def optimize_memory():
    """
    Trigger memory optimization operations.
    
    POST /memory/optimize
    Body: {
        "operation": "truncate_low_value" | "deduplicate" | "compress",
        "threshold": 0.5  // optional, for low-value truncation
    }
    
    Returns:
        {
            "success": true,
            "operation": "truncate_low_value",
            "items_removed": 10,
            "message": "Optimization complete"
        }
    """
    try:
        data = await request.get_json()
        operation = data.get('operation', 'truncate_low_value')
        
        memory_manager = get_memory_manager()
        
        result = {
            "success": True,
            "operation": operation
        }
        
        if operation == 'truncate_low_value':
            # Remove memories below a relevance threshold
            threshold = data.get('threshold', 0.3)
            current_context = data.get('current_context', '')
            
            optimization_result = memory_manager.truncate_low_value_memories(
                threshold=threshold,
                current_context=current_context
            )
            
            result.update(optimization_result)
            result["message"] = f"Truncated {optimization_result['removed_count']} low-value memories"
            result["tokens_saved"] = optimization_result.get('tokens_saved_estimate', 0)
            
        elif operation == 'deduplicate':
            # Remove duplicate or near-duplicate memories
            similarity_threshold = data.get('similarity_threshold', 0.95)
            
            optimization_result = memory_manager.deduplicate_memories(
                similarity_threshold=similarity_threshold
            )
            
            result.update(optimization_result)
            result["message"] = f"Removed {optimization_result['removed_count']} duplicate memories"
            result["tokens_saved"] = optimization_result.get('tokens_saved_estimate', 0)
            
        elif operation == 'compress':
            # Summarize old memories to save tokens
            age_threshold = data.get('age_threshold', 20)
            compression_ratio = data.get('compression_ratio', 0.5)
            
            optimization_result = memory_manager.compress_old_memories(
                age_threshold=age_threshold,
                compression_ratio=compression_ratio
            )
            
            result.update(optimization_result)
            result["message"] = f"Compressed {optimization_result['compressed_count']} old memories"
            result["tokens_saved"] = optimization_result.get('tokens_saved', 0)
            
        else:
            return jsonify({
                "error": f"Unknown operation: {operation}. " +
                        "Valid: truncate_low_value, deduplicate, compress"
            }), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error optimizing memory: {e}")
        return jsonify({"error": str(e)}), 500


# Import datetime for diagnostics endpoint
from datetime import datetime

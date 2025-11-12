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

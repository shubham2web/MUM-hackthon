"""
ATLAS v2.0 API Routes

New endpoints for enhanced features:
- /v2/analyze - Full v2.0 analysis with credibility scoring
- /v2/credibility - Standalone credibility check
- /v2/roles - Get available roles
- /v2/bias-report - Get bias audit report
- /v2/reversal - Conduct role reversal debate
"""
from quart import Blueprint, request, jsonify
import logging

# Import v2.0 integration
from atlas_v2_integration import atlas_v2
from credibility_engine import score_claim_credibility
from role_library import get_debate_roles, role_library
from bias_auditor import bias_auditor

# Create blueprint
v2_bp = Blueprint('v2', __name__, url_prefix='/v2')
logger = logging.getLogger(__name__)


@v2_bp.route('/analyze', methods=['POST'])
async def analyze_v2():
    """
    Full ATLAS v2.0 analysis with all enhanced features.
    
    Request body:
    {
        "claim": "The claim to analyze",
        "num_agents": 4,  // optional
        "enable_reversal": true,  // optional
        "reversal_rounds": 1  // optional
    }
    """
    try:
        data = await request.get_json()
        claim = data.get('claim', '')
        
        if not claim:
            return jsonify({'error': 'Claim text is required'}), 400
        
        num_agents = data.get('num_agents', 4)
        enable_reversal = data.get('enable_reversal', True)
        reversal_rounds = data.get('reversal_rounds', 1)
        
        logger.info(f"V2 Analysis requested for: {claim}")
        
        # Run full v2.0 analysis
        result = await atlas_v2.analyze_claim_v2(
            claim=claim,
            num_agents=num_agents,
            enable_reversal=enable_reversal,
            reversal_rounds=reversal_rounds
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error in v2/analyze: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@v2_bp.route('/credibility', methods=['POST'])
async def check_credibility():
    """
    Standalone credibility scoring endpoint.
    
    Request body:
    {
        "claim": "Claim to check",
        "sources": [
            {
                "url": "...",
                "domain": "...",
                "content": "...",
                "timestamp": "..."  // optional
            }
        ],
        "evidence_texts": ["evidence snippet 1", "evidence snippet 2"]
    }
    """
    try:
        data = await request.get_json()
        claim = data.get('claim', '')
        sources = data.get('sources', [])
        evidence_texts = data.get('evidence_texts', [])
        
        if not claim:
            return jsonify({'error': 'Claim is required'}), 400
        
        logger.info(f"Credibility check for: {claim}")
        
        # Calculate credibility score
        score_result = score_claim_credibility(
            claim=claim,
            sources=sources,
            evidence_texts=evidence_texts
        )
        
        return jsonify(score_result), 200
        
    except Exception as e:
        logger.error(f"Error in v2/credibility: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@v2_bp.route('/roles', methods=['GET'])
async def get_roles():
    """
    Get available debate roles.
    
    Query params:
    - topic: Optional topic to get relevant roles
    - num_agents: Number of agents to return
    """
    try:
        topic = request.args.get('topic', '')
        num_agents = int(request.args.get('num_agents', 4))
        
        if topic:
            roles = get_debate_roles(topic, num_agents)
        else:
            # Return all available roles
            roles = [
                {
                    'name': role.name,
                    'description': role.description,
                    'expertise': role.expertise_level.name,
                    'domains': role.domains,
                    'prompt': role.system_prompt[:200] + '...'  # Truncated
                }
                for role in role_library.roles.values()
            ]
        
        return jsonify({'roles': roles}), 200
        
    except Exception as e:
        logger.error(f"Error in v2/roles: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@v2_bp.route('/bias-report', methods=['GET'])
async def get_bias_report():
    """
    Get comprehensive bias audit report.
    
    Query params:
    - entity: Optional entity name to get specific profile
    """
    try:
        entity = request.args.get('entity')
        
        if entity:
            # Get specific entity profile
            profile = bias_auditor.get_bias_profile(entity)
            if not profile:
                return jsonify({'error': f'No profile found for {entity}'}), 404
            
            recommendations = bias_auditor.get_mitigation_recommendations(entity)
            
            return jsonify({
                'entity': entity,
                'total_flags': profile.total_flags,
                'reputation_score': profile.reputation_score,
                'bias_counts': {bt.value: count for bt, count in profile.bias_counts.items()},
                'severity_distribution': {sev.name: count for sev, count in profile.severity_distribution.items()},
                'recommendations': recommendations
            }), 200
        else:
            # Get full report
            report = bias_auditor.generate_bias_report()
            return jsonify(report), 200
        
    except Exception as e:
        logger.error(f"Error in v2/bias-report: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@v2_bp.route('/bias-ledger', methods=['GET'])
async def get_bias_ledger():
    """
    Get bias ledger for transparency.
    
    Query params:
    - verify: Set to 'true' to verify ledger integrity
    """
    try:
        verify = request.args.get('verify', 'false').lower() == 'true'
        
        if verify:
            is_valid = bias_auditor.verify_ledger_integrity()
            return jsonify({
                'ledger_size': len(bias_auditor.bias_ledger),
                'integrity_verified': is_valid
            }), 200
        else:
            ledger_data = bias_auditor.bias_ledger
            return jsonify({
                'ledger_size': len(ledger_data),
                'entries': ledger_data[-10:]  # Last 10 entries
            }), 200
        
    except Exception as e:
        logger.error(f"Error in v2/bias-ledger: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@v2_bp.route('/reversal-debate', methods=['POST'])
async def conduct_reversal():
    """
    Conduct a role reversal debate.
    
    Request body:
    {
        "topic": "Debate topic",
        "rounds": 2,  // optional, number of reversal rounds
        "agents": 4  // optional, number of agents
    }
    """
    try:
        data = await request.get_json()
        topic = data.get('topic', '')
        rounds = data.get('rounds', 2)
        num_agents = data.get('agents', 4)
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        logger.info(f"Role reversal debate on: {topic}")
        
        # Conduct analysis with focus on reversal
        result = await atlas_v2.analyze_claim_v2(
            claim=topic,
            num_agents=num_agents,
            enable_reversal=True,
            reversal_rounds=rounds
        )
        
        # Return focused on reversal results
        return jsonify({
            'topic': topic,
            'reversal_rounds': result['role_reversal']['rounds'],
            'convergence': result['role_reversal']['convergence'],
            'synthesis': result['synthesis']
        }), 200
        
    except Exception as e:
        logger.error(f"Error in v2/reversal-debate: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@v2_bp.route('/status', methods=['GET'])
async def get_status():
    """Get ATLAS v2.0 system status."""
    try:
        status = atlas_v2.get_system_status()
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error in v2/status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@v2_bp.route('/health', methods=['GET'])
async def health_check():
    """Simple health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': '2.0',
        'message': 'ATLAS v2.0 is operational'
    }), 200

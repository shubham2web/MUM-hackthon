# backend/routes_admin.py
"""
Admin routes for ATLAS configuration management.

Provides endpoints for:
- Domain authority management
- System configuration
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from quart import Blueprint, request, jsonify, render_template

logger = logging.getLogger(__name__)

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Path to store domain authority config
CONFIG_DIR = Path(__file__).parent / "data"
DOMAIN_AUTHORITY_FILE = CONFIG_DIR / "domain_authority.json"

# Default domain authority map
DEFAULT_DOMAIN_AUTHORITY = {
    # Tier 1 - High authority (0.85-0.95)
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bbc.com": 0.90,
    "nytimes.com": 0.88,
    "washingtonpost.com": 0.88,
    "theguardian.com": 0.87,
    "wsj.com": 0.90,
    "economist.com": 0.88,
    "nature.com": 0.95,
    "science.org": 0.95,
    "gov": 0.92,
    "edu": 0.88,
    # Tier 2 - Medium authority (0.50-0.70)
    "cnn.com": 0.70,
    "foxnews.com": 0.60,
    "msnbc.com": 0.65,
    "ndtv.com": 0.65,
    "hindustantimes.com": 0.60,
    "timesofindia.com": 0.55,
    "wikipedia.org": 0.70,
    # Tier 3 - Low authority (0.20-0.40)
    "medium.com": 0.40,
    "substack.com": 0.35,
    "blogspot.com": 0.25,
    "wordpress.com": 0.25,
    "twitter.com": 0.30,
    "facebook.com": 0.20,
    "reddit.com": 0.35
}


def ensure_config_dir():
    """Ensure config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_domain_authority() -> dict:
    """Load domain authority map from file or return defaults."""
    ensure_config_dir()
    
    if DOMAIN_AUTHORITY_FILE.exists():
        try:
            with open(DOMAIN_AUTHORITY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load domain authority: {e}")
    
    return DEFAULT_DOMAIN_AUTHORITY.copy()


def save_domain_authority(domain_map: dict) -> bool:
    """Save domain authority map to file."""
    ensure_config_dir()
    
    try:
        with open(DOMAIN_AUTHORITY_FILE, 'w') as f:
            json.dump(domain_map, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save domain authority: {e}")
        return False


def get_domain_authority(domain: str) -> float:
    """
    Get authority score for a domain.
    This function is meant to be imported by other modules.
    """
    domain_map = load_domain_authority()
    
    # Direct match
    if domain in domain_map:
        return domain_map[domain]
    
    # Check TLD matches (e.g., .gov, .edu)
    for tld in ['gov', 'edu', 'org']:
        if domain.endswith(f'.{tld}') and tld in domain_map:
            return domain_map[tld]
    
    # Default for unknown domains
    return 0.50


@admin_bp.route('/')
async def admin_index():
    """Admin dashboard."""
    return await render_template('admin/domain-authority.html')


@admin_bp.route('/domain-authority')
async def domain_authority_page():
    """Domain authority admin page."""
    return await render_template('admin/domain-authority.html')


@admin_bp.route('/api/get-domain-authority', methods=['GET'])
async def get_domain_authority_api():
    """Get current domain authority map."""
    try:
        domain_map = load_domain_authority()
        return jsonify({
            "success": True,
            "domains": domain_map
        })
    except Exception as e:
        logger.error(f"Error getting domain authority: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/set-domain-authority', methods=['POST'])
async def set_domain_authority_api():
    """Update domain authority map."""
    try:
        data = await request.json
        
        if not isinstance(data, dict):
            return jsonify({"success": False, "error": "Invalid data format"}), 400
        
        # Validate values are between 0 and 1
        validated = {}
        for domain, authority in data.items():
            if not isinstance(domain, str):
                continue
            try:
                auth_value = float(authority)
                auth_value = max(0.0, min(1.0, auth_value))  # Clamp to [0, 1]
                validated[domain.lower().strip()] = round(auth_value, 2)
            except (ValueError, TypeError):
                continue
        
        if save_domain_authority(validated):
            logger.info(f"Domain authority updated: {len(validated)} domains")
            return jsonify({
                "success": True,
                "message": f"Updated {len(validated)} domains"
            })
        else:
            return jsonify({"success": False, "error": "Failed to save"}), 500
            
    except Exception as e:
        logger.error(f"Error setting domain authority: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/reset-domain-authority', methods=['POST'])
async def reset_domain_authority_api():
    """Reset domain authority to defaults."""
    try:
        if save_domain_authority(DEFAULT_DOMAIN_AUTHORITY.copy()):
            return jsonify({
                "success": True,
                "message": "Reset to defaults"
            })
        else:
            return jsonify({"success": False, "error": "Failed to save"}), 500
    except Exception as e:
        logger.error(f"Error resetting domain authority: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

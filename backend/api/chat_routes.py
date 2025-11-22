from quart import Blueprint, request, jsonify, current_app
from services import chat_store as store
import asyncio

chat_bp = Blueprint('chat_api', __name__, url_prefix='/api')


@chat_bp.route('/chats', methods=['GET'])
async def list_chats():
    chats = await store.list_chats()
    return jsonify({'chats': chats})


@chat_bp.route('/chats', methods=['POST'])
async def create_chat():
    body = await request.get_json() or {}
    title = body.get('title', 'New Chat')
    metadata = body.get('metadata')
    chat = await store.create_chat(title=title, metadata=metadata)
    return jsonify({'chat': chat}), 201


@chat_bp.route('/chats/<chat_id>', methods=['GET'])
async def get_chat(chat_id):
    chat = await store.get_chat(chat_id)
    if not chat:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'chat': chat})


@chat_bp.route('/chats/<chat_id>/messages', methods=['POST'])
async def add_message(chat_id):
    body = await request.get_json() or {}
    role = body.get('role', 'user')
    text = body.get('text', '')
    metadata = body.get('metadata')
    if not text:
        return jsonify({'error': 'empty text'}), 400
    chat = await store.append_message(chat_id, role, text, metadata)
    if not chat:
        return jsonify({'error': 'chat not found or update failed'}), 500
    return jsonify({'chat': chat})


@chat_bp.route('/chats/<chat_id>', methods=['DELETE'])
async def delete_chat(chat_id):
    ok = await store.delete_chat(chat_id)
    if not ok:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'deleted': True})


@chat_bp.route('/chats/clear', methods=['POST'])
async def clear_chats():
    # Administrative: clear all chats
    deleted = await store.clear_all_chats()
    return jsonify({'deleted_count': deleted})

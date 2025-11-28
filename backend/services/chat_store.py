"""Async chat persistence using MongoDB (motor).

Provides simple CRUD operations for chat sessions and messages.
Each chat document schema:
{
  _id: ObjectId,
  title: str,
  created_at: ISODate,
  updated_at: ISODate,
  metadata: {...},
  messages: [ { role: 'user'|'assistant', 'text': str, 'timestamp': ISODate, 'metadata': {...} }, ... ]
}

This service is intentionally small and focused. It uses the `MONGODB_URI`
environment variable (default: mongodb://localhost:27017) and the database
name `atlas_chat` with collection `chats`.
"""
from __future__ import annotations

import os
import json
import logging
import asyncio
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Try to use Motor (async MongoDB). If unavailable or incompatible,
# fall back to a simple file-backed JSON store for local development.
USE_MONGO = False
try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    from bson import ObjectId
    USE_MONGO = True
except Exception:
    USE_MONGO = False


def get_mongo_uri() -> str:
    return os.getenv('MONGODB_URI', 'mongodb://localhost:27017')


# -----------------------
# File-backed fallback (per-user)
# -----------------------

# Repo-shipped path (unsafe to use for shared repositories)
_repo_data_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'chats.json'))

def get_user_data_path() -> str:
    """Return a per-user chats.json path.

    Priority:
    - Env var `ATLAS_CHAT_STORE_PATH` or `ATLAS_CHAT_DATA_PATH` (absolute file path)
    - On Windows: %LOCALAPPDATA%\atlas_chat\chats.json
    - On Unix: $XDG_DATA_HOME/atlas_chat/chats.json or ~/.local/share/atlas_chat/chats.json
    """
    env = os.getenv('ATLAS_CHAT_STORE_PATH') or os.getenv('ATLAS_CHAT_DATA_PATH')
    if env:
        return os.path.abspath(env)

    if os.name == 'nt':
        base = os.getenv('LOCALAPPDATA') or os.path.expanduser('~')
    else:
        base = os.getenv('XDG_DATA_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'share')

    d = os.path.join(base, 'atlas_chat')
    return os.path.join(d, 'chats.json')

def _ensure_data_file(user_path: Optional[str] = None):
    path = user_path or get_user_data_path()
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(path):
        # If a repo-shipped chats.json exists, migrate it to the user path (best-effort)
        try:
            if os.path.exists(_repo_data_file):
                shutil.copy2(_repo_data_file, path)
                logger.info(f"Migrated repo chats.json to user path: {path}")
            else:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({'chats': []}, f)
        except Exception:
            # Fallback: create empty file
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'chats': []}, f)

def _now_iso():
    return datetime.utcnow().isoformat()

async def _read_file() -> Dict[str, Any]:
    path = get_user_data_path()
    def _r():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return await asyncio.to_thread(_r)

async def _write_file(data: Dict[str, Any]):
    path = get_user_data_path()
    def _w():
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    await asyncio.to_thread(_w)


if USE_MONGO:
    # Motor-based implementation
    _client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    async def init_chat_db(app=None):
        global _client, db
        if _client is None:
            uri = get_mongo_uri()
            _client = AsyncIOMotorClient(uri)
            db = _client.get_default_database() or _client['atlas_chat']
            logger.info(f"Connected to MongoDB: {uri}")

    def _serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return {}
        out = dict(doc)
        out['id'] = str(out.pop('_id'))
        if 'created_at' in out and isinstance(out['created_at'], datetime):
            out['created_at'] = out['created_at'].isoformat()
        if 'updated_at' in out and isinstance(out['updated_at'], datetime):
            out['updated_at'] = out['updated_at'].isoformat()
        if 'messages' in out and isinstance(out['messages'], list):
            for m in out['messages']:
                if 'timestamp' in m and isinstance(m['timestamp'], datetime):
                    m['timestamp'] = m['timestamp'].isoformat()
        return out

    async def create_chat(title: str = 'New Chat', metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        global db
        if db is None:
            await init_chat_db()
        metadata = metadata or {}
        now = datetime.utcnow()
        doc = {'title': title, 'metadata': metadata, 'created_at': now, 'updated_at': now, 'messages': []}
        res = await db.chats.insert_one(doc)
        doc['_id'] = res.inserted_id
        logger.info(f"Created chat {res.inserted_id}")
        return _serialize_doc(doc)

    async def list_chats(limit: int = 100) -> List[Dict[str, Any]]:
        global db
        if db is None:
            await init_chat_db()
        cursor = db.chats.find({}, sort=[('updated_at', -1)]).limit(limit)
        docs = []
        async for d in cursor:
            docs.append(_serialize_doc(d))
        return docs

    async def get_chat(chat_id: str) -> Optional[Dict[str, Any]]:
        global db
        if db is None:
            await init_chat_db()
        try:
            oid = ObjectId(chat_id)
        except Exception:
            return None
        doc = await db.chats.find_one({'_id': oid})
        return _serialize_doc(doc) if doc else None

    async def append_message(chat_id: str, role: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        global db
        if db is None:
            await init_chat_db()
        try:
            oid = ObjectId(chat_id)
        except Exception:
            return None
        now = datetime.utcnow()
        msg = {'role': role, 'text': text, 'timestamp': now, 'metadata': metadata or {}}
        res = await db.chats.update_one({'_id': oid}, {'$push': {'messages': msg}, '$set': {'updated_at': now}})
        if res.modified_count:
            return await get_chat(chat_id)
        return None

    async def delete_chat(chat_id: str) -> bool:
        global db
        if db is None:
            await init_chat_db()
        try:
            oid = ObjectId(chat_id)
        except Exception:
            return False
        res = await db.chats.delete_one({'_id': oid})
        return res.deleted_count == 1

    async def clear_all_chats() -> int:
        global db
        if db is None:
            await init_chat_db()
        res = await db.chats.delete_many({})
        return res.deleted_count

else:
    # File-based fallback implementation (for local dev without Mongo)

    async def init_chat_db(app=None):
        # Ensure user-specific data file exists and migrate any repo file on first run
        try:
            _ensure_data_file()
        except Exception as e:
            logger.warn('Failed to ensure user data file for chats.json: %s', e)

    async def create_chat(title: str = 'New Chat', metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        metadata = metadata or {}
        data = await _read_file()
        now = _now_iso()
        chat_id = str(uuid4())
        doc = {
            'id': chat_id,
            'title': title,
            'metadata': metadata,
            'created_at': now,
            'updated_at': now,
            'messages': []
        }
        data['chats'].insert(0, doc)
        await _write_file(data)
        logger.info(f"(file-store) Created chat {chat_id}")
        return doc

    async def list_chats(limit: int = 100) -> List[Dict[str, Any]]:
        data = await _read_file()
        return data.get('chats', [])[:limit]

    async def get_chat(chat_id: str) -> Optional[Dict[str, Any]]:
        data = await _read_file()
        for c in data.get('chats', []):
            if c.get('id') == chat_id:
                return c
        return None

    async def append_message(chat_id: str, role: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        data = await _read_file()
        now = _now_iso()
        for c in data.get('chats', []):
            if c.get('id') == chat_id:
                msg = {'role': role, 'text': text, 'timestamp': now, 'metadata': metadata or {}}
                c.setdefault('messages', []).append(msg)
                c['updated_at'] = now
                await _write_file(data)
                return c
        return None

    async def delete_chat(chat_id: str) -> bool:
        data = await _read_file()
        orig = len(data.get('chats', []))
        data['chats'] = [c for c in data.get('chats', []) if c.get('id') != chat_id]
        await _write_file(data)
        return len(data.get('chats', [])) != orig

    async def clear_all_chats() -> int:
        data = await _read_file()
        cnt = len(data.get('chats', []))
        data['chats'] = []
        await _write_file(data)
        return cnt

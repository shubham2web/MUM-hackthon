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
# File-backed fallback
# -----------------------
_file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'chats.json')
_file_path = os.path.abspath(_file_path)

def _ensure_data_dir():
    d = os.path.dirname(_file_path)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(_file_path):
        with open(_file_path, 'w', encoding='utf-8') as f:
            json.dump({'chats': []}, f)

def _now_iso():
    return datetime.utcnow().isoformat()

async def _read_file() -> Dict[str, Any]:
    return await asyncio.to_thread(lambda: json.loads(open(_file_path, 'r', encoding='utf-8').read()))

async def _write_file(data: Dict[str, Any]):
    def _w():
        with open(_file_path, 'w', encoding='utf-8') as f:
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
    _ensure_data_dir()

    async def init_chat_db(app=None):
        # noop for file-based store
        _ensure_data_dir()

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

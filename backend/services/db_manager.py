import sqlite3
import json
import logging
import asyncio
import aiosqlite
import random
import time
import shutil
import os
import gzip
from functools import wraps
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, AsyncIterator, TypedDict, Literal

# --- Configuration ---
# Use absolute path based on this file's location to avoid CWD issues
_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database")
os.makedirs(_DB_DIR, exist_ok=True)  # Ensure directory exists
DATABASE_FILE = os.path.join(_DB_DIR, "database.db")
BACKUP_FILE_PATH = os.path.join(_DB_DIR, "debate_backup.db")
ARCHIVE_FILE_PATH = os.path.join(_DB_DIR, "debate_archive.jsonl.gz")  # Using compressed archive
SLOW_QUERY_THRESHOLD_MS = 10.0
DELETE_CHUNK_SIZE = 500 # Number of records to delete per transaction in batch deletes

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- TypedDict Payloads for Clarity ---
class LogEntryPayload(TypedDict, total=False):
    debate_id: str; topic: str; model_used: str; role: str
    user_message: str; ai_response: str; analysis_metrics: Optional[Dict[str, Any]]; timestamp: Optional[str]

class EvidencePayload(TypedDict, total=False):
    debate_id: str; topic: str; source: str; type: str
    region: str; title: str; content: str; timestamp: Optional[str]

class LogUpdatePayload(TypedDict):
    id: int; updates: Dict[str, Any]

class EvidenceUpdatePayload(TypedDict):
    id: int; updates: Dict[str, Any]

# --- Enhanced Metrics Collector ---
class QueryMetrics:
    """A class to hold and display detailed query performance metrics."""
    def __init__(self):
        self.query_counts: Dict[str, int] = {}
        self.total_times: Dict[str, float] = {}
        self.slow_queries: Dict[str, int] = {}
        self.failed_retries: int = 0
        
    def record(self, func_name: str, duration_ms: float, is_slow: bool):
        self.query_counts[func_name] = self.query_counts.get(func_name, 0) + 1
        self.total_times[func_name] = self.total_times.get(func_name, 0) + duration_ms
        if is_slow: self.slow_queries[func_name] = self.slow_queries.get(func_name, 0) + 1

    def record_failed_retry(self): self.failed_retries += 1
        
    def display(self):
        print("\n" + "="*20 + " Query Performance Metrics " + "="*20)
        if not self.query_counts: print("No queries were recorded."); return
        print(f"{'Query':<40} | {'Count':>10} | {'Slow':>5} | {'Avg Time (ms)':>15}\n" + "-" * 80)
        for name, count in sorted(self.query_counts.items()):
            avg_time = self.total_times[name] / count
            slow_count = self.slow_queries.get(name, 0)
            print(f"{name:<40} | {count:>10} | {slow_count:>5} | {avg_time:>15.2f}")
        print(f"\nTotal Failed Retries After Max Attempts: {self.failed_retries}\n" + "=" * 80)

# --- Decorators ---
def log_query_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        duration = (time.perf_counter() - start_time) * 1000
        is_slow = duration > SLOW_QUERY_THRESHOLD_MS
        AsyncDbManager.metrics.record(func.__name__, duration, is_slow)
        if is_slow: logging.warning(f"Query '{func.__name__}' executed in {duration:.2f} ms [SLOW QUERY]")
        return result
    return wrapper

def retry_on_lock(max_retries=5, initial_delay=0.1):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retries, delay = 0, initial_delay
            while retries < max_retries:
                try: return await func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        retries += 1
                        if retries >= max_retries: AsyncDbManager.metrics.record_failed_retry(); logging.error(f"Max retries for {func.__name__}. Giving up."); raise
                        await asyncio.sleep(delay + (delay * 0.1 * random.uniform(-1, 1))); delay *= 2
                        logging.warning(f"DB locked. Retrying {func.__name__} ({retries}/{max_retries})...")
                    else: raise
        return wrapper
    return decorator

class DbManager:
    @staticmethod
    def _parse_log_rows(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        parsed = []
        for row in rows:
            d = dict(row)
            if d.get('analysis_metrics'):
                try: d['analysis_metrics'] = json.loads(d['analysis_metrics'])
                except (json.JSONDecodeError, TypeError): d['analysis_metrics'] = None
            parsed.append(d)
        return parsed

# --- FINAL UNIFIED ASYNC DEBATE MANAGER ---

class AsyncDbManager:
    _pool: Optional[aiosqlite.Connection] = None
    metrics = QueryMetrics()

    # --- Core Connection, Init, and Transaction Management ---
    @classmethod
    async def _get_pool(cls):
        if not cls._pool or cls._pool._connection is None:
            cls._pool = await aiosqlite.connect(DATABASE_FILE)
            await cls._pool.executescript("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;")
            cls._pool.row_factory = aiosqlite.Row; logging.info("Async connection pool initialized.")
        return cls._pool
    @classmethod
    async def close_pool(cls):
        if cls._pool: await cls._pool.close(); cls._pool = None
    @classmethod
    async def init_db(cls):
        pool = await cls._get_pool()
        await pool.executescript("""
            CREATE TABLE IF NOT EXISTS conversation_logs (id INTEGER PRIMARY KEY, debate_id TEXT NOT NULL, timestamp TEXT NOT NULL, topic TEXT, model_used TEXT, role TEXT, user_message TEXT, ai_response TEXT, analysis_metrics TEXT);
            CREATE TABLE IF NOT EXISTS evidence_logs (id INTEGER PRIMARY KEY, debate_id TEXT NOT NULL, timestamp TEXT NOT NULL, topic TEXT, source TEXT, type TEXT, region TEXT, title TEXT, content TEXT);
            CREATE INDEX IF NOT EXISTS idx_log_timestamp_id ON conversation_logs(timestamp, id);
            CREATE INDEX IF NOT EXISTS idx_evidence_timestamp_id ON evidence_logs(timestamp, id);
            CREATE VIRTUAL TABLE IF NOT EXISTS conversation_logs_fts USING fts5(topic, user_message, ai_response, content='conversation_logs', content_rowid='id');
            CREATE VIRTUAL TABLE IF NOT EXISTS evidence_logs_fts USING fts5(source, title, content, content='evidence_logs', content_rowid='id');
            CREATE TRIGGER IF NOT EXISTS logs_ai AFTER INSERT ON conversation_logs BEGIN INSERT INTO conversation_logs_fts(rowid, topic, user_message, ai_response) VALUES (new.id, new.topic, new.user_message, new.ai_response); END;
            CREATE TRIGGER IF NOT EXISTS logs_ad AFTER DELETE ON conversation_logs BEGIN INSERT INTO conversation_logs_fts(conversation_logs_fts, rowid, topic, user_message, ai_response) VALUES ('delete', old.id, old.topic, old.user_message, old.ai_response); END;
            CREATE TRIGGER IF NOT EXISTS logs_au AFTER UPDATE ON conversation_logs BEGIN INSERT INTO conversation_logs_fts(conversation_logs_fts, rowid, topic, user_message, ai_response) VALUES ('delete', old.id, old.topic, old.user_message, old.ai_response); INSERT INTO conversation_logs_fts(rowid, topic, user_message, ai_response) VALUES (new.id, new.topic, new.user_message, new.ai_response); END;
            CREATE TRIGGER IF NOT EXISTS evidence_ai AFTER INSERT ON evidence_logs BEGIN INSERT INTO evidence_logs_fts(rowid, source, title, content) VALUES (new.id, new.source, new.title, new.content); END;
            CREATE TRIGGER IF NOT EXISTS evidence_ad AFTER DELETE ON evidence_logs BEGIN INSERT INTO evidence_logs_fts(evidence_logs_fts, rowid, source, title, content) VALUES ('delete', old.id, old.source, old.title, old.content); END;
            CREATE TRIGGER IF NOT EXISTS evidence_au AFTER UPDATE ON evidence_logs BEGIN INSERT INTO evidence_logs_fts(evidence_logs_fts, rowid, source, title, content) VALUES ('delete', old.id, old.source, old.title, old.content); INSERT INTO evidence_logs_fts(rowid, source, title, content) VALUES (new.id, new.source, new.title, new.content); END;
        """)
        await pool.commit()
    @classmethod
    @asynccontextmanager
    async def transaction(cls):
        """Get a connection and handle transaction commit/rollback."""
        conn = await cls._get_pool()
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    @classmethod
    @asynccontextmanager
    async def connection(cls):
        yield await cls._get_pool()

    # --- Advanced Search & Unified Streaming ---
    @classmethod
    @log_query_performance
    async def stream_paginated_search_evidence(cls, fts_query: str, limit: int = 20, 
                                               after_rank: Optional[float] = None, after_id: int = 0, 
                                               sort_order: Literal['ASC', 'DESC'] = 'ASC') -> AsyncIterator[Dict[str, Any]]:
        """
        Streams FTS results for evidence with cursor-based pagination.
        - sort_order='ASC': Best matches first (default, lower BM25 is better).
        - sort_order='DESC': Worst matches first.
        - Note: Rank normalization for UI is best handled client-side.
        """
        params: List[Any] = [fts_query]
        query = "SELECT e.*, snippet(evidence_logs_fts, -1, '<b>', '</b>', '...', 15) as snippet, bm25(evidence_logs_fts) as rank FROM evidence_logs e JOIN evidence_logs_fts fts ON e.id = fts.rowid WHERE fts.evidence_logs_fts MATCH ?"
        if after_rank is not None:
            operator = '>' if sort_order == 'ASC' else '<'
            query += f" AND (bm25(evidence_logs_fts), e.id) {operator} (?, ?)"; params.extend([after_rank, after_id])
        query += f" ORDER BY rank {sort_order}, e.id ASC LIMIT ?"; params.append(limit)
        async for row in cls._execute_streaming_query(query, tuple(params)):
            yield dict(row)

    @classmethod
    @log_query_performance
    async def stream_chronological_timeline(cls, debate_id: str, limit: int = 20, after_timestamp: Optional[str] = None, after_id: int = 0, after_type: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Streams a unified, chronological timeline of logs and evidence.
        This uses keyset/cursor pagination on (timestamp, type, id), which is highly
        performant and avoids the issues of LIMIT/OFFSET on large datasets.
        """
        params: List[Any] = [debate_id, debate_id]
        # Using a CTE (WITH clause) is more readable and standard than HAVING for this kind of filtering
        query = """
            WITH timeline AS (
                SELECT id, timestamp, 'log' as type, topic, role, user_message, ai_response FROM conversation_logs WHERE debate_id = ?
                UNION ALL
                SELECT id, timestamp, 'evidence' as type, topic, source, title, content, NULL as ai_response FROM evidence_logs WHERE debate_id = ?
            )
            SELECT * FROM timeline
        """
        
        if after_timestamp:
            # The WHERE clause is now applied to the combined timeline
            query += " WHERE (timestamp, CASE type WHEN 'log' THEN 0 ELSE 1 END, id) > (?, CASE ? WHEN 'log' THEN 0 ELSE 1 END, ?)"
            params.extend([after_timestamp, after_type, after_id])
        
        query += " ORDER BY timestamp ASC, CASE type WHEN 'log' THEN 0 ELSE 1 END, id ASC LIMIT ?"; params.append(limit)
        async for row in cls._execute_streaming_query(query, tuple(params)):
            yield dict(row)
            
    # --- Real-Time Listener with Heartbeat ---
    @classmethod
    @log_query_performance
    async def listen_for_realtime_updates(cls, debate_id: str, poll_interval: float = 2.0) -> AsyncIterator[Dict[str, Any]]:
        """
        Polls for new logs and evidence, yielding them in real-time.
        Also yields periodic 'heartbeat' events if no new data is found.
        Note: For production scale, this would be replaced by a push system (e.g., WebSockets).
        """
        last_log_ts = datetime.now(timezone.utc).isoformat()
        last_evidence_ts = last_log_ts
        
        while True:
            await asyncio.sleep(poll_interval)
            found_new = False
            
            # Check for new logs
            log_query = "SELECT * FROM conversation_logs WHERE debate_id = ? AND timestamp > ? ORDER BY timestamp ASC"
            async for row in cls._execute_streaming_query(log_query, (debate_id, last_log_ts)):
                log = DbManager._parse_log_rows([row])[0]
                yield {"type": "log", "data": log}
                last_log_ts = log['timestamp']; found_new = True
                
            # Check for new evidence
            evidence_query = "SELECT * FROM evidence_logs WHERE debate_id = ? AND timestamp > ? ORDER BY timestamp ASC"
            async for row in cls._execute_streaming_query(evidence_query, (debate_id, last_evidence_ts)):
                evidence = dict(row)
                yield {"type": "evidence", "data": evidence}
                last_evidence_ts = evidence['timestamp']; found_new = True

            if not found_new:
                yield {"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()}

    # --- Batch Insert, Maintenance & Helpers ---
    @classmethod
    @log_query_performance
    @retry_on_lock()
    async def add_log_entries_batch(cls, log_entries: List[LogEntryPayload]):
        data = [(e['debate_id'], e.get('timestamp', datetime.now(timezone.utc).isoformat()), e['topic'], e['model_used'], e['role'], e['user_message'], e['ai_response'], json.dumps(e.get('analysis_metrics'))) for e in log_entries]
        async with cls.transaction() as conn:
            await conn.executemany("INSERT INTO conversation_logs (debate_id, timestamp, topic, model_used, role, user_message, ai_response, analysis_metrics) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", data)
    @classmethod
    @log_query_performance
    @retry_on_lock()
    async def add_evidence_batch(cls, evidence_entries: List[EvidencePayload]):
        data = [(e['debate_id'], e.get('timestamp', datetime.now(timezone.utc).isoformat()), e['topic'], e['source'], e['type'], e['region'], e['title'], e['content']) for e in evidence_entries]
        async with cls.transaction() as conn:
            await conn.executemany("INSERT INTO evidence_logs (debate_id, timestamp, topic, source, type, region, title, content) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", data)
    @classmethod
    @log_query_performance
    async def run_maintenance_tasks(cls, archive_older_than_days: int = 365) -> None:
        logging.info("Starting scheduled maintenance tasks...")
        archive_date = (datetime.now(timezone.utc) - timedelta(days=archive_older_than_days)).isoformat()
        all_debate_ids = await cls.get_all_debate_ids()
        total_archived = sum([await cls.archive_and_delete_logs_incrementally(ARCHIVE_FILE_PATH, debate_id, archive_date) for debate_id in all_debate_ids])
        if total_archived > 0: logging.info(f"Total logs archived across all debates: {total_archived}")
        await cls.rebuild_fts_indexes()
        logging.info("Scheduled maintenance tasks completed.")
    @classmethod
    async def _execute_streaming_query(cls, query: str, params: tuple) -> AsyncIterator[sqlite3.Row]:
        async with cls.connection() as conn:
            async with conn.execute(query, params) as cursor:
                async for row in cursor: yield row
    @classmethod
    async def archive_and_delete_logs_incrementally(cls, archive_file: str, debate_id: str, end_date: str) -> int:
        query = "SELECT * FROM conversation_logs WHERE debate_id = ? AND timestamp <= ?"
        total_archived = 0;
        try:
            with gzip.open(archive_file, 'at', encoding='utf-8') as f:
                ids_to_delete = []
                async for row in cls._execute_streaming_query(query, (debate_id, end_date)):
                    f.write(json.dumps(DbManager._parse_log_rows([row])[0]) + '\n')
                    ids_to_delete.append(row['id']); total_archived += 1
                    if len(ids_to_delete) >= DELETE_CHUNK_SIZE:
                        await cls._delete_in_chunks("conversation_logs", ids_to_delete); ids_to_delete = []
                if ids_to_delete: await cls._delete_in_chunks("conversation_logs", ids_to_delete)
        except (IOError, gzip.BadGzipFile) as e: logging.error(f"Failed to write to archive {archive_file}: {e}"); raise
        return total_archived
    @classmethod
    @retry_on_lock
    async def _delete_in_chunks(cls, table: str, ids: List[int]) -> int:
        total_deleted = 0;
        for i in range(0, len(ids), DELETE_CHUNK_SIZE):
            chunk = ids[i:i + DELETE_CHUNK_SIZE]; placeholders = ', '.join('?' for _ in chunk)
            query = f"DELETE FROM {table} WHERE id IN ({placeholders})"
            async with cls.transaction() as conn:
                cursor = await conn.execute(query, chunk); total_deleted += cursor.rowcount
        return total_deleted
    @classmethod
    @log_query_performance
    async def get_all_debate_ids(cls) -> List[str]:
        async with cls.connection() as conn:
            async with conn.execute("SELECT DISTINCT debate_id FROM conversation_logs") as cursor:
                return [row['debate_id'] for row in await cursor.fetchall()]
    @classmethod
    @log_query_performance
    async def rebuild_fts_indexes(cls) -> None:
        logging.info("Rebuilding FTS indexes...")
        async with cls.transaction() as conn:
            await conn.execute("INSERT INTO conversation_logs_fts(conversation_logs_fts) VALUES('rebuild');")
            await conn.execute("INSERT INTO evidence_logs_fts(evidence_logs_fts) VALUES('rebuild');")
        logging.info("FTS rebuild complete.")

# --- Example Usage ---
async def main():
    print("="*20 + " ULTIMATE MANAGER FINAL EXAMPLE " + "="*20)
    await AsyncDbManager.init_db()
    
    debate_id = f"ultimate_final_debate_{int(datetime.now().timestamp())}"
    print(f"\n--- Seeding data for {debate_id} ---")
    
    # Add items with slightly different timestamps to test chronological streaming
    ts = datetime.now(timezone.utc)
    log_batch: List[LogEntryPayload] = [{'debate_id': debate_id, 'timestamp': (ts - timedelta(seconds=10)).isoformat(), 'topic': 'Timeline Test', 'model_used': 'Chrono', 'role': 'Event 1', 'user_message': '...', 'ai_response': '...'}]
    evidence_batch: List[EvidencePayload] = [{'debate_id': debate_id, 'timestamp': (ts - timedelta(seconds=5)).isoformat(), 'topic': 'Timeline Test', 'source': 'Source', 'type': 'Fact', 'region': 'Global', 'title': 'Fact for Event 1', 'content': 'This is a test fact.'}]
    await AsyncDbManager.add_log_entries_batch(log_batch)
    await AsyncDbManager.add_evidence_batch(evidence_batch)

    # 1. Test True Chronological Timeline Streaming
    print("\n--- Testing True Chronological Timeline Streaming (with CTE) ---")
    async for item in AsyncDbManager.stream_chronological_timeline(debate_id, limit=5):
        print(f"  - [{item['timestamp']}] Type: {item['type']}, Content: {item.get('role') or item.get('title')}")

    # 2. Test Real-Time Listener with Heartbeat
    print("\n--- Testing Real-Time Listener with Heartbeat (runs for ~5s) ---")
    async def consume_listener():
        update_count = 0
        async for update in AsyncDbManager.listen_for_realtime_updates(debate_id, poll_interval=1.0):
            if update['type'] == 'heartbeat':
                print(f"  - Received heartbeat at {update['timestamp']}")
            else:
                update_count += 1
                print(f"  - Received new {update['type']}! Content: {update['data'].get('role') or update['data'].get('title')}")
            if update_count > 0: # Stop after receiving one real update
                break

    listener_task = asyncio.create_task(consume_listener())
    await asyncio.sleep(2.5) # Wait for a heartbeat
    await AsyncDbManager.add_log_entries_batch([{'debate_id': debate_id, 'topic': 'Real-time', 'model_used': 'Live', 'role': 'New Event', 'user_message': '...'}])
    await listener_task # Wait for the consumer to finish

    await AsyncDbManager.close_pool()
    AsyncDbManager.metrics.display()
    print("\n="*20 + " EXAMPLE COMPLETE " + "="*20)

if __name__ == '__main__':
    for f in [DATABASE_FILE, BACKUP_FILE_PATH, ARCHIVE_FILE_PATH]:
        if os.path.exists(f): os.remove(f)
    asyncio.run(main())

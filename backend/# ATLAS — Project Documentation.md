# ATLAS — Project Documentation

**Version:** 1.0
**Generated:** 2025-08-31

---

## Purpose

This document maps the existing repository to the ATLAS PRD you provided, describes each key file, outlines time/space complexity estimates per major function, and provides usage, installation, testing, and contribution guidance for engineering and product teams.

---

## 1. Project Mapping to PRD

* **Multi-Agent Structured Debate**: `server.py` (generator + SSE orchestration) + `ai_agent.py` (agent orchestration & provider fallbacks).
* **Pluggable Model Interface**: `ai_agent.py` implements provider abstraction for HuggingFace and Groq.
* **Evidence Grounder & Source Diversification**: `pro_scraper.py` provides evidence collection, extraction, ranking and dashboard generation.
* **Bias Auditor System**: (Not present as a standalone file) — planned component; hooks available in `server.py` and `ai_agent.py` for integration.
* **Role Reversal & Convergence Rounds**: `server.py` orchestrates roles through `ROLE_PROMPTS` loaded from `config.py`.
* **Moderator & Transparent Synthesis**: `server.py` runs moderator turns and yields structured synthesis events.
* **Audit Log & Transparency UI**: `client_example.py` demonstrates the SSE consumer and transcript export.

---

## 2. Repository — File-by-File Overview

Each entry includes: purpose, key functions, and complexity notes.

### `ai_agent.py`

**Purpose:** Provider abstraction, token rotation, streaming and blocking call helpers, metrics.

**Key classes / functions:**

* `AiAgent.__init__` — load model config, provider map, metrics
* `_call_hf` — cycle HF tokens, call `InferenceClient.chat_completion`
* `_stream_hf` — streaming HF, yields chunks
* `_call_groq` — HTTP POST to Groq with retries/backoff
* `call_blocking` — adaptive provider ordering, metrics, structured `AiResponse`
* `call_streaming` — streaming orchestration with fallback to blocking

**Time Complexity (per call):**

* `_call_hf`: O(t) where t = number of HF\_TOKENS tried (usually small constant). External API latency dominates.
* `_stream_hf`: O(c) where c = number of stream chunks (depends on response size); per-chunk parsing is O(1).
* `_call_groq`: O(r) for `retries` attempts (small constant). JSON parsing O(1) relative to payload size. External network dominates.
* `call_blocking`: O(p \* cost(provider\_call)) where p = number of providers in sequence (small constant). Overall dominated by external LLM latency.

**Space Complexity:**

* Mainly O(1) aside from storing `raw_response` or collected chunks. Streaming saves chunks into a small buffer — O(c).

**Notes / Recommendations:**

* Consider exposing a pluggable provider interface class to add providers more cleanly.
* Add explicit unit tests around token rotation and failure/fallback paths.

---

### `server.py`

**Purpose:** Flask app that exposes endpoints and orchestrates debate generation as an SSE stream.

**Key functions:**

* `generate_debate` — async generator orchestrating evidence retrieval, role turns, moderator synthesis
* `run_turn` — runs a single agent turn in executor and yields SSE events
* Flask endpoints: `/run_debate`, `/chat`, `/` and API key checking middleware

**Time Complexity:**

* `generate_debate`: O(R \* cost(run\_turn) + cost(evidence\_fetch)) where R is number of turns/roles. Each `run_turn` in turn is dominated by LLM call latency.
* `run_turn`: O(1) from Python perspective; external I/O bound.

**Space Complexity:**

* Uses memory for `transcript` and `log_entries` proportional to the length of debate (O(L)). For long debates consider incremental DB writes or chunked uploads.

**Notes / Recommendations:**

* For production, run behind an ASGI server (Uvicorn/Gunicorn with workers) as noted in code comments.
* Tune `ThreadPoolExecutor(max_workers=...)` to match expected concurrent users & LLM latency.

---

### `pro_scraper.py`

**Purpose:** Evidence retrieval pipeline: search, scrape, extract text, summarize, analyze, and produce an interactive HTML dashboard.

**Key functions:**

* `topic_to_urls(topic, num_results)` — scrapes Google News search results
* `make_session()` — HTTP session with retries
* `extract_text_and_meta(html)` — uses trafilatura/BeautifulSoup with date parsing
* `scrape_and_analyze(url, ...)` + thread pool orchestration for concurrent scraping
* Dashboard HTML generator `generate_html_dashboard`

**Time Complexity:**

* `topic_to_urls`: O(num\_results) network calls + parsing cost => O(m)
* Main pipeline: O(U) where U is number of unique URLs to fetch; concurrent model reduces wall time but total CPU/network work scales O(U).

**Space Complexity:**

* O(U) for collected article objects. Dashboard images are base64-encoded images — watch memory if generating many charts.

**Notes / Recommendations:**

* Respect robots.txt and terms of service for crawled domains. Consider using paid news APIs when scaling.
* Add rate-limiting, cache layer, and circuit-breaker for robust production scraping.

---

### `file_parser.py`

**Purpose:** Bulk file discovery and parsing, parallel parsing, optional NLP enrichment hooks, and caching.

**Key functions:**

* `bulk_parse_files(paths, ...)` — walks directories, schedules parsing tasks
* `parse_file(...)` — per-file extraction using trafilatura / tika / PIL OCR fallbacks

**Time Complexity:**

* File discovery: O(F) where F = number of files scanned.
* Parsing: O(F \* cost(per-file-extract)). NLP enrichment adds O(N) where N = number of texts passed into NLP.

**Space Complexity:**

* O(F) aggregated results; temporary buffers for large files (PDFs, images) can spike memory — use streaming extraction where feasible.

**Notes / Recommendations:**

* Add safeguards for huge binary files and limit per-file processing time via timeouts or external worker processes.
* Add unit tests for each extractor path and mock external libraries.

---

### `db_manager.py`

**Purpose:** Async DB manager for conversation logs, evidence, and archival — includes chunked deletes, timeline streaming, FTS index rebuilds, and batch writes.

**Key functions:**

* `add_log_entries_batch`, `add_evidence_batch` — batched inserts
* `_delete_in_chunks` — chunked deletes to avoid huge single-statement deletes
* `stream_chronological_timeline(debate_id, limit)` — yields chronological timeline items

**Time Complexity:**

* Batched ops: O(B) where B = batch size; chunk deletion is O(n) but batched to smaller chunks.
* Timeline streaming queries: depend on DB indices; with proper indexes, queries are O(k) for k items returned.

**Space Complexity:**

* DB-backed; memory usage small for streaming operations but batch building increases memory proportional to batch size.

**Notes / Recommendations:**

* Ensure indexes on `debate_id`, `timestamp`, and FTS tables for performance.
* Use connection pooling and limit long-running transactions.

---

### `client_example.py`

**Purpose:** Example SSE client that connects to `/run_debate`, prints colored roles, saves transcripts to .txt and optionally JSON.

**Key functions:**

* `run_client(topic, model, server_url, export_json)` — establishes streaming HTTP request and consumes SSE events.

**Time Complexity:**

* O(T) where T = number of events/tokens received. Processing per event is O(1).

**Space Complexity:**

* O(L) where L = transcript length saved to disk.

**Notes / Recommendations:**

* Useful as a reference integration; consider shipping a lightweight web client for demos.

---

### `config.py`

**Purpose:** Centralized configuration loader, environment variable parsing, role prompt loading, and validation.

**Key functions:**

* `_get_secret`, `_fetch_from_secrets_manager`, `validate_config`

**Time & Space Complexity:**

* Mostly O(1) for operations; secret fetching uses retries and caching.

**Notes / Recommendations:**

* Secrets retrieval is stubbed — ensure production secret fetching is implemented and tested.

---

## 3. Installation & Setup (Developer quickstart)

1. Create Python virtualenv (Python 3.11+ recommended).

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment variables (example .env keys used in `config.py`):

* `API_KEY` — server API key
* `HF_TOKENS` — comma-separated HF tokens (if using HF provider)
* `GROQ_API_KEY` — Groq API key (if using Groq)
* `ROLE_PROMPTS_FILE` — path to role prompts JSON
* `SINGLE_MODE` / `SINGLE_PROVIDER` — optional provider mode

3. Start dev server:

```bash
python server.py
# or use uvicorn/gunicorn for production as documented in server.py
```

4. Run example client:

```bash
python client_example.py "Is AI a net positive for society?" --json
```

---

## 4. API / Events (Server SSE contract)

The server emits Server-Sent Events (SSE) with event names and JSON payloads. Important events:

* `metadata` — debate metadata (topic, model\_used, debate\_id)
* `start_role` — signals the start of role output; payload `{"role": "role_name"}`
* `token` — tokenized streaming or final text `{"role": "role_name", "text": "..."}`
* `end_role` — indicates role finished
* `structured_synthesis` — final moderator synthesis (JSON) when available
* `analytics_metrics` — post-debate metrics
* `error` / `turn_error` — error details

Clients should handle reconnect/backoff and save transcripts atomically.

---

## 5. Testing & Validation

* Unit tests: write tests around token rotation, provider fallback, `pro_scraper.topic_to_urls`, and DB batch operations.
* Integration tests: a lightweight end-to-end run using a stubbed HF/Groq provider (or local mock server) to validate `generate_debate` stream.
* Load testing: simulate multiple concurrent SSE consumers to tune `ThreadPoolExecutor(max_workers)` and DB connection pool size.

---

## 6. Security & Compliance Notes

* Ensure `API_KEY` checks are enforced for all non-public endpoints.
* Store provider secrets in a real secrets manager (AWS Secrets Manager, GCP Secret Manager, Vault).
* Encrypt DB at rest and in transit (TLS). Use role-based access controls for logs and evidence storage.
* Respect web scraping legal constraints: honor `robots.txt` and service terms.

---

## 7. Roadmap / Next Steps

* Implement Bias Auditor module and integrate as a post-turn pass. Add dedicated `auditor.py` with deterministic rules + LLM checks.
* Add full unit test coverage and CI pipeline.
* Implement moderator GUI and per-claim provenance inspector in the frontend.
* Add credentialed news API integration (newsapi, GDELT, etc.) to reduce scraping fragility.

---

## 8. Appendix — Complexity Summary (Quick)

* LLM calls (HF/Groq): O(1) per call from CPU perspective, network-latency bound; token cycling O(T) where T is number of tokens (small).
* File parsing pipeline: O(F) discovery + O(F \* per-file) extraction.
* Scraper pipeline: O(U) for U unique URLs; concurrency reduces wall time.
* DB batch ops: O(B) per batch; streaming queries O(k) for k returned rows.

---

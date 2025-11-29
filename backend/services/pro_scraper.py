"""
Professional, production-ready news/article scraper and analysis pipeline.

Features:
  - Real-Time Topic Analysis & Advanced Post-Scrape Analysis/Ranking.
  - Interactive HTML Dashboard:
    - Interactive, clickable word cloud (via wordcloud2.js).
    - Clickable entity tags to filter articles.
    - Embedded data visualizations (Word Count & Sentiment graphs).
    - Sidebar for easy navigation and toggle controls.
  - Performance & Efficiency:
    - Caching of scraped articles in SQLite to avoid re-scraping.
    - Option for faster NLP processing by disabling unused spaCy components.
    - Save/Load full analysis reports to/from JSON, bypassing scraping entirely.
  - Polished CLI and Console Output with progress bar and color.
  - Robust Scraping: Includes an improved Google News scraper with multiple
    fallback selectors to handle changes in page structure.
"""

from __future__ import annotations

import argparse
import base64
import collections
import concurrent.futures
import datetime as dt
import hashlib
import io
import json
import logging
import os
import random
import sqlite3
import sys
import textwrap
import time
import urllib.parse as up
from typing import Any, Dict, List, Optional, TypedDict, Tuple
import re
import aiohttp

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry
from fake_useragent import UserAgent

# --- Optional Libraries ---
# Install full suite: pip install spacy textblob sumy transformers tabulate tqdm wordcloud matplotlib colorama
# Download NLP model: python -m spacy download en_core_web_sm

try:
    import trafilatura
except ImportError:
    trafilatura = None
try:
    from dateutil import parser as dateparser
except ImportError:
    dateparser = None
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
try:
    import spacy
    from spacy.cli.download import download as spacy_download
except Exception:
    spacy = None
try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None
try:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
except ImportError:
    PlaintextParser = None
# Temporarily disabled - transformers is very slow to import
# try:
#     from transformers import pipeline as transformers_pipeline
# except Exception:
#     transformers_pipeline = None
transformers_pipeline = None
try:
    from tabulate import tabulate
except ImportError:
    tabulate = None
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None
try:
    from wordcloud import WordCloud
except ImportError:
    WordCloud = None
try:
    from colorama import Fore, Style, init as colorama_init
except ImportError:
    Fore = Style = None

# ==================================================================================
# EVIDENCE HELPERS - Deduplication, Normalization, Probabilistic Combining
# ==================================================================================

# Domain authority baseline map - treat .gov, .edu, major outlets as higher authority
DOMAIN_AUTHORITY_MAP = {
    # Government domains
    '.gov': 0.85, '.gov.uk': 0.85, '.gov.au': 0.85,
    # Educational domains
    '.edu': 0.80, '.ac.uk': 0.80,
    # Major news outlets
    'reuters.com': 0.85, 'apnews.com': 0.85, 'bbc.com': 0.80, 'bbc.co.uk': 0.80,
    'nytimes.com': 0.75, 'washingtonpost.com': 0.75, 'theguardian.com': 0.75,
    'wsj.com': 0.75, 'economist.com': 0.75, 'nature.com': 0.90, 'science.org': 0.90,
    'pubmed.ncbi.nlm.nih.gov': 0.90, 'who.int': 0.85, 'cdc.gov': 0.85,
    # Fact-checkers
    'snopes.com': 0.80, 'factcheck.org': 0.80, 'politifact.com': 0.80,
}

def get_domain_authority(domain: str) -> Optional[float]:
    """Get baseline authority from domain authority map."""
    if not domain:
        return None
    domain = domain.lower()
    # Check exact match first
    if domain in DOMAIN_AUTHORITY_MAP:
        return DOMAIN_AUTHORITY_MAP[domain]
    # Check suffix matches (.gov, .edu, etc.)
    for suffix, auth in DOMAIN_AUTHORITY_MAP.items():
        if suffix.startswith('.') and domain.endswith(suffix):
            return auth
    return None

def normalize_authority(raw_score: Optional[float]) -> float:
    """
    Turn various raw authority signals into a 0.0-1.0 normalized authority score.
    If no signal, give a safe default (0.3).
    """
    try:
        if raw_score is None:
            return 0.3
        s = float(raw_score)
        # If it's a percentage between 0-100, map down
        if s > 1.5:
            s = max(0.0, min(100.0, s)) / 100.0
        return max(0.0, min(1.0, s))
    except Exception:
        return 0.3

def dedupe_articles_by_url(articles: List[dict]) -> List[dict]:
    """Keep first-highest-quality instance for each url_hash, preserve order."""
    seen = {}
    out = []
    for a in articles:
        uh = a.get("url_hash") or hashlib.sha256(a.get("url","").encode()).hexdigest()
        if uh not in seen:
            seen[uh] = a
            out.append(a)
        else:
            # If duplicate and this one has higher authority replace
            old = seen[uh]
            new_auth = a.get("authority", 0)
            old_auth = old.get("authority", 0)
            if new_auth > old_auth:
                # replace in mapping and in out list
                seen[uh] = a
                for i, x in enumerate(out):
                    if (x.get("url_hash") or hashlib.sha256(x.get("url","").encode()).hexdigest()) == uh:
                        out[i] = a
                        break
    return out

def combine_confidences_probabilistic(confidences: List[float], weights: List[float] = None) -> float:
    """
    Probabilistic confidence combining - models diminishing returns.
    
    confidences: list of floats in [0,1]
    weights: optional list of [0,1] same length, used to scale each evidence's contribution.
    Returns combined probability in [0,1] using: 1 - product(1 - w_i * c_i)
    This avoids linear runaway sums and models diminishing returns.
    """
    if not confidences:
        return 0.0
    prod = 1.0
    if weights is None:
        weights = [1.0] * len(confidences)
    for c, w in zip(confidences, weights):
        c_ = max(0.0, min(1.0, c))
        w_ = max(0.0, min(1.0, w))
        prod *= (1.0 - (c_ * w_))
    return 1.0 - prod

# ==================================================================================
# ROBUST EXTRACTION & CLEANING HELPERS
# ==================================================================================

# Optional: pip install readability-lxml for better article extraction
try:
    from readability import Document as ReadabilityDocument
except ImportError:
    ReadabilityDocument = None

def normalize_url_for_dedupe(url: str) -> str:
    """Return normalized URL without query params for deterministic dedupe."""
    try:
        p = up.urlparse(url)
        norm = up.urlunparse((p.scheme or "https", p.netloc.lower().replace("www.", ""), p.path.rstrip('/'), "", "", ""))
        return norm
    except Exception:
        return url

def extract_title_from_html(html: Optional[str], fallback: str = "") -> str:
    """Best-effort title extraction from HTML."""
    if not html:
        return fallback or "No Title"
    try:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("h1") or soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)[:200]
    except Exception:
        pass
    # Try readability
    if ReadabilityDocument:
        try:
            doc = ReadabilityDocument(html)
            title = doc.short_title()
            if title:
                return title.strip()[:200]
        except Exception:
            pass
    return fallback or "No Title"

def strip_boilerplate(text: str) -> str:
    """Heuristically remove common nav/footer/subscribe phrases and compress whitespace."""
    if not text:
        return ""
    # Remove common UI strings and ends of pages
    ui_patterns = [
        r'(Subscribe( now)?|Sign in|Log in|LOGIN|SUBSCRIBE|Register|Create Account).*?(?=\.|$)',
        r'(View Market Dashboard|Latest News|Breaking News|Top Stories).*?(?=\.|$)',
        r'(Premium|Paywall|Unlock this article|Already a member).*?(?=\.|$)',
    ]
    for pattern in ui_patterns:
        text = re.sub(pattern, ' ', text, flags=re.I)
    # Remove repeated words from header scraps like 'English SubscribeSign in View'
    text = re.sub(r'((?:[A-Z][a-z]{1,10}\s?){6,})', lambda m: ' ', text)
    # Remove common junk patterns
    text = re.sub(r'\b(Advertisement|Sponsored|Read More|Share this|Follow us|See Also)\b', ' ', text, flags=re.I)
    # Remove social media
    text = re.sub(r'\b(Facebook|Twitter|LinkedIn|Instagram|Share on|Follow @)\b', ' ', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def fetch_and_clean(url: str, html: Optional[str] = None, max_chars: int = 10000) -> dict:
    """
    Return {'text': clean_text, 'title':title, 'method':'trafilatura|readability|bs4', 'raw_html': html}
    Uses available extractors in order: trafilatura -> readability -> bs4 paragraph join.
    """
    raw_html = html
    text = ""
    method = "none"

    # If trafilatura is available and we don't have HTML, fetch it
    if trafilatura and not html:
        try:
            r = requests.get(url, headers={"User-Agent": DEFAULT_UA}, timeout=TIMEOUT)
            r.raise_for_status()
            raw_html = r.text
        except Exception:
            raw_html = html

    # Try trafilatura first (handles boilerplate well)
    if trafilatura and raw_html:
        try:
            data = trafilatura.extract(raw_html, output_format='text')
            if data and len(data) > 50:
                text = data
                method = "trafilatura"
        except Exception:
            pass

    # Fallback to readability (cleaner article extraction)
    if not text and raw_html and ReadabilityDocument:
        try:
            doc = ReadabilityDocument(raw_html)
            summary = doc.summary()  # returns HTML snippet
            soup = BeautifulSoup(summary, "html.parser")
            text = soup.get_text(" ", strip=True)
            if len(text) > 50:
                method = "readability"
        except Exception:
            text = ""

    # Last resort: plain paragraph join from provided html
    if not text and raw_html:
        soup = BeautifulSoup(raw_html, "html.parser")
        # Remove noisy tags first
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        text = " ".join(ps)
        method = "bs4" if text else method

    # If still empty and caller provided pre-scraped text (not HTML), use it
    if not text and html and not html.strip().startswith('<'):
        text = html
        method = "passthrough"

    # Clean boilerplate
    clean = strip_boilerplate(text)[:max_chars] if text else ""

    title = extract_title_from_html(raw_html, fallback=(clean.split(".")[0][:100] if clean else "No Title"))
    return {"text": clean, "title": title, "method": method or "none", "raw_html": raw_html}

def paraphrase_snippet(text: str, max_chars: int = 200) -> str:
    """
    Safe fallback summarizer:
      - If a transformer pipeline is available use it (not installed by default)
      - Otherwise pick first meaningful sentences, strip boilerplate, and cap length.
    """
    if not text:
        return ""
    # prefer an installed summarizer pipeline if configured
    if SUMMARIZER_PIPELINE:
        try:
            out = SUMMARIZER_PIPELINE(text[:4000], max_length=max_chars, truncation=True)
            return out[0]['summary_text'] if isinstance(out, list) else str(out)
        except Exception:
            pass

    # naive extractive fallback
    s = text.strip()
    # remove repeated header-chunks
    s = re.sub(r'^(Subscribe|Sign in|Home|Dashboard|Latest News)[\s:,-]*', '', s, flags=re.I)
    sentences = re.split(r'(?<=[.!?])\s+', s)
    out = ""
    for sent in sentences:
        if len(out) + len(sent) <= max_chars:
            out += (sent + " ")
        else:
            break
    out = out.strip()
    if not out:
        out = (s[:max_chars]).rsplit(" ", 1)[0]
    return out[:max_chars]
## Pro Feature: New import for plotting
try:
    import matplotlib
    matplotlib.use('Agg') # Non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


# --- TypedDict Definitions & Global Config ---
class Sentiment(TypedDict): polarity: float; subjectivity: float
class ArticleData(TypedDict, total=False):
    url: str; canonical_url: str; url_hash: str; domain: str; title: Optional[str]
    published_at: Optional[str]; text: Optional[str]; fetched_at: str; extraction_method: str
    summary: Optional[str]; keywords_extracted: Optional[List[str]]
    entities: Optional[Dict[str, List[str]]]; sentiment: Optional[Sentiment]; word_count: int

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
TIMEOUT = 25
NLP_MODEL, SUMMARIZER_PIPELINE = None, None

# --- Core Scraping & Analysis Functions ---
# URL detection regex - matches http:// or https:// URLs
URL_REGEX = re.compile(r'^https?://[^\s]+$', re.IGNORECASE)


def is_direct_url(text: str) -> bool:
    """Check if text is a direct URL rather than a search query."""
    if not text:
        return False
    text = text.strip()
    return bool(URL_REGEX.match(text))


def topic_to_urls(topic: str, num_results: int = 5) -> List[str]:
    """
    Finds news article URLs for a topic by scraping Google News.
    If topic is already a URL (http/https), returns it directly.
    This version uses a list of CSS selectors to robustly handle HTML changes.
    """
    # Detect if topic is actually a direct URL
    if is_direct_url(topic):
        logging.info(f"Direct URL detected, skipping Google search: {topic[:80]}...")
        return [topic.strip()]
    
    logging.info(f"Searching for '{topic}' on Google News...")
    search_url = f"https://www.google.com/search?q={up.quote(topic)}&tbm=nws&num={num_results + 5}"
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

    try:
        with requests.Session() as s:
            resp = s.get(search_url, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        urls = []
        
        # This expanded list of CSS selectors increases the chances of finding links
        # even if Google modifies its page structure.
        possible_selectors = [
            "a[jsname='YKoRaf']",                # A common, specific selector for news links
            "div.WlydOe a",                      # A known parent div for article links
            "div.n0jPhd.ynAwRc.MBeuO.nDgy9d a",    # A more complex, but sometimes used, structure
            "h3.not-italic a",                   # Selector for links within a heading tag
            "a.WlydOe",                          # A selector if the anchor tag itself has the class
            "div.g a"                            # A very generic selector for any link within a result block
        ]

        for selector in possible_selectors:
            for link in soup.select(selector):
                href = link.get('href')
                if not href:
                    continue

                # Handle Google's redirect URLs, which are most common
                if href.startswith("/url?q="):
                    cleaned_url = up.parse_qs(up.urlparse(href).query).get('q', [None])[0]
                    if cleaned_url:
                        urls.append(cleaned_url)
                # Handle direct links that might also appear
                elif href.startswith("http"):
                    urls.append(href)
            
            # If we found URLs with the current selector, we can stop and process them
            if urls:
                logging.info(f"Successfully found links using selector: '{selector}'")
                break

        if not urls:
            logging.error("Google scraping failed. Could not find any article links with known selectors.")
            return []

        # Deduplicate the list of URLs while preserving order and return the requested number
        unique_urls = list(dict.fromkeys(urls))
        logging.info(f"Found {len(unique_urls)} potential URLs for '{topic}'.")
        return unique_urls[:num_results]

    except requests.RequestException as e:
        logging.error(f"Failed to fetch search results from Google News: {e}")
        return []

def make_session() -> requests.Session:
    s = requests.Session(); retries = Retry(total=5, backoff_factor=0.8, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries)); s.headers.update({"User-Agent": DEFAULT_UA}); return s

def extract_text_and_meta(html: str) -> Tuple[str, Dict[str, Any], str]:
    if trafilatura:
        data = trafilatura.extract(html, output_format="json", with_metadata=True)
        if data:
            # Handle both string and dict return types from trafilatura
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    data = {}
            
            text = data.get("text")
            # Trafilatura's date can be a Unix timestamp or an ISO string
            pub_date = data.get('date')
            iso_date = None
            if pub_date:
                try:
                    # Check if it's a numeric timestamp
                    if str(pub_date).isdigit():
                        iso_date = dt.datetime.fromtimestamp(int(pub_date), tz=dt.timezone.utc).isoformat()
                    # Otherwise, try parsing it as a date string
                    elif dateparser:
                        iso_date = dateparser.parse(pub_date).isoformat()
                except (ValueError, TypeError, dateparser.ParserError if dateparser else Exception):
                    pass # Date parsing failed, will be None
            if text: return text, {"title": data.get("title"), "published_at": iso_date}, "trafilatura"
    
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "No Title"
    published_at = None
    if dateparser:
        time_tag = soup.find("time")
        if time_tag:
            try: published_at = dateparser.parse(time_tag.get("datetime") or time_tag.get_text()).isoformat()
            except (dateparser.ParserError, TypeError): pass
    ps = [p.get_text(strip=True) for p in (soup.find("article") or soup).find_all("p")]
    text = "\n\n".join([p for p in ps if p and len(p.split()) > 10])
    return text, {"title": title, "published_at": published_at}, "bs4"

def analyze_text(text: str, args: argparse.Namespace) -> Dict[str, Any]:
    analysis = {}
    if not text: return analysis
    if args.use_transformers_summary and SUMMARIZER_PIPELINE:
        analysis['summary'] = SUMMARIZER_PIPELINE(text, max_length=150, min_length=30, do_sample=False)[0]['summary_text']
    elif args.summarize and PlaintextParser:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        analysis['summary'] = " ".join(str(s) for s in LsaSummarizer()(parser.document, 5))
    if args.sentiment and TextBlob:
        blob = TextBlob(text); analysis['sentiment'] = {'polarity': blob.sentiment.polarity, 'subjectivity': blob.sentiment.subjectivity}
    if (args.extract_keywords or args.extract_entities) and NLP_MODEL:
        doc = NLP_MODEL(text)
        if args.extract_keywords:
            analysis['keywords_extracted'] = [t.text.lower() for t in doc if t.pos_ in ('NOUN', 'PROPN') and not t.is_stop and len(t.text) > 2]
        if args.extract_entities:
            analysis['entities'] = {ent.label_: sorted(list(set(e.text for e in doc.ents if e.label_ == ent.label_))) for ent in doc.ents}
    return analysis


def process_scraped_text(scrape_data: dict, args: argparse.Namespace) -> Optional[ArticleData]:
    """
    Takes raw scraped text, analyzes it, and formats the ArticleData dict.
    This is a SYNCHRONOUS, CPU-bound function designed to run in a thread.
    Uses robust extraction (trafilatura/readability/bs4) and creates clean 200-char snippets.
    """
    try:
        url = scrape_data.get('url')
        raw_content = scrape_data.get('content')  # may be raw text or HTML
        extraction_method = scrape_data.get('method')
        
        if not raw_content or len(raw_content) < 50:
            logging.warning(f"Insufficient content from {url}")
            return None
        
        # Use robust extraction: trafilatura -> readability -> bs4 -> passthrough
        clean_res = fetch_and_clean(url, html=raw_content, max_chars=12000)
        clean_text = clean_res.get("text") or ""
        title = clean_res.get("title") or (clean_text.split(".")[0][:100] if clean_text else "No Title")
        used_method = clean_res.get("method") or extraction_method or "unknown"
        
        if not clean_text or len(clean_text) < 50:
            logging.warning(f"Insufficient clean content from {url}")
            return None
        
        # Run NLP analysis on cleaned text
        analysis = analyze_text(clean_text, args)
        
        # Create short paraphrased snippet (≤200 chars, removes site chrome)
        snippet = paraphrase_snippet(clean_text, max_chars=200)
        
        # Normalize domain (strip www.)
        domain = up.urlsplit(url).netloc.lower().replace("www.", "")
        
        # Build forensic_dossier with proper structure (fixes [object Object] UI bug)
        forensic_entities = []
        entities_dict = analysis.get('entities', {})
        for entity_type, entity_names in entities_dict.items():
            for ent_name in (entity_names[:3] if isinstance(entity_names, list) else []):
                forensic_entities.append({
                    "name": ent_name,
                    "type": entity_type,
                    "reputation_score": 50,
                    "red_flags": [],
                    "source": domain
                })
        
        # Get domain-based authority if available
        domain_auth = get_domain_authority(domain)
        base_authority = domain_auth if domain_auth else None
        
        # Build ArticleData with normalized URL hash for deterministic dedupe
        return {
            "url": url,
            "canonical_url": url,
            "url_hash": hashlib.sha256(normalize_url_for_dedupe(url).encode()).hexdigest(),
            "domain": domain,
            "title": title,
            "published_at": None,
            "text": clean_text,
            "summary": snippet,  # Short ≤200 char snippet
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "extraction_method": used_method,
            "word_count": len(clean_text.split()) if clean_text else 0,
            "authority": base_authority,
            "forensic_dossier": {"entities": forensic_entities},
            **analysis,
        }
    except Exception as e:
        logging.error(f"Failed to analyze text from {scrape_data.get('url')}: {e}")
        return None
    

def scrape_and_analyze(url: str, session: requests.Session, args: argparse.Namespace) -> ArticleData:
    """Synchronous scrape and analyze - uses robust extraction."""
    resp = session.get(url, timeout=TIMEOUT); resp.raise_for_status(); html = resp.text
    
    # Use robust extraction
    clean_res = fetch_and_clean(url, html=html, max_chars=12000)
    clean_text = clean_res.get("text") or ""
    title = clean_res.get("title") or "No Title"
    used_method = clean_res.get("method") or "unknown"
    
    analysis = analyze_text(clean_text, args)
    snippet = paraphrase_snippet(clean_text, max_chars=200)
    domain = up.urlsplit(url).netloc.lower().replace("www.", "")
    
    return {
        "url": url, 
        "canonical_url": url, 
        "url_hash": hashlib.sha256(normalize_url_for_dedupe(url).encode()).hexdigest(),
        "domain": domain, 
        "title": title, 
        "published_at": None,
        "text": clean_text, 
        "summary": snippet,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), 
        "extraction_method": used_method,
        "word_count": len(clean_text.split()) if clean_text else 0, 
        **analysis,
    }

# --- Caching and Ranking ---
def get_cached_article(url_hash: str, conn: sqlite3.Connection, ttl: int) -> Optional[ArticleData]:
    if not conn: return None
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=ttl)).isoformat()
    cur = conn.cursor()
    cur.execute("SELECT data FROM cache WHERE url_hash = ? AND fetched_at >= ?", (url_hash, cutoff))
    row = cur.fetchone()
    if row: return json.loads(row[0])
    return None

def cache_article(article: ArticleData, conn: sqlite3.Connection):
    if not conn: return
    # Use a context manager for thread-safe, atomic commits
    with conn:
        conn.execute("INSERT OR REPLACE INTO cache (url_hash, fetched_at, data) VALUES (?, ?, ?)",
                         (article['url_hash'], article['fetched_at'], json.dumps(article)))

def rank_articles(articles: List[ArticleData], rank_by: str, topic: Optional[str]) -> List[ArticleData]:
    def sort_key(a: ArticleData):
        if rank_by == 'relevance' and topic:
            topic_words = set(topic.lower().split())
            title_score = len(topic_words.intersection(a.get('title', '').lower().split())) * 3
            summary_score = len(topic_words.intersection(a.get('summary', '').lower().split()))
            return title_score + summary_score
        if rank_by == 'sentiment':
            return abs(a.get('sentiment', {}).get('polarity', 0.0))
        # Default to date
        try: date = dt.datetime.fromisoformat(a.get("published_at", "1970-01-01T00:00:00+00:00"))
        except (ValueError, TypeError): date = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        return date

    return sorted(articles, key=sort_key, reverse=True)

# --- Visualization and Reporting ---
def generate_word_cloud_data(articles: List[ArticleData]) -> List[List]:
    if not WordCloud: return []
    all_keywords = [kw for a in articles for kw in a.get("keywords_extracted", [])]
    if not all_keywords: return []
    counts = collections.Counter(all_keywords)
    max_count = max(counts.values()) if counts else 1
    return [[kw, 10 + round(count / max_count * 50)] for kw, count in counts.most_common(100)]

def generate_charts_b64(articles: List[ArticleData]) -> Dict[str, str]:
    if not plt or not articles: return {}
    charts = {}
    titles = [textwrap.shorten(a.get('title', 'N/A'), width=20, placeholder="...") for a in articles]
    word_counts = [a.get('word_count', 0) for a in articles]
    sentiments = [a.get('sentiment', {}).get('polarity', 0) for a in articles]
    
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Word Count Bar Chart
    fig, ax = plt.subplots(figsize=(10, max(6, len(titles) * 0.5))); ax.barh(titles, word_counts, color='skyblue')
    ax.set_xlabel('Word Count'); ax.set_title('Article Word Counts'); ax.invert_yaxis(); plt.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format='png'); charts['word_count'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)

    # Sentiment Scatter Plot
    fig, ax = plt.subplots(figsize=(10, 6)); ax.scatter(word_counts, sentiments, color='coral', alpha=0.7)
    ax.set_xlabel('Word Count'); ax.set_ylabel('Sentiment Polarity'); ax.set_title('Sentiment vs. Word Count')
    ax.axhline(0, color='grey', lw=0.5); plt.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format='png'); charts['sentiment'] = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)
    
    return charts

def display_console_summary_table(articles: List[ArticleData]):
    """Prints a summary table to the console."""
    if not tabulate:
        logging.warning("`tabulate` library not found. Skipping console summary table. Try: pip install tabulate")
        return

    headers = ["Title", "Source", "Published", "Sentiment"]
    table_data = []
    for a in articles:
        sentiment_val = a.get('sentiment', {}).get('polarity')
        sentiment_str = f"{sentiment_val:.2f}" if sentiment_val is not None else "N/A"
        
        table_data.append([
            textwrap.shorten(a.get('title', 'N/A'), width=50, placeholder="..."),
            a.get('domain', ''),
            (a.get('published_at') or 'N/A').split('T')[0],
            sentiment_str
        ])
    
    print("\n--- Article Analysis Console Summary ---")
    print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))

def generate_html_dashboard(articles: List[ArticleData], topic: str, filepath: str, wc_data: List, charts: Dict):
    ENTITY_HTML_COLORS = { "PERSON": "#ffc107", "ORG": "#28a745", "GPE": "#007bff", "DATE": "#dc3545", "NORP": "#6f42c1", "EVENT": "#fd7e14"}

    def highlight_html(text, entities):
        if not entities or not text: return text
        replacements = []
        for label, names in entities.items():
            color = ENTITY_HTML_COLORS.get(label, "#6c757d")
            for name in sorted(names, key=len, reverse=True): # Process longer names first
                replacements.append((name, f'<span class="entity" title="{label}" style="background-color:{color};" data-entity-name="{name}" data-entity-type="{label}">{name}</span>'))
        
        # Use a regex to avoid replacing parts of words
        for old, new in replacements:
            try:
                text = re.sub(r'\b' + re.escape(old) + r'\b', new, text)
            except re.error:
                text = text.replace(old, new) # Fallback for complex names
        return text

    articles_html = ""
    for i, a in enumerate(articles):
        all_entities_str = " ".join(f"{label}:{name}" for label, names in a.get("entities", {}).items() for name in names)
        highlighted_summary = highlight_html(a.get('summary', 'N/A'), a.get('entities'))
        articles_html += f"""<div class="article" id="article-{i}" data-entities="{all_entities_str}">
        <h2><a href="{a.get('url', '#')}" target="_blank" rel="noopener noreferrer">{a.get('title', 'No Title')}</a></h2>
        <p class="meta"><b>Source:</b> {a.get('domain')} | <b>Published:</b> {(a.get('published_at') or 'N/A').split('T')[0]}</p>
        <div class="content summary"><b>Summary:</b> {highlighted_summary}</div>
        <div class="content sentiment"><b>Sentiment Polarity:</b> {a.get('sentiment', {}).get('polarity', 0.0):.2f}</div>
        <div class="content keywords"><b>Keywords:</b> {', '.join(a.get('keywords_extracted', []))}</div></div>"""
    
    html_template = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Analysis for: {topic}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/wordcloud2.js/1.1.0/wordcloud2.min.js"></script>
    <style>/* CSS_PLACEHOLDER */</style></head><body>
    <div class="sidebar"> <h2>Controls</h2> <div id="toc"></div> <hr>
        <label><input type="checkbox" id="toggle-summary" checked> Show Summaries</label>
        <label><input type="checkbox" id="toggle-sentiment" checked> Show Sentiment</label>
        <label><input type="checkbox" id="toggle-keywords" checked> Show Keywords</label>
        <hr> <div id="filter-status">No filter active</div> <button id="clear-filter">Clear Filter</button>
    </div>
    <div class="main-content"><h1>Analysis for Topic: {topic}</h1>
        <div class="card"><div id="wordcloud-container" style="height:300px;width:100%;"></div></div>
        {''.join(f'<div class="card"><h2>{title.replace("_", " ").title()}</h2><img src="data:image/png;base64,{b64}" style="max-width:100%;"></div>' for title, b64 in charts.items())}
        <div id="articles-container">{articles_html}</div>
    </div>
    <script>/* JS_PLACEHOLDER */</script></body></html>"""
    
    js_script = f"""
        const wc_data = {json.dumps(wc_data)};
        if(wc_data.length > 0) WordCloud(document.getElementById('wordcloud-container'), {{ list: wc_data, click: (item) => filterByKeyword(item[0]) }});
        
        const toc = document.getElementById('toc');
        document.querySelectorAll('.article h2').forEach((h2, i) => {{
            const link = document.createElement('a'); link.href = `#article-${{i}}`;
            link.textContent = h2.textContent.substring(0, 30) + '...'; toc.appendChild(link);
        }});

        document.getElementById('toggle-summary').addEventListener('change', e => document.body.classList.toggle('hide-summary', !e.target.checked));
        document.getElementById('toggle-sentiment').addEventListener('change', e => document.body.classList.toggle('hide-sentiment', !e.target.checked));
        document.getElementById('toggle-keywords').addEventListener('change', e => document.body.classList.toggle('hide-keywords', !e.target.checked));

        const allArticles = document.querySelectorAll('.article');
        const filterStatus = document.getElementById('filter-status');
        
        function applyFilter(text, filterFn) {{
            filterStatus.textContent = text;
            allArticles.forEach(article => article.style.display = filterFn(article) ? 'block' : 'none');
        }}
        
        function filterByKeyword(keyword) {{
            applyFilter(`Filtering by keyword: ${{keyword}}`, article => article.querySelector('.keywords').textContent.includes(keyword));
        }}

        document.getElementById('clear-filter').addEventListener('click', () => applyFilter('No filter active', () => true));
        document.addEventListener('click', e => {{
            if (e.target.classList.contains('entity')) {{
                const type = e.target.dataset.entityType; const name = e.target.dataset.entityName;
                applyFilter(`Filtering by ${{type}}: ${{name}}`, article => article.dataset.entities.includes(`{{type}}:{{name}}`));
            }}
        }});
    """
    
    css_style = """
    body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:0;display:flex;background:#e9ecef}
    .sidebar{width:250px;background:#f8f9fa;padding:1em;height:100vh;overflow-y:auto;position:fixed;border-right:1px solid #dee2e6}
    .sidebar h2{margin-top:0}.sidebar label{display:block;margin-bottom:0.5em;cursor:pointer}
    .main-content{margin-left:270px;padding:2em;width:calc(100% - 290px)}
    h1,h2{color:#343a40} a{color:#007bff;text-decoration:none} a:hover{text-decoration:underline}
    .card{background:white;border-radius:8px;box-shadow:0 4px 6px rgba(0,0,0,0.05);padding:1.5em;margin-bottom:2em}
    .article{border:1px solid #dee2e6;padding:1.5em;margin-bottom:1.5em;background:white;border-radius:8px;transition:all 0.3s ease}
    .meta{font-size:0.9em;color:#6c757d;margin-bottom:1em} b{color:#495057}
    .entity{cursor:pointer;padding:2px 5px;border-radius:4px;font-weight:bold;color:white;transition:opacity 0.2s ease}
    .entity:hover{opacity:0.8}
    #toc a{display:block;font-size:0.9em;margin-bottom:0.5em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:4px;border-radius:4px}
    #toc a:hover{background:#dee2e6}
    #filter-status{font-size:0.9em;color:#6c757d;margin:1em 0;font-style:italic}
    .hide-summary .summary, .hide-sentiment .sentiment, .hide-keywords .keywords {display:none}
    """
    
    html = html_template.replace("/* CSS_PLACEHOLDER */", css_style).replace("/* JS_PLACEHOLDER */", js_script)

    with open(filepath, 'w', encoding='utf-8') as f: f.write(html)
    logging.info(f"Interactive HTML dashboard saved to {filepath}")

# ----------------------------- NEW IMPORTABLE FUNCTION (REFACTORED) -----------------------------
async def get_diversified_evidence(topic: str, num_results: int = 5, use_cache: bool = True, cache_ttl: int = 86400) -> List[ArticleData]:
    """
    Finds, scrapes, and analyzes articles for a given topic to gather evidence.
    This ASYNC version uses the HybridScraper for robust, anti-blocking scraping.
    
    Args:
        topic: The topic to search for
        num_results: Number of articles to retrieve
        use_cache: Whether to use SQLite caching
        cache_ttl: Cache time-to-live in seconds (default: 1 day)
        
    Returns:
        List of ArticleData dicts with scraped and analyzed content
    """
    logging.info(f"Gathering diversified evidence for topic: '{topic}'")

    # 1. Mock args to control the analysis features
    _cache_ttl = cache_ttl  # Store in local variable to avoid scoping issue
    
    class MockArgs:
        summarize = True
        use_transformers_summary = False  # Use the faster sumy summarizer
        extract_keywords = True
        extract_entities = True
        sentiment = True
        fast_nlp = True  # Use faster NLP processing
        db = "scraper_cache.db" if use_cache else None
        cache_ttl = _cache_ttl
        force_refresh = False

    args = MockArgs()

    # 2. Initialize NLP model (idempotent - only loads once)
    global NLP_MODEL
    if (args.extract_keywords or args.extract_entities) and not NLP_MODEL:
        if spacy:
            try:
                logging.info("Initializing spaCy NLP model...")
                disable = ["parser", "tagger"] if args.fast_nlp else []
                NLP_MODEL = spacy.load("en_core_web_sm", disable=disable)
                logging.info("spaCy model loaded successfully.")
            except OSError:
                logging.warning("spaCy model not found. Downloading 'en_core_web_sm'...")
                spacy_download("en_core_web_sm")
                NLP_MODEL = spacy.load("en_core_web_sm", disable=disable)
        else:
            logging.warning("spaCy not installed. Keyword/entity extraction will be skipped.")
    
    # 3. Open DB Connection for caching
    db_conn = sqlite3.connect(args.db) if args.db else None
    if db_conn:
        db_conn.execute("CREATE TABLE IF NOT EXISTS cache (url_hash TEXT PRIMARY KEY, fetched_at TEXT, data TEXT)")
    
    # 4. Get URLs (run in thread since it's blocking/synchronous)
    try:
        urls = await asyncio.to_thread(topic_to_urls, topic, num_results)
    except Exception as e:
        logging.error(f"Failed to get URLs for topic '{topic}': {e}")
        urls = []
    
    if not urls:
        logging.warning(f"No URLs found for topic: {topic}")
        if db_conn:
            db_conn.close()
        return []

    # 5. Check cache before scraping
    urls_to_fetch = []
    successful_articles = []  # Articles from cache
    
    if db_conn:
        for url in dict.fromkeys(urls):  # Deduplicate
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            cached = None if args.force_refresh else get_cached_article(url_hash, db_conn, args.cache_ttl)
            if cached:
                logging.info(f"CACHE HIT: {url[:70]}...")
                successful_articles.append(cached)
            else:
                urls_to_fetch.append(url)
    else:
        urls_to_fetch = list(dict.fromkeys(urls))  # Just deduplicate
    
    if not urls_to_fetch:
        logging.info(f"All {len(successful_articles)} articles were found in cache.")
        if db_conn:
            db_conn.close()
        return successful_articles

    # 6. Scrape with HybridScraper (only URLs not in cache)
    logging.info(f"Using HybridScraper to fetch {len(urls_to_fetch)} URLs...")
    hybrid_scraper = HybridScraper()
    
    # scrape_multiple runs all scrapes in parallel with intelligent fallback
    scrape_results = await hybrid_scraper.scrape_multiple(urls_to_fetch, max_concurrent=3)
    
    successful_scrapes = [r for r in scrape_results if r.get('content')]
    failed_urls = [r['url'] for r in scrape_results if not r.get('content')]
    
    if not successful_scrapes:
        logging.warning(f"All scraping attempts failed for topic: {topic}")
        if db_conn:
            db_conn.close()
        return successful_articles  # Return cached articles if any

    # 7. Analyze concurrently (CPU-bound NLP analysis in threads)
    logging.info(f"Analyzing {len(successful_scrapes)} successfully scraped articles...")
    
    # Create tasks to run analysis in parallel threads
    analysis_tasks = [
        asyncio.to_thread(process_scraped_text, scrape_data, args)
        for scrape_data in successful_scrapes
    ]
    
    # Run all analysis tasks in parallel
    analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
    
    # Filter out failures and add to cache
    newly_processed_articles = []
    for result in analysis_results:
        if isinstance(result, Exception):
            logging.error(f"Analysis error: {result}")
        elif result:  # Valid ArticleData
            cache_article(result, db_conn)  # Add to cache
            newly_processed_articles.append(result)

    # ==================================================================================
    # EVIDENCE QUALITY: Normalize authority, dedupe, and return top-N
    # ==================================================================================
    
    # Normalize authority for all newly processed articles
    for art in newly_processed_articles:
        raw_auth = art.get('authority')
        if raw_auth is None:
            # Try domain-based authority first
            domain = art.get('domain', '')
            domain_auth = get_domain_authority(domain)
            if domain_auth is not None:
                art['authority'] = normalize_authority(domain_auth)
            else:
                # Heuristic: longer, better-analyzed article = slightly higher authority
                wc = art.get("word_count", 0)
                has_entities = bool(art.get('entities'))
                has_sentiment = bool(art.get('sentiment'))
                base_auth = 0.2 + (wc / 3000) + (0.1 if has_entities else 0) + (0.05 if has_sentiment else 0)
                art['authority'] = normalize_authority(min(0.9, base_auth))
        else:
            art['authority'] = normalize_authority(raw_auth)
    
    # Also normalize cached articles that may not have authority
    for art in successful_articles:
        if 'authority' not in art or art.get('authority') is None:
            domain = art.get('domain', '')
            domain_auth = get_domain_authority(domain)
            if domain_auth is not None:
                art['authority'] = normalize_authority(domain_auth)
            else:
                wc = art.get("word_count", 0)
                art['authority'] = normalize_authority(min(0.7, 0.2 + (wc / 3000)))
    
    # Merge cached + newly processed and dedupe
    all_articles = successful_articles + newly_processed_articles
    all_articles = dedupe_articles_by_url(all_articles)
    
    # Rank by authority (and word_count as tiebreaker) and limit to top N evidence items
    N_EVIDENCE = max(5, num_results)  # At least 5, or requested amount
    all_articles = sorted(
        all_articles, 
        key=lambda a: (a.get('authority', 0), a.get('word_count', 0)), 
        reverse=True
    )[:N_EVIDENCE]
    
    # Attach 'relevance' score for weighting when combining confidences
    # (Future: compute actual topic overlap)
    for a in all_articles:
        a['relevance'] = 1.0
    
    if db_conn:
        db_conn.close()

    logging.info(f"✅ Successfully gathered {len(all_articles)} evidence articles (deduped from {len(successful_articles)} cached + {len(newly_processed_articles)} new).")
    if failed_urls:
        logging.warning(f"⚠️  Failed to gather evidence from {len(failed_urls)} sources.")
    
    # Log scraper statistics
    stats = hybrid_scraper.get_stats()
    logging.info(f"📊 Scraper statistics: {stats}")

    return all_articles



# ==================================================================================
# HYBRID SCRAPER - Robust Multi-Method Scraping Engine
# ==================================================================================

class JinaScraper:
    """Jina Reader API scraper - fastest method"""
    
    def __init__(self):
        self.jina_api_key = os.getenv('JINA_API_KEY', '')
        
    async def scrape(self, url: str) -> str:
        """Scrape using Jina Reader API"""
        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {
                "Authorization": f"Bearer {self.jina_api_key}",
                "X-Return-Format": "text"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(jina_url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Jina successfully scraped {url}")
                        return content
                    else:
                        logger.warning(f"Jina failed for {url}: {response.status}")
                        return ""
        except Exception as e:
            logger.error(f"Jina error for {url}: {e}")
            return ""


class PlaywrightScraper:
    """Browser automation scraper - handles JS and anti-bot measures"""
    
    def __init__(self):
        self.timeout = 30000
        
    async def scrape(self, url: str, wait_for_selector: str = 'body') -> str:
        """Scrape using Playwright with stealth techniques"""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=DEFAULT_UA
                )
                
                # Add stealth scripts
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                page = await context.new_page()
                
                try:
                    await page.goto(url, wait_until='networkidle', timeout=self.timeout)
                except:
                    await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
                
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                except:
                    await asyncio.sleep(2)
                
                content = await page.content()
                await browser.close()
                
                # Parse content
                soup = BeautifulSoup(content, 'html.parser')
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                
                if len(text) > 100:
                    logger.info(f"✅ Playwright successfully scraped {url}")
                    return text
                else:
                    logger.warning(f"Playwright got minimal content from {url}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Playwright error for {url}: {e}")
            return ""


class StealthRequestsScraper:
    """Enhanced requests with stealth headers and retries"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        
    def get_headers(self) -> dict:
        """Generate realistic browser headers"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def scrape(self, url: str, max_retries: int = 3) -> str:
        """Scrape with retries and random delays"""
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(
                    url,
                    headers=self.get_headers(),
                    timeout=15,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    # Fix encoding issues
                    response.encoding = response.apparent_encoding or 'utf-8'
                    
                    soup = BeautifulSoup(response.text, 'html.parser', from_encoding='utf-8')
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()
                    
                    text = soup.get_text(separator='\n', strip=True)
                    
                    # Ensure clean UTF-8 text
                    try:
                        text = text.encode('utf-8', errors='ignore').decode('utf-8')
                    except:
                        pass
                    
                    if len(text) > 100:
                        logger.info(f"✅ Stealth requests succeeded for {url}")
                        return text
                        
            except Exception as e:
                logger.warning(f"Stealth requests attempt {attempt + 1} failed for {url}: {e}")
                
        return ""


class HybridScraper:
    """Combines multiple scraping methods with intelligent fallback"""
    
    def __init__(self):
        self.jina = JinaScraper()
        self.playwright = PlaywrightScraper()
        self.stealth = StealthRequestsScraper()
        
        # Track success rates
        self.success_stats = {
            'jina': {'success': 0, 'total': 0},
            'playwright': {'success': 0, 'total': 0},
            'stealth': {'success': 0, 'total': 0}
        }
        
    async def scrape(self, url: str) -> Dict[str, str]:
        """
        Try multiple methods in order of preference.
        Returns dict with content and method used.
        """
        logger.info(f"🔍 Starting scrape for: {url}")
        
        # Strategy 1: Try Jina (fastest)
        self.success_stats['jina']['total'] += 1
        content = await self.jina.scrape(url)
        if self._is_valid_content(content):
            self.success_stats['jina']['success'] += 1
            return {'content': content, 'method': 'jina', 'url': url}
        
        # Strategy 2: Try stealth requests (fast, medium complexity)
        self.success_stats['stealth']['total'] += 1
        content = await asyncio.to_thread(self.stealth.scrape, url)
        if self._is_valid_content(content):
            self.success_stats['stealth']['success'] += 1
            return {'content': content, 'method': 'stealth_requests', 'url': url}
        
        # Strategy 3: Try Playwright (handles JS, most anti-bot)
        self.success_stats['playwright']['total'] += 1
        content = await self.playwright.scrape(url)
        if self._is_valid_content(content):
            self.success_stats['playwright']['success'] += 1
            return {'content': content, 'method': 'playwright', 'url': url}
        
        # All methods failed
        logger.error(f"❌ All scraping methods failed for {url}")
        return {'content': '', 'method': 'failed', 'url': url}
    
    def _is_valid_content(self, content: str) -> bool:
        """Check if scraped content is valid and substantial"""
        if not content or len(content) < 100:
            return False
        
        # Check for common error indicators
        error_indicators = [
            'access denied', 'captcha', 'please verify', 'robot',
            'blocked', '403 forbidden', '404 not found', '503 service'
        ]
        
        content_lower = content.lower()
        return not any(indicator in content_lower for indicator in error_indicators)
    
    async def scrape_multiple(self, urls: List[str], max_concurrent: int = 3) -> List[Dict[str, str]]:
        """Scrape multiple URLs with concurrency control"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                return await self.scrape(url)
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"Exception scraping {url}: {result}")
                processed_results.append({'content': '', 'method': 'error', 'url': url})
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> dict:
        """Get success rate statistics"""
        stats = {}
        for method, data in self.success_stats.items():
            if data['total'] > 0:
                success_rate = (data['success'] / data['total']) * 100
                stats[method] = {
                    'success': data['success'],
                    'total': data['total'],
                    'success_rate': f"{success_rate:.1f}%"
                }
        return stats


# ----------------------------- MAIN CLI ------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Article Scraper & Analysis Pipeline (Professional Edition)", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", help="Topic to find articles for via Google News")
    group.add_argument("--urls", nargs="*", help="List of URLs to scrape"); group.add_argument("--file", help="File with URLs")
    group.add_argument("--load-report", metavar="FILE", help="Load analysis from a JSON report file, skipping scraping")

    parser.add_argument("--num-results", type=int, default=5, help="Number of articles for a topic")
    parser.add_argument("--db", help="SQLite DB path for caching")
    parser.add_argument("--summarize", action="store_true", help="Generate summary"); parser.add_argument("--use-transformers-summary", action="store_true", help="Use advanced abstractive summary")
    parser.add_argument("--extract-keywords", action="store_true", help="Extract keywords")
    parser.add_argument("--extract-entities", action="store_true", help="Extract named entities")
    parser.add_argument("--sentiment", action="store_true", help="Perform sentiment analysis")
    parser.add_argument("--rank-by", choices=['date', 'relevance', 'sentiment'], default='date', help="How to rank articles")
    parser.add_argument("--summary-table", action="store_true", help="Display a final summary table in console")
    parser.add_argument("--save-failures", help="File path to save failed URLs")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Concurrent workers")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--dashboard", metavar="FILE", help="Generate and save an interactive HTML dashboard report.")
    parser.add_argument("--save-report", metavar="FILE", help="Save full analysis results to a JSON file.")
    parser.add_argument("--color", action="store_true", help="Highlight entities with color in the console output.")
    parser.add_argument("--cache-ttl", type=int, default=86400, help="Cache Time-To-Live in seconds")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache and re-scrape all URLs")
    parser.add_argument("--fast-nlp", action="store_true", help="Use faster spaCy processing by disabling some components")
    
    args = parser.parse_args(argv)
    
    if args.color and Fore: colorama_init()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)-8s %(message)s", handlers=[logging.StreamHandler(sys.stdout)])

    successful_articles = []
    topic = args.topic or "Loaded Report"

    if args.load_report:
        logging.info(f"Loading articles from report: {args.load_report}")
        try:
            with open(args.load_report, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            successful_articles = report_data['articles']
            topic = report_data.get('topic', topic)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Could not load report: {e}"); return 1
    else:
        # --- Setup Analysis Models & DB ---
        global NLP_MODEL, SUMMARIZER_PIPELINE
        if args.sentiment and not TextBlob:
            logging.warning("TextBlob not installed. Sentiment analysis will be skipped. Try: pip install textblob")
        if (args.extract_keywords or args.extract_entities) and not spacy:
            logging.warning("spaCy not installed. Keyword/entity extraction will be skipped. Try: pip install spacy")

        if args.use_transformers_summary and transformers_pipeline:
            try:
                logging.info("Initializing Transformer summarization pipeline (this may take a moment)...")
                SUMMARIZER_PIPELINE = transformers_pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
                logging.info("Transformer pipeline loaded successfully.")
            except Exception as e:
                logging.error(f"Failed to load Transformer model: {e}")
                SUMMARIZER_PIPELINE = None # Ensure it's None on failure
        
        if args.extract_keywords or args.extract_entities:
            if spacy:
                try:
                    disable = ["parser", "tagger"] if args.fast_nlp else []
                    NLP_MODEL = spacy.load("en_core_web_sm", disable=disable)
                except OSError:
                    logging.warning("Downloading spaCy model 'en_core_web_sm'..."); spacy_download("en_core_web_sm"); NLP_MODEL = spacy.load("en_core_web_sm")

        db_conn = sqlite3.connect(args.db) if args.db else None
        if db_conn: db_conn.execute("CREATE TABLE IF NOT EXISTS cache (url_hash TEXT PRIMARY KEY, fetched_at TEXT, data TEXT)")

        urls = []; topic = args.topic
        if args.topic: urls.extend(topic_to_urls(args.topic, args.num_results))
        elif args.urls: urls.extend(args.urls); topic = "Custom URL List"
        elif args.file:
            with open(args.file, 'r') as f: urls.extend([line.strip() for line in f if line.strip()]); topic = args.file

        if not urls: logging.error("No URLs to process."); return 1
        
        session = make_session(); failed_urls = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_url = {}
            urls_to_fetch = []
            for url in dict.fromkeys(urls): # Deduplicate URLs
                url_hash = hashlib.sha256(url.encode()).hexdigest()
                cached = None if args.force_refresh else get_cached_article(url_hash, db_conn, args.cache_ttl)
                if cached:
                    logging.info(f"CACHE HIT: {url[:70]}...")
                    successful_articles.append(cached)
                else:
                    urls_to_fetch.append(url)
            
            future_to_url = {executor.submit(scrape_and_analyze, url, session, args): url for url in urls_to_fetch}
            
            iterable = concurrent.futures.as_completed(future_to_url)
            if tqdm and future_to_url: iterable = tqdm(iterable, total=len(future_to_url), desc="Scraping & Analyzing")
            for future in iterable:
                url = future_to_url[future]
                try:
                    article_data = future.result()
                    successful_articles.append(article_data)
                    cache_article(article_data, db_conn)
                except Exception: failed_urls.append(url); logging.exception(f"Failed to process {url}")
        
        if db_conn: db_conn.close()

    if successful_articles:
        successful_articles = rank_articles(successful_articles, args.rank_by, topic)
        
        wc_data = generate_word_cloud_data(successful_articles)
        charts = generate_charts_b64(successful_articles)

        if args.summary_table:
            display_console_summary_table(successful_articles)
        if args.dashboard: generate_html_dashboard(successful_articles, topic, args.dashboard, wc_data, charts)
        
        if args.save_report:
            with open(args.save_report, 'w', encoding='utf-8') as f:
                json.dump({"topic": topic, "articles": successful_articles}, f, indent=2)
            logging.info(f"Full analysis report saved to {args.save_report}")

    logging.info(f"Pipeline finished. Processed: {len(successful_articles)}")
    if 'failed_urls' in locals() and failed_urls:
        logging.warning(f"Failed to process {len(failed_urls)} URLs:\n" + "\n".join(f"- {url}" for url in failed_urls))

    return 0

if __name__ == "__main__":
    sys.exit(main())

import asyncio
import logging
import os
import random
import time
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class JinaScraper:
    """Original Jina Reader scraper - fastest method"""
    
    def __init__(self):
        self.jina_api_key = os.getenv('JINA_API_KEY', '')
        
    async def scrape(self, url: str) -> str:
        """Scrape using Jina Reader API"""
        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {
                "Authorization": f"Bearer {self.jina_api_key}",
                "X-Return-Format": "text"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(jina_url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Jina successfully scraped {url}")
                        return content
                    else:
                        logger.warning(f"Jina failed for {url}: {response.status}")
                        return ""
        except Exception as e:
            logger.error(f"Jina error for {url}: {e}")
            return ""


class PlaywrightScraper:
    """Browser automation scraper - handles JS and most anti-bot"""
    
    def __init__(self):
        self.timeout = 30000
        
    async def scrape(self, url: str, wait_for_selector: str = 'body') -> str:
        """Scrape using Playwright with stealth techniques"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process'
                    ]
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060}
                )
                
                # Add stealth scripts
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    window.chrome = {
                        runtime: {}
                    };
                """)
                
                page = await context.new_page()
                
                # Navigate with retry logic
                try:
                    await page.goto(url, wait_until='networkidle', timeout=self.timeout)
                except:
                    await page.goto(url, wait_until='domcontentloaded', timeout=self.timeout)
                
                # Wait for content
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                except:
                    await asyncio.sleep(2)
                
                # Scroll to load lazy content
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                
                content = await page.content()
                await browser.close()
                
                # Parse content
                soup = BeautifulSoup(content, 'html.parser')
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                
                if len(text) > 100:
                    logger.info(f"✅ Playwright successfully scraped {url}")
                    return text
                else:
                    logger.warning(f"Playwright got minimal content from {url}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Playwright error for {url}: {e}")
            return ""


class StealthRequestsScraper:
    """Enhanced requests with stealth headers and retries"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        
    def get_headers(self) -> dict:
        """Generate realistic browser headers"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'TE': 'trailers'
        }
    
    def scrape(self, url: str, max_retries: int = 3) -> str:
        """Scrape with retries and random delays"""
        for attempt in range(max_retries):
            try:
                # Random delay to avoid rate limiting
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(
                    url,
                    headers=self.get_headers(),
                    timeout=15,
                    allow_redirects=True,
                    verify=True
                )
                
                if response.status_code == 200:
                    # Fix encoding issues
                    response.encoding = response.apparent_encoding or 'utf-8'
                    
                    soup = BeautifulSoup(response.text, 'html.parser', from_encoding='utf-8')
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()
                    
                    text = soup.get_text(separator='\n', strip=True)
                    
                    # Ensure clean UTF-8 text
                    try:
                        text = text.encode('utf-8', errors='ignore').decode('utf-8')
                    except:
                        pass
                    
                    if len(text) > 100:
                        logger.info(f"✅ Stealth requests succeeded for {url}")
                        return text
                        
            except Exception as e:
                logger.warning(f"Stealth requests attempt {attempt + 1} failed for {url}: {e}")
                
        return ""


class ScraperAPIScraper:
    """ScraperAPI - handles CAPTCHAs and complex anti-bot"""
    
    def __init__(self):
        self.api_key = os.getenv('SCRAPERAPI_KEY', '')
        
    def scrape(self, url: str) -> str:
        """Scrape using ScraperAPI"""
        if not self.api_key:
            logger.warning("ScraperAPI key not set")
            return ""
            
        try:
            api_url = f"http://api.scraperapi.com"
            params = {
                'api_key': self.api_key,
                'url': url,
                'render': 'true',  # Enable JavaScript rendering
                'country_code': 'us'
            }
            
            response = requests.get(api_url, params=params, timeout=60)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                logger.info(f"✅ ScraperAPI successfully scraped {url}")
                return text
            else:
                logger.error(f"ScraperAPI failed for {url}: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"ScraperAPI error for {url}: {e}")
            return ""


class ZenRowsScraper:
    """ZenRows - alternative CAPTCHA solver"""
    
    def __init__(self):
        self.api_key = os.getenv('ZENROWS_API_KEY', '')
        
    def scrape(self, url: str) -> str:
        """Scrape using ZenRows"""
        if not self.api_key:
            logger.warning("ZenRows API key not set")
            return ""
            
        try:
            api_url = "https://api.zenrows.com/v1/"
            params = {
                'apikey': self.api_key,
                'url': url,
                'js_render': 'true',
                'antibot': 'true',
                'premium_proxy': 'true'
            }
            
            response = requests.get(api_url, params=params, timeout=60)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                logger.info(f"✅ ZenRows successfully scraped {url}")
                return text
            else:
                logger.error(f"ZenRows failed for {url}: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"ZenRows error for {url}: {e}")
            return ""


class HybridScraper:
    """Combines all scraping methods with intelligent fallback"""
    
    def __init__(self):
        self.jina = JinaScraper()
        self.playwright = PlaywrightScraper()
        self.stealth = StealthRequestsScraper()
        self.scraper_api = ScraperAPIScraper()
        self.zenrows = ZenRowsScraper()
        
        # Track success rates for optimization
        self.success_stats = {
            'jina': {'success': 0, 'total': 0},
            'playwright': {'success': 0, 'total': 0},
            'stealth': {'success': 0, 'total': 0},
            'scraper_api': {'success': 0, 'total': 0},
            'zenrows': {'success': 0, 'total': 0}
        }
        
    async def scrape(self, url: str) -> Dict[str, str]:
        """
        Try multiple methods in order of preference
        Returns dict with content and method used
        """
        logger.info(f"🔍 Starting scrape for: {url}")
        
        # Strategy 1: Try Jina (fastest, works for most sites)
        self.success_stats['jina']['total'] += 1
        content = await self.jina.scrape(url)
        if self._is_valid_content(content):
            self.success_stats['jina']['success'] += 1
            return {'content': content, 'method': 'jina', 'url': url}
        
        # Strategy 2: Try stealth requests (fast, medium complexity)
        self.success_stats['stealth']['total'] += 1
        content = await asyncio.to_thread(self.stealth.scrape, url)
        if self._is_valid_content(content):
            self.success_stats['stealth']['success'] += 1
            return {'content': content, 'method': 'stealth_requests', 'url': url}
        
        # Strategy 3: Try Playwright (handles JS, most anti-bot)
        self.success_stats['playwright']['total'] += 1
        content = await self.playwright.scrape(url)
        if self._is_valid_content(content):
            self.success_stats['playwright']['success'] += 1
            return {'content': content, 'method': 'playwright', 'url': url}
        
        # Strategy 4: Try ScraperAPI (handles CAPTCHAs)
        self.success_stats['scraper_api']['total'] += 1
        content = await asyncio.to_thread(self.scraper_api.scrape, url)
        if self._is_valid_content(content):
            self.success_stats['scraper_api']['success'] += 1
            return {'content': content, 'method': 'scraper_api', 'url': url}
        
        # Strategy 5: Last resort - ZenRows
        self.success_stats['zenrows']['total'] += 1
        content = await asyncio.to_thread(self.zenrows.scrape, url)
        if self._is_valid_content(content):
            self.success_stats['zenrows']['success'] += 1
            return {'content': content, 'method': 'zenrows', 'url': url}
        
        # All methods failed
        logger.error(f"❌ All scraping methods failed for {url}")
        return {'content': '', 'method': 'failed', 'url': url}
    
    def _is_valid_content(self, content: str) -> bool:
        """Check if scraped content is valid and substantial"""
        if not content:
            return False
        
        # Must have minimum length
        if len(content) < 100:
            return False
        
        # Check for common error indicators
        error_indicators = [
            'access denied',
            'captcha',
            'please verify',
            'robot',
            'blocked',
            '403 forbidden',
            '404 not found',
            '503 service'
        ]
        
        content_lower = content.lower()
        if any(indicator in content_lower for indicator in error_indicators):
            return False
        
        return True
    
    async def scrape_multiple(self, urls: List[str], max_concurrent: int = 3) -> List[Dict[str, str]]:
        """Scrape multiple URLs with concurrency control"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                return await self.scrape(url)
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"Exception scraping {url}: {result}")
                processed_results.append({'content': '', 'method': 'error', 'url': url})
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> dict:
        """Get success rate statistics"""
        stats = {}
        for method, data in self.success_stats.items():
            if data['total'] > 0:
                success_rate = (data['success'] / data['total']) * 100
                stats[method] = {
                    'success': data['success'],
                    'total': data['total'],
                    'success_rate': f"{success_rate:.1f}%"
                }
        return stats


# Legacy ProScraper for backwards compatibility
class ProScraper:
    """Wrapper for backwards compatibility"""
    
    def __init__(self):
        self.hybrid = HybridScraper()
    
    async def scrape(self, url: str) -> str:
        """Scrape single URL - returns content only"""
        result = await self.hybrid.scrape(url)
        return result['content']
    
    async def scrape_multiple(self, urls: List[str]) -> Dict[str, str]:
        """Scrape multiple URLs - returns dict of url: content"""
        results = await self.hybrid.scrape_multiple(urls)
        return {r['url']: r['content'] for r in results}


# Example usage
async def main():
    scraper = HybridScraper()
    
    # Test URLs
    test_urls = [
        "https://www.bbc.com/news",
        "https://www.theguardian.com",
        "https://www.reuters.com"
    ]
    
    results = await scraper.scrape_multiple(test_urls)
    
    for result in results:
        print(f"\n{'='*80}")
        print(f"URL: {result['url']}")
        print(f"Method: {result['method']}")
        print(f"Content length: {len(result['content'])} chars")
        print(f"Preview: {result['content'][:200]}...")
    
    print(f"\n{'='*80}")
    print("Statistics:")
    print(scraper.get_stats())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

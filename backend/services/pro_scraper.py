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
def topic_to_urls(topic: str, num_results: int = 5) -> List[str]:
    """
    Finds news article URLs for a topic by scraping Google News.
    This version uses a list of CSS selectors to robustly handle HTML changes.
    """
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
    

def scrape_and_analyze(url: str, session: requests.Session, args: argparse.Namespace) -> ArticleData:
    resp = session.get(url, timeout=TIMEOUT); resp.raise_for_status(); html = resp.text
    text, meta, method = extract_text_and_meta(html)
    analysis = analyze_text(text or "", args)
    return {
        "url": url, "canonical_url": url, "url_hash": hashlib.sha256(url.encode()).hexdigest(),
        "domain": up.urlsplit(url).netloc, "title": meta.get("title"), "published_at": meta.get("published_at"),
        "text": text, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "extraction_method": method,
        "word_count": len(text.split()) if text else 0, **analysis,
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

# ----------------------------- NEW IMPORTABLE FUNCTION -----------------------------
def get_diversified_evidence(topic: str, num_results: int = 5) -> List[ArticleData]:
    """
    Finds, scrapes, and analyzes articles for a given topic to gather evidence.
    This function is designed to be imported and used by other scripts (e.g., a server).
    It initializes necessary models and reuses the core scraping/analysis logic.
    """
    logging.info(f"Gathering diversified evidence for topic: '{topic}'")

    # 1. Mock args to control the analysis features since we're not using the CLI parser.
    class MockArgs:
        summarize = True
        use_transformers_summary = False  # Use the faster sumy summarizer
        extract_keywords = True
        extract_entities = True
        sentiment = True
        workers = 4
        fast_nlp = True # Use faster NLP processing for server environments

    args = MockArgs()

    # 2. Idempotent initialization of the global NLP model.
    # This ensures the model is loaded only once.
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
                NLP_MODEL = spacy.load("en_core_web_sm")
        else:
            logging.warning("spaCy not installed. Keyword/entity extraction will be skipped.")
    
    # 3. Get URLs for the topic.
    urls = topic_to_urls(topic, num_results)
    if not urls:
        logging.warning(f"No URLs found for topic: {topic}")
        return []

    # 4. Scrape and analyze concurrently, reusing existing functions.
    session = make_session()
    successful_articles = []
    failed_urls = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_url = {executor.submit(scrape_and_analyze, url, session, args): url for url in set(urls)}
        
        iterable = concurrent.futures.as_completed(future_to_url)
        if tqdm: iterable = tqdm(iterable, total=len(future_to_url), desc="Gathering Evidence")

        for future in iterable:
            url = future_to_url[future]
            try:
                article_data = future.result()
                if article_data and article_data.get('text'):
                    successful_articles.append(article_data)
            except Exception as e:
                failed_urls.append(url)
                logging.error(f"Failed to process {url} for evidence: {e}", exc_info=False)

    logging.info(f"Successfully gathered evidence from {len(successful_articles)} sources for '{topic}'.")
    if failed_urls:
        logging.warning(f"Failed to gather evidence from {len(failed_urls)} sources.")

    return successful_articles


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
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()
                    
                    text = soup.get_text(separator='\n', strip=True)
                    
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

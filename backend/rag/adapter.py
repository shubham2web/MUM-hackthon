# rag/adapter.py
"""
RAG Evidence Adapter for ATLAS v4.1.3

Provides the adapter layer between the raw scraper output and the verdict engine:
- process_scraper_results(): Clean, dedupe, normalize, and format evidence
- build_evidence_prompt(): Create evidence-constrained LLM system prompt
- format_citations(): Insert citation markers [1], [2], etc.

This is the central integration point for RAG → Chat & Debate flows.
"""

import hashlib
import re
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger("rag.adapter")

# Configuration
MAX_SNIPPET_CHARS = 200
MAX_EVIDENCE_ITEMS = 10
MIN_AUTHORITY_THRESHOLD = 0.3

# Domain authority tiers
TIER_1_DOMAINS = [
    'reuters.com', 'apnews.com', 'bbc.com', 'bbc.co.uk',
    '.gov', '.edu', 'who.int', 'un.org', 'factcheck.org',
    'snopes.com', 'politifact.com', 'fullfact.org', 'nature.com', 'science.org'
]

TIER_2_DOMAINS = [
    'nytimes.com', 'washingtonpost.com', 'theguardian.com',
    'economist.com', 'ft.com', 'bloomberg.com', 'wsj.com',
    'npr.org', 'pbs.org', 'thehindu.com', 'ndtv.com'
]


def normalize_url(url: str) -> str:
    """
    Normalize URL for deterministic deduplication.
    Strips query params, fragments, normalizes scheme and domain.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        # Normalize: lowercase domain, remove www., strip trailing slash, remove query/fragment
        domain = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.rstrip('/')
        normalized = urlunparse((
            parsed.scheme or "https",
            domain,
            path,
            "",  # params
            "",  # query
            ""   # fragment
        ))
        return normalized
    except Exception:
        return url


def compute_url_hash(url: str) -> str:
    """Compute deterministic hash for normalized URL."""
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()


def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return domain
    except Exception:
        return ""


def sanitize_title(title: str, max_chars: int = 100) -> str:
    """
    Sanitize title to remove UI junk and site chrome.
    Removes LOGIN, SUBSCRIBE, navigation text from titles.
    """
    if not title:
        return "Unknown Source"
    
    # NDTV breadcrumb and UI garbage removal
    NDTV_BREADCRUMB = [
        "Our Network", "NDTV", "हिन्दी", "मराठी", "World", "Profit",
        "Apps", "Live TV", "India", "Entertainment", "Movies",
        "Latest", "ePaper", "Delhi", "°C", "MPCG", "Marathi"
    ]
    
    if any(b in title for b in NDTV_BREADCRUMB):
        # Remove everything until the LAST segment (the actual headline)
        if "|" in title:
            parts = [p.strip() for p in title.split("|") if p.strip()]
            if len(parts) > 1:
                title = parts[-1]
        elif "•" in title:
            parts = [p.strip() for p in title.split("•") if p.strip()]
            if len(parts) > 1:
                title = parts[-1]
    
    # Remove common UI junk from titles
    title_junk_patterns = [
        r'(LOGIN|SUBSCRIBE|Sign in|Log in|Register)\s*[-|—:]*\s*',
        r'[-|—:]\s*(LOGIN|SUBSCRIBE|Sign in|Log in|Register)\s*$',
        r'\s*\|\s*(Home|News|Opinion|Business|Tech|Sport|World)\s*$',
        r'^\s*(Home|Dashboard|Latest)\s*[-|—:]\s*',
        r'\s*[-|—]\s*[A-Z][a-z]+\s+(News|Times|Post|Tribune|Journal)\s*$',  # - BBC News, etc
    ]
    
    clean_title = title
    for pattern in title_junk_patterns:
        clean_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE)
    
    # Clean whitespace
    clean_title = ' '.join(clean_title.split()).strip()
    
    # If title is mostly junk and now empty, fallback
    if not clean_title or len(clean_title) < 5:
        return "Unknown Source"
    
    # Truncate if too long
    if len(clean_title) > max_chars:
        clean_title = clean_title[:max_chars - 3] + "..."
    
    return clean_title


def calculate_authority(url: str, domain: str, existing_authority: Optional[float] = None) -> float:
    """
    Calculate authority score (0.0-1.0) based on domain tier.
    If existing_authority provided and valid, use it.
    """
    if existing_authority is not None:
        try:
            auth = float(existing_authority)
            if 0.0 <= auth <= 1.0:
                return round(auth, 3)
            elif 1.0 < auth <= 100.0:
                return round(auth / 100.0, 3)
        except (ValueError, TypeError):
            pass
    
    domain_lower = domain.lower() if domain else ""
    url_lower = url.lower() if url else ""
    
    # Tier 1: 0.85-1.0
    for t1 in TIER_1_DOMAINS:
        if t1 in domain_lower or t1 in url_lower:
            return 0.9
    
    # Tier 2: 0.65-0.84
    for t2 in TIER_2_DOMAINS:
        if t2 in domain_lower or t2 in url_lower:
            return 0.75
    
    # Default: 0.5
    return 0.5


def sanitize_snippet(text: str, max_chars: int = MAX_SNIPPET_CHARS) -> str:
    """
    Sanitize and truncate snippet text.
    - Removes UI junk (Subscribe, Sign in, LOGIN, etc.)
    - Truncates to max_chars
    - Cleans whitespace
    """
    if not text:
        return ""
    
    # NDTV and Indian news site specific patterns
    BAD_PATTERNS = [
        r'Delhi\s*\d+°C',
        r'Our Network',
        r'NDTV',
        r'Download the.*App Store.*',
        r'Choose Your Destination',
        r'Edition India World',
        r'ePaper',
        r'Live TV',
        r'SUBSCRIBE',
        r'Sign in',
        r'Login',
    ]
    
    clean_text = text
    for pat in BAD_PATTERNS:
        clean_text = re.sub(pat, '', clean_text, flags=re.IGNORECASE)
    
    # Remove common UI strings and site chrome junk
    junk_patterns = [
        # Authentication / subscription noise
        r'(Subscribe|Sign in|Log in|LOGIN|SUBSCRIBE|Register|Create Account)[\s:,-]*',
        r'(Already a member|Sign up|Unlock this article|Premium|Paywall)[\s:,.-]*',
        # Navigation / site chrome
        r'(View Market|Latest News|Breaking News|Top Stories|Dashboard|Home)[\s:,-]*',
        r'(Menu|Navigation|Search|Toggle|Sidebar)[\s:,-]*',
        # Cookie / privacy
        r'(Cookie|Privacy Policy|Terms of Service|Accept Cookies|Manage Preferences)[\s:,-]*',
        # Ads / sponsored content
        r'(Advertisement|Sponsored|Read More|Share this|Follow us|See Also)[\s:,-]*',
        # Social media
        r'(Facebook|Twitter|LinkedIn|Instagram|Share on|Follow @)[\s:,-]*',
        # Copyright
        r'(©|Copyright|All rights reserved).*?\d{4}',
        # Repeated header-like patterns (e.g., "English SubscribeSign in View Market")
        r'^\s*(?:[A-Z][a-z]{1,10}\s?){5,}(?=\s)',
        # Language selectors
        r'(English|Español|Français|Deutsch)\s*(?=Subscribe|Sign|Log)',
    ]
    clean_text = text
    for pattern in junk_patterns:
        clean_text = re.sub(pattern, ' ', clean_text, flags=re.IGNORECASE)
    
    # Remove forbidden tokens
    forbidden = ['proponent', 'opponent', 'transcript', 'debate']
    for token in forbidden:
        clean_text = re.sub(rf'\b{token}\b', '', clean_text, flags=re.IGNORECASE)
    
    # Clean whitespace (collapse multiple spaces)
    clean_text = ' '.join(clean_text.split())
    
    # Truncate intelligently at sentence boundary if possible
    if len(clean_text) > max_chars:
        truncated = clean_text[:max_chars]
        # Try to break at last complete sentence
        last_period = truncated.rfind('.')
        if last_period > max_chars // 2:
            clean_text = truncated[:last_period + 1]
        else:
            clean_text = truncated.rsplit(' ', 1)[0] + "..."
    
    return clean_text.strip()


def classify_source_type(url: str, domain: str, title: str = "") -> str:
    """Classify source type based on URL/domain patterns."""
    combined = f"{url} {domain} {title}".lower()
    
    if any(p in combined for p in ['factcheck', 'snopes', 'politifact', 'fullfact', 'verify']):
        return "Fact-check"
    if any(p in combined for p in ['.gov', 'government', 'ministry', 'official']):
        return "Government"
    if any(p in combined for p in ['.edu', 'nature.com', 'science.org', 'research', 'journal']):
        return "Research"
    if any(p in combined for p in ['news', 'times', 'post', 'guardian', 'bbc', 'reuters']):
        return "News"
    
    return "Other"


def process_scraper_results(
    scraped_items: List[Dict[str, Any]],
    max_results: int = MAX_EVIDENCE_ITEMS,
    min_authority: float = MIN_AUTHORITY_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Central adapter function: Clean, dedupe, normalize, and format evidence.
    
    Input: Raw scraper output (list of dicts with url, text/content, title, etc.)
    
    Output: Normalized evidence bundle ready for verdict engine:
    [
        {
            "title": str,
            "url": str,
            "domain": str,
            "snippet": str (max 200 chars),
            "authority": float (0.0-1.0),
            "source_type": str,
            "url_hash": str,
            "citation_idx": int (1-based)
        },
        ...
    ]
    """
    if not scraped_items:
        return []
    
    normalized = []
    seen_hashes = set()
    
    for item in scraped_items:
        if not item:
            continue
        
        url = item.get("url", "")
        if not url or not url.startswith("http"):
            continue
        
        # Skip malformed URLs
        if len(url) < 15 or url in ('https://www', 'http://www'):
            continue
        
        # Compute normalized URL hash for deduplication
        url_hash = compute_url_hash(url)
        if url_hash in seen_hashes:
            continue
        seen_hashes.add(url_hash)
        
        # Extract domain
        domain = item.get("domain") or extract_domain(url)
        
        # Calculate authority
        raw_authority = item.get("authority")
        authority = calculate_authority(url, domain, raw_authority)
        
        # Filter by minimum authority
        if authority < min_authority:
            continue
        
        # Get text content (try multiple fields)
        text = (
            item.get("summary") or 
            item.get("snippet") or 
            item.get("text", "")[:500] or 
            item.get("content", "")[:500] or
            item.get("excerpt", "")
        )
        
        # Sanitize snippet
        snippet = sanitize_snippet(text)
        
        # Get and sanitize title (remove LOGIN/SUBSCRIBE junk)
        raw_title = item.get("title", "Unknown Source")
        title = sanitize_title(raw_title)
        
        # Build normalized evidence item
        evidence_item = {
            "title": title,
            "url": url,
            "domain": domain,
            "snippet": snippet,
            "authority": authority,
            "source_type": classify_source_type(url, domain, title),
            "url_hash": url_hash[:16]  # Shortened hash for display
        }
        
        normalized.append(evidence_item)
    
    # Sort by authority (deterministic ordering)
    normalized.sort(key=lambda x: (x["authority"], x["title"]), reverse=True)
    
    # Limit and add citation indices
    result = normalized[:max_results]
    for idx, item in enumerate(result, start=1):
        item["citation_idx"] = idx
    
    logger.info(f"📦 Processed {len(scraped_items)} scraped items → {len(result)} evidence items")
    
    return result


def build_evidence_prompt(evidence_bundle: List[Dict[str, Any]], claim: str) -> str:
    """
    Build the evidence-constrained system prompt for LLM.
    
    This prompt enforces:
    - Only use provided evidence
    - Cite by index [1], [2], etc.
    - Refuse to hallucinate
    """
    if not evidence_bundle:
        return f"""You are analyzing the claim: "{claim}"

No evidence was found. Reply with: "Inconclusive — no reliable sources found for this claim."
Do not invent facts or include external knowledge."""
    
    evidence_text = "\n".join([
        f"{e['citation_idx']}) {e['title']} — {e['domain']} — authority {int(e['authority']*100)}%\n   {e['snippet']}"
        for e in evidence_bundle
    ])
    
    return f"""You must answer ONLY using the evidence items below. Cite evidence by index [1], [2], etc.
If evidence is insufficient, reply "Inconclusive based on available sources."
Do not invent facts or include external knowledge beyond these items.

CLAIM: {claim}

EVIDENCE:
{evidence_text}

TASK: Answer the claim succinctly. Include a 1-2 sentence summary and cite evidence indices inline.
Format your response as: "Based on [1] and [2], ..." or "The evidence shows [1] that..."
"""


def format_assistant_with_citations(
    assistant_text: str,
    evidence_bundle: List[Dict[str, Any]]
) -> str:
    """
    Ensure assistant text has proper citation markers.
    If no citations found, append a sources section.
    """
    if not evidence_bundle:
        return assistant_text
    
    # Check if citations already exist
    if re.search(r'\[\d+\]', assistant_text):
        return assistant_text
    
    # Append sources section if no inline citations
    sources = "\n\n**Sources:**\n" + "\n".join([
        f"[{e['citation_idx']}] {e['title']} ({e['domain']})"
        for e in evidence_bundle[:5]
    ])
    
    return assistant_text + sources


def get_citation_urls(evidence_bundle: List[Dict[str, Any]]) -> Dict[int, str]:
    """Get mapping of citation index to URL for frontend linking."""
    return {e["citation_idx"]: e["url"] for e in evidence_bundle}


# Export main functions
__all__ = [
    'process_scraper_results',
    'build_evidence_prompt', 
    'format_assistant_with_citations',
    'normalize_url',
    'compute_url_hash',
    'sanitize_snippet',
    'sanitize_title',
    'get_citation_urls'
]

"""
Tools Module - External RAG and Utility Functions

Provides web scraping, URL extraction, and other utility tools
for external data retrieval and processing.
"""
from .web_scraper import fetch_url_content, extract_url

__all__ = ['fetch_url_content', 'extract_url']

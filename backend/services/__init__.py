"""
Services - OCR, Scraping, Database
"""
from .ocr_processor import get_ocr_processor, OCRProcessor
from .pro_scraper import get_diversified_evidence
from .db_manager import AsyncDbManager

__all__ = ['get_ocr_processor', 'OCRProcessor', 'get_diversified_evidence', 'AsyncDbManager']

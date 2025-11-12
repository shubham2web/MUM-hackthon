"""
Services - OCR, Scraping, Database
"""
# Lazy imports to avoid slow PyTorch loading at startup
# from .ocr_processor import get_ocr_processor, OCRProcessor
from .pro_scraper import get_diversified_evidence
from .db_manager import AsyncDbManager

def get_ocr_processor():
    """Lazy import OCR processor to avoid slow startup"""
    from .ocr_processor import get_ocr_processor as _get_ocr
    return _get_ocr()

def OCRProcessor(*args, **kwargs):
    """Lazy import OCR processor class"""
    from .ocr_processor import OCRProcessor as _OCRProcessor
    return _OCRProcessor(*args, **kwargs)

__all__ = ['get_ocr_processor', 'OCRProcessor', 'get_diversified_evidence', 'AsyncDbManager']


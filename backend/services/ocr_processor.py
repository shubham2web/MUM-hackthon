"""
OCR Processor Module
Handles Optical Character Recognition for uploaded images.
Extracts text from images and prepares it for AI analysis.
Uses EasyOCR - no Tesseract installation required!
"""
import logging
import os
import tempfile
from typing import Dict, Optional, Tuple
from pathlib import Path
import io

try:
    import easyocr
    from PIL import Image
    import numpy as np
    EASYOCR_AVAILABLE = True
except (ImportError, OSError) as e:
    EASYOCR_AVAILABLE = False
    logging.warning(f"OCR dependencies not available: {e}. Install with: pip install easyocr pillow torch torchvision")


class OCRProcessor:
    """
    Handles OCR processing for images using EasyOCR.
    No Tesseract installation required - works out of the box!
    """
    
    def __init__(self, languages: list = ['en']):
        """
        Initialize OCR processor with EasyOCR.
        
        Args:
            languages: List of language codes (default: ['en'] for English)
                      Supports: 'en', 'hi', 'es', 'fr', 'de', 'ar', 'zh', etc.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if not EASYOCR_AVAILABLE:
            raise ImportError(
                "OCR dependencies not available. "
                "Install with: pip install easyocr pillow"
            )
        
        try:
            self.logger.info(f"Initializing EasyOCR with languages: {languages}")
            # Initialize EasyOCR Reader (downloads models on first run)
            self.reader = easyocr.Reader(languages, gpu=False)  # Set gpu=True if you have CUDA
            self.logger.info("✅ EasyOCR initialized successfully (no Tesseract needed!)")
        except Exception as e:
            self.logger.error(f"EasyOCR initialization failed: {e}")
            raise RuntimeError(f"Failed to initialize EasyOCR: {e}")
    
    def extract_text(
        self, 
        image_path: str, 
        detail: int = 1,
        paragraph: bool = False
    ) -> Dict[str, any]:
        """
        Extract text from an image file.
        
        Args:
            image_path: Path to the image file
            detail: Level of detail (0=fast, 1=balanced, 2=accurate)
            paragraph: If True, combine text into paragraphs
            
        Returns:
            Dictionary containing:
                - text: Extracted text
                - confidence: OCR confidence score (0-100)
                - word_count: Number of words extracted
                - success: Boolean indicating success
                - error: Error message if failed
        """
        result = {
            "text": "",
            "confidence": 0.0,
            "word_count": 0,
            "success": False,
            "error": None
        }
        
        try:
            # Read and process image with EasyOCR
            ocr_results = self.reader.readtext(image_path, detail=detail, paragraph=paragraph)
            
            if not ocr_results:
                result.update({
                    "text": "",
                    "confidence": 0.0,
                    "word_count": 0,
                    "success": True,
                    "error": "No text detected in image"
                })
                return result
            
            # Extract text and confidence scores
            extracted_text = []
            confidences = []
            
            for detection in ocr_results:
                # Each detection: (bbox, text, confidence)
                bbox, text, confidence = detection
                if text.strip():
                    extracted_text.append(text.strip())
                    confidences.append(confidence * 100)  # Convert to percentage
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Join text
            final_text = ' '.join(extracted_text)
            word_count = len(final_text.split())
            
            result.update({
                "text": final_text,
                "confidence": round(avg_confidence, 2),
                "word_count": word_count,
                "success": True
            })
            
            self.logger.info(
                f"✅ OCR extracted {word_count} words "
                f"with {avg_confidence:.2f}% confidence"
            )
            
        except FileNotFoundError:
            error_msg = f"Image file not found: {image_path}"
            self.logger.error(error_msg)
            result["error"] = error_msg
            
        except Exception as e:
            error_msg = f"OCR extraction failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            result["error"] = error_msg
        
        return result
    
    def extract_text_from_bytes(
        self, 
        image_bytes: bytes, 
        detail: int = 1,
        paragraph: bool = False
    ) -> Dict[str, any]:
        """
        Extract text from image bytes (e.g., from upload).
        
        Args:
            image_bytes: Image data as bytes
            detail: Level of detail (0=fast, 1=balanced, 2=accurate)
            paragraph: If True, combine text into paragraphs
            
        Returns:
            Same as extract_text()
        """
        result = {
            "text": "",
            "confidence": 0.0,
            "word_count": 0,
            "success": False,
            "error": None
        }
        
        try:
            # Convert bytes to numpy array for EasyOCR
            image = Image.open(io.BytesIO(image_bytes))
            img_array = np.array(image)
            
            # Read and process image with EasyOCR
            ocr_results = self.reader.readtext(img_array, detail=detail, paragraph=paragraph)
            
            if not ocr_results:
                result.update({
                    "text": "",
                    "confidence": 0.0,
                    "word_count": 0,
                    "success": True,
                    "error": "No text detected in image"
                })
                return result
            
            # Extract text and confidence scores
            extracted_text = []
            confidences = []
            
            for detection in ocr_results:
                bbox, text, confidence = detection
                if text.strip():
                    extracted_text.append(text.strip())
                    confidences.append(confidence * 100)
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Join text
            final_text = ' '.join(extracted_text)
            word_count = len(final_text.split())
            
            result.update({
                "text": final_text,
                "confidence": round(avg_confidence, 2),
                "word_count": word_count,
                "success": True
            })
            
            self.logger.info(
                f"✅ OCR extracted {word_count} words "
                f"with {avg_confidence:.2f}% confidence"
            )
            
        except Exception as e:
            error_msg = f"OCR extraction failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            result["error"] = error_msg
        
        return result
    
    def is_text_rich(self, ocr_result: Dict[str, any], min_words: int = 5) -> bool:
        """
        Check if OCR result contains meaningful text.
        
        Args:
            ocr_result: Result from extract_text()
            min_words: Minimum word count to be considered text-rich
            
        Returns:
            True if image contains meaningful text
        """
        return (
            ocr_result.get("success", False) and 
            ocr_result.get("word_count", 0) >= min_words
        )
    
    @staticmethod
    def get_supported_formats() -> list:
        """Get list of supported image formats for OCR."""
        return ['.png', '.jpg', '.jpeg']
    
    @staticmethod
    def is_supported_format(filename: str) -> bool:
        """Check if file format is supported for OCR."""
        ext = Path(filename).suffix.lower()
        return ext in OCRProcessor.get_supported_formats()


# Singleton instance for easy import
_ocr_processor_instance = None

def get_ocr_processor() -> OCRProcessor:
    """Get singleton OCR processor instance."""
    global _ocr_processor_instance
    if _ocr_processor_instance is None:
        # Initialize EasyOCR with English (add more languages if needed)
        _ocr_processor_instance = OCRProcessor(languages=['en'])
    return _ocr_processor_instance

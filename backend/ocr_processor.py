"""
OCR Processor Module
Handles Optical Character Recognition for uploaded images.
Extracts text from images and prepares it for AI analysis.
"""
import logging
import os
import tempfile
from typing import Dict, Optional, Tuple
from pathlib import Path

try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logging.warning("OCR dependencies not installed. Install with: pip install pytesseract pillow opencv-python")


class OCRProcessor:
    """
    Handles OCR processing for images.
    Extracts text from images and provides preprocessing capabilities.
    """
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize OCR processor.
        
        Args:
            tesseract_cmd: Path to tesseract executable (optional)
                          On Windows: r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
                          On Linux/Mac: Usually auto-detected
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if not PYTESSERACT_AVAILABLE:
            raise ImportError(
                "OCR dependencies not available. "
                "Install with: pip install pytesseract pillow opencv-python"
            )
        
        # Set Tesseract path - try multiple sources
        if tesseract_cmd:
            self.logger.info(f"Using provided Tesseract path: {tesseract_cmd}")
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        elif os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
            self.logger.info("Found Tesseract at default Windows location")
            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        
        # Verify Tesseract is available
        try:
            version = pytesseract.get_tesseract_version()
            self.logger.info(f"Tesseract OCR initialized successfully (version: {version})")
        except Exception as e:
            self.logger.error(f"Tesseract not found: {e}")
            self.logger.error(f"Current tesseract_cmd: {pytesseract.pytesseract.tesseract_cmd}")
            raise RuntimeError(
                f"Tesseract OCR is not installed or not found. "
                f"Tried path: {pytesseract.pytesseract.tesseract_cmd}. "
                f"Download from: https://github.com/UB-Mannheim/tesseract/wiki"
            )
    
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image to improve OCR accuracy.
        
        Args:
            image: PIL Image object
            
        Returns:
            Preprocessed PIL Image
        """
        try:
            # Convert PIL Image to numpy array for OpenCV
            img_array = np.array(image)
            
            # Convert to grayscale if not already
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # Apply denoising
            denoised = cv2.fastNlMeansDenoising(gray)
            
            # Apply adaptive thresholding to handle varying lighting
            binary = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Convert back to PIL Image
            return Image.fromarray(binary)
            
        except Exception as e:
            self.logger.warning(f"Preprocessing failed, using original image: {e}")
            return image
    
    def extract_text(
        self, 
        image_path: str, 
        preprocess: bool = True,
        language: str = 'eng'
    ) -> Dict[str, any]:
        """
        Extract text from an image file.
        
        Args:
            image_path: Path to the image file
            preprocess: Whether to preprocess the image (default: True)
            language: Tesseract language code (default: 'eng')
            
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
            # Load image
            image = Image.open(image_path)
            
            # Preprocess if requested
            if preprocess:
                image = self.preprocess_image(image)
            
            # Extract text with confidence data
            ocr_data = pytesseract.image_to_data(
                image, 
                lang=language, 
                output_type=pytesseract.Output.DICT
            )
            
            # Filter out low-confidence results
            filtered_text = []
            confidences = []
            
            for i, conf in enumerate(ocr_data['conf']):
                if conf > 0:  # -1 means no confidence data
                    text = ocr_data['text'][i].strip()
                    if text:
                        filtered_text.append(text)
                        confidences.append(conf)
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Join text
            extracted_text = ' '.join(filtered_text)
            
            result.update({
                "text": extracted_text,
                "confidence": round(avg_confidence, 2),
                "word_count": len(filtered_text),
                "success": True
            })
            
            self.logger.info(
                f"OCR extracted {len(filtered_text)} words "
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
        preprocess: bool = True,
        language: str = 'eng'
    ) -> Dict[str, any]:
        """
        Extract text from image bytes (e.g., from upload).
        
        Args:
            image_bytes: Image data as bytes
            preprocess: Whether to preprocess the image
            language: Tesseract language code
            
        Returns:
            Same as extract_text()
        """
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            tmp_file.write(image_bytes)
            tmp_path = tmp_file.name
        
        try:
            result = self.extract_text(tmp_path, preprocess, language)
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except Exception as e:
                self.logger.warning(f"Failed to delete temp file {tmp_path}: {e}")
        
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
        """Get list of supported image formats."""
        return ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp']
    
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
        # Try to get Tesseract path from environment
        tesseract_path = os.getenv("TESSERACT_CMD")
        _ocr_processor_instance = OCRProcessor(tesseract_cmd=tesseract_path)
    return _ocr_processor_instance

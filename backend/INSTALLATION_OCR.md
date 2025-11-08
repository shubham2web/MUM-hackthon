# OCR Installation Guide for ATLAS

This guide will help you set up Optical Character Recognition (OCR) functionality in the ATLAS application.

## Prerequisites

### 1. Install Tesseract OCR Engine

Tesseract is the OCR engine that extracts text from images.

#### Windows:
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (recommended: `tesseract-ocr-w64-setup-5.3.3.20231005.exe`)
3. During installation, note the installation path (default: `C:\Program Files\Tesseract-OCR`)
4. Add Tesseract to your system PATH or configure it in `.env` file

#### Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install libtesseract-dev
```

#### macOS:
```bash
brew install tesseract
```

### 2. Install Python Dependencies

Install the required Python packages:

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- `pytesseract` - Python wrapper for Tesseract
- `pillow` - Image processing library
- `opencv-python` - Image preprocessing

### 3. Configure Tesseract Path (Windows only)

If Tesseract is not in your system PATH, add this to your `.env` file:

```env
# OCR Configuration
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Verify Installation

Run this test script to verify OCR is working:

```python
import pytesseract
from PIL import Image

# Test Tesseract installation
try:
    version = pytesseract.get_tesseract_version()
    print(f"✅ Tesseract installed successfully: {version}")
except Exception as e:
    print(f"❌ Tesseract not found: {e}")
```

## Features

The OCR functionality provides:

1. **Text Extraction**: Extract text from uploaded images
2. **Image Preprocessing**: Automatic image enhancement for better OCR accuracy
3. **Confidence Scoring**: Get confidence scores for extracted text
4. **AI Analysis**: Automatically analyze extracted text with AI
5. **Multiple Formats**: Support for PNG, JPG, TIFF, BMP, GIF, WebP

## Usage

### Web Interface

1. Start the server:
```bash
python server.py
```

2. Navigate to: `http://localhost:5000/ocr`

3. Upload an image or drag-and-drop

4. Optionally add a question about the text

5. Click "Process Image with OCR"

### API Endpoint

```javascript
// Upload image for OCR
const formData = new FormData();
formData.append('image', imageFile);
formData.append('analyze', 'true');
formData.append('question', 'What is this document about?');

const response = await fetch('/ocr_upload', {
    method: 'POST',
    body: formData
});

const result = await response.json();
console.log(result.ocr_result.text);
console.log(result.ai_analysis);
```

### Response Format

```json
{
    "success": true,
    "ocr_result": {
        "text": "Extracted text from image...",
        "confidence": 87.5,
        "word_count": 42
    },
    "ai_analysis": "AI-generated analysis of the text...",
    "filename": "document.png"
}
```

## Supported Image Formats

- PNG (.png)
- JPEG (.jpg, .jpeg)
- TIFF (.tiff, .tif)
- BMP (.bmp)
- GIF (.gif)
- WebP (.webp)

## Tips for Better OCR Accuracy

1. **Use high-resolution images** - Better quality = better results
2. **Ensure good lighting** - Avoid shadows and glare
3. **Straight text orientation** - Rotate images to be upright
4. **Clear fonts** - Handwriting may have lower accuracy
5. **High contrast** - Dark text on light background works best

## Troubleshooting

### "Tesseract not found" Error

**Windows:**
- Verify Tesseract is installed: Check `C:\Program Files\Tesseract-OCR`
- Add to PATH or set `TESSERACT_CMD` in `.env`
- Restart your terminal/IDE after installation

**Linux/Mac:**
- Run: `which tesseract` to verify installation
- Reinstall if needed: `sudo apt install tesseract-ocr`

### "OCR dependencies not available" Error

Install missing packages:
```bash
pip install pytesseract pillow opencv-python
```

### Low Confidence Scores

- Check image quality and resolution
- Ensure text is clearly visible
- Try preprocessing the image manually
- Use better lighting when capturing images

### Empty Text Results

- Verify the image contains readable text
- Check if text orientation is correct
- Try a different image format
- Increase image resolution

## Advanced Configuration

### Custom Language Support

Install additional language packs:

```bash
# Windows: Download from Tesseract GitHub releases
# Linux:
sudo apt install tesseract-ocr-<lang>

# Example: Spanish
sudo apt install tesseract-ocr-spa
```

Use in code:
```python
ocr_result = ocr_processor.extract_text(
    image_path, 
    language='spa'  # Spanish
)
```

### Performance Tuning

For large images, consider:
- Resizing images before processing
- Cropping to text regions only
- Batch processing multiple images
- Caching results for repeated queries

## Security Considerations

1. **File Size Limits**: Configure max upload size in server settings
2. **File Type Validation**: Only accept image formats
3. **Sanitize Filenames**: Prevent path traversal attacks
4. **Rate Limiting**: Prevent abuse of OCR endpoint
5. **Temporary File Cleanup**: Ensure temp files are deleted

## Support

For issues or questions:
- Check the main README.md
- Review error logs in the console
- Verify all dependencies are installed
- Test with sample images first

---

**Note**: OCR accuracy varies based on image quality, font types, and text clarity. For best results, use clear, high-contrast images with standard fonts.

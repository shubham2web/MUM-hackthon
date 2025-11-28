# 📷 OCR Feature - Quick Start Guide

## What is OCR?

**OCR (Optical Character Recognition)** is a technology that converts images containing text into editable, searchable, and machine-readable text. ATLAS uses OCR to:

- Extract text from uploaded images
- Analyze documents, receipts, screenshots, and more
- Answer questions about text in images
- Verify information with AI-powered fact-checking

## Quick Setup (3 Steps)

### Step 1: Install Tesseract OCR

**Windows:**
1. Download: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer
3. Note the installation path (usually `C:\Program Files\Tesseract-OCR`)

**Linux:**
```bash
sudo apt update
sudo apt install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### Step 2: Install Python Packages

```bash
cd backend
pip install pytesseract pillow opencv-python
```

### Step 3: Configure (Windows Only)

If Tesseract is not in your PATH, edit `.env`:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Verify Installation

Run the test script:

```bash
cd backend
python test_ocr.py
```

You should see:
```
🎉 All tests PASSED! OCR is ready to use!
```

## How to Use

### Web Interface

1. **Start the server:**
   ```bash
   python server.py
   ```

2. **Open your browser:**
   ```
   http://localhost:5000/ocr
   ```

3. **Upload an image:**
   - Click the upload area or drag-and-drop
   - Supports: PNG, JPG, JPEG, TIFF, BMP, GIF, WebP

4. **Ask a question (optional):**
   - Example: "What is this document about?"
   - Example: "Summarize the key points"
   - Example: "Is this information accurate?"

5. **Click "Process Image with OCR"**

6. **View results:**
   - Extracted text with confidence score
   - AI-powered analysis and insights

### API Usage

```javascript
const formData = new FormData();
formData.append('image', imageFile);
formData.append('analyze', 'true');
formData.append('question', 'What does this say?');

const response = await fetch('http://localhost:5000/ocr_upload', {
    method: 'POST',
    body: formData
});

const result = await response.json();
console.log('Text:', result.ocr_result.text);
console.log('AI Analysis:', result.ai_analysis);
```

### Python API

```python
from ocr_processor import get_ocr_processor

# Initialize processor
ocr = get_ocr_processor()

# Extract text from image
result = ocr.extract_text('path/to/image.png')

print(f"Text: {result['text']}")
print(f"Confidence: {result['confidence']}%")
print(f"Words: {result['word_count']}")
```

## Example Use Cases

### 1. Document Analysis
Upload a scanned document to extract and analyze its content.

### 2. Receipt Processing
Extract purchase details from receipt photos.

### 3. Screenshot Text Extraction
Convert text from screenshots into editable format.

### 4. Social Media Verification
Check text claims in social media images.

### 5. Historical Document Digitization
Convert old documents into searchable text.

### 6. Multilingual Support
Extract text in different languages (requires language packs).

## Tips for Best Results

✅ **DO:**
- Use high-resolution images (300+ DPI)
- Ensure good lighting and contrast
- Keep text orientation upright
- Use clear, standard fonts
- Capture images straight-on

❌ **AVOID:**
- Blurry or low-quality images
- Shadows or glare on text
- Tilted or rotated text
- Handwritten text (lower accuracy)
- Complex backgrounds

## Response Format

```json
{
  "success": true,
  "ocr_result": {
    "text": "Extracted text from the image...",
    "confidence": 87.5,
    "word_count": 42
  },
  "ai_analysis": "This document appears to be a receipt...",
  "filename": "receipt.jpg"
}
```

### Confidence Scores

- **80-100%** 🟢 High confidence (excellent quality)
- **60-79%** 🟡 Medium confidence (good quality)
- **0-59%** 🔴 Low confidence (may need verification)

## Troubleshooting

### "Tesseract not found"

**Fix:** Install Tesseract or set `TESSERACT_CMD` in `.env`

### "OCR dependencies not available"

**Fix:** 
```bash
pip install pytesseract pillow opencv-python
```

### Low Confidence Scores

**Fix:**
- Use higher resolution images
- Improve lighting
- Increase contrast
- Ensure text is straight

### No Text Detected

**Fix:**
- Verify image contains readable text
- Check image orientation
- Try different image format
- Zoom in on text area

## Advanced Features

### Image Preprocessing

Images are automatically enhanced before OCR:
- Noise reduction
- Contrast adjustment
- Adaptive thresholding
- Grayscale conversion

### Supported Languages

Install additional language packs:

```bash
# Spanish
sudo apt install tesseract-ocr-spa

# French
sudo apt install tesseract-ocr-fra

# German
sudo apt install tesseract-ocr-deu
```

Use in code:
```python
result = ocr.extract_text('image.png', language='spa')
```

### Batch Processing

Process multiple images:

```python
from ocr_processor import get_ocr_processor
import os

ocr = get_ocr_processor()
results = []

for filename in os.listdir('images/'):
    if filename.endswith(('.png', '.jpg')):
        result = ocr.extract_text(f'images/{filename}')
        results.append({
            'file': filename,
            'text': result['text'],
            'confidence': result['confidence']
        })

# Export results
import json
with open('ocr_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

## Security & Performance

### File Size Limits
- Default: 10MB per image
- Configure in server settings

### Rate Limiting
- Prevent abuse with rate limiting
- Default: 10 requests/minute per IP

### Temporary Files
- Auto-cleanup after processing
- No permanent storage of uploads

### Performance
- Average processing: 1-3 seconds
- Depends on image size and complexity
- Uses async processing for scalability

## Integration with ATLAS

OCR integrates seamlessly with ATLAS features:

1. **Fact-Checking**: Verify claims in images
2. **Evidence Gathering**: Extract quotes from screenshots
3. **Document Analysis**: Analyze policy documents
4. **Social Media**: Check viral image text
5. **Research**: Digitize historical documents

## Support & Resources

- **Installation Guide**: `INSTALLATION_OCR.md`
- **Test Script**: `python test_ocr.py`
- **API Documentation**: See server.py `/ocr_upload` endpoint
- **Tesseract Docs**: https://tesseract-ocr.github.io/

## Next Steps

1. ✅ Complete installation
2. ✅ Run test script
3. ✅ Try sample images
4. ✅ Integrate with your workflow
5. ✅ Explore advanced features

---

**Ready to extract text from images with AI-powered analysis!** 🚀

For questions or issues, check the main README.md or run `python test_ocr.py` to diagnose problems.

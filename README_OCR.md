# 📷 ATLAS OCR Feature - README

## Welcome to OCR Text Recognition!

ATLAS now includes powerful **Optical Character Recognition (OCR)** capabilities, allowing you to extract and analyze text from images using AI.

---

## 🚀 Quick Start (3 Minutes)

### 1️⃣ Install Tesseract OCR

Choose your platform:

<details>
<summary><b>Windows</b></summary>

1. Download installer: [Tesseract for Windows](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer (default location is fine)
3. Complete installation

</details>

<details>
<summary><b>Linux (Ubuntu/Debian)</b></summary>

```bash
sudo apt update
sudo apt install tesseract-ocr libtesseract-dev
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
brew install tesseract
```

</details>

### 2️⃣ Install Python Dependencies

```bash
cd backend
pip install pytesseract pillow opencv-python
```

### 3️⃣ Verify Installation

```bash
cd backend
python test_ocr.py
```

✅ You should see: **"All tests PASSED! OCR is ready to use!"**

---

## 💡 How to Use

### Via Web Interface

1. **Start the server:**
   ```bash
   cd backend
   python server.py
   ```

2. **Open your browser:**
   ```
   http://localhost:5000/ocr
   ```

3. **Upload an image:**
   - Click the upload area or drag-and-drop
   - Supported formats: PNG, JPG, JPEG, TIFF, BMP, GIF, WebP

4. **Ask a question (optional):**
   - Example: "What is this document about?"
   - Example: "Is this information accurate?"

5. **Click "Process Image with OCR"**

6. **View results:**
   - Extracted text with confidence score
   - AI-powered analysis

### From Homepage

1. Go to `http://localhost:5000`
2. Click the **📷 OCR** button
3. Upload and process your image

---

## 📊 What You Get

### 1. Text Extraction
- Automatically extract all text from images
- Get confidence scores (0-100%)
- See word counts

### 2. AI Analysis
- Analyze extracted text for accuracy
- Ask specific questions about the content
- Verify claims with ATLAS's fact-checking

### 3. Multiple Formats
Support for all major image formats:
- PNG, JPG, JPEG
- TIFF, BMP
- GIF, WebP

---

## 🎯 Example Use Cases

1. **📄 Document Scanning**
   - Convert paper documents to digital text
   - Digitize receipts, invoices, contracts

2. **📱 Screenshot Analysis**
   - Extract text from screenshots
   - Verify social media claims

3. **🔍 Fact-Checking**
   - Check information in shared images
   - Verify memes and viral content

4. **📚 Research**
   - Digitize historical documents
   - Extract quotes from book pages

5. **♿ Accessibility**
   - Read text from images aloud
   - Make visual content accessible

---

## 📖 Documentation

- **[Quick Start Guide](OCR_GUIDE.md)** - Get started in 5 minutes
- **[Installation Guide](backend/INSTALLATION_OCR.md)** - Detailed setup instructions
- **[Implementation Summary](OCR_IMPLEMENTATION_SUMMARY.md)** - Technical details

---

## 🔧 Automated Setup

### Windows:
```bash
setup_ocr.bat
```

### Linux/macOS:
```bash
chmod +x setup_ocr.sh
./setup_ocr.sh
```

These scripts will:
- ✅ Check Python installation
- ✅ Install required packages
- ✅ Verify Tesseract
- ✅ Run tests
- ✅ Confirm everything works

---

## 🧪 Testing

Verify your OCR installation:

```bash
cd backend
python test_ocr.py
```

This will test:
- Package imports
- Tesseract availability
- OCR processor functionality
- Text extraction accuracy

---

## ⚙️ Configuration

### Windows Users Only

If Tesseract is not in your PATH, add this to `backend/.env`:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Linux/macOS Users

No configuration needed! Tesseract is auto-detected.

---

## 🎨 Features

### Image Preprocessing
- ✅ Automatic noise reduction
- ✅ Contrast enhancement
- ✅ Adaptive thresholding
- ✅ Grayscale conversion

### Accuracy Optimization
- ✅ High-quality text extraction
- ✅ Confidence scoring
- ✅ Multiple language support
- ✅ Format detection

### AI Integration
- ✅ Automatic text analysis
- ✅ Question answering
- ✅ Fact-checking
- ✅ Misinformation detection

---

## 💻 API Usage

### JavaScript Example:

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
console.log('Confidence:', result.ocr_result.confidence);
console.log('AI Analysis:', result.ai_analysis);
```

### Python Example:

```python
from ocr_processor import get_ocr_processor

ocr = get_ocr_processor()
result = ocr.extract_text('path/to/image.png')

print(f"Text: {result['text']}")
print(f"Confidence: {result['confidence']}%")
print(f"Words: {result['word_count']}")
```

---

## 🏆 Best Practices

### For Best Results:

✅ **Use high-resolution images** (300+ DPI)  
✅ **Ensure good lighting** (avoid shadows)  
✅ **Keep text upright** (not tilted)  
✅ **Use clear fonts** (standard typefaces)  
✅ **High contrast** (dark text on light background)

### Avoid:

❌ Blurry or low-quality images  
❌ Complex backgrounds  
❌ Tilted or rotated text  
❌ Handwritten text (lower accuracy)  
❌ Poor lighting conditions

---

## 🐛 Troubleshooting

<details>
<summary><b>"Tesseract not found" error</b></summary>

**Solution:**
1. Verify Tesseract is installed
2. Windows: Add path to `.env` file
3. Linux/Mac: Run `which tesseract`
4. Reinstall if necessary

</details>

<details>
<summary><b>"OCR dependencies not available"</b></summary>

**Solution:**
```bash
pip install pytesseract pillow opencv-python
```

</details>

<details>
<summary><b>Low confidence scores</b></summary>

**Solution:**
- Use higher resolution images
- Improve lighting
- Increase contrast
- Ensure text is straight

</details>

<details>
<summary><b>No text detected</b></summary>

**Solution:**
- Verify image contains readable text
- Check image orientation
- Try different image format
- Increase image quality

</details>

---

## 📦 Dependencies

### Required:
- **Tesseract OCR** - Text extraction engine
- **pytesseract** - Python wrapper (v0.3.13)
- **Pillow** - Image processing (v12.0.0)
- **opencv-python** - Computer vision (v4.11.0.86)

### Optional:
- Additional language packs for multilingual OCR

---

## 🌍 Language Support

### Default:
- English (eng)

### Install Additional Languages:

**Linux:**
```bash
sudo apt install tesseract-ocr-spa  # Spanish
sudo apt install tesseract-ocr-fra  # French
sudo apt install tesseract-ocr-deu  # German
```

**Usage:**
```python
result = ocr.extract_text('image.png', language='spa')
```

---

## 🔒 Security

- ✅ File type validation
- ✅ Size limits (10MB default)
- ✅ Temporary file cleanup
- ✅ Rate limiting
- ✅ Path sanitization

---

## 📈 Performance

- **Processing Time:** 1-3 seconds per image
- **Accuracy:** 80-95% on quality images
- **Concurrent Requests:** Supported via async processing
- **File Size Limit:** 10MB (configurable)

---

## 🛠️ Tech Stack

- **Backend:** Python, Quart (async)
- **OCR Engine:** Tesseract
- **Image Processing:** Pillow, OpenCV
- **AI Integration:** Groq/HuggingFace LLMs
- **Frontend:** HTML5, CSS3, JavaScript

---

## 📝 Response Format

```json
{
  "success": true,
  "ocr_result": {
    "text": "Extracted text from image...",
    "confidence": 87.5,
    "word_count": 42
  },
  "ai_analysis": "AI-generated insights...",
  "filename": "image.png"
}
```

---

## 🎯 Next Steps

1. ✅ Complete installation
2. ✅ Run test script
3. ✅ Upload a test image
4. ✅ Try asking questions
5. ✅ Explore advanced features

---

## 🤝 Integration with ATLAS

OCR works seamlessly with:
- **Analytical Mode** - Analyze extracted text
- **Debate Mode** - Debate claims in images
- **Evidence Gathering** - Extract supporting quotes
- **Fact-Checking** - Verify image content

---

## 📞 Support

Need help?
1. Run `python test_ocr.py` to diagnose
2. Check [Installation Guide](backend/INSTALLATION_OCR.md)
3. Review [Quick Start Guide](OCR_GUIDE.md)
4. Check console error logs

---

## ✨ Features at a Glance

| Feature | Status |
|---------|--------|
| Text Extraction | ✅ |
| Image Preprocessing | ✅ |
| Confidence Scoring | ✅ |
| AI Analysis | ✅ |
| Multiple Formats | ✅ |
| Drag-and-Drop | ✅ |
| Question Answering | ✅ |
| Fact-Checking | ✅ |
| API Access | ✅ |
| Web Interface | ✅ |

---

## 🎉 Ready to Use!

Your OCR system is ready! Start extracting text from images with AI-powered analysis.

**Get Started:** `http://localhost:5000/ocr`

---

*Built with ❤️ for the ATLAS Misinformation Fighter*

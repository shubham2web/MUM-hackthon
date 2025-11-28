# OCR Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        ATLAS OCR SYSTEM                         │
└─────────────────────────────────────────────────────────────────┘

                              USER
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Upload Image        │
                    │   (PNG/JPG/TIFF/etc)  │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Web Interface       │
                    │   /ocr endpoint       │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Server Receives     │
                    │   /ocr_upload POST    │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Validate File       │
                    │   - Type check        │
                    │   - Size limit        │
                    └───────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────────┐
        │              OCR PROCESSOR                    │
        ├───────────────────────────────────────────────┤
        │                                               │
        │   1. IMAGE PREPROCESSING                      │
        │      ├─ Convert to grayscale                  │
        │      ├─ Noise reduction (fastNlMeans)         │
        │      ├─ Contrast enhancement                  │
        │      └─ Adaptive thresholding                 │
        │                                               │
        │   2. TEXT EXTRACTION (Tesseract)              │
        │      ├─ OCR processing                        │
        │      ├─ Word detection                        │
        │      ├─ Confidence scoring                    │
        │      └─ Text assembly                         │
        │                                               │
        │   3. RESULT COMPILATION                       │
        │      ├─ Extracted text                        │
        │      ├─ Confidence score (0-100%)             │
        │      ├─ Word count                            │
        │      └─ Success status                        │
        │                                               │
        └───────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   AI Analysis         │
                    │   (Optional)          │
                    └───────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
    ┌───────────────────────┐       ┌───────────────────────┐
    │   Create AI Prompt    │       │   No Analysis         │
    │   - Extracted text    │       │   Return OCR only     │
    │   - User question     │       └───────────────────────┘
    │   - System context    │
    └───────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │   AI Agent            │
    │   (Groq/HuggingFace)  │
    └───────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │   Stream Response     │
    │   - Analyze text      │
    │   - Answer question   │
    │   - Fact check        │
    └───────────────────────┘
                │
                └───────────────┬───────────────┘
                                ▼
                    ┌───────────────────────┐
                    │   Compile Results     │
                    │   - OCR data          │
                    │   - AI analysis       │
                    │   - Metadata          │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   JSON Response       │
                    │   {                   │
                    │     success: true,    │
                    │     ocr_result: {...},│
                    │     ai_analysis: "..." │
                    │   }                   │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Display Results     │
                    │   - Extracted text    │
                    │   - Confidence badge  │
                    │   - Word count        │
                    │   - AI insights       │
                    └───────────────────────┘
                                │
                                ▼
                              USER
                        (Views Results)


═══════════════════════════════════════════════════════════════════

                    TECHNOLOGY STACK

┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Frontend                                                      │
│   ├─ HTML5 (ocr.html)                                           │
│   ├─ CSS3 (Responsive design)                                   │
│   └─ JavaScript (Fetch API, FormData)                           │
│                                                                 │
│   Backend                                                       │
│   ├─ Python 3.x                                                 │
│   ├─ Quart (Async web framework)                                │
│   ├─ ocr_processor.py (OCR logic)                               │
│   └─ ai_agent.py (AI integration)                               │
│                                                                 │
│   OCR Engine                                                    │
│   ├─ Tesseract OCR (v5.x)                                       │
│   ├─ pytesseract (Python wrapper)                               │
│   ├─ Pillow (Image I/O)                                         │
│   └─ OpenCV (Preprocessing)                                     │
│                                                                 │
│   AI Layer                                                      │
│   ├─ Groq API (Primary)                                         │
│   ├─ HuggingFace (Fallback)                                     │
│   └─ LLaMA 3 models                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════

                    DATA FLOW

    Image Upload → Validation → Preprocessing → OCR → AI → Results


═══════════════════════════════════════════════════════════════════

                    SECURITY LAYERS

┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   1. Input Validation                                           │
│      ✓ File type checking (.png, .jpg, etc)                    │
│      ✓ File size limits (10MB default)                         │
│      ✓ Content type verification                               │
│                                                                 │
│   2. Processing                                                 │
│      ✓ Temporary file storage                                  │
│      ✓ Auto-cleanup after processing                           │
│      ✓ No permanent storage                                    │
│                                                                 │
│   3. API Security                                               │
│      ✓ Rate limiting                                           │
│      ✓ CORS configuration                                      │
│      ✓ Error handling                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════

                    PERFORMANCE METRICS

    Average Processing Time: 1-3 seconds
    Supported Concurrent Users: 10+ (async)
    OCR Accuracy: 80-95% (quality dependent)
    Max File Size: 10MB
    Supported Formats: 7 (PNG, JPG, JPEG, TIFF, BMP, GIF, WebP)


═══════════════════════════════════════════════════════════════════
```

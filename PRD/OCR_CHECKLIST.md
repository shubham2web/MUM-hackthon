# ✅ OCR Installation Checklist

Use this checklist to ensure your OCR setup is complete and working.

---

## Pre-Installation

- [ ] Python 3.7+ is installed
- [ ] pip is available and updated
- [ ] Git repository is cloned
- [ ] Backend folder exists

---

## Step 1: Install Tesseract OCR

### Windows
- [ ] Downloaded Tesseract installer from https://github.com/UB-Mannheim/tesseract/wiki
- [ ] Ran the installer
- [ ] Noted installation path (e.g., `C:\Program Files\Tesseract-OCR`)
- [ ] Added to PATH OR configured in `.env`

### Linux (Ubuntu/Debian)
- [ ] Ran: `sudo apt update`
- [ ] Ran: `sudo apt install tesseract-ocr libtesseract-dev`
- [ ] Verified: `tesseract --version`

### macOS
- [ ] Ran: `brew install tesseract`
- [ ] Verified: `tesseract --version`

---

## Step 2: Install Python Dependencies

- [ ] Navigated to backend folder: `cd backend`
- [ ] Installed packages: `pip install pytesseract pillow opencv-python`
- [ ] No installation errors occurred
- [ ] All packages installed successfully

---

## Step 3: Configuration

### Windows Only
- [ ] Opened `backend/.env` file
- [ ] Added line: `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
- [ ] Saved the file

### Linux/macOS
- [ ] No configuration needed ✓

---

## Step 4: Verification

- [ ] Navigated to backend: `cd backend`
- [ ] Ran test script: `python test_ocr.py`
- [ ] Saw message: "All tests PASSED!"
- [ ] All dependency checks passed
- [ ] Tesseract version displayed
- [ ] Test image created successfully
- [ ] OCR extraction worked

---

## Step 5: Start Server

- [ ] In backend folder, ran: `python server.py`
- [ ] Server started without errors
- [ ] Saw message about server running on port 5000

---

## Step 6: Test Web Interface

- [ ] Opened browser
- [ ] Navigated to: `http://localhost:5000`
- [ ] Saw ATLAS homepage
- [ ] Clicked "📷 OCR" button
- [ ] OCR page loaded successfully

---

## Step 7: Upload Test Image

- [ ] Clicked upload area or dragged image
- [ ] Image preview appeared
- [ ] "Process Image with OCR" button enabled
- [ ] Clicked process button
- [ ] Loading indicator appeared
- [ ] Results displayed successfully
- [ ] Extracted text shown
- [ ] Confidence score displayed
- [ ] Word count shown

---

## Step 8: Test AI Analysis

- [ ] Uploaded another image
- [ ] Entered a question in the question field
- [ ] Clicked "Process Image with OCR"
- [ ] Extracted text displayed
- [ ] AI analysis section appeared
- [ ] AI response was relevant to the question

---

## Step 9: Test API (Optional)

- [ ] Created test script or used curl/Postman
- [ ] Sent POST request to `/ocr_upload`
- [ ] Included image file in form data
- [ ] Received JSON response
- [ ] Response contained `ocr_result` object
- [ ] Response contained extracted text

---

## Step 10: Error Handling Test

- [ ] Tried uploading non-image file
- [ ] Error message displayed
- [ ] Tried uploading very large file
- [ ] Appropriate error handling occurred

---

## Troubleshooting Checks

If something didn't work, verify:

### Tesseract Issues
- [ ] Tesseract is installed: Run `tesseract --version`
- [ ] Path is correct in `.env` (Windows)
- [ ] Tesseract is in system PATH

### Python Package Issues
- [ ] All packages installed: `pip list | grep -E "(pytesseract|Pillow|opencv)"`
- [ ] Correct Python version: `python --version`
- [ ] Virtual environment activated (if using one)

### Server Issues
- [ ] Port 5000 is not in use
- [ ] No firewall blocking
- [ ] All dependencies imported without errors

### OCR Processing Issues
- [ ] Image file is valid
- [ ] Image contains readable text
- [ ] Image format is supported
- [ ] File size is under limit

---

## Final Verification

Run through this complete test:

1. **Start Server**
   ```bash
   cd backend
   python server.py
   ```

2. **Open Browser**
   ```
   http://localhost:5000/ocr
   ```

3. **Upload Sample Image**
   - Find an image with clear text
   - Upload via drag-and-drop or click

4. **Process Image**
   - Click "Process Image with OCR"
   - Wait for results

5. **Verify Results**
   - [ ] Text extracted correctly
   - [ ] Confidence score reasonable (60%+)
   - [ ] Word count accurate

6. **Test AI Analysis**
   - Ask: "What is this document about?"
   - [ ] AI response is relevant
   - [ ] Analysis makes sense

---

## Success Criteria

✅ All items checked above
✅ Test script passes all tests
✅ Server starts without errors
✅ Web interface loads properly
✅ Images upload successfully
✅ Text extraction works
✅ AI analysis functions
✅ No console errors

---

## If All Checks Pass

🎉 **Congratulations!** Your OCR system is fully operational!

You can now:
- Extract text from images
- Analyze documents with AI
- Verify information in images
- Integrate OCR into your workflow

---

## If Some Checks Fail

📋 **Next Steps:**

1. Note which checks failed
2. Review error messages in console
3. Check relevant documentation:
   - `INSTALLATION_OCR.md` for detailed setup
   - `OCR_GUIDE.md` for usage help
   - `README_OCR.md` for overview

4. Common fixes:
   - **Tesseract not found**: Reinstall or fix PATH
   - **Import errors**: Reinstall Python packages
   - **Server won't start**: Check port availability
   - **No text extracted**: Verify image quality

5. Re-run test script: `python test_ocr.py`

---

## Support Resources

- **Test Script**: `python test_ocr.py`
- **Installation Guide**: `backend/INSTALLATION_OCR.md`
- **Quick Start**: `OCR_GUIDE.md`
- **Technical Details**: `OCR_IMPLEMENTATION_SUMMARY.md`
- **Workflow Diagram**: `OCR_WORKFLOW.md`

---

## Automated Setup

Instead of manual steps, you can run:

**Windows:**
```bash
setup_ocr.bat
```

**Linux/macOS:**
```bash
chmod +x setup_ocr.sh
./setup_ocr.sh
```

These scripts automate many of the above steps.

---

## Notes

- Some checks may vary based on your OS
- Installation paths may differ
- Performance depends on hardware
- Accuracy varies with image quality

---

**Date Completed**: _____________

**Tested By**: _____________

**Status**: ⬜ Not Started | ⬜ In Progress | ⬜ Complete | ⬜ Issues

---

*Save this checklist for future reference or troubleshooting*

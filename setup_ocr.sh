#!/bin/bash

# ========================================
# ATLAS OCR Setup Script for Linux/macOS
# ========================================

echo ""
echo "========================================"
echo "  ATLAS OCR Installation Script"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3 first"
    exit 1
fi

echo "[OK] Python is installed"
echo ""

# Navigate to backend directory
cd "$(dirname "$0")/backend"

# Install Python dependencies
echo "Installing Python dependencies..."
echo ""
pip3 install pytesseract pillow opencv-python

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to install Python packages"
    exit 1
fi

echo ""
echo "[OK] Python packages installed"
echo ""

# Check if Tesseract is installed
if ! command -v tesseract &> /dev/null; then
    echo "========================================"
    echo "  Tesseract OCR Not Found"
    echo "========================================"
    echo ""
    echo "Tesseract OCR is required but not installed."
    echo ""
    
    # Detect OS and provide installation instructions
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Install on Ubuntu/Debian:"
        echo "  sudo apt update"
        echo "  sudo apt install tesseract-ocr libtesseract-dev"
        echo ""
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Install on macOS:"
        echo "  brew install tesseract"
        echo ""
    fi
    
    echo "After installation, run this script again."
    echo ""
    exit 1
else
    echo "[OK] Tesseract OCR is installed"
    TESSERACT_VERSION=$(tesseract --version | head -n 1)
    echo "    Version: $TESSERACT_VERSION"
    echo ""
fi

# Run test script
echo "Running OCR verification test..."
echo ""
python3 test_ocr.py

if [ $? -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "  Setup Incomplete"
    echo "========================================"
    echo ""
    echo "Some tests failed. Please review the errors above."
    echo "Check INSTALLATION_OCR.md for detailed instructions."
    echo ""
    exit 1
else
    echo ""
    echo "========================================"
    echo "  Setup Complete!"
    echo "========================================"
    echo ""
    echo "OCR is ready to use!"
    echo ""
    echo "To start using OCR:"
    echo "  1. Run: python3 server.py"
    echo "  2. Open: http://localhost:5000/ocr"
    echo ""
fi

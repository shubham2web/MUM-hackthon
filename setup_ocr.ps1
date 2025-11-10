# ========================================
# Quick Install Script for EasyOCR Setup
# ========================================
# Run this in PowerShell from project root

Write-Host "🚀 Installing OCR dependencies (no Tesseract needed!)..." -ForegroundColor Cyan
Write-Host ""

# Navigate to backend
Set-Location backend

# Install core OCR dependencies
Write-Host "📦 Installing EasyOCR and dependencies..." -ForegroundColor Yellow
pip install easyocr pillow torch torchvision

Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Note: On first run, EasyOCR will download language models (~100MB)" -ForegroundColor Yellow
Write-Host "         This happens automatically and only once!" -ForegroundColor Yellow
Write-Host ""
Write-Host "🎯 Starting server..." -ForegroundColor Cyan
Write-Host ""

# Start the server
python server.py

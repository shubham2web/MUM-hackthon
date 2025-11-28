@echo off
REM ========================================
REM ATLAS OCR Setup Script for Windows
REM ========================================

echo.
echo ========================================
echo   ATLAS OCR Installation Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python is installed
echo.

REM Navigate to backend directory
cd /d "%~dp0backend"

echo Installing Python dependencies...
echo.
pip install pytesseract pillow opencv-python

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install Python packages
    pause
    exit /b 1
)

echo.
echo [OK] Python packages installed
echo.

REM Check if Tesseract is installed
where tesseract >nul 2>&1
if errorlevel 1 (
    echo ========================================
    echo   Tesseract OCR Not Found
    echo ========================================
    echo.
    echo Tesseract OCR is required but not installed.
    echo.
    echo Please follow these steps:
    echo.
    echo 1. Download Tesseract installer from:
    echo    https://github.com/UB-Mannheim/tesseract/wiki
    echo.
    echo 2. Run the installer
    echo.
    echo 3. Note the installation path
    echo    (usually C:\Program Files\Tesseract-OCR)
    echo.
    echo 4. Add the path to your .env file:
    echo    TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
    echo.
    echo 5. Run this script again
    echo.
    pause
    exit /b 1
) else (
    echo [OK] Tesseract OCR is installed
    echo.
)

REM Run test script
echo Running OCR verification test...
echo.
python test_ocr.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo   Setup Incomplete
    echo ========================================
    echo.
    echo Some tests failed. Please review the errors above.
    echo Check INSTALLATION_OCR.md for detailed instructions.
    echo.
) else (
    echo.
    echo ========================================
    echo   Setup Complete!
    echo ========================================
    echo.
    echo OCR is ready to use!
    echo.
    echo To start using OCR:
    echo   1. Run: python server.py
    echo   2. Open: http://localhost:5000/ocr
    echo.
)

pause

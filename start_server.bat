@echo off
echo ========================================
echo    ATLAS - AI Misinformation Fighter
echo    Starting Server...
echo ========================================
echo.

cd /d "%~dp0backend"

REM Activate virtual environment and start server
call .venv\Scripts\activate.bat
python server.py

pause

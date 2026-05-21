@echo off
echo ============================================================
echo   RAG Financial Analysis Bot — Windows Launcher
echo ============================================================
echo.

echo [1/2] Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/2] Starting Telegram bot...
echo.
python rag_demo.py
pause

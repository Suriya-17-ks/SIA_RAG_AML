@echo off
echo Stopping SIA-RAG Backend...
:: Kill any uvicorn / python process holding port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo ✅ All servers stopped.
pause

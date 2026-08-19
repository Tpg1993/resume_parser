@echo off
echo ========================================================
echo 🔄 Restarting Chrome with Remote Debugging (Port 9222)
echo ========================================================
echo.
echo Forcing Chrome to close completely to enable debugging...
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 /nobreak >nul
echo.
echo Starting your regular Chrome browser with debugging enabled...
start chrome.exe --remote-debugging-port=9222
echo.
echo Done! Chrome has restarted.
echo 1. Click 'Restore' in Chrome if prompted to restore your tabs.
echo 2. Make sure you have FlowCV open at the resume editor in one of the tabs.
echo 3. Return to your terminal and run:
echo    .\.venv\Scripts\python.exe run_flowcv_sync.py
echo ========================================================
pause

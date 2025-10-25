@echo off
title File Categorizer Web Interface
echo Starting File Categorizer Web Interface...
echo.
echo The web interface will open at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

REM Start the File Categorizer web interface in background
start /B file-categorizer web --debug

REM Wait a moment for server to start
timeout /t 3 /nobreak >nul

REM Open browser
start http://localhost:5000

REM Keep window open for server control
echo.
echo ✓ File Categorizer is running at http://localhost:5000
echo ✓ Browser should open automatically
echo.
echo Press any key to stop the server...
pause >nul

REM Stop the server (this will close the background process)
taskkill /f /im python.exe /fi "WINDOWTITLE eq File Categorizer*" 2>nul

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Error starting File Categorizer. Press any key to close.
    pause >nul
)
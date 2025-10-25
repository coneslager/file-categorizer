# File Categorizer Web Interface Launcher
# This script starts the File Categorizer web interface and opens it in your browser

Write-Host "🗂️  File Categorizer Web Interface" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Check if file-categorizer is available
try {
    $version = & file-categorizer --version 2>$null
    Write-Host "✓ File Categorizer found: $version" -ForegroundColor Green
} catch {
    Write-Host "❌ File Categorizer not found. Please install it first:" -ForegroundColor Red
    Write-Host "   pip install -e ." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host ""
Write-Host "🚀 Starting web interface..." -ForegroundColor Yellow
Write-Host "   URL: http://localhost:5000" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Start the web interface in background and open browser
Start-Job -ScriptBlock { file-categorizer web --debug } -Name "FileCategorizer"

# Wait a moment for server to start
Start-Sleep -Seconds 3

# Open browser
try {
    Start-Process "http://localhost:5000"
    Write-Host "✓ Browser opened" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not open browser automatically" -ForegroundColor Yellow
    Write-Host "   Please open: http://localhost:5000" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Press any key to stop the server and exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Stop the background job
Stop-Job -Name "FileCategorizer" -ErrorAction SilentlyContinue
Remove-Job -Name "FileCategorizer" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "✓ File Categorizer stopped" -ForegroundColor Green
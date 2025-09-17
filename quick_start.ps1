# Academic Paper Recommendation System - Quick Start
Write-Host "Starting Academic Paper Recommendation System..." -ForegroundColor Green
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "./article_recommend/Scripts/Activate.ps1"
# Check if in correct directory
if (!(Test-Path "backend") -or !(Test-Path "frontend")) {
    Write-Host "Please run this script from the project root directory" -ForegroundColor Red
    exit 1
}

# Start backend
Write-Host "Starting backend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
cd backend
Write-Host 'Starting optimized backend server...' -ForegroundColor Green
Write-Host 'Backend API: http://127.0.0.1:8000' -ForegroundColor Cyan
Write-Host 'API Docs: http://127.0.0.1:8000/docs' -ForegroundColor Cyan
python start_dev.py
"@

# Wait for backend to start
Write-Host "Waiting for backend to initialize..." -ForegroundColor Gray
Write-Host "This may take 10-15 seconds for first startup..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Start frontend
Write-Host "Starting frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
cd frontend
Write-Host 'Starting optimized frontend server...' -ForegroundColor Green
Write-Host 'Frontend URL: http://localhost:5173' -ForegroundColor Cyan
Write-Host 'Suppressing Node.js deprecation warnings...' -ForegroundColor Gray
npm run dev-quiet
"@

Write-Host ""
Write-Host "Services starting..." -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173 (auto-opening)" -ForegroundColor Cyan
Write-Host "Backend API: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "API Docs: http://127.0.0.1:8000/docs (auto-opening)" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 Browsers will open automatically..." -ForegroundColor Yellow
Write-Host "⏱️  Please wait for services to start..." -ForegroundColor Gray
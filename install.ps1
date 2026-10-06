# ========================================================
#  VICTOR Installation Script for Windows (PowerShell)
#  Creator: AMKC
#  VICTOR: Virtual Intelligence Created To Outsmart Reality
# ========================================================
$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  VICTOR AI Installation Script (Windows) " -ForegroundColor Cyan
Write-Host "  Creator: AMKC                           " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "[OK] Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 3.10+ is required but was not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python from https://python.org or the Microsoft Store." -ForegroundColor Yellow
    exit 1
}

# 2. Check Node.js
try {
    $nodeVersion = & node --version 2>&1
    Write-Host "[OK] Node.js detected: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Node.js not detected. Some npm automation modules may be limited." -ForegroundColor Yellow
}

# 3. Create Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment (.venv)..." -ForegroundColor Yellow
    & python -m venv .venv
}
Write-Host "[OK] Virtual environment ready." -ForegroundColor Green

# 4. Install Python Dependencies
$pipPath = ".\.venv\Scripts\pip.exe"
if (-not (Test-Path $pipPath)) {
    $pipPath = "pip"
}
Write-Host "Installing Python dependencies from requirements.txt..." -ForegroundColor Yellow
& $pipPath install --upgrade pip
& $pipPath install -r requirements.txt

# 5. Install Node.js Dependencies
if (Test-Path "package.json") {
    Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
    & npm install --no-audit --prefer-offline 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Node modules installed." -ForegroundColor Green
    }
}

# 6. Setup .env
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host ""
        Write-Host "[IMPORTANT] Created '.env' from '.env.example'!" -ForegroundColor Magenta
        Write-Host "Please open '.env' and add your GEMINI_API_KEY from:" -ForegroundColor Magenta
        Write-Host "  https://aistudio.google.com/app/apikey" -ForegroundColor Cyan
    }
} else {
    Write-Host "[OK] '.env' configuration file is already present." -ForegroundColor Green
}

# 7. Create data and config directories
if (-not (Test-Path "notes")) { New-Item -ItemType Directory -Path "notes" | Out-Null }
if (-not (Test-Path "tasks")) { New-Item -ItemType Directory -Path "tasks" | Out-Null }
if (-not (Test-Path "config")) { New-Item -ItemType Directory -Path "config" | Out-Null }

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Installation Completed Successfully!    " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To launch VICTOR:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe main.py" -ForegroundColor White
Write-Host "  OR double-click 'start.bat'" -ForegroundColor White
Write-Host ""

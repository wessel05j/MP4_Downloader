$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

try {
    python --version | Out-Null
}
catch {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
}

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

& ".\venv\Scripts\Activate.ps1"

Write-Host "Preparing runtime dependencies..."
python setup_env.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Dependency setup failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

python MP4.py @args
exit $LASTEXITCODE

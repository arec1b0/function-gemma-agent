# Convenience script for Windows 11 development
Write-Host "Starting FunctionGemma Agent in Development Mode..." -ForegroundColor Cyan

# 1. Check/Create Venv
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
    .\venv\Scripts\pip install -e .[dev]
}

# 2. Explicitly Load Hugging Face Token from Cache
$TokenPath = "$env:USERPROFILE\.cache\huggingface\token"
if (Test-Path $TokenPath) {
    $Token = Get-Content -Path $TokenPath -Raw
    $env:HF_TOKEN = $Token.Trim()
    Write-Host "Authenticated with Hugging Face token." -ForegroundColor Green
} else {
    Write-Warning "No Hugging Face token found at $TokenPath. Model download might fail."
}

# 3. Set Environment Variables
$VenvPython = ".\venv\Scripts\python.exe"
$env:ENV="development"
$env:LOG_LEVEL="DEBUG"

# 4. Run Application
& $VenvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Build and Run the Agent in Docker (Production Mode)
Write-Host "Preparing FunctionGemma Agent for Docker..." -ForegroundColor Cyan

# 1. Retrieve Hugging Face Token
$TokenPath = "$env:USERPROFILE\.cache\huggingface\token"
if (Test-Path $TokenPath) {
    $env:HF_TOKEN = (Get-Content -Path $TokenPath -Raw).Trim()
    Write-Host "Injecting HF_TOKEN into container build." -ForegroundColor Green
} else {
    Write-Error "No Hugging Face token found! Run 'huggingface-cli login' locally first."
    exit 1
}

# 2. Build and Run
# We use -f to point to the file, and --project-directory to ensure context is correct
docker-compose -f deployment/docker-compose.yml --project-directory . up --build -d

Write-Host "`nAgent is running at http://localhost:8000" -ForegroundColor Green
Write-Host "To view logs: docker-compose -f deployment/docker-compose.yml logs -f" -ForegroundColor Gray
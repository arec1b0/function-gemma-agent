#!/usr/bin/env pwsh

<#
.SYNOPSIS
    FunctionGemma Agent Rollback Script for PowerShell
    This script provides a quick rollback mechanism for failed deployments

.DESCRIPTION
    Performs rollback of Helm releases with proper validation and status checks

.PARAMETER Namespace
    Kubernetes namespace (default: production)

.PARAMETER ReleaseName
    Helm release name (default: function-gemma-agent)

.PARAMETER Revision
    Revision to rollback to (default: 0, previous version)

.EXAMPLE
    .\rollback.ps1
    Rollback to previous version

.EXAMPLE
    .\rollback.ps1 -Revision 2
    Rollback to revision 2

.EXAMPLE
    .\rollback.ps1 -Namespace staging -ReleaseName agent-staging -Revision 5
    Rollback staging release to revision 5
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$Namespace = "production",
    
    [Parameter(Mandatory = $false)]
    [string]$ReleaseName = "function-gemma-agent",
    
    [Parameter(Mandatory = $false)]
    [int]$Revision = 0,
    
    [Parameter(Mandatory = $false)]
    [switch]$Help
)

# Color output functions
function Write-Status($message) {
    Write-Host "[INFO] $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor Yellow
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

# Show help
if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

# Check if helm is installed
if (!(Get-Command helm -ErrorAction SilentlyContinue)) {
    Write-Error "Helm is not installed or not in PATH"
    exit 1
}

# Check if kubectl is installed
if (!(Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Error "kubectl is not installed or not in PATH"
    exit 1
}

# Check if release exists
Write-Status "Checking if release $ReleaseName exists in namespace $Namespace..."
try {
    $null = helm status $ReleaseName -n $Namespace 2>$null
}
catch {
    Write-Error "Release $ReleaseName not found in namespace $Namespace"
    exit 1
}

# Get current revision
$history = helm history $ReleaseName -n $Namespace -o json | ConvertFrom-Json
$currentRevision = $history[-1].revision
Write-Status "Current revision: $currentRevision"

# Get available revisions
Write-Status "Available revisions:"
helm history $ReleaseName -n $Namespace

# Confirm rollback
if ($Revision -eq 0) {
    $targetRevision = $currentRevision - 1
    Write-Warning "You are about to rollback to the previous version (revision $targetRevision)"
}
else {
    $targetRevision = $Revision
    Write-Warning "You are about to rollback to revision $targetRevision"
}

$confirmation = Read-Host "Do you want to continue? (y/N)"
if ($confirmation -notmatch '^[Yy]$') {
    Write-Status "Rollback cancelled"
    exit 0
}

# Perform rollback
Write-Status "Performing rollback..."
try {
    helm rollback $ReleaseName $targetRevision -n $Namespace
    if ($LASTEXITCODE -ne 0) {
        throw "Helm rollback failed"
    }
    Write-Status "Rollback initiated successfully"
}
catch {
    Write-Error "Rollback failed: $_"
    exit 1
}

# Wait for rollout to complete
Write-Status "Waiting for rollout to complete..."
kubectl rollout status deployment/$ReleaseName -n $Namespace --timeout=300s

if ($LASTEXITCODE -ne 0) {
    Write-Warning "Rollout timeout - please check status manually"
}

# Show final status
Write-Status "Rollback completed successfully!"
Write-Status "Current release status:"
helm status $ReleaseName -n $Namespace

# Show pod status
Write-Status "Pod status:"
kubectl get pods -n $Namespace -l "app.kubernetes.io/instance=$ReleaseName"

# Get service URL for health check
try {
    $serviceUrl = kubectl get ingress $ReleaseName -n $Namespace -o jsonpath='{.spec.rules[0].host}' 2>$null
    if ($serviceUrl) {
        Write-Status "Service URL: https://$serviceUrl"
        Write-Status "Performing health check..."
        
        try {
            $response = Invoke-WebRequest -Uri "https://$serviceUrl/api/v1/health" -UseBasicParsing -TimeoutSec 10
            if ($response.StatusCode -eq 200) {
                Write-Status "Health check passed!"
            }
            else {
                Write-Warning "Health check failed with status code: $($response.StatusCode)"
            }
        }
        catch {
            Write-Warning "Health check failed - please verify the deployment manually"
        }
    }
}
catch {
    Write-Warning "Could not retrieve service URL for health check"
}

Write-Status "Rollback process completed!"

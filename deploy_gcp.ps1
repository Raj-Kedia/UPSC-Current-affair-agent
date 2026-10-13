# ==============================================================================
# Google Cloud Run & Cloud Scheduler Deployment Script
# Automatically builds, deploys, and sets up automated Sunday newsletter mailing
# ==============================================================================

param(
    [string]$ProjectId = "project-779f14c7-956f-4fdd-b95",
    [string]$Region = "us-central1",
    [string]$ServiceName = "upsc-digest",
    [string]$CronSecret = "upsc-auto-dispatch-key-2026"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  UPSC Agentic Intelligence - Google Cloud Deployment    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check gcloud CLI
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error "Google Cloud SDK (gcloud) is not installed or not in PATH."
    Exit 1
}

# 2. Load environment variables from agent/.env
$envPath = Join-Path $PSScriptRoot "agent\.env"
if (-not (Test-Path $envPath)) {
    Write-Error "Could not find agent/.env. Please ensure credentials are set."
    Exit 1
}

Write-Host "Reading credentials from agent/.env..." -ForegroundColor Yellow
$envVars = @{}
Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $parts = $line.Split("=", 2)
        $envVars[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$geminiKey     = $envVars["GEMINI_API_KEY"]
$smtpUser      = $envVars["SMTP_USER"]
$smtpPass      = $envVars["SMTP_PASSWORD"]
$receiverEmail = $envVars["RECEIVER_EMAIL"]
$smtpHost      = if ($envVars["SMTP_HOST"]) { $envVars["SMTP_HOST"] } else { "smtp.gmail.com" }
$smtpPort      = if ($envVars["SMTP_PORT"]) { $envVars["SMTP_PORT"] } else { "587" }

if (-not $geminiKey -or -not $smtpUser -or -not $smtpPass) {
    Write-Error "Missing essential credentials (GEMINI_API_KEY, SMTP_USER, SMTP_PASSWORD) in agent/.env."
    Exit 1
}

Write-Host "Deploying to Project: $ProjectId in Region: $Region" -ForegroundColor Green

# 3. Enable required Google Cloud services
Write-Host "Ensuring required Google Cloud APIs are enabled..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com artifactregistry.googleapis.com --project $ProjectId --quiet

# 4. Deploy unified service (FastAPI + React Dashboard) to Cloud Run
Write-Host "Submitting build and deploying to Cloud Run (this builds the container in GCP)..." -ForegroundColor Yellow

# Generate env.yaml for gcloud deploy (avoids comma-delimiter escaping issues)
$envYamlPath = Join-Path $PSScriptRoot "env.yaml"
$yamlContent = @"
GEMINI_API_KEY: "$geminiKey"
GEMINI_MODEL: "gemini-2.0-flash"
SMTP_HOST: "$smtpHost"
SMTP_PORT: "$smtpPort"
SMTP_USER: "$smtpUser"
SMTP_PASSWORD: "$smtpPass"
RECEIVER_EMAIL: "$receiverEmail"
CRON_SECRET: "$CronSecret"
"@
Set-Content -Path $envYamlPath -Value $yamlContent -Encoding UTF8

try {
    gcloud run deploy $ServiceName `
        --source . `
        --project $ProjectId `
        --region $Region `
        --platform managed `
        --allow-unauthenticated `
        --memory 2Gi `
        --cpu 2 `
        --timeout 600 `
        --env-vars-file $envYamlPath `
        --quiet
} finally {
    if (Test-Path $envYamlPath) { Remove-Item $envYamlPath -Force }
}

# 5. Retrieve deployed URL
$serviceUrl = (gcloud run services describe $ServiceName --project $ProjectId --region $Region --format "value(status.url)").Trim()

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Cloud Run Deployment Succeeded!" -ForegroundColor Green
Write-Host " Website URL: $serviceUrl" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""

# 6. Setup Google Cloud Scheduler for Automatic Sunday Mailing (Zero Manual Work)
Write-Host "Configuring Cloud Scheduler: Automated Sunday 8:00 AM dispatch..." -ForegroundColor Yellow
$jobName = "weekly-upsc-digest-mailer"
$cronUri = "$serviceUrl/api/cron/weekly-dispatch"

# Check if job already exists
$jobExists = $false
try {
    $existing = gcloud scheduler jobs describe $jobName --project $ProjectId --location $Region --format "value(name)" 2>$null
    if ($existing) { $jobExists = $true }
} catch {
    $jobExists = $false
}

if ($jobExists) {
    Write-Host "Updating existing Cloud Scheduler job '$jobName'..." -ForegroundColor Cyan
    gcloud scheduler jobs update http $jobName `
        --project $ProjectId `
        --location $Region `
        --schedule "0 8 * * 0" `
        --time-zone "Asia/Kolkata" `
        --uri $cronUri `
        --http-method POST `
        --update-headers "Content-Type=application/json,x-cron-secret=$CronSecret" `
        --description "Automated weekly UPSC intelligence digest dispatched every Sunday at 8:00 AM IST to active users" `
        --quiet
} else {
    Write-Host "Creating new Cloud Scheduler job '$jobName'..." -ForegroundColor Cyan
    gcloud scheduler jobs create http $jobName `
        --project $ProjectId `
        --location $Region `
        --schedule "0 8 * * 0" `
        --time-zone "Asia/Kolkata" `
        --uri $cronUri `
        --http-method POST `
        --headers "Content-Type=application/json,x-cron-secret=$CronSecret" `
        --description "Automated weekly UPSC intelligence digest dispatched every Sunday at 8:00 AM IST to active users" `
        --quiet
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " ALL SYSTEMS OPERATIONAL & AUTOMATED!" -ForegroundColor Green
Write-Host " - Website is live at: $serviceUrl" -ForegroundColor Cyan
Write-Host " - Automatic weekly mailing: Scheduled every Sunday at 08:00 AM IST" -ForegroundColor Cyan
Write-Host " - Target: Dispatches automatically to all active subscribers" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green

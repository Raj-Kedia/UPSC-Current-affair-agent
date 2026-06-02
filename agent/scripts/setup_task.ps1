# Setup Daily UPSC Agent Task Scheduler Script
# This script registers a daily Windows scheduled task that runs the agent SILENTLY at 8:00 AM.
# Using wscript.exe + VBScript ensures NO CMD window pops up during execution.
# MUST BE RUN AS ADMINISTRATOR.

# Check for administrative privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "This script must be run as Administrator to register scheduled tasks."
    Write-Host "Please open an elevated PowerShell prompt (Run as Administrator) and execute this script again."
    Write-Host "Command to run:"
    Write-Host "powershell -ExecutionPolicy Bypass -File d:\project\agent\scripts\setup_task.ps1" -ForegroundColor Yellow
    Exit
}

$taskName = "UPSCDailyAgent"
$vbsPath   = "d:\project\agent\scripts\run_agent_silent.vbs"
$batchPath = "d:\project\agent\scripts\run_agent.bat"  # kept for manual use only

if (-not (Test-Path $vbsPath)) {
    Write-Error "Could not find run_agent_silent.vbs at $vbsPath. Please ensure the workspace path is correct."
    Exit
}

Write-Host "Setting up Scheduled Task: $taskName" -ForegroundColor Cyan
Write-Host "Action: Run $vbsPath (silent, no CMD window)" -ForegroundColor Cyan
Write-Host "Trigger: Daily at 8:00 AM" -ForegroundColor Cyan

# 1. Define the action: use wscript.exe to run VBScript silently (no console window)
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`""

# 2. Define daily trigger at 8:00 AM
# We use a standard time format (08:00)
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM

# 3. Configure advanced settings
# -WakeToRun: Wake the computer to run the task if sleeping
# -StartWhenAvailable: Run the task as soon as possible if a scheduled start is missed
# -AllowStartIfOnBatteries: Run on laptops even when unplugged
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Hidden

# 4. Register the scheduled task under the current user context
# This ensures it runs with the user's paths and credentials
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Registering task for user: $currentUser" -ForegroundColor Cyan

try {
    # Check if task already exists and unregister if it does
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Write-Host "Task '$taskName' already exists. Re-registering..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User $currentUser -RunLevel Highest
    
    Write-Host "Successfully registered scheduled task '$taskName'!" -ForegroundColor Green
    Write-Host "You can inspect it in Windows Task Scheduler (taskschd.msc)." -ForegroundColor Green
    Write-Host "Settings configured:" -ForegroundColor Green
    Write-Host "  - Runs daily at 8:00 AM" -ForegroundColor Green
    Write-Host "  - Wakes PC to run: Yes" -ForegroundColor Green
    Write-Host "  - Run as soon as possible if missed: Yes" -ForegroundColor Green
    Write-Host "  - Run on battery power: Yes" -ForegroundColor Green
}
catch {
    Write-Error "Failed to register scheduled task: $_"
}

# setup_windows_task.ps1 — Register AutoJobHunt Daemon in Windows Task Scheduler
# Keeps the job scanner running silently in the background and starts on user logon.

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status
)

$TaskName = "AutoJobHunt-BackgroundDaemon"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VbsPath = Join-Path $ScriptDir "run_daemon_background.vbs"

if ($Uninstall) {
    Write-Host "Unregistering scheduled task: $TaskName..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "✓ AutoJobHunt background task removed." -ForegroundColor Green
    return
}

if ($Status) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "Task Name:   $TaskName" -ForegroundColor Cyan
        Write-Host "State:       $($task.State)" -ForegroundColor Green
    } else {
        Write-Host "Task '$TaskName' is not currently registered." -ForegroundColor DarkGray
    }
    return
}

# Default or -Install:
Write-Host "Registering $TaskName to run silently on user logon..." -ForegroundColor Cyan

$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "AutoJobHunt 24/7 background job discovery and email alerting daemon." -Force

Write-Host "✓ Successfully registered $TaskName in Windows Task Scheduler." -ForegroundColor Green
Write-Host "  • Script: $VbsPath"
Write-Host "  • Trigger: Runs automatically when you log into Windows."
Write-Host "  • To start immediately: Start-ScheduledTask -TaskName $TaskName"
Write-Host "  • To uninstall: .\\setup_windows_task.ps1 -Uninstall"

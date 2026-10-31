# setup_windows_task.ps1 - Register AutoJobHunt Daemon in Windows Startup / Task Scheduler
# Keeps the job scanner running silently in the background and starts on user logon.

param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status
)

$TaskName = "AutoJobHunt-BackgroundDaemon"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $ScriptDir) {
    $ScriptDir = (Get-Location).Path
}
$VbsPath = Join-Path $ScriptDir "run_daemon_background.vbs"
$StartupFolder = [System.IO.Path]::Combine($env:APPDATA, "Microsoft\Windows\Start Menu\Programs\Startup")
$StartupShortcut = Join-Path $StartupFolder "AutoJobHuntDaemon.lnk"

if ($Uninstall) {
    Write-Host "Removing AutoJobHunt Daemon autostart..." -ForegroundColor Yellow
    if (Test-Path $StartupShortcut) {
        Remove-Item $StartupShortcut -Force
        Write-Host "[OK] Removed startup shortcut from Windows Startup folder." -ForegroundColor Green
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] AutoJobHunt autostart configuration removed." -ForegroundColor Green
    exit 0
}

if ($Status) {
    Write-Host "AutoJobHunt Autostart Status:" -ForegroundColor Cyan
    $inStartup = Test-Path $StartupShortcut
    if ($inStartup) {
        Write-Host "  * Windows Startup Folder: ACTIVE ($StartupShortcut)" -ForegroundColor Green
    } else {
        Write-Host "  * Windows Startup Folder: Not registered" -ForegroundColor DarkGray
    }

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "  * Windows Task Scheduler: ACTIVE ($($task.State))" -ForegroundColor Green
    } else {
        Write-Host "  * Windows Task Scheduler: Not registered" -ForegroundColor DarkGray
    }
    exit 0
}

# Install / Register autostart:
Write-Host "Setting up AutoJobHunt Daemon autostart on user logon..." -ForegroundColor Cyan

# 1. Install to user's personal Windows Startup folder (requires zero admin rights)
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($StartupShortcut)
    $Shortcut.TargetPath = "wscript.exe"
    $Shortcut.Arguments = "`"$VbsPath`""
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.Description = "AutoJobHunt 24/7 background job discovery daemon"
    $Shortcut.Save()
    Write-Host "[OK] Created autostart shortcut in Windows Startup folder:" -ForegroundColor Green
    Write-Host "     $StartupShortcut"
} catch {
    Write-Host "[-] Failed to write to Startup folder: $_" -ForegroundColor Yellow
}

# 2. Also try registering via Task Scheduler if running elevated
try {
    $Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`"" -WorkingDirectory $ScriptDir
    $Trigger = New-ScheduledTaskTrigger -AtLogOn
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "AutoJobHunt 24/7 background job discovery and email alerting daemon." -Force -ErrorAction Stop | Out-Null
    Write-Host "[OK] Registered in Windows Task Scheduler." -ForegroundColor Green
} catch {
    # Task scheduler requires admin; Startup folder shortcut is sufficient and fully functional
    Write-Host "[i] Note: Task Scheduler registration skipped (requires Admin). User Startup folder shortcut is active." -ForegroundColor DarkGray
}

Write-Host "`nAutoJobHunt Daemon is configured to run silently on every Windows login." -ForegroundColor Green
Write-Host "  * To test run now silently: wscript.exe `"$VbsPath`""
Write-Host "  * To check status:          python background_daemon.py --status"
Write-Host "  * To uninstall:             .\setup_windows_task.ps1 -Uninstall"

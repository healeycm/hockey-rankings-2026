# scripts/register_task.ps1
#
# Registers a daily Windows Task Scheduler job that runs
# scripts/daily_update.py (men's hockey by default) using this project's
# conda environment's python.exe. Run this ONCE per machine, from an
# elevated (Run as Administrator) PowerShell prompt:
#
#     powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
#
# To also run women's hockey daily, edit -Argument below to add "--women",
# or register a second task pointing at --women-only on a different time.
#
# Publishing the site: clone the PUBLIC Pages repo somewhere once, e.g.
#     git clone https://github.com/<you>/hockey-rankings-site D:\hockey-rankings-site
# then either set $SiteRepoPath below, or leave it blank and set the
# SITE_REPO_PATH environment variable / pass --site-repo yourself. Task
# Scheduler runs non-interactively, so `git push` needs credentials already
# cached (gh auth login, or an SSH remote with a passphrase-less key) --
# test with `git push` by hand from $SiteRepoPath first.
#
# To remove the task later:
#     Unregister-ScheduledTask -TaskName "HockeyRankingsDailyUpdate" -Confirm:$false

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe = "C:\Users\chris\anaconda3\envs\hockey-rankings-2026\python.exe"
$TaskName = "HockeyRankingsDailyUpdate"

# Set this to the local clone of the public Pages repo to publish
# automatically. Leave blank ("") to build the site locally each run
# without pushing it anywhere.
$SiteRepoPath = "C:\Users\chris\Documents\hockey-rankings-site"

if (-not (Test-Path $PythonExe)) {
    throw "Conda env python.exe not found at $PythonExe -- update `$PythonExe in this script if the env path has changed."
}

$RunArgs = "-m scripts.daily_update"
if ($SiteRepoPath) {
    $RunArgs += " --site-repo `"$SiteRepoPath`""
} else {
    $RunArgs += " --no-publish"
}

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $RunArgs `
    -WorkingDirectory $ProjectRoot

# 6:00 AM daily -- USCHO scores from the previous night's games are final by then.
$Trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Scrapes latest college hockey scores and regenerates rankings/projections/analysis/simulations." `
    -Force

Write-Host "Registered scheduled task '$TaskName': runs daily at 6:00 AM as $env:USERNAME."
Write-Host "Test it immediately with: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Check its last result with: Get-ScheduledTaskInfo -TaskName '$TaskName'"

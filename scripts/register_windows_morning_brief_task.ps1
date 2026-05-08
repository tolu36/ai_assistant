param(
    [string]$TaskName = "Personal AI Assistant Morning Brief",
    [string]$CondaEnv = "ai_ast",
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$At = "09:00"
)

$condaCommand = Get-Command conda -ErrorAction Stop
$scriptPath = Join-Path $ProjectRoot "scripts\send_morning_brief.py"
$argument = "run -n $CondaEnv python `"$scriptPath`""

$action = New-ScheduledTaskAction `
    -Execute $condaCommand.Source `
    -Argument $argument `
    -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $At

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Description "Sends the Personal AI Assistant morning brief email." `
    -Force

Write-Host "Registered scheduled task '$TaskName' for $At."

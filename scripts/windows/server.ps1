<#
  Talaba Ovozi on Windows - manage the server. Run it with scripts\server.bat:

    scripts\server.bat status            is it running? + the public address
    scripts\server.bat logs [name]       follow a log: server (default) | web | bot | tunnel   (Ctrl+C to stop)
    scripts\server.bat restart           after changing .env (code updates: update)
    scripts\server.bat stop | start
    scripts\server.bat update            the newest version from GitHub: a backup first, then the new version
                                         is checked - if it doesn't run properly, the previous one comes back
    scripts\server.bat backup            a database copy now (one is made every night at 03:30 by itself)
    scripts\server.bat backups           the copies (data\backups)
    scripts\server.bat restore <file>    put a copy back - replaces ALL data
    scripts\server.bat transfer          one file for moving to another computer

  The server is the task "Talaba Ovozi" (Task Scheduler), set up by scripts\setup.bat.
#>
param([string]$Command = "status", [string]$Arg = "", [switch]$Elevated)
$ErrorActionPreference = "Continue"
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $Root
$TaskName = "Talaba Ovozi"
$VenvPy = "$Root\.venv\Scripts\python.exe"
$Runtime = "$Root\data\runtime"

function Stop-Server {   # the task's programs end with it; the loop is the safety net
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "-m app\.(server|web|bot)") -or
        ($_.Name -eq "cloudflared.exe" -and $_.CommandLine -like "*$Root*") } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item "$Root\data\runtime\server_status.json" -ErrorAction SilentlyContinue   # no stale "running"
}

function Wait-Started {   # until the new server reports (at most a minute)
    Write-Host "Starting..."
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Path "$Runtime\server_status.json") { Start-Sleep -Seconds 3; break }
    }
}

function Show-Status {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) { Write-Host "Not installed - run scripts\setup.bat" -ForegroundColor Red; return }
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $status = $null
    if (Test-Path "$Runtime\server_status.json") {
        $status = Get-Content "$Runtime\server_status.json" -Raw | ConvertFrom-Json
        # written in the last minute, by a server that still runs
        if ($now - $status.at -gt 60 -or -not (Get-Process -Id $status.pid -ErrorAction SilentlyContinue)) { $status = $null }
    }
    if ($task.State -ne "Running" -or -not $status) {
        Write-Host ("  server   NOT running (task: " + $task.State + ")  -  scripts\server.bat start") -ForegroundColor Red
    } else {
        foreach ($c in $status.children.PSObject.Properties) {
            $mins = [int](($now - $c.Value.since) / 60)
            if ($c.Value.running) {
                Write-Host ("  {0,-8} running for {1} min (restarts: {2})" -f $c.Name, $mins, $c.Value.restarts) -ForegroundColor Green
            } else {
                Write-Host ("  {0,-8} NOT running - see: scripts\server.bat logs {0}" -f $c.Name) -ForegroundColor Red
            }
        }
    }
    $tunnel = if (Test-Path "$Runtime\tunnel_status") { (Get-Content "$Runtime\tunnel_status" -Raw).Split("|")[0] } else { "unknown" }
    $url = if (Test-Path "$Runtime\webapp_url") { (Get-Content "$Runtime\webapp_url" -Raw).Trim() } else { "" }
    if ($url) {
        Write-Host "  address  $url   (last check: $tunnel)"
        Write-Host "  survey   $url/survey   (students open it from the bot)"
    } else {
        Write-Host "  address  none yet (the tunnel is starting)"
    }
    Write-Host "  admin    http://127.0.0.1:8000/admin   (on this computer)"
    $last = Get-ChildItem "$Root\data\backups" -Filter "feedback-*.sql.gz" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -Last 1
    Write-Host ("  backup   " + $(if ($last) { $last.Name } else { "none yet" }))
    if (Test-Path "$Runtime\version.json") {
        $v = Get-Content "$Runtime\version.json" -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($v.current) {
            $news = if ($v.behind -gt 0) { " - $($v.behind) newer on GitHub (scripts\server.bat update)" } else { "" }
            $d = "$($v.current.date)"; if ($d.Length -gt 10) { $d = $d.Substring(0, 10) }
            Write-Host ("  version  " + $v.current.short + " of " + $d + $news)
        }
    }
}

# start / stop / restart / update / restore need administrator rights (a new window opens)
$needsAdmin = @("start", "stop", "restart", "update", "restore") -contains $Command
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if ($needsAdmin -and -not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" $Command -Elevated"
    if ($Arg) { $argList += " `"$((Resolve-Path $Arg).Path)`"" }
    try { Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -ErrorAction Stop }
    catch { Write-Host "Administrator rights are needed for '$Command'." -ForegroundColor Red; exit 1 }
    Write-Host "Continues in the new window."
    exit 0
}

switch ($Command) {
    "status" { Show-Status }
    "start" { Start-ScheduledTask -TaskName $TaskName; Wait-Started; Show-Status }
    "stop" { Stop-Server; Write-Host "Stopped. It starts again with Windows, or: scripts\server.bat start" }
    "restart" {
        Stop-Server; Start-Sleep -Seconds 2; Start-ScheduledTask -TaskName $TaskName
        Wait-Started; Show-Status
    }
    "update" {   # the running server does it (app.server: backup, check, put back if needed)
        & $VenvPy -X utf8 -m app.server update
        if ($LASTEXITCODE -eq 2) {   # the server is not running: the plain way
            Write-Host "The server is not running - updating the plain way"
            & git -c safe.directory=* -C $Root pull --ff-only
            if ($LASTEXITCODE -ne 0) { Write-Host "git pull failed (see above)" -ForegroundColor Red; break }
            Stop-Server
            & $VenvPy -m pip install -q --disable-pip-version-check -r "$Root\requirements.txt"
            Start-ScheduledTask -TaskName $TaskName   # the server updates the database when it starts
            Wait-Started
        }
        Show-Status
    }
    "logs" {
        $name = if ($Arg) { $Arg } else { "server" }
        Get-Content "$Runtime\logs\$name.log" -Tail 60 -Wait -Encoding UTF8
    }
    "backup" { & $VenvPy -X utf8 -m app.backup now }
    "backups" { & $VenvPy -X utf8 -m app.backup list }
    "transfer" { & $VenvPy -X utf8 -m app.backup transfer }
    "restore" {
        if (-not $Arg) { Write-Host "Which copy?  scripts\server.bat restore data\backups\feedback-....sql.gz"; break }
        Stop-Server
        & $VenvPy -X utf8 -m app.backup restore $Arg
        Start-ScheduledTask -TaskName $TaskName
        Wait-Started; Show-Status
    }
    default { Get-Content $PSCommandPath | Select-Object -Skip 1 -First 15 }
}
if ($Elevated) { Write-Host ""; Read-Host "Press Enter to close" | Out-Null }

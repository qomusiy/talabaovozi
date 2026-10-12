<#
  Talaba Ovozi - make this Windows computer (10 or 11) the server. Run it with scripts\setup.bat:

    1. git clone https://github.com/qomusiy/talabaovozi.git C:\talabaovozi
    2. put the transfer file (talaba-transfer-....tar.gz, made on the old computer) in C:\talabaovozi
    3. double-click C:\talabaovozi\scripts\setup.bat   (or run it in a terminal)

  It installs what is missing - Python 3.12, PostgreSQL 16 (the database), cloudflared or Tailscale (the public
  address) - restores the data from the transfer file, keeps Windows awake, and adds the task "Talaba Ovozi" that
  runs the server (python -m app.server) whenever Windows starts, before anyone signs in.
  Safe to run again: it skips what is done.
#>
param([string]$Transfer = "", [switch]$Elevated)
$ErrorActionPreference = "Continue"   # native programs report through exit codes, checked below
# winget installs come from its own source: the Microsoft Store source fails on some networks (certificate errors).
$ProgressPreference = "SilentlyContinue"   # downloads are much faster without the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $Root
$TaskName = "Talaba Ovozi"
$PgVersion = "16"
$PgService = "postgresql-x64-$PgVersion"
$PgBin = "$env:ProgramFiles\PostgreSQL\$PgVersion\bin"
$SuperFile = "$Root\data\runtime\postgres_password.txt"   # this computer's database superuser password
$VenvPy = "$Root\.venv\Scripts\python.exe"

function Say([string]$t) { Write-Host ""; Write-Host "-- $t" -ForegroundColor Cyan }
function Ok([string]$t) { Write-Host "OK  $t" -ForegroundColor Green }
function Done { Write-Host ""; Read-Host "Press Enter to close" | Out-Null }
function Fail([string]$t) { Write-Host ""; Write-Host "ERROR: $t" -ForegroundColor Red; Done; exit 1 }
function Download([string]$url, [string]$file) {
    try { Invoke-WebRequest $url -OutFile $file -UseBasicParsing -ErrorAction Stop }
    catch { Fail "Could not download $url - is the internet on? ($($_.Exception.Message))" }
}
function Get-EnvValue([string]$key) {
    if (-not (Test-Path "$Root\.env")) { return "" }
    $line = @(Get-Content "$Root\.env" -Encoding UTF8 | Where-Object { $_ -match "^$key=" }) | Select-Object -Last 1
    if (-not $line) { return "" }
    return ($line -replace "^$key=", "").Trim().Trim('"').Trim("'")
}
function Set-EnvValue([string]$key, [string]$value) {
    $found = $false
    $lines = @(Get-Content "$Root\.env" -Encoding UTF8 | ForEach-Object {
        if ($_ -match "^$key=") { $found = $true; "$key=$value" } else { $_ } })
    if (-not $found) { $lines += "$key=$value" }
    [IO.File]::WriteAllLines("$Root\.env", [string[]]$lines)   # UTF-8 without BOM, as the app reads it
}
function Psql([string]$user, [string]$pass, [string]$db, [string]$sql) {
    $env:PGPASSWORD = $pass
    $out = & "$PgBin\psql.exe" -h 127.0.0.1 -p $DbPort -U $user -d $db -tAc $sql 2>&1
    $env:PGPASSWORD = $null
    return ("$out").Trim()
}
function Wait-Postgres {
    for ($i = 0; $i -lt 60; $i++) {
        & "$PgBin\pg_isready.exe" -h 127.0.0.1 -p $DbPort -q
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 1
    }
    Fail "PostgreSQL does not answer on port $DbPort"
}
function Stop-Server {   # the task's programs end with it; the loop is the safety net
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -eq "python.exe" -and $_.CommandLine -match "-m app\.(server|web|bot)") -or
        ($_.Name -eq "cloudflared.exe" -and $_.CommandLine -like "*$Root*") } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item "$Root\data\runtime\server_status.json" -ErrorAction SilentlyContinue   # no stale "running"
}

# --- administrator rights (a new window opens) ---------------------------------------------------------------
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Elevated"
    if ($Transfer) { $argList += " -Transfer `"$((Resolve-Path $Transfer).Path)`"" }
    Write-Host "Asking for administrator rights - the setup continues in a new window."
    try { Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -ErrorAction Stop }
    catch { Write-Host "Administrator rights are needed (Windows asked and was told no)." -ForegroundColor Red }
    exit 0
}
Write-Host "Talaba Ovozi setup in $Root"
try {   # a click inside the window would start "Select" mode, which pauses everything until Esc
    Add-Type -Namespace Win32 -Name ConsoleMode -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern System.IntPtr GetStdHandle(int handle);
[DllImport("kernel32.dll")] public static extern bool GetConsoleMode(System.IntPtr handle, out uint mode);
[DllImport("kernel32.dll")] public static extern bool SetConsoleMode(System.IntPtr handle, uint mode);
'@
    $in = [Win32.ConsoleMode]::GetStdHandle(-10)
    $mode = 0
    if ([Win32.ConsoleMode]::GetConsoleMode($in, [ref]$mode)) {
        [void][Win32.ConsoleMode]::SetConsoleMode($in, ($mode -band (-bnot 0x40)) -bor 0x80)   # QuickEdit off
    }
} catch { }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping the running server while it is updated..."
    Stop-Server
}
# An earlier attempt with WSL (Ubuntu inside Windows) must not run a second bot.
if (Get-ScheduledTask -TaskName "Talaba Ovozi server" -ErrorAction SilentlyContinue) {
    Write-Host "Removing the earlier WSL setup..."
    Stop-ScheduledTask -TaskName "Talaba Ovozi server" -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "Talaba Ovozi server" -Confirm:$false
    & wsl.exe -d Ubuntu-24.04 --exec bash -lc "systemctl --user disable --now talaba-web talaba-bot talaba-tunnel talaba-backup.timer 2>/dev/null; true"
    & wsl.exe --terminate Ubuntu-24.04 2>$null | Out-Null
}

# --- 1. Python ------------------------------------------------------------------------------------------------
Say "1/7 Python 3.12"
function Find-Python {
    foreach ($p in @("$env:ProgramFiles\Python312\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}
$python = Find-Python
if (-not $python) {
    Write-Host "Installing Python 3.12 (a minute)..."
    $installer = "$env:TEMP\python-3.12.10-amd64.exe"
    Download "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" $installer
    Start-Process $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=0 Include_test=0" -Wait
    $python = Find-Python
    if (-not $python) { Fail "Python did not install" }
}
Ok $python

# --- 2. Python packages ---------------------------------------------------------------------------------------
Say "2/7 Python packages (a few minutes the first time)"
if (-not (Test-Path $VenvPy)) {
    & $python -m venv "$Root\.venv"
    if ($LASTEXITCODE -ne 0) { Fail "Could not create .venv" }
}
& $VenvPy -m pip install -q --disable-pip-version-check --upgrade pip
& $VenvPy -m pip install -q --disable-pip-version-check -r "$Root\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "Installing the Python packages failed (see above)" }
Ok ".venv"

# --- the transfer file ----------------------------------------------------------------------------------------
if (-not $Transfer) {
    $found = @(Get-ChildItem -Path $Root, "$env:USERPROFILE\Downloads" -Filter "talaba-transfer-*.tar.gz" `
        -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($found.Count -gt 0) { $Transfer = $found[0].FullName }
}
while (-not $Transfer -and -not (Test-Path "$Root\.env")) {   # first run: the data from the old computer
    Write-Host ""
    Write-Host "The transfer file (talaba-transfer-....tar.gz) is not in $Root or in Downloads." -ForegroundColor Yellow
    $answer = Read-Host "Copy it into $Root, then press Enter (or type NEW to start without any data)"
    if ($answer -eq "NEW") { break }
    $found = @(Get-ChildItem -Path $Root, "$env:USERPROFILE\Downloads" -Filter "talaba-transfer-*.tar.gz" `
        -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($found.Count -gt 0) { $Transfer = $found[0].FullName }
}
if ($Transfer) { Write-Host "Data from: $Transfer" }
$Unpacked = $null
if ($Transfer) {
    $Unpacked = Join-Path $env:TEMP ("talaba-" + [guid]::NewGuid())
    New-Item -ItemType Directory $Unpacked | Out-Null
    & tar.exe -xzf $Transfer -C $Unpacked
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$Unpacked\.env")) { Fail "Could not unpack $Transfer" }
}

# --- 3. PostgreSQL --------------------------------------------------------------------------------------------
Say "3/7 PostgreSQL $PgVersion (the database)"
$envFile = if (Test-Path "$Root\.env") { "$Root\.env" } elseif ($Unpacked) { "$Unpacked\.env" } else { "$Root\.env.example" }
$dbUrl = (@(Get-Content $envFile -Encoding UTF8 | Where-Object { $_ -match "^DATABASE_URL=" }) | Select-Object -Last 1) -replace "^DATABASE_URL=", ""
if (-not ($dbUrl -match '^postgresql(\+\w+)?://([^:]+):([^@]+)@([^:/]+):(\d+)/([\w-]+)')) {
    Fail "DATABASE_URL in .env is not understood: $dbUrl"
}
$DbUser = $Matches[2]; $DbPass = $Matches[3]; $DbPort = $Matches[5]; $DbName = $Matches[6]
if (-not (Test-Path "$PgBin\psql.exe")) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        Fail "winget is missing: install 'App Installer' from the Microsoft Store, then run this again"
    }
    $super = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    New-Item -ItemType Directory -Force "$Root\data\runtime" | Out-Null
    Set-Content -Path $SuperFile -Value $super -Encoding ASCII
    Write-Host "Installing PostgreSQL $PgVersion (a few minutes)..."
    & winget.exe install -e --id "PostgreSQL.PostgreSQL.$PgVersion" --source winget --accept-package-agreements --accept-source-agreements `
        --override "--mode unattended --unattendedmodeui none --superpassword $super --serverport $DbPort --disable-components pgAdmin,stackbuilder"
    if (-not (Test-Path "$PgBin\psql.exe")) { Fail "PostgreSQL did not install (see above)" }
}
$svc = Get-Service $PgService -ErrorAction SilentlyContinue
if (-not $svc) { Fail "The Windows service $PgService is missing - PostgreSQL is not installed properly" }
if ($svc.StartType -ne "Automatic") { Set-Service $PgService -StartupType Automatic }
if ($svc.Status -ne "Running") { Start-Service $PgService }
Wait-Postgres
Psql $DbUser $DbPass $DbName "select 1" | Out-Null
if ($LASTEXITCODE -ne 0) {   # first time: the app's database user and database
    if (-not (Test-Path $SuperFile)) {
        Fail "PostgreSQL was installed before, without this script. Create user '$DbUser' (password from DATABASE_URL in .env) and database '$DbName' owned by it, on port $DbPort - or uninstall PostgreSQL and run this again."
    }
    $super = (Get-Content $SuperFile -Raw).Trim()
    if ((Psql "postgres" $super "postgres" "select 1 from pg_roles where rolname = '$DbUser'") -ne "1") {
        Psql "postgres" $super "postgres" "CREATE ROLE $DbUser LOGIN PASSWORD '$DbPass'" | Out-Null
    }
    if ((Psql "postgres" $super "postgres" "select 1 from pg_database where datname = '$DbName'") -ne "1") {
        Psql "postgres" $super "postgres" "CREATE DATABASE $DbName OWNER $DbUser ENCODING 'UTF8' TEMPLATE template0" | Out-Null
    }
    # Only this computer may connect (the database password is in the public repository).
    Psql "postgres" $super "postgres" "ALTER SYSTEM SET listen_addresses = 'localhost'" | Out-Null
    Restart-Service $PgService
    Wait-Postgres
    $answer = Psql $DbUser $DbPass $DbName "select 1"
    if ($LASTEXITCODE -ne 0) { Fail "Could not log in to the database: $answer" }
}
Ok "PostgreSQL $PgVersion on port $DbPort, database $DbName (starts with Windows)"

# --- 4. .env and data -----------------------------------------------------------------------------------------
Say "4/7 Settings (.env) and your data"
$rows = Psql $DbUser $DbPass $DbName "select (select count(*) from public.admins) + (select count(*) from public.feedback)"
$empty = ($LASTEXITCODE -ne 0) -or ($rows -eq "0")   # no tables yet, or no admin accounts and no ratings in them
$replace = $false
if ($Unpacked -and -not $empty) {   # set up before: this computer has data of its own
    Write-Host "This computer's database already has data." -ForegroundColor Yellow
    $answer = Read-Host "Replace it with the data from $(Split-Path $Transfer -Leaf)? (a copy of it is saved first) [y/N]"
    $replace = $answer -match '^\s*(y|yes|ha)\s*$'
}
if ($Unpacked -and ($empty -or $replace)) {
    if ($replace) {   # this computer keeps its own .env (its address settings); only the data comes
        & $VenvPy -X utf8 -m app.backup now
        if ($LASTEXITCODE -ne 0) { Fail "Could not save a copy of the current data first - nothing was replaced" }
    } else {
        if ((Test-Path "$Root\.env") -and (Get-FileHash "$Root\.env").Hash -ne (Get-FileHash "$Unpacked\.env").Hash) {
            Copy-Item "$Root\.env" ("$Root\.env.old-" + (Get-Date -Format "yyyy-MM-dd_HHmm"))
            Write-Host "The .env that was here is kept as .env.old-..."
        }
        Copy-Item "$Unpacked\.env" "$Root\.env" -Force
    }
    $dump = Get-ChildItem "$Unpacked\data\backups" -Filter "feedback-*.sql.gz" | Select-Object -First 1
    if (-not $dump) { Fail "There is no database copy in $Transfer" }
    New-Item -ItemType Directory -Force "$Root\data\backups" | Out-Null
    Copy-Item $dump.FullName "$Root\data\backups\" -Force
    Write-Host "Restoring the database from $($dump.Name)..."
    & $VenvPy -X utf8 -c "import sys; from pathlib import Path; from app import backup; backup.restore(Path(sys.argv[1]))" $dump.FullName
    if ($LASTEXITCODE -ne 0) { Fail "Restoring the database failed (see above) - the data that was here is unchanged" }
    Ok "Database restored: users, ratings, groups, admins and settings are back"
} elseif ($Unpacked) {
    Write-Host "The data that was here is kept (the transfer file's data was not used)."
    if (-not (Test-Path "$Root\.env")) { Copy-Item "$Unpacked\.env" "$Root\.env" }
}
if ($Unpacked) {
    foreach ($d in @("media", "uploads", "runtime\chatfiles")) {
        if (Test-Path "$Unpacked\data\$d") {
            New-Item -ItemType Directory -Force "$Root\data\$d" | Out-Null
            Copy-Item "$Unpacked\data\$d\*" "$Root\data\$d\" -Recurse -Force
        }
    }
    Remove-Item $Unpacked -Recurse -Force
}
if (-not (Test-Path "$Root\.env")) {   # a fresh start without data
    Copy-Item "$Root\.env.example" "$Root\.env"
    Set-EnvValue "SECRET_KEY" ((& $VenvPy -c "import secrets; print(secrets.token_urlsafe(32))") | Out-String).Trim()
    Set-EnvValue "BOT_TOKEN" (Read-Host "Telegram bot token (from @BotFather)").Trim()
    Ok ".env created - keep a copy of it somewhere safe (without its SECRET_KEY nobody can log in)"
}
if ((Get-EnvValue "DEV_MODE") -eq "true") {
    Set-EnvValue "DEV_MODE" "false"
    Write-Host "DEV_MODE switched off in .env (never on a server)"
}
& $VenvPy -X utf8 -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail "Updating the database failed (see above)" }
Ok ".env and database ready"

# --- 5. Public address ----------------------------------------------------------------------------------------
Say "5/7 Public address"
$mode = Get-EnvValue "TUNNEL"
if (-not $mode) {
    Write-Host "How do students reach the survey?"
    Write-Host "  1) tailscale  - free, the address never changes (recommended; a free Tailscale account)"
    Write-Host "  2) quick      - free, nothing to sign up for, but a new address after every restart"
    Write-Host "  3) cloudflare - your own domain (needs a Cloudflare tunnel token)"
    $choice = Read-Host "1, 2 or 3 [1]"
    $mode = switch ($choice) { "2" { "quick" } "3" { "cloudflare" } default { "tailscale" } }
    Set-EnvValue "TUNNEL" $mode
}
if ($mode -eq "cloudflare") {
    if (-not (Get-EnvValue "CLOUDFLARE_TUNNEL_TOKEN")) {
        Set-EnvValue "CLOUDFLARE_TUNNEL_TOKEN" (Read-Host "Cloudflare tunnel token (the long text after --token)").Trim()
    }
    if (-not (Get-EnvValue "WEBAPP_URL")) {
        Set-EnvValue "WEBAPP_URL" (Read-Host "Its address, e.g. https://ovoz.example.uz").Trim().TrimEnd("/")
    }
}
if ($mode -eq "quick" -or $mode -eq "cloudflare") {
    if (-not (Test-Path "$Root\tools\cloudflared.exe")) {
        New-Item -ItemType Directory -Force "$Root\tools" | Out-Null
        Download "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" "$Root\tools\cloudflared.exe"
    }
    Ok "cloudflared (TUNNEL=$mode)"
} elseif ($mode -eq "tailscale") {
    $ts = "$env:ProgramFiles\Tailscale\tailscale.exe"
    if (-not (Test-Path $ts)) {
        Write-Host "Installing Tailscale..."
        & winget.exe install -e --id Tailscale.Tailscale --source winget --accept-package-agreements --accept-source-agreements --silent
        if (-not (Test-Path $ts)) { Fail "Tailscale did not install (see above)" }
        Start-Sleep -Seconds 5
    }
    & $ts status *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Sign in to Tailscale: open the link below (Ctrl+click) and sign in - Google, GitHub or Microsoft."
        & $ts up --unattended --hostname=talaba-ovozi --accept-dns=false
        if ($LASTEXITCODE -ne 0) { Fail "Tailscale sign-in did not finish (see above)" }
    }
    Write-Host "Turning on Funnel (the public address). If a link appears, open it, allow Funnel, and wait here."
    & $ts funnel --bg 8000
    if ($LASTEXITCODE -ne 0) { Fail "Tailscale Funnel did not turn on (see above)" }
    Ok "Tailscale Funnel (TUNNEL=tailscale)"
} else {
    Fail "TUNNEL=$mode in .env - use quick, tailscale or cloudflare"
}

# --- 6. Windows stays awake -----------------------------------------------------------------------------------
Say "6/7 Windows stays awake"
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0
powercfg /hibernate off   # also turns off Fast Startup, which would skip the "when Windows starts" task
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 2>$null
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 2>$null
powercfg /setactive SCHEME_CURRENT
Ok "no sleep, no hibernation, closing a laptop lid does nothing (the screen may still turn off)"

# --- 7. The task that runs the server -------------------------------------------------------------------------
Say "7/7 Start the server with Windows"
$action = New-ScheduledTaskAction -Execute $VenvPy -Argument "-X utf8 -m app.server" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Starting..."
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Path "$Root\data\runtime\webapp_url") { break }
}
& "$PSScriptRoot\server.ps1" status

if ($Transfer -and (Test-Path $Transfer)) {
    $answer = Read-Host "The transfer file holds the bot token and all student data. Delete $Transfer now? [Y/n]"
    if ($answer -ne "n") { Remove-Item $Transfer -Force; Write-Host "Deleted. Delete it from the USB stick too." }
}
Write-Host ""
Write-Host "Done. The server runs now and starts by itself whenever Windows starts - nobody has to sign in." -ForegroundColor Green
Write-Host "Check it once: restart Windows, do not sign in, wait 2 minutes, then use the bot on your phone."
Write-Host "Manage it:  scripts\server.bat status | logs | restart | update"
Done

<#
  Talaba Ovozi - make this Windows computer the server.

  The server is Linux software, so it runs in WSL: Ubuntu inside Windows, made by Microsoft. This script sets
  up Windows and then runs scripts/setup.sh inside Ubuntu (the same setup as on a Linux computer).

  Put this file and the transfer file (talaba-transfer-....tar.gz) in Downloads, open PowerShell as
  Administrator (Start > type PowerShell > right-click > Run as administrator) and run:

    cd $HOME\Downloads
    powershell -ExecutionPolicy Bypass -File .\setup-windows.ps1 -Transfer .\talaba-transfer-2026-10-07_0912.tar.gz

  Safe to run again. If it asks you to restart Windows, restart and run the same command again.

  What it does:
    1. Installs WSL with Ubuntu 24.04 (you create a Linux user name and password once).
    2. Turns on systemd in Ubuntu - it starts the database, web server, bot and tunnel.
    3. Downloads the project into Ubuntu (~/talaba-ovozi) and runs scripts/setup.sh there with your data.
    4. Keeps Windows awake: no sleep, no hibernation, closing a laptop lid does nothing.
    5. Adds the task "Talaba Ovozi server": it starts Ubuntu - and so the whole server - when Windows starts,
       before anyone signs in, and starts it again within 30 seconds if it ever stops.
#>
param(
    [string]$Transfer = "",
    [string]$Repo = "https://github.com/qomusiy/talaba-ovozi.git",
    [string]$Distro = "Ubuntu-24.04"
)
$ErrorActionPreference = "Continue"   # native programs report through exit codes, checked below
$env:WSL_UTF8 = "1"                    # wsl.exe prints UTF-16 otherwise
$TaskName = "Talaba Ovozi server"
$Project = "talaba-ovozi"              # the folder in the Linux home directory

function Say([string]$text) { Write-Host ""; Write-Host "-- $text" -ForegroundColor Cyan }
function Fail([string]$text) { Write-Host ""; Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }
function Get-Distros {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return @() }
    return @(& wsl.exe -l -q 2>$null | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
}

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail "Open PowerShell as Administrator (right-click > Run as administrator) and run this again."
}
if ($Transfer) {
    if (-not (Test-Path -LiteralPath $Transfer)) { Fail "No such file: $Transfer" }
    $Transfer = (Resolve-Path -LiteralPath $Transfer).Path
    if ($Transfer -notmatch '^[A-Za-z]:\\') { Fail "Put the transfer file on a drive with a letter (e.g. Downloads): $Transfer" }
}

# ---------------------------------------------------------------------------------------------------------------
Say "1/5 WSL and $Distro"
if ((Get-Distros) -notcontains $Distro) {
    Write-Host "Installing $Distro. Ubuntu will ask you to create a Linux user name and password:"
    Write-Host "remember the password - the setup asks for it. When you then see a line like"
    Write-Host "    name@computer:~`$"
    Write-Host "type  exit  and press Enter."
    Write-Host "(If it says virtualization is off: turn on Intel VT-x / AMD SVM in the BIOS, then run this again.)"
    & wsl.exe --install -d $Distro
    if ((Get-Distros) -notcontains $Distro) {
        Write-Host ""
        Write-Host "Restart Windows. If an Ubuntu window opens after the restart, create the user there, type exit,"
        Write-Host "then run this script again (same command)." -ForegroundColor Yellow
        exit 0
    }
}
& wsl.exe --update 2>$null | Out-Null   # the newest WSL can start before anyone signs in
$version = @(& wsl.exe -l -v) | ForEach-Object { $_ -replace "`0", "" } |
    Where-Object { $_ -match ("\s" + [regex]::Escape($Distro) + "\s") } | Select-Object -First 1
if ($version -match "\s1\s*$") { & wsl.exe --set-version $Distro 2 }
$linuxUser = ((& wsl.exe -d $Distro --exec whoami) | Out-String).Trim()
if (-not $linuxUser -or $linuxUser -eq "root") {
    Fail "Ubuntu has no user yet: open Ubuntu from the Start menu, create a user, type exit, and run this again."
}
Write-Host "OK: $Distro, Linux user $linuxUser"

# ---------------------------------------------------------------------------------------------------------------
Say "2/5 systemd in Ubuntu"
$conf = (& wsl.exe -d $Distro -u root --exec cat /etc/wsl.conf 2>$null) | Out-String
if ($conf -notmatch "systemd\s*=\s*true") {
    & wsl.exe -d $Distro -u root --exec sh -c "printf '\n[boot]\nsystemd=true\n' >> /etc/wsl.conf"
    & wsl.exe --terminate $Distro | Out-Null
    Write-Host "Turned on (Ubuntu restarted)"
} else {
    Write-Host "OK"
}

# ---------------------------------------------------------------------------------------------------------------
Say "3/5 The project in Ubuntu (~/$Project) and scripts/setup.sh"
Write-Host "When asked for a password here, it is your Linux password (Ubuntu's, not Windows')."
& wsl.exe -d $Distro --cd "~" --exec bash -lc "command -v git >/dev/null || { sudo apt-get update -q && sudo apt-get install -y git; }; if [ -d $Project/.git ]; then git -C $Project pull --ff-only; else git clone $Repo $Project; fi"
if ($LASTEXITCODE -ne 0) { Fail "Could not download the project from $Repo" }
$bundle = ""
if ($Transfer) {
    $name = Split-Path -Leaf $Transfer
    $linuxPath = "/mnt/" + $Transfer.Substring(0, 1).ToLower() + $Transfer.Substring(2).Replace("\", "/")
    & wsl.exe -d $Distro --cd "~" --exec bash -lc "cp '$linuxPath' ~/$name && chmod 600 ~/$name"
    if ($LASTEXITCODE -ne 0) { Fail "Could not copy $Transfer into Ubuntu" }
    $bundle = "~/$name"
}
for ($try = 1; $try -le 3; $try++) {
    & wsl.exe -d $Distro --cd "~" --exec bash -lc "cd $Project && scripts/setup.sh $bundle"
    $code = $LASTEXITCODE
    if ($code -ne 3) { break }   # 3: setup.sh wants Ubuntu restarted (Docker), then run again
    Write-Host "Restarting Ubuntu once (Docker), then continuing..." -ForegroundColor Yellow
    & wsl.exe --terminate $Distro | Out-Null
}
if ($code -ne 0) { Fail "scripts/setup.sh did not finish - read the message above, fix it, and run this script again." }

# ---------------------------------------------------------------------------------------------------------------
Say "4/5 Windows stays awake"
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0
powercfg /hibernate off   # also turns off Fast Startup, which would skip the "when Windows starts" task
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 2>$null
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0 2>$null
powercfg /setactive SCHEME_CURRENT
Write-Host "OK: no sleep, no hibernation, the lid does nothing (the screen may still turn off - that is fine)"

# ---------------------------------------------------------------------------------------------------------------
Say "5/5 Start the server when Windows starts"
# Ubuntu runs while a program uses it: this loop keeps one running, and starts it again if it stops.
$keepalive = 'while ($true) { wsl.exe -d ' + $Distro + ' --exec sleep infinity; Start-Sleep -Seconds 30 }'
$action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command `"$keepalive`""
$user = "$env:USERDOMAIN\$env:USERNAME"
$triggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn -User $user))
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Write-Host "Windows needs your Windows password to start the server before anyone signs in"
Write-Host "(for a Microsoft account: that account's password, not the PIN). Windows keeps it, this script does not."
$cred = Get-Credential -UserName $user -Message "Windows password of $user"
$atBoot = $false
if ($cred) {
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings `
            -User $user -Password $cred.GetNetworkCredential().Password -Force -ErrorAction Stop | Out-Null
        $atBoot = $true
    } catch {
        Write-Host "Windows did not accept that password: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}
if (-not $atBoot) {
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings `
        -Principal $principal -Force | Out-Null
}
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 15
& wsl.exe -d $Distro --cd "~" --exec bash -lc "cd $Project && scripts/server.sh status"

Write-Host ""
if ($atBoot) {
    Write-Host "Done. The server starts by itself whenever Windows starts - nobody needs to sign in." -ForegroundColor Green
    Write-Host "Check it once: restart Windows, do not sign in, wait 2 minutes, then use the bot on your phone."
} else {
    Write-Host "Done, but the server starts only when $user signs in to Windows." -ForegroundColor Yellow
    Write-Host "Run this script again with the right Windows password, or turn on automatic sign-in."
    Write-Host "Lock the computer (Windows+L) instead of signing out - signing out stops the server."
}
Write-Host "Dashboard on this computer: http://127.0.0.1:8000/admin"
Write-Host "Server commands: open Ubuntu from the Start menu, then:  cd ~/$Project; scripts/server.sh status"

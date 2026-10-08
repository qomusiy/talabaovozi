@echo off
rem Manage the Talaba Ovozi server on Windows: status, logs, restart, stop, start, update, backup - scripts\windows\server.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\server.ps1" %*

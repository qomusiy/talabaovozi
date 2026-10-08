@echo off
rem Set up this Windows computer as the Talaba Ovozi server (or update it): scripts\windows\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\setup.ps1" %*

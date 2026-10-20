@echo off
setlocal
cd /d "%~dp0"
"portable\windows\python\python.exe" launch.py
if errorlevel 1 pause

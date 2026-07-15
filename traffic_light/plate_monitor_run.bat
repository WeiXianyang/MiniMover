@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"
start "" pythonw "%~dp0plate_monitor_window.py"

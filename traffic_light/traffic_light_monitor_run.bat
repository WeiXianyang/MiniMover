@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0..;%PYTHONPATH%"
start "" pythonw "%~dp0traffic_light_monitor_window.py"

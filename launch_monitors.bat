@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   MiniMover Monitor Launcher
echo   Plate + TrafficLight + Fire
echo ==========================================
echo.

echo [1/3] Launching Plate Monitor...
start "" pythonw "%~dp0traffic_light\plate_monitor_window.py"

echo [2/3] Launching Traffic Light Monitor...
start "" pythonw "%~dp0traffic_light\traffic_light_monitor_window.py"

echo [3/3] Launching Fire Monitor...
start "" pythonw "%~dp0fire_smoke_detection\fire_monitor_test_window.py"

echo.
echo All 3 windows launched. Check your desktop.
echo You may close this window now.
pause >nul

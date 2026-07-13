@echo off
setlocal
cd /d "E:\MiniMover"

echo ========================================
echo   MiniMover Multi-Car Coordinator
echo   Restart mode
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  pause
  exit /b 1
)

if not exist "multi_car_coordinator.py" (
  echo [ERROR] Project file was not found: E:\MiniMover\multi_car_coordinator.py
  pause
  exit /b 1
)

echo Stopping coordinator on port 8888...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8888" ^| findstr "LISTENING"') do taskkill /PID %%P /T /F >nul 2>nul
timeout /t 2 /nobreak >nul

echo Starting coordinator...
start "MiniMover Coordinator" /min python "E:\MiniMover\multi_car_coordinator.py"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(15); do { Start-Sleep -Milliseconds 500; $ready=Get-NetTCPConnection -LocalPort 8888 -State Listen -ErrorAction SilentlyContinue } while (-not $ready -and (Get-Date) -lt $deadline); if (-not $ready) { exit 1 }"
if errorlevel 1 (
  echo [ERROR] Coordinator failed to start after 15 seconds.
  echo Check E:\MiniMover\tmp\multi_car_coordinator.err.log
  pause
  exit /b 1
)

echo Coordinator restarted successfully.
start "" "http://localhost:8888/dashboard"
exit /b 0
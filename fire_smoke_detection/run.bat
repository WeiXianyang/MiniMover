@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  exit /b 1
)

if not exist "model\best.pt" (
  echo [ERROR] Missing model\best.pt
  exit /b 1
)

if "%~1"=="" (
  python detector.py --source 0 --view-img
) else (
  python detector.py %*
)
exit /b %errorlevel%

@echo off
setlocal
set "ROOT=%~dp0"
set "DEMO_DIR=%ROOT%demo_showcase"
set "PLAYER=%DEMO_DIR%\player.py"
set "COMBINED="
for /f "delims=" %%F in ('powershell -NoProfile -Command "Get-ChildItem -LiteralPath '%DEMO_DIR%\videos' -Filter '*.mp4' | Where-Object { $_.Name -notmatch 'license|traffic|fire' } | Select-Object -First 1 -ExpandProperty FullName"') do set "COMBINED=%%F"

if /I "%~1"=="--fallback" goto fallback

where python >nul 2>&1
if errorlevel 1 goto check_failed
python -c "import cv2" >nul 2>&1
if errorlevel 1 goto check_failed

python "%PLAYER%" "videos\license_plate_demo.mp4" --check >nul
if errorlevel 1 goto check_failed
python "%PLAYER%" "videos\traffic_light_demo.mp4" --check >nul
if errorlevel 1 goto check_failed
python "%PLAYER%" "videos\fire_smoke_demo.mp4" --check >nul
if errorlevel 1 goto check_failed
if not defined COMBINED goto check_failed
python "%PLAYER%" "%COMBINED%" --check >nul
if errorlevel 1 goto check_failed

if /I "%~1"=="--check" (
    echo [PASS] Python, OpenCV and all demo videos are ready.
    exit /b 0
)

echo ============================================================
echo   MiniMover - Three Recognition Modules Defense Demo
echo ============================================================
echo   Starting three independent windows...
echo   Press Q or Esc in any window to close it.
echo   Fallback video: %COMBINED%
echo ============================================================

start "Demo 1 - License Plate" /D "%DEMO_DIR%" python "player.py" "videos\license_plate_demo.mp4" --title "1 - License Plate Recognition" --x 20 --y 20
start "Demo 2 - Traffic Light" /D "%DEMO_DIR%" python "player.py" "videos\traffic_light_demo.mp4" --title "2 - Traffic Light Recognition" --x 680 --y 20
start "Demo 3 - Fire Smoke" /D "%DEMO_DIR%" python "player.py" "videos\fire_smoke_demo.mp4" --title "3 - Fire and Smoke Recognition" --x 350 --y 390

timeout /t 2 /nobreak >nul
exit /b 0

:check_failed
echo [ERROR] Demo self-check failed.
echo Required: Python 3 with OpenCV, plus all files under demo_showcase\videos.
echo Fallback video: %COMBINED%
if /I "%~1"=="--check" exit /b 1

:fallback
if not defined COMBINED (
    echo [ERROR] Combined fallback video was not found.
    exit /b 1
)
start "" "%COMBINED%"
exit /b 0

@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   License Plate Detector
echo ========================================
echo.
echo Usage:
echo   plate_run.bat                 - use the local camera
echo   plate_run.bat car_A           - use the direct low-latency car_A stream
echo   plate_run.bat car_B           - use the direct low-latency car_B stream
echo   plate_run.bat proxy:car_A     - use the car_A coordination-center proxy
if "%~1"=="" (
    python plate_detector.py 0
) else (
    python plate_detector.py %*
)

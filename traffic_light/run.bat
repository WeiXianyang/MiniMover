@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   Traffic Light Detector
echo ========================================
echo.
echo Usage:
echo   run.bat                 - use the local camera
echo   run.bat car_A           - use the direct low-latency car_A stream
echo   run.bat car_B           - use the direct low-latency car_B stream
echo   run.bat proxy:car_A     - use the car_A coordination-center proxy
echo   run.bat video.mp4       - use a local video file or custom URL
if "%~1"=="" (
    python detector.py 0
) else (
    python detector.py %*
)

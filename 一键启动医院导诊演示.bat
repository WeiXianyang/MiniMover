@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   MiniMover 医院导诊现场演示
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 未找到 Python 3，请先安装并加入 PATH。
  pause
  exit /b 1
)
python -c "import paramiko" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 缺少 paramiko。请执行: python -m pip install paramiko
  pause
  exit /b 1
)
if not exist "%~dp0scripts\start_hospital_guide_demo.py" (
  echo [ERROR] 启动器文件不存在。
  pause
  exit /b 1
)

python "%~dp0scripts\start_hospital_guide_demo.py" %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERROR] 医院导诊演示启动失败，退出码 %RC%。
  pause
  exit /b %RC%
)
echo [OK] 医院导诊演示已启动。
start "" "http://192.168.202.171:5000/hospital-guide"
exit /b 0

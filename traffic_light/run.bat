@echo off
cd /d "E:\MiniMover\traffic_light"
echo ========================================
echo   Traffic Light Detector - 红绿灯识别
echo ========================================
echo.
echo 用法:
echo   run.bat camera      - 使用摄像头实时检测
echo   run.bat image.jpg   - 检测单张图片
echo   run.bat test        - 运行测试集
echo   run.bat video.mp4   - 检测视频文件
echo.
if "%1"=="" (
    echo 正在用摄像头检测...
    python detector.py 0
) else if "%1"=="test" (
    echo 运行测试...
    python detector.py test_images/red_light.jpg
    python detector.py test_images/green_light.jpg
    python detector.py test_images/yellow_light.jpg
    echo 查看结果: test_images/*_result.jpg
) else (
    python detector.py %1
)

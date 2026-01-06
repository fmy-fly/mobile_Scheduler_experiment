@echo off
setlocal enabledelayedexpansion

:: ----------------------------------------------------
:: 1. 解决乱码问题：切换控制台代码页为 UTF-8
:: ----------------------------------------------------
chcp 65001 > nul

:: ----------------------------------------------------
:: 2. 解决找不到文件问题：强制进入脚本所在的目录
:: 即使你在 D盘 调用 C盘 的脚本，也会自动跳过去
:: ----------------------------------------------------
cd /d "%~dp0"

echo ==========================================
echo       Android Trace 脚本一键部署工具
echo ==========================================

:: 定义手机上的中转目录
set REMOTE_DIR=/sdcard/bpftrace_work

:: 检查文件是否存在
if not exist "capture.bt" (
    echo [错误] 找不到 capture.bt
    echo 请确保脚本和 capture.bt 在同一个文件夹内！
    pause
    exit /b
)
if not exist "live_analyzer.py" (
    echo [错误] 找不到 live_analyzer.py
    echo 请确保脚本和 live_analyzer.py 在同一个文件夹内！
    pause
    exit /b
)

echo [1/3] 检查 ADB 连接...
adb devices | findstr "device$" > nul
if %errorlevel% neq 0 (
    echo [错误] 未找到手机，请检查 USB 连接或驱动。
    pause
    exit /b
)

echo [2/3] 清理并创建中转目录: %REMOTE_DIR%
:: 先尝试删除旧的确保干净（可选），再创建
adb shell "rm -rf %REMOTE_DIR% && mkdir -p %REMOTE_DIR%"

echo [3/3] 开始传输文件...
adb push capture.bt %REMOTE_DIR%/
adb push live_analyzer_with_freq.py %REMOTE_DIR%/
adb push freq_config.py %REMOTE_DIR%/
adb push run_with_freq %REMOTE_DIR%/

echo.
echo ==========================================
echo [成功] 文件已上传到手机 /sdcard/bpftrace_work
echo ==========================================
echo.
echo 接下来，请在 Termux (Proot Ubuntu) 中运行下面这行命令
echo (它会自动把文件拿进来并开始运行，省去手动 cp 的麻烦)：
echo.
echo ------------------------------------------------------------------------
echo cp /sdcard/bpftrace_work/* . && ls -l && echo "Ready to run!"
echo ------------------------------------------------------------------------
echo.

pause
@echo off
setlocal enabledelayedexpansion

chcp 65001 > nul
cd /d "%~dp0"

echo ==========================================
echo   Android Trace Script Deploy Tool
echo ==========================================
echo.

set REMOTE_DIR=/sdcard/bpftrace_work

if not exist "capture.bt" (
    echo [ERROR] capture.bt not found
    echo Please ensure capture.bt is in the same folder
    pause
    exit /b
)

if not exist "live_analyzer_with_freq.py" (
    echo [ERROR] live_analyzer_with_freq.py not found
    echo Please ensure live_analyzer_with_freq.py is in the same folder
    pause
    exit /b
)

if not exist "freq_config.py" (
    echo [ERROR] freq_config.py not found
    echo Please ensure freq_config.py is in the same folder
    pause
    exit /b
)

echo [1/3] Checking ADB connection...
adb devices | findstr "device$" > nul
if %errorlevel% neq 0 (
    echo [ERROR] No device found, please check USB connection
    pause
    exit /b
)

echo [2/3] Cleaning and creating directory: %REMOTE_DIR%
adb shell "rm -rf %REMOTE_DIR% 2>nul"
adb shell "mkdir -p %REMOTE_DIR%"

echo [3/3] Transferring files...
adb push capture.bt %REMOTE_DIR%/
adb push live_analyzer_with_freq.py %REMOTE_DIR%/
adb push freq_config.py %REMOTE_DIR%/
if exist "run_with_freq" (
    adb push run_with_freq %REMOTE_DIR%/
)

echo.
echo ==========================================
echo [SUCCESS] Files uploaded to /sdcard/bpftrace_work
echo ==========================================
echo.
echo Next, run this command in Termux (Proot Ubuntu):
echo.
echo ------------------------------------------------------------------------
echo cp /sdcard/bpftrace_work/* . ^&^& ls -l ^&^& echo Ready to run!
echo ------------------------------------------------------------------------
echo.

pause

@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ============================================================
rem  摆线针轮减速器 · 原理演示 一键环境配置 + 运行脚本
rem  每次运行都会检查/补齐依赖 (numpy matplotlib PyQt5 ezdxf cadquery)
rem  cadquery 体积较大，首次安装请耐心等待
rem ============================================================

cd /d "%~dp0"

echo.
echo ============================================
echo   Cycloidal Reducer - Principle Demo
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ from:
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "cycloid_anim.py" (
    echo [ERROR] cycloid_anim.py not found.
    pause
    exit /b 1
)

echo [INFO] Checking dependencies...
python -c "import numpy, matplotlib, PyQt5" >nul 2>nul
if %errorlevel%==0 (
    echo [INFO] Dependencies OK. Launching...
    goto :run
)

if exist ".env_done" del /q ".env_done"

echo [INFO] Installing dependencies (cadquery ~200MB, please wait)...
echo.

set "PIP_OK=0"
python -m pip install --upgrade pip >nul 2>nul
python -m pip install -r requirements.txt >nul 2>nul
if %errorlevel%==0 set "PIP_OK=1"
if "!PIP_OK!"=="0" (
    echo [FALLBACK] Trying py -m pip ...
    py -m pip install --upgrade pip >nul 2>nul
    py -m pip install -r requirements.txt >nul 2>nul
    if %errorlevel%==0 set "PIP_OK=1"
)
if "!PIP_OK!"=="0" (
    echo [FALLBACK] Trying pip ...
    pip install --upgrade pip >nul 2>nul
    pip install -r requirements.txt >nul 2>nul
    if %errorlevel%==0 set "PIP_OK=1"
)

if "!PIP_OK!"=="0" (
    echo.
    echo [ERROR] pip failed. Try manually:
    echo   pip install numpy matplotlib PyQt5 ezdxf cadquery
    echo.
    echo If pip also fails, reinstall Python:
    echo   https://www.python.org/downloads/
    pause
    exit /b 1
)

echo. > ".env_done"
echo [INFO] Dependencies installed.

:run
echo.
echo [INFO] Launching program...
python cycloid_anim.py
echo.
echo [INFO] Program exited.
pause

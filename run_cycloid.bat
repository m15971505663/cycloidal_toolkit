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
echo   摆线针轮减速器 · 原理演示
echo ============================================
echo.

rem ---- 检查 Python 是否可用 ----
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8 及以上版本。
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

rem ---- 检查 cycloid_anim.py 是否存在 ----
if not exist "cycloid_anim.py" (
    echo [错误] 找不到 cycloid_anim.py，请确认脚本与程序在同一目录。
    echo.
    pause
    exit /b 1
)

rem ---- 安装/补齐依赖（已装则秒过；cadquery 首次下载约 200MB，请耐心等待）----
echo [信息] 检查依赖 (已装好的会自动跳过)...
python -m pip install --upgrade pip >nul 2>nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败。可能原因：
    echo   - 网络无法访问 PyPI，请检查网络或配置镜像源，例如：
    echo     python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
    pause
    exit /b 1
)

echo.
echo [信息] 正在启动程序...
python cycloid_anim.py

echo.
echo [信息] 程序已退出。
pause
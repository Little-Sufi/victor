@echo off
title VICTOR AI - Autonomous Agent
cd /d "%~dp0"

echo ========================================================
echo   Launching VICTOR AI...
echo ========================================================
echo.

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe main.py
) else (
    python main.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] VICTOR exited with error code %ERRORLEVEL%.
    pause
)

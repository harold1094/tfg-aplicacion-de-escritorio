@echo off
cd /d "%~dp0"
if exist "..\run\python312\python.exe" (
    "..\run\python312\python.exe" app\main.py
) else (
    python -m app.main
)
pause

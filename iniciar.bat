@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo No se encontro .venv\Scripts\pythonw.exe
    echo Crea el entorno e instala dependencias antes de iniciar la aplicacion.
    exit /b 1
)

start "" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" -m app.main

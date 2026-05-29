@echo off
cd /d "%~dp0"

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "BOOTSTRAP_PYTHON="

if exist "%VENV_PYTHON%" goto ensure_deps
if exist "..\run\python312\python.exe" set "BOOTSTRAP_PYTHON=..\run\python312\python.exe"
if not defined BOOTSTRAP_PYTHON (
    py -3.11 -c "import sys" >nul 2>&1 && set "BOOTSTRAP_PYTHON=py -3.11"
)
if not defined BOOTSTRAP_PYTHON (
    py -3.12 -c "import sys" >nul 2>&1 && set "BOOTSTRAP_PYTHON=py -3.12"
)
if not defined BOOTSTRAP_PYTHON set "BOOTSTRAP_PYTHON=py -3.14"

echo Creando entorno virtual...
call %BOOTSTRAP_PYTHON% -m venv .venv
if errorlevel 1 goto fail

:ensure_deps
echo Verificando dependencias Python...
call "%VENV_PYTHON%" -c "import PySide6, PIL, pytesseract, pypdf, supabase, openpyxl, reportlab, dotenv" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    call "%VENV_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto fail
)

echo Verificando motor OCR...
call "%VENV_PYTHON%" -c "from app.services.ocr_service import OcrService; ok, _ = OcrService.ensure_image_ocr_installed(); raise SystemExit(0 if ok else 1)" >nul 2>&1
if errorlevel 1 (
    echo No se pudo preparar OCR automaticamente en este arranque.
    echo La aplicacion volvera a intentarlo cuando se use la importacion por imagen.
)

call "%VENV_PYTHON%" -m app.main
goto end

:fail
echo No se pudo preparar el entorno o arrancar la aplicacion.

:end
pause

@echo off
setlocal
cd /d "%~dp0"
title PDF Analyzer 0.26.0-m4a - Portable r2

set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py"
if not defined PY_CMD where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    echo [EROARE] Python nu este instalat sau nu este disponibil in PATH.
    echo Instaleaza Python 64-bit si bifeaza optiunea Add Python to PATH.
    pause
    exit /b 1
)

%PY_CMD% -c "import struct,sys; sys.exit(0 if struct.calcsize('P')*8 == 64 and sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [EROARE] Este necesar Python 64-bit, versiunea 3.10 sau mai noua.
    pause
    exit /b 1
)

set "VENV_BASE=%LOCALAPPDATA%\PDFAnalyzer"
if not defined LOCALAPPDATA set "VENV_BASE=%TEMP%\PDFAnalyzer"
set "VENV_DIR=%VENV_BASE%\venv-0.26.0-m4a"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_MARKER=%VENV_DIR%\.pdf-analyzer-0.26.0-m4a"
set "WHEEL_CACHE=%VENV_BASE%\wheels-0.26.0-m4a"

set "NEED_SETUP=0"
if not exist "%VENV_PYTHON%" set "NEED_SETUP=1"
if not exist "%VENV_MARKER%" set "NEED_SETUP=1"

if "%NEED_SETUP%"=="1" (
    echo Prima pornire: se pregateste mediul local offline...
    echo Mediul Python: "%VENV_DIR%"
    if not exist "wheels" goto :package_error
    if not exist "requirements-lock.txt" goto :package_error
    if not exist "%VENV_BASE%" mkdir "%VENV_BASE%"
    if not exist "%WHEEL_CACHE%" mkdir "%WHEEL_CACHE%"
    echo Se copiaza librariile intr-o cale Windows scurta...
    robocopy "%~dp0wheels" "%WHEEL_CACHE%" *.whl /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
    if errorlevel 8 goto :setup_error
    copy /Y "%~dp0requirements-lock.txt" "%WHEEL_CACHE%\requirements-lock.txt" >nul
    if errorlevel 1 goto :setup_error
)

if not exist "%VENV_PYTHON%" (
    %PY_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :setup_error
)

if "%NEED_SETUP%"=="1" (
    "%VENV_PYTHON%" -m pip install --disable-pip-version-check --no-index --find-links "%WHEEL_CACHE%" -r "%WHEEL_CACHE%\requirements-lock.txt"
    if errorlevel 1 goto :setup_error
    type nul > "%VENV_MARKER%"
)

"%VENV_PYTHON%" -c "import fitz, PySide6, xlsxwriter"
if errorlevel 1 goto :setup_error

"%VENV_PYTHON%" app.py %*
if errorlevel 1 (
    echo.
    echo Aplicatia s-a inchis cu o eroare.
    pause
)
exit /b 0

:setup_error
echo.
echo [EROARE] Mediul Python nu a putut fi pregatit.
echo Sterge folderul "%VENV_DIR%" si ruleaza din nou acest BAT.
pause
exit /b 1

:package_error
echo.
echo [EROARE] Pachetul este incomplet: lipsesc wheels sau requirements-lock.txt.
echo Extrage din nou intreaga arhiva ZIP intr-un folder local.
pause
exit /b 1

@echo off
setlocal
cd /d "%~dp0"
title Construire EXE - PDF Analyzer 0.26.0-m4a

rem ---------------------------------------------------------------
rem Construieste dist\PDF Analyzer\PDF Analyzer.exe (PyInstaller, onedir).
rem Functioneaza offline daca exista folderele wheels si build\wheels;
rem altfel descarca pachetele de pe PyPI.
rem ---------------------------------------------------------------

set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py"
if not defined PY_CMD where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    echo [EROARE] Python nu este instalat sau nu este disponibil in PATH.
    pause
    exit /b 1
)

%PY_CMD% -c "import struct,sys; sys.exit(0 if struct.calcsize('P')*8 == 64 and sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [EROARE] Este necesar Python 64-bit, versiunea 3.10 sau mai noua.
    pause
    exit /b 1
)

if not exist "app.py" goto :package_error
if not exist "build\pdf_analyzer.spec" goto :package_error
if not exist "requirements-lock.txt" goto :package_error

set "VENV_BASE=%LOCALAPPDATA%\PDFAnalyzer"
if not defined LOCALAPPDATA set "VENV_BASE=%TEMP%\PDFAnalyzer"
set "BUILD_VENV=%VENV_BASE%\build-venv-0.26.0-m4a"
set "BUILD_PYTHON=%BUILD_VENV%\Scripts\python.exe"
set "BUILD_MARKER=%BUILD_VENV%\.pdf-analyzer-build-0.26.0-m4a"
set "BUILD_WHEELS=%VENV_BASE%\build-wheels-0.26.0-m4a"
set "WORK_DIR=%VENV_BASE%\build-work-0.26.0-m4a"
set "DIST_DIR=%~dp0dist"
set "APP_DIR=%~dp0dist\PDF Analyzer"
set "ZIP_FILE=%~dp0dist\PDF-Analyzer-0.26.0-m4a-win64.zip"

if not exist "runtime\Tesseract-OCR\tesseract.exe" (
    echo [ATENTIE] runtime\Tesseract-OCR lipseste. EXE-ul va fi construit fara OCR inclus;
    echo           OCR va functiona doar daca Tesseract este instalat separat pe calculator.
    echo.
)

if exist "%BUILD_MARKER%" goto :build

echo Prima construire: se pregateste mediul de build...
if not exist "%VENV_BASE%" mkdir "%VENV_BASE%"
if not exist "%BUILD_PYTHON%" %PY_CMD% -m venv "%BUILD_VENV%"
if not exist "%BUILD_PYTHON%" goto :setup_error

if not exist "wheels\*.whl" goto :online_install
if not exist "build\wheels\*.whl" goto :online_install

echo Instalare offline din wheels si build\wheels...
if not exist "%BUILD_WHEELS%" mkdir "%BUILD_WHEELS%"
robocopy "%~dp0wheels" "%BUILD_WHEELS%" *.whl /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto :setup_error
robocopy "%~dp0build\wheels" "%BUILD_WHEELS%" *.whl /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto :setup_error
"%BUILD_PYTHON%" -m pip install --disable-pip-version-check --no-index --find-links "%BUILD_WHEELS%" -r "requirements-lock.txt" -r "build\requirements-build.txt"
if errorlevel 1 goto :setup_error
goto :install_done

:online_install
echo Instalare online de pe PyPI...
"%BUILD_PYTHON%" -m pip install --disable-pip-version-check -r "requirements-lock.txt" -r "build\requirements-build.txt"
if errorlevel 1 goto :setup_error

:install_done
type nul > "%BUILD_MARKER%"

:build
echo.
echo Se construieste EXE-ul. Dureaza cateva minute...
if exist "%APP_DIR%" rmdir /s /q "%APP_DIR%"
"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --distpath "%DIST_DIR%" --workpath "%WORK_DIR%" "build\pdf_analyzer.spec"
if errorlevel 1 goto :build_error
if not exist "%APP_DIR%\PDF Analyzer.exe" goto :build_error

if exist "GHID RAPID PDF ANALYZER.pdf" copy /Y "GHID RAPID PDF ANALYZER.pdf" "%APP_DIR%\" >nul
if exist "INSTRUCTIUNI EXE.txt" copy /Y "INSTRUCTIUNI EXE.txt" "%APP_DIR%\" >nul

echo.
echo Se creeaza arhiva ZIP pentru distribuire...
if exist "%ZIP_FILE%" del /q "%ZIP_FILE%"
tar -a -c -f "%ZIP_FILE%" -C "%DIST_DIR%" "PDF Analyzer"
if errorlevel 1 echo [ATENTIE] Arhiva ZIP nu a putut fi creata. Folderul EXE este totusi gata.

echo.
echo ===============================================================
echo  GATA: "%APP_DIR%\PDF Analyzer.exe"
echo  Copiaza tot folderul "PDF Analyzer", nu doar EXE-ul.
echo ===============================================================
start "" explorer "%DIST_DIR%"
pause
exit /b 0

:setup_error
echo.
echo [EROARE] Mediul de build nu a putut fi pregatit.
echo Sterge folderul "%BUILD_VENV%" si ruleaza din nou acest BAT.
pause
exit /b 1

:build_error
echo.
echo [EROARE] PyInstaller nu a putut construi EXE-ul. Vezi mesajele de mai sus.
pause
exit /b 1

:package_error
echo.
echo [EROARE] Lipsesc fisiere: app.py, requirements-lock.txt sau build\pdf_analyzer.spec.
pause
exit /b 1

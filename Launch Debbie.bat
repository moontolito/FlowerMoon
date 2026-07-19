@echo off
setlocal

set "DEBBIE_ROOT=%~dp0"
set "DEBBIE_PYTHON=%DEBBIE_ROOT%.venv313\Scripts\python.exe"

if not exist "%DEBBIE_PYTHON%" (
    echo Debbie could not find the repository-local Python environment.
    echo Expected: "%DEBBIE_PYTHON%"
    echo Create .venv313 and install the project before launching Debbie.
    pause
    exit /b 1
)

pushd "%DEBBIE_ROOT%" || (
    echo Debbie could not open its repository directory.
    pause
    exit /b 1
)

"%DEBBIE_PYTHON%" -m debbie.desktop %*
set "DEBBIE_EXIT_CODE=%ERRORLEVEL%"
popd

if not "%DEBBIE_EXIT_CODE%"=="0" (
    echo.
    echo Debbie exited with error code %DEBBIE_EXIT_CODE%.
    pause
)

exit /b %DEBBIE_EXIT_CODE%

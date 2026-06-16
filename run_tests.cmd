@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: run_tests.cmd                                      [DEV]
:: Testy jednostkowe i integracyjne (pytest) dla pasywnyportfel.
:: Wymaga: pip install -r requirements-dev.txt
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

echo.
echo ================================================================
echo  pasywnyportfel — testy jednostkowe (pytest)
echo ================================================================
echo  Python: %PY%
echo ================================================================
echo.

"%PY%" -m pytest --version >nul 2>nul
if errorlevel 1 (
    echo BRAK pytest. Instaluje z requirements-dev.txt...
    "%PY%" -m pip install -r requirements-dev.txt
)

echo.
"%PY%" -m pytest %*

echo.
if %ERRORLEVEL%==0 (
    echo WYNIK: wszystkie testy przeszly.
) else (
    echo WYNIK: sa bledy — zobacz output powyzej.
)
echo.
pause

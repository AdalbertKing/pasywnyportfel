@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: test_after_start.cmd                                [USER]
:: Kontrola stanu pakietu po 1-start_setup.cmd.
:: Cala logika jest w app\bin\health_check.py (czysty Python),
:: zeby uniknac problemow CMD z wieloliniowymi python -c.
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

"%PY%" "app\bin\health_check.py"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo Kontrola zakonczona bez bledow krytycznych.) else (echo Liczba bledow FAIL: %RC%. Zobacz powyzej.)
pause
exit /b %RC%

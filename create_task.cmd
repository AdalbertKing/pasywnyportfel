@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: create_task.cmd                                      [USER]
:: ============================================================
:: Tworzy nowy task z szablonu comparison_2005 i automatycznie
:: waliduje konfiguracje. Po utworzeniu edytuj pliki w nowym
:: folderze i uruchom run_task.cmd <nowy_task>.
::
:: Uzycie:
::   create_task.cmd moja_analiza
::   create_task.cmd bfly_short_test --force
::
:: Dozwolone znaki w nazwie: litery ASCII, cyfry, _ i -
:: ============================================================

if "%~1"=="" (
    echo Podaj nazwę nowej analizy/taska, np.:
    echo   create_task.cmd bfly_10y_vs_vuds_2005
    echo.
    echo Dozwolone znaki: litery ASCII, cyfry, _ i -
    pause
    exit /b 1
)
set "TASK=%~1"
if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")
"%PY%" "app\bin\create_task.py" "%TASK%"
pause

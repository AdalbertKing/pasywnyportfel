@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
:: ============================================================
:: check_task.cmd                                       [USER]
:: ============================================================
:: Walidacja konfiguracji jednego taska PRZED uruchomieniem.
:: Sprawdza: start < end, mapy istnieja, wagi = 100%,
:: tickery pokryte przez biblioteki SYNTH/HIST.
::
:: Uzycie:
::   check_task.cmd user_template
::   check_task.cmd bfly_10y_vs_vuds_2005
::
:: Jesli sa ostrzezenia o HIST:
::   refresh_quotes.cmd <task>
:: ============================================================

if "%~1"=="" (
    echo Podaj nazwę taska, np.:
    echo   check_task.cmd user_template
    pause
    exit /b 1
)
if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")
"%PY%" "app\bin\validate_task.py" "%~1"
pause

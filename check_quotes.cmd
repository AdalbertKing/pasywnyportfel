@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: check_quotes.cmd                                     [DEV]
:: ============================================================
:: Sprawdza czy lokalna biblioteka HIST pokrywa wymagane tickery
:: i daty startu dla danego taska. Nie pobiera danych z internetu.
::
:: Uzycie:
::   check_quotes.cmd <task>
::   check_quotes.cmd --startup
::   check_quotes.cmd --all-tasks
::
:: Jesli brakuje pokrycia:
::   refresh_quotes.cmd <task>
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

if "%~1"=="" (
    echo Podaj nazwe taska albo --startup / --all-tasks, np.:
    echo   check_quotes.cmd daily_hist_smoke_3m
    echo   check_quotes.cmd --startup
    pause
    exit /b 1
)

"%PY%" "app\bin\refresh_quotes.py" --check %*
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%

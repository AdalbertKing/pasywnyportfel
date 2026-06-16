@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: refresh_quotes.cmd                                   [USER]
:: ============================================================
:: Pobiera/aktualizuje notowania ETF z Yahoo Finance do lokalnej
:: biblioteki HIST (data\in\libraries\HIST_LIBRARY_DAILY.csv).
:: Pobiera tylko tickery wymagane przez dany task.
::
:: Uzycie:
::   refresh_quotes.cmd <task>
::   refresh_quotes.cmd --startup        (taski z startup_order.csv)
::   refresh_quotes.cmd --all-tasks      (wszystkie taski)
::
:: Wymaga dostepu do internetu.
:: Po pobraniu sprawdz: check_quotes.cmd <task>
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

if "%~1"=="" (
    echo Podaj nazwe taska albo --startup / --all-tasks, np.:
    echo   refresh_quotes.cmd daily_hist_smoke_3m
    echo   refresh_quotes.cmd user_template
    echo   refresh_quotes.cmd --startup
    echo   refresh_quotes.cmd --all-tasks
    pause
    exit /b 1
)

"%PY%" "app\bin\refresh_quotes.py" %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo OK: biblioteka notowan HIST odswiezona.) else (echo ERROR: refresh_quotes zakonczyl sie kodem %RC%.)
pause
exit /b %RC%

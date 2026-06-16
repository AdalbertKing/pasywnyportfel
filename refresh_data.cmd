@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: refresh_data.cmd                                     [USER]
:: ============================================================
:: Odswierza wspolne dane wejsciowe z internetu:
::   - CPI USD (FRED, od 1960)
::   - CPI PLN (GUS, od 1995)
::   - FX USD/PLN (NBP, od 2002)
::
:: Uzycie:
::   refresh_data.cmd
::
:: Wymaga dostepu do internetu. Pliki wynikowe:
::   data\in\cpi\CPI_USD.csv
::   data\in\cpi\CPI_PLN_GUS.csv
::   data\inx\DB_FX.csv
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

echo ROOT=%CD%
echo PY=%PY%
echo.
echo Odswiezam wspolne dane:
echo   data\in\cpi\CPI_USD.csv
echo   data\in\cpi\CPI_PLN_GUS.csv
echo   data\in\fx\DB_FX.csv
echo.

"%PY%" "app\bin\bootstrap.py" --refresh-common
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
    echo OK: dane wspolne odswiezone.
) else (
    echo ERROR: odswiezanie danych zakonczylo sie kodem %RC%.
)
pause
exit /b %RC%

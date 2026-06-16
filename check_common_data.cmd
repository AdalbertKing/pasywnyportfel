@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: check_common_data.cmd                                [DEV]
:: ============================================================
:: Sprawdza czy pliki wspolne (CPI, FX, biblioteki) istnieja.
:: Nie sprawdza swiezosci — do tego uzyj test_after_start.cmd.
::
:: Uzycie:
::   check_common_data.cmd
::
:: Jesli brakuje plikow, uruchom:
::   refresh_data.cmd
:: ============================================================

echo === CHECK COMMON DATA ===
set "ERR=0"
if exist "data\in\cpi\CPI_USD.csv" (echo OK   data\in\cpi\CPI_USD.csv) else (echo BRAK data\in\cpi\CPI_USD.csv & set "ERR=1")
if exist "data\in\cpi\CPI_PLN_GUS.csv" (echo OK   data\in\cpi\CPI_PLN_GUS.csv) else (echo BRAK data\in\cpi\CPI_PLN_GUS.csv & set "ERR=1")
if exist "data\in\fx\DB_FX.csv" (echo OK   data\in\fx\DB_FX.csv) else (echo BRAK data\in\fx\DB_FX.csv & set "ERR=1")
if exist "data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv" (echo OK   data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv) else (echo BRAK data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv & set "ERR=1")
echo.
if "%ERR%"=="0" (echo WYNIK: OK) else (
    echo WYNIK: BRAKI
    echo Uruchomienie run_task.cmd samo sprobuje wykonac:
    echo   python app\bin\bootstrap.py --generate-missing
)
pause
exit /b %ERR%

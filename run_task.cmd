@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: run_task.cmd                                         [USER]
:: ============================================================
:: Glowna komenda: uruchamia pelna analize jednego taska.
:: Automatycznie sprawdza dane wspolne i notowania HIST.
:: Wyniki w: analysis_results\<task>__<data_godzina>\
::
:: Uzycie:
::   run_task.cmd user_template
::   run_task.cmd bfly_10y_vs_vuds_2005
::   run_task.cmd user_template --dry-run    (podglad komend)
::
:: Kazdy przebieg tworzy run.log w folderze wynikowym
:: z pelnym outputem i tracebackiem przy bledzie.
:: ============================================================

if "%~1"=="" (
    echo Podaj nazwe taska, np.:
    echo   run_task.cmd user_template
    echo   run_task.cmd bfly_10y_vs_vuds_2005
    echo   run_task.cmd daily_hist_smoke_3m
    echo.
    echo Mozesz dodac --dry-run aby tylko wypisac komendy bez wykonywania:
    echo   run_task.cmd user_template --dry-run
    echo.
    echo Dostepne taski:
    for /d %%D in (analysis_definitions\*) do if exist "%%D\settings.csv" if exist "%%D\portfolios.csv" echo   %%~nxD
    pause
    exit /b 1
)
set "TASK=%~1"
set "DRYRUN="
if /i "%~2"=="--dry-run" set "DRYRUN=--dry-run"
if /i "%~2"=="-n"         set "DRYRUN=--dry-run"

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

echo ROOT=%CD%
echo TASK=%TASK%
echo PY=%PY%
echo.

"%PY%" "app\bin\validate_task.py" "%TASK%"
if not %ERRORLEVEL%==0 (
    echo.
    echo ERROR: walidacja taska nie powiodla sie. Analiza nie zostanie uruchomiona.
    pause
    exit /b %ERRORLEVEL%
)

call :CHECK_COMMON_DATA
if "%COMMON_DATA_OK%"=="0" (
    echo.
    echo Brakuje wspolnych danych wejsciowych. Generuje tylko brakujace pliki:
    echo "%PY%" "app\bin\bootstrap.py" --generate-missing
    echo.
    "%PY%" "app\bin\bootstrap.py" --generate-missing
    if errorlevel 1 (
        echo.
        echo ERROR: bootstrap.py --generate-missing zakonczyl sie bledem.
        echo Nie uruchamiam analizy.
        pause
        exit /b 21
    )
)

call :CHECK_COMMON_DATA
if "%COMMON_DATA_OK%"=="0" (
    echo.
    echo ERROR: nadal brakuje wspolnych danych wejsciowych:
    if not exist "data\in\cpi\CPI_USD.csv" echo   BRAK data\in\cpi\CPI_USD.csv
    if not exist "data\in\cpi\CPI_PLN_GUS.csv" echo   BRAK data\in\cpi\CPI_PLN_GUS.csv
    if not exist "data\in\fx\DB_FX.csv" echo   BRAK data\in\fx\DB_FX.csv
    if not exist "data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv" echo   BRAK data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv
    echo.
    echo Analiza nie zostanie uruchomiona.
    pause
    exit /b 20
)

echo.
echo COMMON DATA: OK - uzywam istniejacych plikow CPI/FX.
echo Jezeli chcesz swiadomie odswiezyc CPI/FX, uruchom osobno:
echo   refresh_data.cmd
echo.
echo HIST QUOTES: sprawdzam lokalna biblioteke ETF/proxy dla tego taska.
"%PY%" "app\bin\refresh_quotes.py" "%TASK%" --check
set "QRC=%ERRORLEVEL%"
if not "%QRC%"=="0" (
    echo.
    echo HIST QUOTES: lokalna biblioteka jest pusta albo za krotka.
    echo HIST QUOTES: probuje automatycznie pobrac/uzupelnic notowania z Yahoo/yfinance.
    "%PY%" "app\bin\refresh_quotes.py" "%TASK%"
    if errorlevel 1 (
        echo.
        echo ERROR: nie udalo sie odswiezyc HIST_LIBRARY_DAILY.csv.
        echo Sprawdz internet, yfinance albo uruchom recznie: refresh_quotes.cmd %TASK%
        pause
        exit /b 31
    )
    "%PY%" "app\bin\refresh_quotes.py" "%TASK%" --check
    if errorlevel 1 (
        echo.
        echo ERROR: po odswiezeniu biblioteka HIST nadal nie pokrywa wymaganego zakresu.
        pause
        exit /b 32
    )
)
echo.
echo RUN TASK: %TASK% %DRYRUN%
"%PY%" "app\bin\analysis.py" --definition "analysis_definitions\%TASK%" %DRYRUN%
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo OK: task zakonczony. Wyniki sa w analysis_results.) else (echo ERROR: task zakonczyl sie kodem %RC%.)
pause
exit /b %RC%

:CHECK_COMMON_DATA
set "COMMON_DATA_OK=1"
if not exist "data\in\cpi\CPI_USD.csv" (
    echo BRAK data\in\cpi\CPI_USD.csv
    set "COMMON_DATA_OK=0"
)
if not exist "data\in\cpi\CPI_PLN_GUS.csv" (
    echo BRAK data\in\cpi\CPI_PLN_GUS.csv
    set "COMMON_DATA_OK=0"
)
if not exist "data\in\fx\DB_FX.csv" (
    echo BRAK data\in\fx\DB_FX.csv
    set "COMMON_DATA_OK=0"
)
if not exist "data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv" (
    echo BRAK data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv
    set "COMMON_DATA_OK=0"
)
exit /b 0

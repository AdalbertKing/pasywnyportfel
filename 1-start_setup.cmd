@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: 1-start_setup.cmd                                    [USER]
:: ============================================================
:: Jednorazowy pelny setup projektu. Uruchom po rozpakowaniu ZIP.
::
:: Co robi:
::   1. Instaluje/sprawdza srodowisko Python i biblioteki
::   2. Odswierza dane wspolne: CPI USD, CPI PLN, FX USD/PLN
::   3. Pobiera notowania HIST dla taskow z startup_order.csv
::   4. Uruchamia domyslne analizy
::
:: Ponowne uruchomienie jest bezpieczne — nadpisuje dane wspolne
:: i tworzy nowe foldery wynikowe (nie kasuje starych).
::
:: Po zakonczeniu sprawdz stan pakietu:
::   test_after_start.cmd
:: ============================================================

call "app\bin\ensure_python_env.cmd"
if errorlevel 1 (
    echo.
    echo ERROR: Przygotowanie Pythona/bibliotek nie powiodlo sie.
    echo Popraw problem opisany powyzej i uruchom ponownie 1-start_setup.cmd.
    echo.
    pause
    exit /b 10
)

if exist "_python_cmd.txt" (
    set /p PY=<_python_cmd.txt
) else if exist "runtime\python\python.exe" (
    set "PY=runtime\python\python.exe"
) else (
    set "PY=python"
)

"%PY%" -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo ERROR: zapisany Python nie uruchamia sie poprawnie: %PY%
    echo Usun _python_cmd.txt i uruchom ponownie 1-start_setup.cmd.
    echo.
    pause
    exit /b 30
)

echo.
echo ================================================================
echo Start pelnej konfiguracji i domyslnych analiz
echo ================================================================
echo ROOT=%CD%
echo PY=%PY%
echo.
echo Ten skrypt:
echo   1. odswiezy CPI/FX,
echo   2. odswiezy notowania HIST dla taskow startowych,
echo   3. uruchomi taski z analysis_definitions\startup_order.csv,
echo   4. zapisze wyniki w analysis_results\^<task^>__^<timestamp^>.
echo.

"%PY%" "app\bin\bootstrap.py" --refresh-common
if errorlevel 1 (
    echo ERROR: odswiezenie CPI/FX nie powiodlo sie.
    pause
    exit /b 41
)

"%PY%" "app\bin\refresh_quotes.py" --startup
if errorlevel 1 (
    echo ERROR: odswiezenie notowan HIST dla taskow startowych nie powiodlo sie.
    pause
    exit /b 42
)

"%PY%" "app\bin\bootstrap.py" --run-default
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo OK: pelny start zakonczony.
) else (
    echo ERROR: pelny start zakonczyl sie kodem %RC%.
)
pause
exit /b %RC%

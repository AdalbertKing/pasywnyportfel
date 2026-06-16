@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: check_project.cmd                                    [DEV]
:: ============================================================
:: Pelny audyt paczki: kompilacja, struktura, czystosc katalogu.
:: Laczy check_stage1.cmd + check_stage1_clean.cmd + check_common_data.cmd.
::
:: Uzycie:
::   check_project.cmd
:: ============================================================

call check_stage1.cmd
if errorlevel 1 (
    echo.
    echo ERROR: check_stage1.cmd zakonczyl sie bledem.
    pause
    exit /b 1
)

call check_stage1_clean.cmd
if errorlevel 1 (
    echo.
    echo ERROR: check_stage1_clean.cmd zakonczyl sie bledem.
    pause
    exit /b 2
)

python "app\bin\release_root_audit.py"
if errorlevel 1 (
    echo.
    echo ERROR: release_root_audit.py wykryl balagan w katalogu glownym.
    pause
    exit /b 3
)

echo.
echo CHECK PROJECT: OK
pause
exit /b 0

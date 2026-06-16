@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
:: ============================================================
:: check_stage1.cmd                                     [DEV]
:: ============================================================
:: Kompilacja wszystkich modulow Python + walidacja taskow.
:: Sprawdza skladnie, struktury plikow, mapy wag, daty.
::
:: Uzycie:
::   check_stage1.cmd
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")
"%PY%" "app\bin\stage1_quick_check.py"
pause

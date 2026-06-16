@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
:: ============================================================
:: check_stage1_clean.cmd                               [DEV]
:: ============================================================
:: Audyt czystosci paczki — sprawdza czy nie ma niepotrzebnych
:: plikow w katalogu glownym (np. __pycache__, .pyc, artefakty).
::
:: Uzycie:
::   check_stage1_clean.cmd
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")
"%PY%" "app\bin\stage1_clean_audit.py"
pause

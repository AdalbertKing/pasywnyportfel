@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: cleanup_old_results.cmd                            [USER]
:: Usuwa stare przebiegi z analysis_results, zachowujac
:: N najnowszych per task (domyslnie 5).
::
:: Przyklady:
::   cleanup_old_results.cmd --dry-run
::   cleanup_old_results.cmd
::   cleanup_old_results.cmd --keep 10
::   cleanup_old_results.cmd --task user_template
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

"%PY%" "app\bin\cleanup_old_results.py" %*
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%

@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

:: ============================================================
:: run_all_tasks.cmd                                  [USER]
:: Batchowe uruchomienie analiz dla wielu taskow naraz.
:: Zaklada gotowe dane wspolne (CPI/FX) i biblioteke HIST.
:: Jesli nie masz pewnosci, uruchom najpierw kazdy task raz
:: przez run_task.cmd albo 1-start_setup.cmd.
::
:: Przyklady:
::   run_all_tasks.cmd
::   run_all_tasks.cmd --startup-only
::   run_all_tasks.cmd --only user_template,daily_hist_smoke_3m
::   run_all_tasks.cmd --exclude daily_hist_smoke_3m
::   run_all_tasks.cmd --dry-run
:: ============================================================

if exist "_python_cmd.txt" (set /p PY=<_python_cmd.txt) else if exist "runtime\python\python.exe" (set "PY=runtime\python\python.exe") else (set "PY=python")

"%PY%" "app\bin\run_all_tasks.py" %*
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo OK: batch zakonczony bez bledow.) else (echo UWAGA: liczba niepowodzen = %RC%. Zobacz PODSUMOWANIE powyzej.)
pause
exit /b %RC%

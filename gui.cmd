@echo off
REM [USER] gui.cmd — uruchamia GUI pasywnyportfel (dwuklik)
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [BLAD] Nie znaleziono python w PATH.
    echo Zainstaluj Python 3.13 i upewnij sie ze jest dodany do PATH.
    pause
    exit /b 1
)

python -c "import customtkinter" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Brak pakietu customtkinter — instaluje...
    pip install customtkinter
    if errorlevel 1 (
        echo [BLAD] Instalacja customtkinter nie powiodla sie.
        pause
        exit /b 1
    )
)

python app\bin\gui.py
if errorlevel 1 (
    echo.
    echo [BLAD] GUI zakonczylo sie bledem — patrz powyzej.
    pause
    exit /b 1
)

endlocal

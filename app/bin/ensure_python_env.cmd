@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\..\.."

echo.
echo ================================================================
echo Sprawdzanie Pythona i bibliotek
echo ================================================================

set "PY="
if exist "_python_cmd.txt" del /q "_python_cmd.txt" >nul 2>nul

if exist "runtime\python\python.exe" (
    set "PY=runtime\python\python.exe"
    echo OK: uzywam Pythona z paczki: runtime\python\python.exe
    goto :python_found
)

call :find_working_python
if defined PY goto :python_found

echo.
echo BRAK: Nie znaleziono dzialajacego Pythona.
echo Probuje zainstalowac Python przez winget...

where winget >nul 2>nul
if not %ERRORLEVEL%==0 (
    echo.
    echo ERROR: Brak dzialajacego Pythona i brak winget.
    echo Zainstaluj Python recznie z python.org, zaznaczajac "Add python.exe to PATH",
    echo a potem uruchom ponownie 1-start_setup.cmd.
    exit /b 10
)

echo Proba 1: winget Python 3.13, scope=user
winget install --id Python.Python.3.13 -e --source winget --scope user --accept-package-agreements --accept-source-agreements
if not %ERRORLEVEL%==0 (
    echo.
    echo WARN: Python 3.13 scope=user nie powiodl sie.
    echo Proba 2: winget Python 3.13 bez scope...
    winget install --id Python.Python.3.13 -e --source winget --accept-package-agreements --accept-source-agreements
)

if not %ERRORLEVEL%==0 (
    echo.
    echo WARN: Instalacja Python.Python.3.13 przez winget nie powiodla sie.
    echo Probuje Python.Python.3.12 scope=user...
    winget install --id Python.Python.3.12 -e --source winget --scope user --accept-package-agreements --accept-source-agreements
    if not !ERRORLEVEL!==0 (
        echo.
        echo WARN: Python 3.12 scope=user nie powiodl sie.
        echo Probuje Python.Python.3.12 bez scope...
        winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
        if not !ERRORLEVEL!==0 (
            echo.
            echo ERROR: Nie udalo sie zainstalowac Pythona przez winget.
            echo Zainstaluj Python recznie z python.org, zaznaczajac "Add python.exe to PATH",
            echo a potem uruchom ponownie 1-start_setup.cmd.
            exit /b 11
        )
    )
)

echo.
echo Python zostal zainstalowany. Szukam go ponownie, takze poza PATH...

call :find_working_python
if defined PY goto :python_found

echo.
echo ERROR: Python zostal zainstalowany, ale nie znalazlem dzialajacego python.exe.
echo Sprobuj zamknac okno CMD i uruchomic 1-start_setup.cmd ponownie.
exit /b 12

:python_found
echo.
echo Python:
"%PY%" --version
if not %ERRORLEVEL%==0 (
    echo ERROR: Python znaleziony, ale nie uruchamia sie poprawnie.
    exit /b 13
)

echo.
echo ================================================================
echo Instalacja / aktualizacja pip i bibliotek projektu
echo ================================================================

"%PY%" -m ensurepip --upgrade >nul 2>nul

"%PY%" -m pip --version >nul 2>nul
if not %ERRORLEVEL%==0 (
    echo ERROR: Ten Python nie ma dzialajacego pip.
    echo Zainstaluj Python recznie z python.org i zaznacz "pip" oraz "Add python.exe to PATH".
    exit /b 19
)

"%PY%" -m pip install --upgrade pip --no-warn-script-location
if not %ERRORLEVEL%==0 (
    echo ERROR: Nie udalo sie zaktualizowac pip.
    exit /b 20
)

if not exist "requirements.txt" (
    echo ERROR: Brak requirements.txt w katalogu projektu.
    exit /b 21
)

"%PY%" -m pip install --upgrade -r requirements.txt --no-warn-script-location
if not %ERRORLEVEL%==0 (
    echo ERROR: Nie udalo sie zainstalowac wymaganych bibliotek z requirements.txt.
    exit /b 22
)

echo.
echo ================================================================
echo Sprawdzenie importow
echo ================================================================

"%PY%" -c "import pandas,numpy,matplotlib,yfinance,requests,dateutil; print('OK: biblioteki Pythona sa dostepne')"
if not %ERRORLEVEL%==0 (
    echo ERROR: Biblioteki zostaly zainstalowane, ale import testowy nie przeszedl.
    exit /b 23
)

> "_python_cmd.txt" echo %PY%

echo.
echo OK: srodowisko Python jest gotowe.
exit /b 0


:find_working_python
echo.
echo Szukam dzialajacego systemowego python.exe...

for /f "delims=" %%P in ('where python 2^>nul') do (
    echo Sprawdzam: %%P
    "%%P" -c "import sys; print(sys.executable)" >nul 2>nul
    if !ERRORLEVEL!==0 (
        set "PY=%%P"
        echo OK: znaleziono dzialajacego Pythona: %%P
        exit /b 0
    ) else (
        echo POMIJAM: %%P
        echo          Ten plik nie uruchamia prawdziwego Pythona poprawnie.
    )
)

echo.
echo Szukam launchera py -3...

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do (
        if not defined PY set "PY=%%P"
    )
    if defined PY (
        "%PY%" -c "import sys; print(sys.executable)" >nul 2>nul
        if !ERRORLEVEL!==0 (
            echo OK: znaleziono dzialajacy Python przez launcher py -3: !PY!
            exit /b 0
        ) else (
            set "PY="
            echo POMIJAM: py -3 nie uruchamia prawdziwego Pythona poprawnie.
        )
    )
)

echo.
echo Szukam Pythona w typowych katalogach instalacyjnych winget/python.org...

for %%P in (
    "%LocalAppData%\Programs\Python\Python313\python.exe"
    "%LocalAppData%\Programs\Python\Python312\python.exe"
    "%LocalAppData%\Programs\Python\Python311\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
) do (
    if exist "%%~P" (
        echo Sprawdzam: %%~P
        "%%~P" -c "import sys; print(sys.executable)" >nul 2>nul
        if !ERRORLEVEL!==0 (
            set "PY=%%~P"
            echo OK: znaleziono dzialajacego Pythona: %%~P
            exit /b 0
        ) else (
            echo POMIJAM: %%~P
        )
    )
)

set "PY="
exit /b 0

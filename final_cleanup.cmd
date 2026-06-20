@echo off
REM [USER] final_cleanup.cmd - porzadkuje repo przed commitem
setlocal

echo ============================================================
echo Krok 1: usuwam pliki scratch (posluzyly swojemu celowi)
echo ============================================================
if exist KOMENDY_TESTOWE.md del KOMENDY_TESTOWE.md
if exist KOMENDY_TESTOWE_FINALNE.md del KOMENDY_TESTOWE_FINALNE.md
if exist RAPORT_I_INSTRUKCJA.md del RAPORT_I_INSTRUKCJA.md
if exist app\bin\test_rebal_patch.py del app\bin\test_rebal_patch.py
if exist porownaj_wyniki.ps1 del porownaj_wyniki.ps1
if exist posprzataj.cmd del posprzataj.cmd
if exist test.log del test.log
if exist test_cmd.cmd del test_cmd.cmd
echo   gotowe

echo.
echo ============================================================
echo Krok 2: przenosze dokumenty projektowe do docs\
echo ============================================================
if not exist docs mkdir docs
if exist GUI_PROJECT_SPEC.md move GUI_PROJECT_SPEC.md docs\GUI_PROJECT_SPEC.md >nul
if exist GUI_REFERENCE.md move GUI_REFERENCE.md docs\GUI_REFERENCE.md >nul
echo   gotowe (oba dokumenty wymagaja jeszcze scalenia - osobna rozmowa)

echo.
echo ============================================================
echo Krok 3: status przed renormalizacja koncow linii
echo ============================================================
git status --short

echo.
echo ============================================================
echo Krok 4: renormalizacja koncow linii (wymaga .gitattributes w korzeniu)
echo ============================================================
if not exist .gitattributes (
    echo   [BLAD] brak .gitattributes - wgraj go najpierw, potem odpal ten skrypt ponownie
    pause
    exit /b 1
)
git add --renormalize .
echo   gotowe

echo.
echo ============================================================
echo GOTOWE. Sprawdz teraz: git status
echo Powinienes zobaczyc TYLKO realne zmiany:
echo   app\bin\cmd_builders.py  app\bin\analysis.py  (REBAL_PERIOD)
echo   analysis_definitions\*\portfolios.csv  (kolumna REBAL_PERIOD)
echo   tests\  pytest.ini  (odzyskane + nowy plik testow)
echo   docs\GUI_PROJECT_SPEC.md  docs\GUI_REFERENCE.md  (przeniesione)
echo   .gitattributes  (nowy)
echo ============================================================
pause
endlocal

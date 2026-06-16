# pasywnyportfel ver. 2.1.5 — clean root

## Cel

Wersja 2.1.5 porządkuje katalog główny paczki użytkowej.

Nie zmienia algorytmów względem 2.1.4.

## Usunięto z katalogu głównego

- artefakty budowy `_VER_*`, `_STAGE*`, `_AUDIT*`,
- lokalny `_python_cmd.txt`,
- stare launchery kompatybilności `2-start_check.cmd`, `3-start_myanalise.cmd`.

## Przeniesiono do `docs\`

- szczegółowe README,
- opisy metodologii,
- procedury testowe.

## Przeniesiono do `docs\archive\`

- stare notatki wersji `README_WERSJA_*`.

## Docelowy root

Katalog główny ma zawierać głównie:
- `README.md`
- `INSTRUKCJA_START.txt`
- `ABOUT.txt`
- `VERSION.txt`
- `1-start_setup.cmd`
- `run_task.cmd`
- `refresh_data.cmd`
- `create_task.cmd`
- `check_project.cmd`
- `check_task.cmd`
- katalogi `app`, `analysis_definitions`, `data`, `runtime`, `docs`.

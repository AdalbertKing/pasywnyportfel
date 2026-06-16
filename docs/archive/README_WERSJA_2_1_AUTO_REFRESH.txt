# pasywnyportfel ver. 2.1 PRE-GUI

## Najważniejsze polecenia

Kontrola:

```cmd
check_project.cmd
check_stage1.cmd
check_stage1_clean.cmd
```

Odświeżenie wspólnych danych:

```cmd
refresh_data.cmd
```

Uruchomienie konkretnego taska:

```cmd
run_task.cmd user_template
run_task.cmd daily_hist_smoke_3m
run_task.cmd bfly_10y_vs_vuds_2005
```

Pełny start:

```cmd
1-start_setup.cmd
```

## Co nowego w 2.1

- `run_task.cmd` odświeża CPI/FX przed analizą.
- Dodano `refresh_data.cmd`.
- Dodano `end=AUTO`.
- Dodano `start=AUTO-3M`.
- Dodano `analysis_mode=hist_only`.
- Dodano task `daily_hist_smoke_3m`.
- DB HIST ma sufiks częstotliwości: `_D`, `_W`, `_M`.

## Test świeżych danych

```cmd
run_task.cmd daily_hist_smoke_3m
```

Ten task pobiera notowania ETF/HIST z internetu przy budowie DB i liczy dzienny ledger za ostatnie 3 miesiące.

## Ver 2.1.1 — refresh danych jako osobny krok

Domyślne zachowanie jest rozdzielone:

```cmd
refresh_data.cmd
```

świadomie odświeża wspólne dane CPI/FX:

```text
data\in\cpi\CPI_USD.csv
data\in\cpi\CPI_PLN_GUS.csv
data\in\fx\DB_FX.csv
```

```cmd
run_task.cmd <nazwa_taska>
```

uruchamia analizę na istniejących CPI/FX. Jeżeli któregoś wspólnego pliku brakuje, `run_task.cmd` wygeneruje tylko brakujące dane przez `bootstrap.py --generate-missing`.

To pozwala zrobić wiele analiz jednego dnia bez dociągania CPI/FX przy każdym uruchomieniu.

Uwaga: notowania ETF/HIST w tej wersji nadal są pobierane przy budowie DB danego przebiegu. Cache notowań zostaje osobnym przyszłym etapem.

## Ver 2.1.2 — CPI daily/real hotfix

Poprawiona polityka CPI:

```text
CPI z YYYY-MM-01 obowiązuje tylko dla sesji z tego miesiąca.
Nie wolno przenosić CPI z ostatniego znanego miesiąca na kolejne miesiące.
```

Czyli:
- dzienne notowania + miesięczny CPI są obsługiwane,
- ale po ostatnim miesiącu CPI wartości realne są puste,
- summary real liczy tylko faktycznie pokryty CPI zakres.

Dodano plik:

```text
data\in\cpi\CPI_PLN_FLASH.csv
```

z lokalnymi szybkimi szacunkami, np. kwiecień 2026:
`m/m +0.6%`, `r/r +3.2%`, status `PROVISIONAL`.

`refresh_data.cmd` używa tego pliku przy budowie `CPI_PLN_GUS.csv`.

## Ver 2.1.3 — krótkie okresy: RETURN zamiast CAGR w PNG

W krótkich analizach, np. `daily_hist_smoke_3m`, CAGR jest annualizacją kilku tygodni/miesięcy i może wyglądać „astronomicznie”.

Od wersji 2.1.3:
- `ledger_summary.py` zapisuje `RETURN_%`, `RETURN_NOM_%`, `DAYS`, `YEARS`,
- `summary_*.png` dla okresów krótszych niż rok pokazuje `Return real` i `Return nominal`,
- `CAGR_%` zostaje w CSV jako annualizowana metryka diagnostyczna,
- sortowanie `AUTO` dla krótkich okresów używa `RETURN_%`, a dla długich `CAGR_%`.

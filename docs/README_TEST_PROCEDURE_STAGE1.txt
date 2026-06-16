PROCEDURA TESTOWA ver. 2.0

Po rozpakowaniu:

1. Kontrola struktury:

   check_stage1.cmd

2. Kontrola braku starych ścieżek/dokumentów:

   check_stage1_clean.cmd

3. Kontrola danych wspólnych:

   check_common_data.cmd

   Na czystym pakiecie CPI/FX mogą jeszcze nie istnieć. To jest OK.

4. Test pojedynczego taska:

   run_task.cmd user_template

   Jeżeli brakuje CPI/FX, skrypt sam spróbuje je wygenerować.

5. Test tworzenia nowego taska:

   create_task.cmd test_stage1
   check_task.cmd test_stage1
   run_task.cmd test_stage1

6. Pełny start:

   1-start_setup.cmd

   Oczekiwane wyniki:
   analysis_results\benchmark_1970_synth_usd_gross__...
   analysis_results\synth_vs_etf_2005_full10__...

---
Autor: Wojciech Król, lurk@lurk.com.pl

## Ver 2.1 — AUTO daty, refresh danych i test dzienny

Nowe wejścia:

```cmd
refresh_data.cmd
```

odświeża wspólne dane:

```text
data\in\cpi\CPI_USD.csv
data\in\cpi\CPI_PLN_GUS.csv
data\in\fx\DB_FX.csv
```

`run_task.cmd <task>` używa istniejących CPI/FX, a brakujące pliki tylko dogenerowuje.

Nowy szybki test świeżych notowań:

```cmd
run_task.cmd daily_hist_smoke_3m
```

Task `daily_hist_smoke_3m` liczy dzienną analizę HIST za ostatnie 3 miesiące:
- S&P 500,
- US 60/40,
- Golden Butterfly.

Nowe ustawienia w `settings.csv`:

```csv
start,AUTO-3M
end,AUTO
analysis_mode,hist_only
freq,daily
```

`AUTO` jest rozwiązywane według daty systemowej komputera. Notowania ETF/HIST są pobierane podczas budowy DB dla danego przebiegu.

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

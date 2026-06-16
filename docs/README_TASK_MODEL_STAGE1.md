# Model tasków — ver. 2.0

## Zasada

Analiza jest folderem:

```text
analysis_definitions\<task>
```

Wynik ma nazwę:

```text
analysis_results\<task>__<timestamp>
```

## Struktura taska

```text
analysis_definitions\<task>\
  settings.csv
  portfolios.csv
  maps\hist\
  maps\synth\
```

`portfolios.csv` wskazuje mapy lokalne, np.:

```text
maps\hist\my_portfolio_hist.csv
maps\synth\my_portfolio_syn.csv
```

## Common

```text
analysis_definitions\common\maps\
analysis_definitions\common\task_templates\
```

`common` jest biblioteką wzorców. Nie jest taskiem do uruchamiania.

## Szablon nowego taska

```text
analysis_definitions\common\task_templates\comparison_2005
```

`create_task.cmd <nazwa>` kopiuje ten czysty szablon do:

```text
analysis_definitions\<nazwa>
```

## Uruchamianie

```cmd
run_task.cmd <nazwa>
```

`run_task.cmd` waliduje task, sprawdza dane wspólne i uruchamia `analysis.py --definition analysis_definitions\<nazwa>`.

## Domyślny syntetyczny benchmark od 1970

Domyślny duży przebieg syntetyczny startuje od `1970-01-31`, czyli z parametrem danych `dbstart_synth=1970-01-01`.

Powód: główna analiza ma obejmować współczesny reżim po końcowej fazie Bretton Woods / dolara powiązanego ze złotem. Okres wcześniejszy nie jest domyślnie uruchamiany, żeby nie mieszać głównego porównania portfeli z wcześniejszym reżimem monetarnym.

Pełny start uruchamia taski z `analysis_definitions\startup_order.csv`:
- `benchmark_1970_synth_usd_gross`
- `synth_vs_etf_2005_full10`

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

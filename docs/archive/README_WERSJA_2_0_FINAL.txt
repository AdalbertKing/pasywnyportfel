pasywnyportfel ver. 2.0 — finalna wersja wsadowa przed GUI

STATUS:
Wersja wsadowa zamknięta operacyjnie jako baza pod GUI.

NAJWAŻNIEJSZY MODEL:
- analiza = folder w analysis_definitions
- wynik = analysis_results\<nazwa_taska>__<timestamp>
- mapy portfeli są lokalnie w tasku: analysis_definitions\<task>\maps\
- wzorce map są w: analysis_definitions\common\maps\
- czysty szablon nowej analizy jest w: analysis_definitions\common\task_templates\comparison_2005\

PEŁNY START:
1-start_setup.cmd

Pełny start uruchamia taski z:
analysis_definitions\startup_order.csv

Domyślnie:
- benchmark_1970_synth_usd_gross
- synth_vs_etf_2005_full10

POJEDYNCZA ANALIZA:
run_task.cmd <nazwa_taska>

Przykład:
run_task.cmd user_template
run_task.cmd bfly_10y_vs_vuds_2005

TWORZENIE NOWEJ ANALIZY:
create_task.cmd moja_analiza

Następnie edytuj:
analysis_definitions\moja_analiza\settings.csv
analysis_definitions\moja_analiza\portfolios.csv
analysis_definitions\moja_analiza\maps\hist\*.csv
analysis_definitions\moja_analiza\maps\synth\*.csv

AUTOR:
Wojciech Król
lurk@lurk.com.pl


Kontrola projektu jednym poleceniem:

```cmd
check_project.cmd
```

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

`run_task.cmd <task>` przed analizą uruchamia odświeżenie CPI/FX, a potem liczy task.

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

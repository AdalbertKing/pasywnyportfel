# pasywnyportfel ver. 2.2.5A

Autor koncepcji i projektu: Wojciech Król
email: lurk@lurk.com.pl

Wsadowe narzędzie do analizy portfeli pasywnych.
Nie stanowi rekomendacji inwestycyjnej.

---

## Szybki start

```cmd
cd /d D:\analises\pasywnyportfel
1-start_setup.cmd
```

Pełny start: instaluje środowisko, odświeża CPI/FX, pobiera notowania HIST,
uruchamia domyślne analizy ze `startup_order.csv`.

## Codzienna praca

Pięć komend, które używasz regularnie:

```cmd
run_task.cmd <task>                 uruchom analizę jednego taska
create_task.cmd <nowy_task>         stwórz nowy task z szablonu
refresh_data.cmd                    odśwież CPI/FX
refresh_quotes.cmd <task>           odśwież notowania HIST dla taska
test_after_start.cmd                kontrola stanu pakietu (FAIL/WARN/OK)
```

Opcjonalnie:

```cmd
run_task.cmd <task> --dry-run       podgląd komend bez wykonywania
run_all_tasks.cmd                   batch: uruchom wszystkie taski naraz
run_all_tasks.cmd --startup-only    batch: tylko taski startowe
cleanup_old_results.cmd --dry-run   pokaż co można usunąć z analysis_results
```

## Wyniki

```
analysis_results\<task>__<YYYYMMDD_HHMMSS>\
  run.log                   pełny log przebiegu (z tracebackiem przy błędzie)
  summary_gross_USD_real.csv    wyniki GROSS w USD-real
  summary_net_PLN_USD_real.csv  wyniki po Belce w USD-real (jeśli tax_mode=net)
  charts\                   wykresy PNG
  tables\                   tabele podsumowań
  crash\                    crash-test: najgorsze okna 3/5/7/10 lat
  config\                   kopia settings.csv i portfolios.csv użytych w tym przebiegu
```

Nazwa pliku summary odzwierciedla tryb podatkowy:
- `gross` — bez podatku
- `net_PLN` — polska Belka 19% od zysku w PLN (wymaga FX)
- `net_USD` — model poglądowy, podatek w USD

## Konfiguracja taska

Każdy task to folder w `analysis_definitions\<task>\`:

```
settings.csv       parametry: okres, biblioteki, podatek, częstotliwość
portfolios.csv     lista portfeli z mapami SYNTH i HIST
maps\synth\        mapy składu portfela (dane syntetyczne od 1970)
maps\hist\         mapy składu portfela (realne ETF od 2005)
```

Podatek Belki:

```csv
tax_mode,net
tax_base,PLN
tax_rate,0.19
```

Walidacja konfiguracji: `check_task.cmd <task>`

## Testy

```cmd
run_tests.cmd                       402 testy jednostkowe (pytest)
test_after_start.cmd                kontrola środowiska, danych, taskow
```

## Struktura plików

Szczegółowa mapa: `docs\README_STRUCTURE.md`

## Dokumentacja

```
docs\README_METHODOLOGY.md          metodologia backtestów
docs\README_TASK_MODEL_STAGE1.md    model tasków
docs\README_STRUCTURE.md            mapa plików projektu
docs\README_TEST_PROCEDURE_2_2_5A.md  procedura testowa
```

## Historia wersji

Patrz `docs\CHANGELOG_2_2_5A.md`

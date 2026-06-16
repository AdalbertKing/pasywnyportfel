# Struktura plików — pasywnyportfel ver. 2.2.5A

Autor: Wojciech Król, lurk@lurk.com.pl

---

## Legenda

- **[USER]** — komenda/plik dla użytkownika, uruchamiany ręcznie
- **[AUTO]** — wywoływany automatycznie przez inne skrypty; użytkownik nie musi go znać
- **[DEV]** — narzędzie deweloperskie (testy, audyt)
- **[LIB]** — moduł biblioteczny importowany przez inne pliki; nigdy nie uruchamiany samodzielnie
- **[LEGACY]** — alias wstecznej kompatybilności; nie używaj w nowym kodzie

---

## Katalog główny — komendy .cmd

Codzienne:

| Plik | Rola | Opis |
|---|---|---|
| `run_task.cmd` | [USER] | Uruchom analizę jednego taska |
| `create_task.cmd` | [USER] | Stwórz nowy task z szablonu |
| `refresh_data.cmd` | [USER] | Odśwież CPI/FX |
| `refresh_quotes.cmd` | [USER] | Odśwież notowania HIST dla taska |
| `test_after_start.cmd` | [USER] | Kontrola stanu pakietu (FAIL/WARN/OK) |

Rzadsze:

| Plik | Rola | Opis |
|---|---|---|
| `1-start_setup.cmd` | [USER] | Jednorazowy pełny setup + domyślne analizy |
| `run_all_tasks.cmd` | [USER] | Batch: uruchom wiele tasków naraz |
| `cleanup_old_results.cmd` | [USER] | Retencja: usuń stare przebiegi |
| `check_task.cmd` | [USER] | Walidacja konfiguracji jednego taska |

Diagnostyczne:

| Plik | Rola | Opis |
|---|---|---|
| `run_tests.cmd` | [DEV] | Uruchom pytest (402 testy) |
| `check_project.cmd` | [DEV] | Audyt struktury paczki |
| `check_common_data.cmd` | [DEV] | Sprawdź pliki CPI/FX/bibliotek |
| `check_quotes.cmd` | [DEV] | Sprawdź pokrycie notowań HIST |
| `check_stage1.cmd` | [DEV] | Kompilacja + walidacja tasków |
| `check_stage1_clean.cmd` | [DEV] | Audyt czystości paczki |

---

## Katalog główny — inne pliki

| Plik | Rola | Opis |
|---|---|---|
| `README.md` | [USER] | Główna dokumentacja |
| `INSTRUKCJA_START.txt` | [USER] | Instrukcja pierwszego uruchomienia |
| `ABOUT.txt` | [USER] | Informacje o projekcie |
| `VERSION.txt` | [USER] | Numer wersji |
| `SOURCES.md` | [USER] | Źródła danych |
| `requirements.txt` | [USER] | Zależności Python (luźne piny) |
| `requirements-lock.txt` | [USER] | Zależności Python (zablokowane wersje) |
| `requirements-dev.txt` | [DEV] | Zależności deweloperskie (pytest) |
| `pytest.ini` | [DEV] | Konfiguracja pytest |

---

## app/bin/ — silnik projektu

Użytkownik **nie otwiera tych plików** — są wywoływane automatycznie
przez komendy `.cmd`. Podział na trzy warstwy:

### Warstwa 1: Biblioteki [LIB]

Importowane przez inne moduły. Nigdy nie uruchamiane samodzielnie.

| Plik | Opis |
|---|---|
| `common.py` | Narzędzia ścieżkowe, bool_setting, resolve_auto_date_token |
| `task_config.py` | Odczyt settings/portfolios, walidacja podatku, list_tasks |
| `cmd_builders.py` | Budowanie komend CLI, nazwy plików, raportów |
| `run_logging.py` | RunLogger — zapis run.log z tracebackiem |
| `ledger_primitives.py` | Prymitywy dat, cen, resampligu |
| `ledger_io.py` | Odczyt baz cen (wide CSV) i CPI |
| `ledger_tax.py` | Model podatku Belki (LossBucket) |
| `ledger_engine.py` | Silnik symulacji: build_event_dates + simulate_ledger |

### Warstwa 2: Punkty wejścia CLI [AUTO]

Wywoływane jako subprocess przez `analysis.py` lub przez `.cmd`.
Każdy ma `if __name__ == "__main__"`.

| Plik | Wywoływany przez | Opis |
|---|---|---|
| `analysis.py` | `run_task.cmd` | Orkiestrator analizy (główny skrypt) |
| `passive_ledger.py` | `analysis.py` | Symulacja portfela (backtest) |
| `bootstrap.py` | `1-start_setup.cmd` | Pełny setup środowiska |
| `validate_task.py` | `check_task.cmd` | Walidacja taska |
| `create_task.py` | `create_task.cmd` | Tworzenie taska z szablonu |
| `refresh_quotes.py` | `refresh_quotes.cmd` | Odświeżanie notowań HIST |
| `run_all_tasks.py` | `run_all_tasks.cmd` | Batch runner |
| `cleanup_old_results.py` | `cleanup_old_results.cmd` | Retencja wyników |
| `health_check.py` | `test_after_start.cmd` | Kontrola stanu pakietu |
| `stage1_quick_check.py` | `check_stage1.cmd` | Kompilacja + walidacja |
| `build_db_synthetic.py` | `analysis.py` | Budowa DB z biblioteki SYNTH |
| `build_db_freq.py` | `analysis.py` | Budowa DB z biblioteki HIST |
| `build_cpi_usd_fred.py` | `bootstrap.py` | Pobieranie CPI USD z FRED |
| `build_cpi_pln_gus.py` | `bootstrap.py` | Pobieranie CPI PLN z GUS |
| `build_fx_nbp.py` | `bootstrap.py` | Pobieranie FX USD/PLN z NBP |
| `plot_ledger_template.py` | `analysis.py` | Generowanie wykresów PNG |
| `make_summary_table.py` | `analysis.py` | Generowanie tabel PNG |
| `ledger_summary.py` | `analysis.py` | Tabele podsumowań CSV |
| `crash_by_portfolio.py` | `analysis.py` | Crash-test: najgorsze okna |
| `crash_test_windows.py` | `analysis.py` | Pomocnicze okna crash-testu |

### Warstwa 3: Narzędzia deweloperskie i legacy [DEV/LEGACY]

| Plik | Rola | Opis |
|---|---|---|
| `stage1_clean_audit.py` | [DEV] | Audyt czystości paczki |
| `release_root_audit.py` | [DEV] | Audyt plików w katalogu głównym |
| `rank_synth_hist_gaps.py` | [DEV] | Analiza luk synth vs hist |
| `scan_lost_decades.py` | [DEV] | Skanowanie straconych dekad |
| `analiza.py` | [LEGACY] | Alias → `analysis.main()` (nie używaj) |
| `init_project.py` | [LEGACY] | Alias → `bootstrap.main()` (nie używaj) |

---

## tests/ — testy jednostkowe

Uruchamiane przez `run_tests.cmd` (pytest). 402 testy pokrywające
wszystkie moduły [LIB] i kluczowe ścieżki [AUTO].

| Plik | Testuje |
|---|---|
| `conftest.py` | Fixtures: project_root, synth_portfolio_csv, wide_price_db_csv |
| `test_common.py` | norm_path, detect_root, rel, task_rel, truthy, bool_setting |
| `test_task_config.py` | setting_value, freq, dates, PLN outputs, tax_settings |
| `test_validate_task.py` | validate_dates, weight_sum, library coverage |
| `test_ledger_primitives.py` | parse_date, resample, upsampling guard, fx attach |
| `test_ledger_io.py` | read_wide_db_csv, read_cpi_csv |
| `test_ledger_tax.py` | LossBucket (@dataclass), apply_loss_buckets, FIFO |
| `test_ledger_engine.py` | build_event_dates, simulate_ledger BH/DRIFT/NET, subprocess |
| `test_run_logging.py` | Tee, RunLogger OK/FAIL/resilience |
| `test_cmd_builders.py` | run() streaming, dry-run, integracja z RunLogger |
| `test_create_task.py` | create_task + auto-walidacja, CLI |
| `test_batch_tools.py` | list_tasks, run_all_tasks, cleanup_old_results |
| `test_health_check.py` | Counter, freshness, phases, main() |

---

## Hierarchia importów (bez cykli)

```
analysis.py → task_config.py → common.py
            → cmd_builders.py → task_config.py
            → run_logging.py
            → common.py

passive_ledger.py → ledger_engine.py → ledger_primitives.py
                                     → ledger_io.py
                                     → ledger_tax.py

validate_task.py → common.py
health_check.py  → common.py, task_config.py, validate_task.py
```

---

## Dane

```
data\in\cpi\CPI_USD.csv                              CPI US (od 1960)
data\in\cpi\CPI_PLN_GUS.csv                          CPI PL (od 1995)
data\in\fx\DB_FX.csv                                 FX USD/PLN (od 2002)
data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv       dane syntetyczne (od 1833)
data\in\libraries\HIST_LIBRARY_DAILY.csv              notowania ETF (generowane przez refresh_quotes)
```

---

*Autor: Wojciech Król, lurk@lurk.com.pl*

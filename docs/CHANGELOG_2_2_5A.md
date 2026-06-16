# Changelog — VER 2.2.5A

Data: 2026-06-16
Autor zmian: Claude (Anthropic) na zlecenie Wojciecha Króla

---

## Refaktoryzacja modułowa

- `analysis.py` (888 → 353 linii) rozbity na:
  `task_config.py` (konfiguracja), `cmd_builders.py` (budowanie komend)
- `passive_ledger.py` (1076 → 87 linii) rozbity na:
  `ledger_primitives.py`, `ledger_io.py`, `ledger_tax.py`, `ledger_engine.py`
- Wydzielony `common.py` — jedyne źródło `detect_root`, `rel`, `task_rel`,
  `bool_setting`, `truthy`, `resolve_auto_date_token`, `read_settings`
- Wydzielony `run_logging.py` — RunLogger (zapis run.log)

## Poprawki błędów

- `bool_setting`: puste VALUE w settings.csv zwracało True zamiast default
- `@dataclass` na `LossBucket`: zgubiony podczas podziału modułów,
  uniemożliwiał `tax_mode=net` (polska Belka)
- Nazwy plików summary: hardcoded `gross` → dynamiczne `gross`/`net_PLN`/`net_USD`
  (nazwy plików, podpisy PNG, README_ANALYSIS.txt)

## Nowe funkcje

- Walidacja `start < end` w `validate_task.py` z obsługą tokenów AUTO
- Walidacja pokrycia tickerów map przez biblioteki SYNTH/HIST
- `run.log` w każdym folderze wynikowym (pełny output + traceback przy błędzie)
- `run_all_tasks.cmd` — batch: wiele tasków naraz, podsumowanie OK/FAIL/czas
- `run_task.cmd --dry-run` — podgląd komend bez wykonywania
- `cleanup_old_results.cmd` — retencja: zachowaj N najnowszych per task
- `create_task.cmd` — auto-walidacja po utworzeniu taska
- `health_check.py` / `test_after_start.cmd` — 6-fazowa kontrola stanu pakietu
- `tax_label()` — dynamiczne etykiety `gross`/`net_PLN`/`net_USD`

## Testy

- 402 testy jednostkowe (pytest) w `tests/`
- `run_tests.cmd` — wrapper uruchamiający pytest
- `requirements-dev.txt` — zależności deweloperskie

## Wymagania

- `requirements.txt` — luźne piny (do świeżych instalacji)
- `requirements-lock.txt` — zablokowane wersje (do reprodukowalności)

## Dokumentacja

- `README.md` — zaktualizowany do wersji 2.2.5A
- `INSTRUKCJA_START.txt` — zaktualizowana
- `docs/README_STRUCTURE.md` — mapa plików z klasyfikacją [USER]/[AUTO]/[LIB]/[DEV]/[LEGACY]
- `docs/README_TEST_PROCEDURE_2_2_5A.md` — procedura testowa z komendami
- `docs/CHANGELOG_2_2_5A.md` — ten plik

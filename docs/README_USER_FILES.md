# Pliki użytkownika — ver. 2.0

Ten plik jest generowany przez `app/bin/bootstrap.py`.

## Komendy

- `1-start_setup.cmd` — pełny setup i taski z `analysis_definitions/startup_order.csv`.
- `2-start_check.cmd` — kontrola bez liczenia.
- `3-start_myanalise.cmd` — skrót do `run_task.cmd user_template`.
- `create_task.cmd <nazwa>` — tworzy nowy task z czystego szablonu.
- `run_task.cmd <nazwa>` — uruchamia wskazany task.

## Edycja własnego taska

Edytuj lokalne pliki taska:

- `analysis_definitions/<task>/settings.csv`
- `analysis_definitions/<task>/portfolios.csv`
- `analysis_definitions/<task>/maps/hist/*.csv`
- `analysis_definitions/<task>/maps/synth/*.csv`

## Wyniki

`analysis_results/<task>__YYYYMMDD_HHMMSS`

## Wzorce

`analysis_definitions/common/maps/` oraz `analysis_definitions/common/task_templates/`.

---
Autor: Wojciech Król, lurk@lurk.com.pl

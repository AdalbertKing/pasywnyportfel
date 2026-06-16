# pasywnyportfel ver. 2.2.1 — HIST library hotfix

## Naprawa

`refresh_quotes.cmd daily_hist_smoke_3m` wyrzucał:

```text
ParserError: Expected 2 fields in line 22, saw 3
```

Przyczyna: `settings.csv` zawiera wartości z przecinkami, np.:

```csv
plot_currencies,USD,PLN
```

To jest poprawny format projektu. Parser musi dzielić tylko po pierwszym przecinku.

Dodatkowo `refresh_quotes.py` normalizuje ścieżki map zapisane po windowsowemu, np. `maps\hist\sp500_hist.csv`.

## Test

```cmd
check_project.cmd
refresh_data.cmd
refresh_quotes.cmd daily_hist_smoke_3m
check_quotes.cmd daily_hist_smoke_3m
run_task.cmd daily_hist_smoke_3m
```

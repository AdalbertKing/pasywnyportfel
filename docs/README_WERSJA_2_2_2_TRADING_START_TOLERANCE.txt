# pasywnyportfel ver. 2.2.2 — trading start tolerance

## Problem

Po `refresh_quotes.cmd daily_hist_smoke_3m` biblioteka miała dane od `2026-03-02`, ale `check_quotes.cmd` nadal zgłaszał błąd, bo task wymagał `start=2026-02-28`.

`2026-02-28` była sobotą. Pierwszą sesją był poniedziałek `2026-03-02`.

## Poprawka

- `refresh_quotes.py --check` akceptuje pierwszą sesję do 7 dni po żądanym starcie.
- `build_db_freq.py --library` używa tej samej tolerancji.
- `analysis.py` przekazuje `--start-tolerance-days`.
- `daily_hist_smoke_3m/settings.csv` ma `start_tolerance_days,7`.

## Test

```cmd
refresh_data.cmd
refresh_quotes.cmd daily_hist_smoke_3m
check_quotes.cmd daily_hist_smoke_3m
run_task.cmd daily_hist_smoke_3m
```

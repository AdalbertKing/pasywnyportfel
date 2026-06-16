# daily_hist_smoke_3m

Szybki test dzienny HIST za ostatnie 3 miesiące.

Cel:
- sprawdzić, czy `run_task.cmd` odświeża CPI/FX,
- sprawdzić, czy `build_db_freq.py` pobiera najnowsze notowania ETF/HIST z internetu,
- policzyć dzienny ledger dla: S&P 500, US 60/40, Golden Butterfly.

Uruchomienie:

```cmd
run_task.cmd daily_hist_smoke_3m
```

Ustawienia:
- `analysis_mode=hist_only`
- `freq=daily`
- `start=AUTO-3M`
- `end=AUTO`
- `make_crash=0`

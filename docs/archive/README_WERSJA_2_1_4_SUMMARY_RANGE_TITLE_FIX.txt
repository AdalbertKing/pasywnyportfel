# pasywnyportfel ver. 2.1.4 — summary range title fix

Hotfix kosmetyczny.

Nie zmienia algorytmu ledgera ani summary CSV.

Poprawia:
- podtytuł `summary_*.png`,
- zakres dat w podtytule ma pochodzić z faktycznych `START/END` w `summary_*.csv`, a nie z żądanych dat `settings.csv`.

Test:
```cmd
run_task.cmd daily_hist_smoke_3m
```

Dla krótkiego smoke-testu po poprawce podtytuł PNG powinien pokazać np.:
```text
2026-03-02 to 2026-04-30 | daily | gross | metrics in PLN-real
```
a nie:
```text
2026-02-28 to 2026-05-28 | daily | gross | metrics in PLN-real
```

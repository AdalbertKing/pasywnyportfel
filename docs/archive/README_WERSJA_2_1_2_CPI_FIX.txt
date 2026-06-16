# pasywnyportfel ver. 2.1.2 — CPI daily/real hotfix

## Problem

W krótkim teście dziennym PLN-real mógł być równy PLN-nominal, gdy CPI_PLN kończył się na wcześniejszym miesiącu. To oznaczało ciche założenie inflacji 0% po ostatnim CPI.

## Poprawka

- CPI miesięczne jest nakładane na dzienne/tygodniowe/miesięczne daty.
- CPI z danego miesiąca obowiązuje tylko w tym miesiącu.
- Po ostatnim dostępnym miesiącu CPI wartości realne są puste.
- Summary real liczy tylko zakres z poprawnymi realnymi wartościami.
- Tytuł summary PNG pokazuje faktyczny zakres metryk z summary CSV.

## Szybki szacunek GUS

Plik:

```text
data\in\cpi\CPI_PLN_FLASH.csv
```

pozwala dopisać prowizoryczne szybkie szacunki CPI_PLN. W paczce jest wpis dla 2026-04-01:

```csv
date,infl_mom,infl_yoy,status,source,comment
2026-04-01,0.006,0.032,PROVISIONAL,GUS_FLASH,...
```

## Test

```cmd
refresh_data.cmd
run_task.cmd daily_hist_smoke_3m
```

Sprawdź `summary_gross_PLN_real.png` oraz zakres dat w tytule. PLN-real powinien kończyć się na ostatnim miesiącu pokrytym CPI_PLN.

## Ver 2.1.3 — krótkie okresy: RETURN zamiast CAGR w PNG

W krótkich analizach, np. `daily_hist_smoke_3m`, CAGR jest annualizacją kilku tygodni/miesięcy i może wyglądać „astronomicznie”.

Od wersji 2.1.3:
- `ledger_summary.py` zapisuje `RETURN_%`, `RETURN_NOM_%`, `DAYS`, `YEARS`,
- `summary_*.png` dla okresów krótszych niż rok pokazuje `Return real` i `Return nominal`,
- `CAGR_%` zostaje w CSV jako annualizowana metryka diagnostyczna,
- sortowanie `AUTO` dla krótkich okresów używa `RETURN_%`, a dla długich `CAGR_%`.

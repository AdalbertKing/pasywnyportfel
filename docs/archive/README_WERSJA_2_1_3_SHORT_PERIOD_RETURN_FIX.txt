# pasywnyportfel ver. 2.1.3 — short-period return fix

## Diagnoza

Ledger w teście `daily_hist_smoke_3m` był liczony poprawnie po hotfixie CPI:
- wartości realne kończyły się na ostatnim miesiącu CPI,
- maj bez CPI miał wartości realne puste.

Problem był w tabeli summary:
- dla krótkiego okresu 2-3 miesięcy pokazywano CAGR,
- CAGR jest annualizacją krótkiego zwrotu,
- dlatego wyglądał „astronomicznie”.

## Poprawka

Dla krótkich okresów `< 1 rok` `summary_*.png` pokazuje:
- `Return real`,
- `Return nominal`,

zamiast:
- `CAGR real`,
- `CAGR nominal`.

CSV nadal zawiera CAGR, ale dodatkowo ma:
- `RETURN_%`,
- `RETURN_NOM_%`,
- `DAYS`,
- `YEARS`.

## Test

```cmd
refresh_data.cmd
run_task.cmd daily_hist_smoke_3m
```

Otwórz `summary_gross_PLN_real.png` i `summary_gross_USD_real.png`. Dla krótkiego testu w tabeli powinien być zwrot za okres, nie annualizowany CAGR.

## Ver 2.1.4 — hotfix podtytułu summary PNG

W 2.1.3 obliczenia i summary CSV były poprawne, ale podtytuł PNG mógł pokazywać żądany zakres `start/end`, zamiast faktycznego zakresu metryk z summary CSV.

Przyczyna: `analysis.py::summary_actual_range()` używał `pd`, ale `analysis.py` nie importował pandas. Funkcja wpadała w fallback.

W 2.1.4 poprawiono to lokalnym importem pandas w `summary_actual_range()`.

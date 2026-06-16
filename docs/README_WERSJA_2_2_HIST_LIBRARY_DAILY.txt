# pasywnyportfel ver. 2.2 — HIST_LIBRARY_DAILY

## Cel

Wersja 2.2 dodaje lokalną bibliotekę dziennych notowań ETF/HIST:

```text
data\in\libraries\HIST_LIBRARY_DAILY.csv
data\in\libraries\HIST_LIBRARY_DAILY_manifest.csv
```

To odpowiednik istniejącej biblioteki syntetyków:

```text
data\in\libraries\SYNTH_LIBRARY_MONTHLY_USD.csv
```

## Kontrakt

```cmd
refresh_quotes.cmd <task>
```

pobiera / aktualizuje notowania HIST dla tickerów używanych w tasku.

```cmd
run_task.cmd <task>
```

liczy z lokalnej biblioteki. Nie pobiera Yahoo w czasie analizy.

Jeżeli brakuje tickera lub zakresu:

```text
BRAK NOTOWAŃ W HIST_LIBRARY_DAILY
Uruchom: refresh_quotes.cmd <task>
```

## Typowy test

```cmd
refresh_data.cmd
refresh_quotes.cmd daily_hist_smoke_3m
check_quotes.cmd daily_hist_smoke_3m
run_task.cmd daily_hist_smoke_3m
```

## Punkt wycofania

Jeżeli coś pójdzie nie tak, wracamy do:

```text
pasywnyportfel_VER_2_1_5_CLEAN_ROOT.zip
```

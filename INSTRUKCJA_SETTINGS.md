# Komplet settings.csv — uzupelnione brakujace klucze

NIE jest to README projektu (uwaga z poprzedniej wpadki) - to instrukcja
tej konkretnej paczki.

## Co naprawione

5 z 6 taskow nie mialo `analysis_mode`/`plot_currencies` w settings.csv —
GUI pokazywal "—" zamiast wartosci. `benchmark_1970_synth_usd_gross` mial
juz komplet, wiec NIE jest w tej paczce (nic do zmiany).

| Task | Dodano |
|---|---|
| bfly_10y_vs_vuds_2005 | analysis_mode=both, plot_currencies=USD,PLN |
| golden_butterfly_proxy_review_2005 | analysis_mode=both, plot_currencies=USD,PLN |
| synth_vs_etf_2005_full10 | analysis_mode=both, plot_currencies=USD,PLN |
| user_template | analysis_mode=both, plot_currencies=USD,PLN |
| daily_hist_smoke_3m | NAPRAWIONY BUG: plot_currencies,USD,PLN bez cudzyslowu |

## Dlaczego akurat te wartosci, nie zgadywane

Sprawdzone w kodzie (task_config.py): pusty analysis_mode i tak dzialal
jak "oba" (synth+hist), bo zaden z 4 taskow nie mial samego MAP_SYNTH ani
samego MAP_HIST - kazdy portfel mial oba. Wpisanie "both" tylko to nazywa,
NIE zmienia zachowania (kod sprawdza tylko czy wartosc to synth_only/
hist_only - "both" nie pasuje do zadnego, wiec dziala jak pusta wartosc
zawsze dzialala).

Plot_currencies=USD,PLN identycznie - bo wszystkie 4 maja fx+cpi_pl+
value_col_pln wypelnione, co kod (has_pln_outputs) i tak juz interpretowal
jako "dolacz PLN".

## PRAWDZIWY BUG znaleziony przy okazji w daily_hist_smoke_3m

Oryginalny plik mial `plot_currencies,USD,PLN` BEZ cudzyslowu. Prawdziwy
parser CSV (Python csv.DictReader, ktorego uzywa common.read_settings())
czyta to jako 3 kolumny przy 2-kolumnowym naglowku KEY,VALUE - VALUE
dostaje tylko "USD", ",PLN" znika po cichu. Zweryfikowane realnym
wywolaniem read_settings() - przed poprawka zwracalo ['USD'], po
poprawce ['USD', 'PLN']. To znaczy ze task milczaco NIE generowal
wynikow PLN mimo ze mial wszystkie dane do tego.

## Jak wgrac

Rozpakuj do korzenia repo, nadpisz. Zweryfikowane --dry-run na wszystkich
6 taskow (z poprawionymi plikami) na Twoim repo przed wyslaniem - wszystkie
[OK].

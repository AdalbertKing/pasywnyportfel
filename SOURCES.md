# Źródła danych Analiza Portfeli Pasywnych 1.0

Ten plik jest generowany przez `app/bin/bootstrap.py`.

## Automatycznie generowane

- `data/in/cpi/CPI_USD.csv` — FRED CPIAUCNS, przez `build_cpi_usd_fred.py`.
- `data/in/cpi/CPI_PLN_GUS.csv` — GUS CPI, przez `build_cpi_pln_gus.py`.
- `data/in/fx/DB_FX.csv` — USD/PLN. Dla PLN-real roboczą granicą metodologiczną jest 1995-01-01, czyli denominacja nowego PLN. API NBP może zwrócić dane dopiero od 2002-01-02; wtedy analiza 2005 jest dopuszczalna, ale analiza PLN-real od 1995 wymaga osobnego pełniejszego źródła FX.

## Wymagany półprodukt projektu

- `data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv` — biblioteka syntetyków miesięcznych USD.
  Jeżeli jej brakuje, bootstrap zgłasza błąd. Nie rekonstruować automatycznie bez zatwierdzonego pipeline'u, bo każdy składnik był rzeźbiony inną metodą.


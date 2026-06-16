#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.1-cpi-tail-fix
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-
"""
passive_ledger.py — punkt wejścia CLI symulatora portfela.

Logika wydzielona do:
  ledger_primitives.py — prymitywy dat, cen, resampligu
  ledger_io.py         — odczyt baz cen i CPI
  ledger_tax.py        — model podatku od strat
  ledger_engine.py     — build_event_dates + simulate_ledger
"""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil.relativedelta import relativedelta
import re

from ledger_engine import simulate_ledger

# 5 BEGIN
def main():
    p = argparse.ArgumentParser(
        description="Generator ledgeru portfela dla danych daily/weekly/monthly. FX i CPI są opcjonalne."
    )
    p.add_argument("--portfolio", required=True, help="CSV portfela: ISIN,Ticker,WEIGHT,...")
    p.add_argument("--prices", required=True, help="DB cen (np. DB_Tasty.csv)")
    p.add_argument("--fx", default=None, help="Opcjonalny DB FX (np. DB_FX.csv). Brak => nie liczy PLN i nie przycina ledgeru przez FX.")
    p.add_argument("--cpi-pl", default=None, help="Opcjonalny CPI_PLN.csv. Brak => nie liczy PLN-real i nie przycina ledgeru przez CPI_PLN.")
    p.add_argument("--cpi-us", default=None, help="Opcjonalny CPI_USD.csv. Brak => nie liczy USD-real i nie przycina ledgeru przez CPI_USD.")
    p.add_argument("--start", required=True, help="Start analizy YYYY-MM-DD")
    p.add_argument("--end", default=None, help="Koniec analizy YYYY-MM-DD (opcjonalnie)")
    p.add_argument("--freq", default="daily", choices=["daily", "weekly", "monthly", "D", "W", "M"], help="Częstotliwość ledgeru: daily/D, weekly/W, monthly/M. Ceny mogą być w tej częstotliwości albo gęstsze; skrypt sam resampluje ceny w dół.")
    p.add_argument("--saldo", type=float, default=100000.0, help="Kapitał startowy w USD (domyślnie 100000)")
    p.add_argument("--period", default="12M", help="Częstotliwość rebalansu, np. 12M, 3M, 1M")
    p.add_argument("--sma-fast", "-sma-fast", type=int, default=None, help="Opcjonalne: okno SMA FAST w barach/próbkach danej częstotliwości. Podanie razem z --sma-slow włącza SMA.")
    p.add_argument("--sma-slow", "-sma-slow", type=int, default=None, help="Opcjonalne: okno SMA SLOW w barach/próbkach danej częstotliwości. Brak obu parametrów = SMA off.")
    p.add_argument("--max-drift", type=float, default=0.0, help="Maks. dryft wagi względem celu (relatywnie). Np. 20 oznacza ±20%% celu; 0 wyłącza.")
    p.add_argument("--settle-md", default="12-31", help="Dzień rozliczenia rocznego MM-DD (domyślnie 12-31)")
    p.add_argument("--tax-mode", choices=["net", "gross"], default="gross", help="gross = bez Belki (domyślnie), net = z Belką")
    p.add_argument("--tax-base", choices=["PLN", "USD", "pln", "usd"], default="PLN", help="Waluta naliczania podatku: PLN = realna Belka z FX (domyślnie), USD = akademicki podatek od zysków liczony w USD")
    p.add_argument("--tax-rate", type=float, default=0.19, help="Stawka podatku (domyślnie 0.19)")
    p.add_argument("--loss-window-years", type=int, default=5, help="Okno strat (lata), domyślnie 5")
    p.add_argument("--loss-bucket-annual-cap", type=float, default=0.50, help="Limit roczny koszyka straty jako ułamek (domyślnie 0.50)")
    # Backward-compat: starsze wersje miały --add-real-series. W v2 serie REAL są zawsze włączone.
    p.add_argument("--add-real-series", action="store_true", help="(compat) Ignorowane; serie REAL są zawsze generowane")
    p.add_argument("--final-settle", action="store_true", help="Opcjonalnie rozlicz podatek na ostatniej dacie ledgeru, nawet jeśli rok jest niepełny")
    p.add_argument("--no-rebalance", action="store_true", help="Kup według wag mappingu na starcie i nie wykonuj rebalansów; SETTLE_YE jest tylko wierszem kontrolnym/rozliczeniowym bez transakcji.")
    p.add_argument("--conditional-rebalance", action="store_true", help="Tryb warunkowy/Atlas-like: --period jest częstotliwością screeningu, a rebalans następuje tylko po przekroczeniu relatywnego --max-drift. Brak bezwarunkowego rebalansu rocznego/miesięcznego.")
    p.add_argument("--out", required=True, help="Ścieżka pliku wynikowego CSV")
    args = p.parse_args()

    out = simulate_ledger(
        portfolio_csv=args.portfolio,
        prices_csv=args.prices,
        fx_csv=args.fx,
        cpi_pl_csv=args.cpi_pl,
        cpi_us_csv=args.cpi_us,
        start_str=args.start,
        end_str=args.end,
        saldo_usd=args.saldo,
        period=args.period,
        sma_fast=args.sma_fast,
        sma_slow=args.sma_slow,
        max_drift=args.max_drift,
        settle_md=args.settle_md,
        tax_mode=args.tax_mode,
        tax_base=args.tax_base,
        tax_rate=args.tax_rate,
        loss_window_years=args.loss_window_years,
        loss_bucket_annual_cap=args.loss_bucket_annual_cap,
        freq=args.freq,
        final_settle=args.final_settle,
        no_rebalance=args.no_rebalance,
        conditional_rebalance=args.conditional_rebalance,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"OK: zapisano {len(out)} wierszy -> {out_path}")

if __name__ == "__main__":
    main()
# 5 END

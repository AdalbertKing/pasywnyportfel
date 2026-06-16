#!/usr/bin/env python3
# pasywnyportfel — Autor koncepcji i projektu: Wojciech Król / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""ledger_io.py — odczyt baz cen i CPI (blok 2)."""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil.relativedelta import relativedelta
import re

from ledger_primitives import _parse_date, _ensure_float

# 2 BEGIN
def read_wide_db_csv(path: str) -> Tuple[Dict[str, List[str]], pd.DataFrame]:
    """
    Czyta format DB_*.csv używany w projekcie:
    - kilka wierszy metadanych: ASSET/TICKER/ISIN/COST/NAME...
    - potem wiersze dzienne: YYYY-MM-DD, price1, price2, ...
    Zwraca:
    - meta: dict[name -> list wartości per kolumna-instrument]
    - df: DataFrame (index=date, columns=tickery z wiersza TICKER)
    """
    meta_rows: List[List[str]] = []
    data_rows: List[List[str]] = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            d = _parse_date(row[0])
            if d is None:
                meta_rows.append(row)
            else:
                data_rows.append(row)

    if not meta_rows:
        raise ValueError(f"Brak metadanych w pliku {path}")

    header = meta_rows[0]
    ncols = len(header)
    meta: Dict[str, List[str]] = {}
    for r in meta_rows:
        if len(r) != ncols:
            r = (r + [""] * ncols)[:ncols]
        key = (r[0] or "").strip()
        if key:
            meta[key] = r[1:]

    tickers = meta.get("TICKER")
    if not tickers:
        # Fallback: niektóre pliki (np. DB_FX.csv) nie mają wiersza TICKER.
        # Wtedy traktujemy nagłówek (pierwszy wiersz metadanych) jako listę tickerów/kolumn.
        tickers = header[1:]
        tickers = [(t or "").strip() for t in tickers]
        if not tickers or any(t == "" for t in tickers):
            raise ValueError(f"Brak wiersza TICKER i niepoprawny nagłówek w pliku {path}")
        meta["TICKER"] = tickers
    else:
        tickers = [(t or "").strip() for t in tickers]

    dates: List[dt.date] = []
    values: List[List[Optional[float]]] = []
    for r in data_rows:
        if len(r) != ncols:
            r = (r + [""] * ncols)[:ncols]
        d = _parse_date(r[0])
        if d is None:
            continue
        row_vals = [_ensure_float(x) for x in r[1:]]
        dates.append(d)
        values.append(row_vals)

    df = pd.DataFrame(values, index=pd.to_datetime(dates), columns=tickers)
    df.index.name = "DATE"
    return meta, df


def read_cpi_csv(path: str) -> pd.DataFrame:
    """
    Oczekiwany format: date,cpi[,infl_mom][,infl_yoy] (miesięczne, date = YYYY-MM-01).
    Jeśli infl_mom / infl_yoy brakują, policzymy je.
    """
    cpi = pd.read_csv(path)
    if "date" not in cpi.columns or "cpi" not in cpi.columns:
        raise ValueError(f"Zły format CPI: {path} (wymagane kolumny: date,cpi)")
    cpi["date"] = pd.to_datetime(cpi["date"])
    cpi = cpi.sort_values("date").set_index("date")
    cpi["cpi"] = pd.to_numeric(cpi["cpi"], errors="coerce").ffill()
    if "infl_mom" not in cpi.columns:
        cpi["infl_mom"] = cpi["cpi"].pct_change()
    else:
        cpi["infl_mom"] = pd.to_numeric(cpi["infl_mom"], errors="coerce")
        cpi["infl_mom"] = cpi["infl_mom"].where(cpi["infl_mom"].notna(), cpi["cpi"].pct_change())
    if "infl_yoy" not in cpi.columns:
        cpi["infl_yoy"] = cpi["cpi"].pct_change(12)
    else:
        cpi["infl_yoy"] = pd.to_numeric(cpi["infl_yoy"], errors="coerce")
        cpi["infl_yoy"] = cpi["infl_yoy"].where(cpi["infl_yoy"].notna(), cpi["cpi"].pct_change(12))
    return cpi[["cpi", "infl_mom", "infl_yoy"]]
# 2 END

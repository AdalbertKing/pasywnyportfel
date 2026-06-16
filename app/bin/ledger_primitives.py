#!/usr/bin/env python3
# pasywnyportfel — Autor koncepcji i projektu: Wojciech Król / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""ledger_primitives.py — prymitywy dat, cen i resampligu (blok 1)."""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil.relativedelta import relativedelta
import re

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 1 BEGIN
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _parse_date(s: str) -> Optional[dt.date]:
    s = (s or "").strip()
    if not DATE_RE.match(s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None

def _last_day_of_month(d: dt.date) -> dt.date:
    first = d.replace(day=1)
    next_month = first + relativedelta(months=1)
    return next_month - dt.timedelta(days=1)

def _ensure_float(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s == "":
        return None
    try:
        return float(s)
    except Exception:
        return None

def _safe_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0

def _normalize_freq(freq: str) -> str:
    f = (freq or "daily").strip().lower()
    aliases = {
        "d": "daily",
        "daily": "daily",
        "w": "weekly",
        "weekly": "weekly",
        "m": "monthly",
        "monthly": "monthly",
    }
    if f not in aliases:
        raise ValueError(f"Nieprawidłowe --freq={freq}; użyj daily/weekly/monthly albo D/W/M.")
    return aliases[f]



def _infer_price_freq(index: pd.DatetimeIndex) -> str:
    """
    Szacuje częstotliwość wejściowego DB cen po medianie odstępów dat.
    Służy tylko do blokowania niebezpiecznego upsamplingu, np. monthly -> weekly.
    """
    idx = pd.DatetimeIndex(index).dropna().sort_values().unique()
    if len(idx) < 3:
        return "unknown"
    diffs = pd.Series(idx).diff().dropna().dt.days
    if diffs.empty:
        return "unknown"
    med = float(diffs.median())
    if med <= 4.0:
        return "daily"
    if med <= 10.0:
        return "weekly"
    return "monthly"


def _freq_rank(freq: str) -> int:
    return {"daily": 0, "weekly": 1, "monthly": 2}[_normalize_freq(freq)]


def _resample_prices_to_freq(prices: pd.DataFrame, tickers: List[str], freq: str) -> pd.DataFrame:
    """
    Przygotowuje kalendarz cen pod żądaną częstotliwość ledgeru.

    Zasada:
      - daily: bez resamplingu,
      - weekly: ostatni kompletny wiersz cen w tygodniu W-FRI,
      - monthly: ostatni kompletny wiersz cen w miesiącu.

    Nie wykonujemy upsamplingu. DB dzienny można użyć dla weekly/monthly,
    DB weekly można użyć dla monthly, ale DB monthly nie może udawać weekly/daily.
    """
    freq = _normalize_freq(freq)
    px = prices[tickers].copy().sort_index()
    px.index = pd.to_datetime(px.index)
    px = px[~px.index.duplicated(keep="last")].sort_index()

    source_freq = _infer_price_freq(px.dropna(how="all").index)
    if source_freq != "unknown" and _freq_rank(source_freq) > _freq_rank(freq):
        raise ValueError(
            f"Niepoprawna kombinacja: --freq {freq}, ale plik cen wygląda na {source_freq}. "
            f"Nie robię upsamplingu. Użyj DB o częstotliwości {freq} albo gęstszej."
        )

    if freq == "daily":
        return px

    complete = px.dropna(subset=tickers)
    if complete.empty:
        raise ValueError("Brak kompletnych wierszy cen do resamplingu.")

    if freq == "weekly":
        groups = complete.index.to_period("W-FRI")
    elif freq == "monthly":
        groups = complete.index.to_period("M")
    else:
        raise ValueError(f"Nieobsługiwana częstotliwość: {freq}")

    out = complete.groupby(groups, group_keys=False).tail(1).sort_index()
    out.index.name = "DATE"
    if out.empty:
        raise ValueError(f"Resampling cen do --freq={freq} zwrócił pustą ramkę.")
    return out



def _previous_month_end(d: dt.date) -> dt.date:
    first = d.replace(day=1)
    return first - dt.timedelta(days=1)

def _pick_last_available_in_period(index: pd.DatetimeIndex, period_start: dt.date, period_end: dt.date) -> Optional[dt.date]:
    idx = index.sort_values()
    mask = (idx.date >= period_start) & (idx.date <= period_end)
    if not mask.any():
        return None
    return idx[mask][-1].date()

def _effective_ledger_end(index: pd.DatetimeIndex, freq: str, end_ref: dt.date) -> dt.date:
    """
    Wyznacza faktyczną ostatnią datę ledgeru.

    Zasada:
      - daily: ostatnia dostępna data <= end_ref,
      - weekly: ostatnia dostępna sesja w ostatnim pełnym tygodniu zakończonym w piątek <= end_ref,
      - monthly: ostatnia dostępna sesja w ostatnim pełnym miesiącu <= end_ref.

    Jeśli kalendarzowy koniec tygodnia/miesiąca wypada w dzień bez notowań,
    wybieramy ostatnią dostępną sesję z tego okresu.
    """
    freq = _normalize_freq(freq)
    if index.empty:
        raise ValueError("Brak dat do wyznaczenia końca ledgeru.")

    idx = index.sort_values()

    if freq == "daily":
        candidates = idx[idx.date <= end_ref]
        if len(candidates) == 0:
            raise ValueError(f"Brak danych <= end_ref={end_ref.isoformat()}.")
        return candidates[-1].date()

    if freq == "weekly":
        # Python: Monday=0 ... Friday=4 ... Sunday=6
        days_since_friday = (end_ref.weekday() - 4) % 7
        period_end = end_ref - dt.timedelta(days=days_since_friday)
        while True:
            period_start = period_end - dt.timedelta(days=6)
            picked = _pick_last_available_in_period(idx, period_start, period_end)
            if picked is not None:
                return picked
            period_end -= dt.timedelta(days=7)
            if period_end < idx[0].date():
                raise ValueError("Brak danych w pełnych tygodniach przed end_ref.")

    if freq == "monthly":
        current_month_end = _last_day_of_month(end_ref)
        if end_ref >= current_month_end:
            period_end = current_month_end
        else:
            period_end = _previous_month_end(end_ref)
        while True:
            period_start = period_end.replace(day=1)
            picked = _pick_last_available_in_period(idx, period_start, period_end)
            if picked is not None:
                return picked
            period_end = _previous_month_end(period_end)
            if period_end < idx[0].date():
                raise ValueError("Brak danych w pełnych miesiącach przed end_ref.")

    raise ValueError(f"Nieobsługiwana częstotliwość: {freq}")

def _attach_fx_to_prices(prices: pd.DataFrame, fx: pd.DataFrame, tickers: List[str], freq: str) -> pd.DataFrame:
    """
    Łączy ceny ETF z USD/PLN.

    daily:
      - zachowuje starą logikę inner join po dokładnej dacie, aby test regresyjny daily
        był maksymalnie zgodny z poprzednimi wersjami.

    weekly/monthly:
      - kalendarzem głównym są daty cen ETF,
      - FX dopinamy jako ostatni znany USD/PLN <= data wyceny portfela,
      - nie używamy przyszłego FX, więc nie ma look-ahead.
    """
    freq = _normalize_freq(freq)
    prices_part = prices[tickers].sort_index()
    fx_part = fx[["USD/PLN"]].dropna().sort_index()

    if freq == "daily":
        df = prices_part.join(fx_part, how="inner")
        df = df.dropna(subset=tickers + ["USD/PLN"]).sort_index()
        if df.empty:
            raise ValueError("Brak wspólnych sesji z kompletem danych (prices+fx).")
        return df

    px = prices_part.dropna(subset=tickers).sort_index().reset_index().rename(columns={"DATE": "DATE"})
    fxr = fx_part.reset_index().rename(columns={"DATE": "DATE"})

    df = pd.merge_asof(
        px,
        fxr,
        on="DATE",
        direction="backward",
        allow_exact_matches=True,
    )
    df = df.set_index("DATE").sort_index()
    df.index.name = "DATE"
    df = df.dropna(subset=tickers + ["USD/PLN"])
    if df.empty:
        raise ValueError(
            "Brak danych po dopięciu FX metodą last-known <= date. "
            "Sprawdź zakres DB_FX.csv względem bazy cen."
        )
    return df
# 1 END

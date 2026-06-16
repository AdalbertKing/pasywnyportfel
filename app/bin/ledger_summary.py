#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import glob
import os
import sys
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

VERSION = "1.3-short-period-return-safe"

DATE_CANDIDATES = ["DATE", "Date", "DATA", "Data", "DATETIME", "Datetime"]
DEFAULT_NOM_COL = "TOTAL_USD_POST"
DEFAULT_REAL_COL = "TOTAL_USD_POST_REAL"


def expand_paths(patterns: List[str]) -> List[str]:
    out: List[str] = []
    for p in patterns:
        matches = glob.glob(p)
        if matches:
            out.extend(matches)
        elif os.path.exists(p):
            out.append(p)
        else:
            print(f"WARN: nie znaleziono pliku/wzorca: {p}", file=sys.stderr)
    seen = set()
    uniq = []
    for p in out:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            uniq.append(p)
    return uniq


def find_date_col(df: pd.DataFrame) -> str:
    for c in DATE_CANDIDATES:
        if c in df.columns:
            return c
    for c in df.columns:
        if str(c).strip().upper() in {"DATE", "DATA", "DATETIME"}:
            return c
    raise ValueError("Nie znaleziono kolumny daty. Oczekuję DATE/Data/DATA/DATETIME.")


def infer_name(path: str, strip_prefix: str = "ledger_", strip_suffix: str = ".csv") -> str:
    base = os.path.basename(path)
    if strip_suffix and base.lower().endswith(strip_suffix.lower()):
        base = base[: -len(strip_suffix)]
    if strip_prefix and base.startswith(strip_prefix):
        base = base[len(strip_prefix):]
    return base


def max_drawdown_and_recovery(dates: pd.Series, values: pd.Series) -> Tuple[float, Optional[pd.Timestamp], Optional[pd.Timestamp], Optional[pd.Timestamp], Optional[int]]:
    s = pd.Series(pd.to_numeric(values, errors="coerce").to_numpy(), index=pd.to_datetime(dates))
    s = s.dropna()
    if len(s) < 2:
        return np.nan, None, None, None, None

    cummax = s.cummax()
    dd = s / cummax - 1.0
    trough_date = dd.idxmin()
    maxdd = float(dd.loc[trough_date])

    before = s.loc[:trough_date]
    peak_value = float(before.cummax().loc[trough_date])
    peak_candidates = before[before >= peak_value * (1.0 - 1e-12)]
    peak_date = peak_candidates.index[-1] if len(peak_candidates) else before.idxmax()

    after = s.loc[trough_date:]
    rec = after[after >= peak_value * (1.0 - 1e-12)]
    recovery_date = rec.index[0] if len(rec) else None
    recovery_months = None
    if recovery_date is not None:
        recovery_months = int(round((recovery_date - peak_date).days / 30.4375))

    return maxdd, peak_date, trough_date, recovery_date, recovery_months


def cagr(dates: pd.Series, values: pd.Series) -> float:
    d = pd.to_datetime(dates)
    v = pd.to_numeric(values, errors="coerce")
    mask = d.notna() & v.notna()
    d = d[mask].reset_index(drop=True)
    v = v[mask].reset_index(drop=True)
    if len(v) < 2 or v.iloc[0] <= 0:
        return np.nan
    years = (d.iloc[-1] - d.iloc[0]).days / 365.25
    if years <= 0:
        return np.nan
    return float((v.iloc[-1] / v.iloc[0]) ** (1.0 / years) - 1.0)



def total_return(values: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce").dropna().reset_index(drop=True)
    if len(v) < 2 or v.iloc[0] <= 0:
        return np.nan
    return float(v.iloc[-1] / v.iloc[0] - 1.0)


def years_between(dates: pd.Series) -> float:
    d = pd.to_datetime(dates, errors="coerce").dropna().reset_index(drop=True)
    if len(d) < 2:
        return np.nan
    return float((d.iloc[-1] - d.iloc[0]).days / 365.25)


def days_between(dates: pd.Series) -> int:
    d = pd.to_datetime(dates, errors="coerce").dropna().reset_index(drop=True)
    if len(d) < 2:
        return 0
    return int((d.iloc[-1] - d.iloc[0]).days)


def ann_stdev(values: pd.Series, periods_per_year: float = 12.0) -> float:
    v = pd.to_numeric(values, errors="coerce").dropna()
    if len(v) < 3:
        return np.nan
    r = v.pct_change().dropna()
    if len(r) < 2:
        return np.nan
    return float(r.std(ddof=1) * np.sqrt(periods_per_year))


def infer_periods_per_year(df: pd.DataFrame, dcol: str) -> float:
    if "FREQ" in df.columns:
        vals = df["FREQ"].dropna().astype(str).str.lower().str.strip()
        if not vals.empty:
            f = vals.mode().iloc[0]
            if f.startswith("d"):
                return 252.0
            if f.startswith("w"):
                return 52.0
            if f.startswith("m"):
                return 12.0
    d = pd.to_datetime(df[dcol], errors="coerce").dropna().sort_values()
    if len(d) < 3:
        return 12.0
    med_days = d.diff().dropna().dt.days.median()
    if med_days <= 4:
        return 252.0
    if med_days <= 10:
        return 52.0
    return 12.0


def filtered_dates_values(df: pd.DataFrame, dcol: str, col: str) -> Tuple[pd.Series, pd.Series]:
    d = pd.to_datetime(df[dcol], errors="coerce")
    v = pd.to_numeric(df[col], errors="coerce")
    mask = d.notna() & v.notna() & (v > 0)
    return d[mask].reset_index(drop=True), v[mask].reset_index(drop=True)


def summarize_one(path: str, name: Optional[str] = None, value_col: Optional[str] = None, nom_col: Optional[str] = None) -> dict:
    df = pd.read_csv(path)
    dcol = find_date_col(df)
    df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
    df = df.dropna(subset=[dcol]).sort_values(dcol).reset_index(drop=True)
    dates = df[dcol]

    # Try to be helpful for PLN/ USD use cases.
    if value_col is None:
        value_col = DEFAULT_REAL_COL
    if nom_col is None:
        if value_col == "TOTAL_PLN_POST_REAL" and "TOTAL_PLN_POST" in df.columns:
            nom_col = "TOTAL_PLN_POST"
        elif value_col == "TOTAL_USD_POST_REAL" and "TOTAL_USD_POST" in df.columns:
            nom_col = "TOTAL_USD_POST"
        elif DEFAULT_NOM_COL in df.columns:
            nom_col = DEFAULT_NOM_COL
        else:
            nom_col = value_col

    missing = [c for c in [value_col, nom_col] if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: brak kolumn: {missing}. Dostępne: {list(df.columns)}")

    value_dates, value = filtered_dates_values(df, dcol, value_col)
    nom_dates, nom = filtered_dates_values(df, dcol, nom_col)
    periods_per_year = infer_periods_per_year(df, dcol)

    dd_value, peak_value, trough_value, rec_value, months_value = max_drawdown_and_recovery(value_dates, value)
    dd_nom, peak_nom, trough_nom, rec_nom, months_nom = max_drawdown_and_recovery(nom_dates, nom)

    value_has = len(value) > 0
    nom_has = len(nom) > 0
    value_years = years_between(value_dates) if value_has else np.nan
    nom_years = years_between(nom_dates) if nom_has else np.nan

    row = {
        "PORTFEL": name or infer_name(path),
        "PLIK": path,
        "VALUE_COL": value_col,
        "NOM_COL": nom_col,
        "START": value_dates.iloc[0].date().isoformat() if value_has else "",
        "END": value_dates.iloc[-1].date().isoformat() if value_has else "",
        "ROWS": int(len(value)),
        "DAYS": days_between(value_dates) if value_has else 0,
        "YEARS": round(value_years, 6) if value_has and np.isfinite(value_years) else np.nan,
        "NOM_START": nom_dates.iloc[0].date().isoformat() if nom_has else "",
        "NOM_END": nom_dates.iloc[-1].date().isoformat() if nom_has else "",
        "NOM_ROWS": int(len(nom)),
        "NOM_DAYS": days_between(nom_dates) if nom_has else 0,
        "NOM_YEARS": round(nom_years, 6) if nom_has and np.isfinite(nom_years) else np.nan,
        "PERIODS_PER_YEAR": periods_per_year,
        "RETURN_%": round(total_return(value) * 100.0, 3) if value_has else np.nan,
        "RETURN_NOM_%": round(total_return(nom) * 100.0, 3) if nom_has else np.nan,
        "CAGR_%": round(cagr(value_dates, value) * 100.0, 3) if value_has else np.nan,
        "MAXDD_%": round(dd_value * 100.0, 3) if value_has else np.nan,
        "DD_PEAK": peak_value.date().isoformat() if peak_value is not None else "",
        "DD_TROUGH": trough_value.date().isoformat() if trough_value is not None else "",
        "DD_RECOVERY": rec_value.date().isoformat() if rec_value is not None else "",
        "MONTHS_TO_RECOVERY": months_value if months_value is not None else "",
        "STDEV_%": round(ann_stdev(value, periods_per_year) * 100.0, 3) if value_has else np.nan,
        "END_VALUE": round(float(value.iloc[-1]), 2) if value_has else np.nan,
        "CAGR_NOM_%": round(cagr(nom_dates, nom) * 100.0, 3) if nom_has else np.nan,
        "MAXDD_NOM_%": round(dd_nom * 100.0, 3) if nom_has else np.nan,
        "DD_NOM_PEAK": peak_nom.date().isoformat() if peak_nom is not None else "",
        "DD_NOM_TROUGH": trough_nom.date().isoformat() if trough_nom is not None else "",
        "DD_NOM_RECOVERY": rec_nom.date().isoformat() if rec_nom is not None else "",
        "MONTHS_TO_RECOVERY_NOM": months_nom if months_nom is not None else "",
        "STDEV_NOM_%": round(ann_stdev(nom, periods_per_year) * 100.0, 3) if nom_has else np.nan,
        "END_NOM": round(float(nom.iloc[-1]), 2) if nom_has else np.nan,
    }

    # Backward-compatible aliases when summarizing the old default USD-real column.
    if value_col == DEFAULT_REAL_COL:
        row.update({
            "RETURN_REAL_%": row["RETURN_%"],
            "CAGR_REAL_%": row["CAGR_%"],
            "MAXDD_REAL_%": row["MAXDD_%"],
            "DD_REAL_PEAK": row["DD_PEAK"],
            "DD_REAL_TROUGH": row["DD_TROUGH"],
            "DD_REAL_RECOVERY": row["DD_RECOVERY"],
            "MONTHS_TO_RECOVERY_REAL": row["MONTHS_TO_RECOVERY"],
            "END_REAL": row["END_VALUE"],
        })

    return row


def parse_names(names_arg: Optional[str], n: int) -> List[Optional[str]]:
    if not names_arg:
        return [None] * n
    names = [x.strip() for x in names_arg.split(",")]
    if len(names) != n:
        raise SystemExit(f"--names ma {len(names)} nazw, a ledgerów jest {n}. Liczby muszą być zgodne.")
    return names


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=f"ledger_summary.py {VERSION} — tabela metryk z ledgerów")
    p.add_argument("ledgers", nargs="+", help="Pliki ledger CSV albo wzorce glob, np. .\\bfly\\ledger_*.csv")
    p.add_argument("--out", default="ledger_summary.csv", help="CSV wynikowy")
    p.add_argument("--sort", default="AUTO", help="Kolumna sortowania: AUTO, RETURN_%, CAGR_%, MAXDD_%, MONTHS_TO_RECOVERY")
    p.add_argument("--ascending", action="store_true", help="Sortuj rosnąco; domyślnie malejąco")
    p.add_argument("--names", default=None, help="Opcjonalne nazwy portfeli rozdzielone przecinkiem, w kolejności ledgerów")
    p.add_argument("--sep", default=",", help="Separator CSV wyjściowego; domyślnie przecinek")
    p.add_argument("--value-col", default=DEFAULT_REAL_COL, help="Kolumna wartości do CAGR/MaxDD/STDEV, np. TOTAL_PLN_POST_REAL albo TOTAL_USD_POST_REAL")
    p.add_argument("--nom-col", default=None, help="Kolumna nominalna pomocnicza; domyślnie dobierana do --value-col")
    args = p.parse_args(argv)

    paths = expand_paths(args.ledgers)
    if not paths:
        raise SystemExit("ERROR: nie znaleziono żadnego ledgera.")

    names = parse_names(args.names, len(paths))
    rows = []
    for path, name in zip(paths, names):
        try:
            rows.append(summarize_one(path, name=name, value_col=args.value_col, nom_col=args.nom_col))
        except Exception as e:
            print(f"ERROR: {path}: {e}", file=sys.stderr)
            raise

    out = pd.DataFrame(rows)
    sort_col = args.sort
    if sort_col and str(sort_col).upper() == "AUTO":
        yrs = pd.to_numeric(out.get("YEARS", pd.Series(dtype=float)), errors="coerce")
        short_period = yrs.notna().any() and float(yrs.max()) < 1.0
        sort_col = "RETURN_%" if short_period and "RETURN_%" in out.columns else "CAGR_%"
    if sort_col:
        if sort_col not in out.columns:
            cols = ", ".join(out.columns)
            raise SystemExit(f"ERROR: nie ma kolumny sortowania '{sort_col}'. Dostępne: {cols}")
        out = out.sort_values(sort_col, ascending=args.ascending, kind="mergesort")

    out.to_csv(args.out, index=False, encoding="utf-8-sig", sep=args.sep)
    print(f"OK: ledger_summary.py {VERSION}")
    print(f"OK: ledgers={len(paths)}; out={args.out}; value_col={args.value_col}; sort={args.sort}; ascending={args.ascending}")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

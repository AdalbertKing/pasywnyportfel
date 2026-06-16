#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import math
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

VERSION = "1.0"


def _fmt_pct(x: Optional[float]) -> Optional[float]:
    if x is None or pd.isna(x):
        return None
    return float(x) * 100.0


def _max_drawdown(series: pd.Series) -> Tuple[float, pd.Timestamp, pd.Timestamp, Optional[pd.Timestamp]]:
    s = series.dropna().astype(float)
    if s.empty:
        return float("nan"), pd.NaT, pd.NaT, pd.NaT
    running_peak = s.cummax()
    dd = s / running_peak - 1.0
    trough_date = dd.idxmin()
    max_dd = float(dd.loc[trough_date])
    peak_date = s.loc[:trough_date].idxmax()
    peak_val = float(s.loc[peak_date])
    recovery_date = pd.NaT
    if peak_val > 0:
        after = s.loc[trough_date:]
        recovered = after[after >= peak_val]
        if not recovered.empty:
            recovery_date = recovered.index[0]
    return max_dd, peak_date, trough_date, recovery_date


def _safe_cagr(start_val: float, end_val: float, years: float) -> Optional[float]:
    if start_val <= 0 or end_val <= 0 or years <= 0:
        return None
    return (end_val / start_val) ** (1.0 / years) - 1.0


def scan_windows(df: pd.DataFrame, column: str, window_years: float, step_months: int) -> pd.DataFrame:
    if "DATE" not in df.columns:
        raise ValueError("Ledger nie ma kolumny DATE.")
    if column not in df.columns:
        raise ValueError(f"Ledger nie ma kolumny {column!r}.")

    d = df[["DATE", column]].copy()
    d["DATE"] = pd.to_datetime(d["DATE"], errors="coerce")
    d[column] = pd.to_numeric(d[column], errors="coerce")
    d = d.dropna(subset=["DATE", column]).sort_values("DATE")
    d = d[d[column] > 0]
    if len(d) < 2:
        raise ValueError("Za mało poprawnych wartości do analizy.")
    d = d.drop_duplicates(subset=["DATE"], keep="last").set_index("DATE")
    dates = d.index

    rows = []
    i = 0
    while i < len(dates):
        start_date = dates[i]
        target_end = start_date + pd.DateOffset(months=int(round(window_years * 12)))
        j = dates.searchsorted(target_end, side="left")
        if j >= len(dates):
            break
        end_date = dates[j]
        start_val = float(d.iloc[i][column])
        end_val = float(d.loc[end_date, column])
        if start_val <= 0 or end_val <= 0:
            i += max(1, step_months)
            continue

        window = d.loc[start_date:end_date, column]
        elapsed_years = (end_date - start_date).days / 365.2425
        cagr = _safe_cagr(start_val, end_val, elapsed_years)
        total_return = end_val / start_val - 1.0
        max_dd, peak_date, trough_date, recovery_date = _max_drawdown(window)

        months_to_recovery = None
        if pd.notna(recovery_date) and pd.notna(peak_date):
            months_to_recovery = (recovery_date.year - peak_date.year) * 12 + (recovery_date.month - peak_date.month)

        rows.append({
            "START": start_date.date().isoformat(),
            "END": end_date.date().isoformat(),
            "YEARS": round(elapsed_years, 3),
            "START_VALUE": start_val,
            "END_VALUE": end_val,
            "TOTAL_RETURN_%": _fmt_pct(total_return),
            "CAGR_%": _fmt_pct(cagr),
            "MAX_DD_%": _fmt_pct(max_dd),
            "DD_PEAK_DATE": peak_date.date().isoformat() if pd.notna(peak_date) else "",
            "DD_TROUGH_DATE": trough_date.date().isoformat() if pd.notna(trough_date) else "",
            "DD_RECOVERY_DATE": recovery_date.date().isoformat() if pd.notna(recovery_date) else "",
            "MONTHS_TO_RECOVERY": months_to_recovery,
            "LOST_NOMINAL_OR_REAL": bool(total_return <= 0.0),
        })
        i += max(1, step_months)

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("Nie znaleziono pełnych okien dla podanego window-years.")
    out = out.sort_values(["CAGR_%", "TOTAL_RETURN_%", "MAX_DD_%"], ascending=[True, True, True]).reset_index(drop=True)
    out.insert(0, "RANK", range(1, len(out) + 1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Skaner straconych dekad / rolling windows dla ledgerów pasywnych.")
    ap.add_argument("--ledger", required=True, help="Plik ledger CSV")
    ap.add_argument("--column", default="TOTAL_USD_POST_REAL", help="Kolumna do analizy, np. TOTAL_USD_POST_REAL albo TOTAL_USD_POST")
    ap.add_argument("--window-years", type=float, default=10.0, help="Długość okna w latach, np. 10, 15, 20")
    ap.add_argument("--step-months", type=int, default=1, help="Krok przesuwania okna w miesiącach/próbkach; dla monthly zwykle 1")
    ap.add_argument("--top", type=int, default=25, help="Ile najgorszych okien wypisać na ekran")
    ap.add_argument("--out", required=True, help="Wyjściowy CSV z rankingiem okien")
    args = ap.parse_args()

    df = pd.read_csv(args.ledger)
    result = scan_windows(df, args.column, args.window_years, args.step_months)
    result.to_csv(args.out, index=False, encoding="utf-8")

    print(f"OK: scan_lost_decades.py {VERSION}")
    print(f"OK: ledger={args.ledger}; column={args.column}; window_years={args.window_years}; windows={len(result)}")
    print(f"OK: zapisano {args.out}")
    print(result.head(max(1, args.top)).to_string(index=False))


if __name__ == "__main__":
    main()

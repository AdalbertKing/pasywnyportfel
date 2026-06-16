#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-

VERSION = "crash_by_portfolio.py 1.1"

import argparse
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

LOG_SCALE_CRASH_PLOTS = True


def pct_axis_formatter(x, pos):
    try:
        return f"{x:.0f}%"
    except Exception:
        return ""


import pandas as pd


def safe_token(s: str) -> str:
    repl = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o",
        "ś": "s", "ż": "z", "ź": "z", "&": "and",
    }
    s = str(s).strip().lower()
    for a, b in repl.items():
        s = s.replace(a, b)
    out = []
    for ch in s:
        if ch.isalnum() or ch in ["_", "-"]:
            out.append(ch)
        elif ch in [" ", "/", "\\", ":", ";", ",", "|", "(", ")"]:
            out.append("_")
        else:
            out.append("_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_-")


def norm_key(s: str) -> str:
    return safe_token(s).replace("_", "").replace("-", "").upper()


def parse_series_arg(arg: str) -> Tuple[str, Path]:
    if "=" not in arg:
        raise ValueError(f"Niepoprawny argument serii {arg!r}. Oczekuję LABEL=ledger.csv")
    label, path = arg.split("=", 1)
    return label.strip(), Path(path)


def load_series(path: Path, column: str) -> pd.Series:
    df = pd.read_csv(path)
    if "DATE" not in df.columns:
        raise ValueError(f"{path}: brak kolumny DATE.")
    if column not in df.columns:
        raise ValueError(f"{path}: brak kolumny {column}.")
    d = df[["DATE", column]].copy()
    d["DATE"] = pd.to_datetime(d["DATE"], errors="coerce")
    d[column] = pd.to_numeric(d[column], errors="coerce")
    d = d.dropna(subset=["DATE", column]).sort_values("DATE")
    d = d[d[column] > 0]
    d = d.drop_duplicates(subset=["DATE"], keep="last").set_index("DATE")
    if d.empty:
        raise ValueError(f"{path}: brak poprawnych wartości w kolumnie {column}.")
    return d[column].astype(float)


def max_drawdown(series: pd.Series) -> Tuple[float, pd.Timestamp, pd.Timestamp, Optional[pd.Timestamp]]:
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


def safe_cagr(start_val: float, end_val: float, years: float) -> Optional[float]:
    if start_val <= 0 or end_val <= 0 or years <= 0:
        return None
    return (end_val / start_val) ** (1.0 / years) - 1.0


def window_metrics(series: pd.Series, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict[str, object]:
    s = series.dropna().sort_index()
    w = s.loc[start_date:end_date]
    if len(w) < 2:
        return {}
    actual_start = w.index[0]
    actual_end = w.index[-1]
    start_val = float(w.iloc[0])
    end_val = float(w.iloc[-1])
    years = (actual_end - actual_start).days / 365.2425
    total_return = end_val / start_val - 1.0
    cagr = safe_cagr(start_val, end_val, years)
    max_dd, peak_date, trough_date, recovery_date = max_drawdown(w)
    months_to_recovery = None
    if pd.notna(recovery_date) and pd.notna(peak_date):
        months_to_recovery = (recovery_date.year - peak_date.year) * 12 + (recovery_date.month - peak_date.month)
    return {
        "START": actual_start.date().isoformat(),
        "END": actual_end.date().isoformat(),
        "YEARS": round(years, 3),
        "START_VALUE": start_val,
        "END_VALUE": end_val,
        "TOTAL_RETURN_%": total_return * 100.0,
        "CAGR_%": None if cagr is None else cagr * 100.0,
        "MAX_DD_%": max_dd * 100.0,
        "DD_PEAK_DATE": peak_date.date().isoformat() if pd.notna(peak_date) else "",
        "DD_TROUGH_DATE": trough_date.date().isoformat() if pd.notna(trough_date) else "",
        "DD_RECOVERY_DATE": recovery_date.date().isoformat() if pd.notna(recovery_date) else "",
        "MONTHS_TO_RECOVERY": months_to_recovery,
    }


def find_worst_window(series: pd.Series, window_years: float, step_months: int = 1) -> Dict[str, object]:
    s = series.dropna().sort_index()
    dates = s.index
    best = None
    i = 0
    while i < len(dates):
        start_date = dates[i]
        target_end = start_date + pd.DateOffset(months=int(round(window_years * 12)))
        j = dates.searchsorted(target_end, side="left")
        if j >= len(dates):
            break
        end_date = dates[j]
        m = window_metrics(s, start_date, end_date)
        if m:
            if best is None:
                best = m
            else:
                key = (
                    float(m.get("CAGR_%")) if m.get("CAGR_%") is not None else math.inf,
                    float(m.get("TOTAL_RETURN_%")) if m.get("TOTAL_RETURN_%") is not None else math.inf,
                    float(m.get("MAX_DD_%")) if m.get("MAX_DD_%") is not None else math.inf,
                )
                best_key = (
                    float(best.get("CAGR_%")) if best.get("CAGR_%") is not None else math.inf,
                    float(best.get("TOTAL_RETURN_%")) if best.get("TOTAL_RETURN_%") is not None else math.inf,
                    float(best.get("MAX_DD_%")) if best.get("MAX_DD_%") is not None else math.inf,
                )
                if key < best_key:
                    best = m
        i += max(1, step_months)
    if best is None:
        raise ValueError(f"Nie znaleziono pełnego okna {window_years}Y.")
    return best


def normalize_window(series: pd.Series, start: str, end: str) -> pd.Series:
    s = series.dropna().sort_index()
    w = s.loc[pd.to_datetime(start):pd.to_datetime(end)]
    if w.empty:
        return w
    return w / float(w.iloc[0]) * 100.0


def series_kind(label: str) -> str:
    n = norm_key(label)
    if "HIST" in n:
        return "HIST"
    if "SYN" in n:
        return "SYN"
    return ""


def is_sp500(label: str) -> bool:
    n = norm_key(label)
    return "SP500" in n or "SP" in n and "500" in n or "SANDP500" in n


def is_6040(label: str) -> bool:
    n = norm_key(label)
    return "6040" in n or "60" in n and "40" in n and "US" in n


def pick_one(labels: List[str], predicate, preferred_kind: str, exclude: str) -> Optional[str]:
    candidates = [x for x in labels if x != exclude and predicate(x)]
    if preferred_kind:
        same = [x for x in candidates if series_kind(x) == preferred_kind]
        if same:
            return same[0]
    return candidates[0] if candidates else None


def choose_benchmarks(label: str, all_series: Dict[str, pd.Series]) -> List[str]:
    labels = list(all_series.keys())
    kind = series_kind(label)
    selected = []

    sp = pick_one(labels, is_sp500, kind, label)
    if sp:
        selected.append(sp)

    us6040 = pick_one(labels, is_6040, kind, label)
    if us6040 and us6040 not in selected:
        selected.append(us6040)

    return selected[:2]


def plot_window(
    focus_label: str,
    labels_to_plot: List[str],
    all_series: Dict[str, pd.Series],
    start: str,
    end: str,
    title: str,
    out_png: Path,
):
    plt.figure(figsize=(11.5, 6.5))
    for label in labels_to_plot:
        norm = normalize_window(all_series[label], start, end)
        if norm.empty:
            continue
        lw = 3.0 if label == focus_label else 1.9
        plt.plot(norm.index, norm.values, linewidth=lw, label=label)

    plt.axhline(100.0, linestyle="--", linewidth=1.0)
    plt.title(title)
    plt.ylabel("Start okna = 100%, log scale")
    plt.xlabel("Data")
    plt.grid(True, alpha=0.25)
    plt.yscale("log")
    plt.gca().yaxis.set_major_formatter(FuncFormatter(pct_axis_formatter))
    plt.gca().yaxis.set_minor_formatter(FuncFormatter(pct_axis_formatter))
    plt.legend(loc="best")
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=160)
    plt.close()


def main():
    ap = argparse.ArgumentParser(
        description="Crash-test per portfel: najgorsze okna czasowe portfela na tle S&P 500 i US 60/40."
    )
    ap.add_argument("series", nargs="+", help="Serie w formacie LABEL=ledger.csv")
    ap.add_argument("--column", required=True, help="Kolumna ledgera, np. TOTAL_USD_POST_REAL")
    ap.add_argument("--windows", default="3,5,7,10,15,20")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--focus", default="", help="Opcjonalny filtr labeli/ID; puste = wszystkie")
    ap.add_argument("--step-months", type=int, default=1)
    args = ap.parse_args()

    parsed = [parse_series_arg(x) for x in args.series]
    all_series: Dict[str, pd.Series] = {}
    for label, path in parsed:
        all_series[label] = load_series(path, args.column)

    windows = [float(x.strip()) for x in args.windows.split(",") if x.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "charts"
    plots_dir.mkdir(parents=True, exist_ok=True)

    focus_filter = args.focus.strip().upper()
    target_labels = []
    for label in all_series:
        if focus_filter and focus_filter not in label.upper():
            continue
        target_labels.append(label)

    if not target_labels:
        raise SystemExit("Brak portfeli do analizy po zastosowaniu focus.")

    summary_rows = []

    for label in target_labels:
        rows_for_label = []
        for wy in windows:
            try:
                worst = find_worst_window(all_series[label], wy, step_months=args.step_months)
            except Exception as e:
                summary_rows.append({
                    "PORTFOLIO": label,
                    "WINDOW_YEARS": wy,
                    "ERROR": str(e),
                })
                continue

            row = {"PORTFOLIO": label, "WINDOW_YEARS": wy, **worst}
            bench_labels = choose_benchmarks(label, all_series)
            labels_to_plot = [label] + bench_labels

            for b in bench_labels:
                bm = window_metrics(all_series[b], pd.to_datetime(worst["START"]), pd.to_datetime(worst["END"]))
                prefix = safe_token(b).upper()
                row[f"{prefix}_CAGR_%"] = bm.get("CAGR_%")
                row[f"{prefix}_TOTAL_RETURN_%"] = bm.get("TOTAL_RETURN_%")
                row[f"{prefix}_MAX_DD_%"] = bm.get("MAX_DD_%")

            wy_token = int(wy) if wy.is_integer() else str(wy).replace(".", "_")
            out_png = plots_dir / f"{safe_token(label)}_worst_{wy_token}y.png"
            title = (
                f"{label}: najgorsze okno {wy_token}Y "
                f"({worst['START']} - {worst['END']})\n"
                f"na tle S&P 500 i US 60/40"
            )
            plot_window(label, labels_to_plot, all_series, worst["START"], worst["END"], title, out_png)

            row["PLOT"] = str(out_png)
            row["BENCHMARKS_ON_PLOT"] = " | ".join(bench_labels)
            rows_for_label.append(row)
            summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out_dir / "summary_by_portfolio.csv", index=False, encoding="utf-8")
    summary.to_csv(out_dir / "worst_windows_by_portfolio.csv", index=False, encoding="utf-8")
    print(f"OK: {VERSION}")
    print(f"OK: portfele={len(target_labels)}; windows={args.windows}; out={out_dir}")
    print(f"OK: charts={plots_dir}")
    print(f"OK: summary={out_dir / 'summary_by_portfolio.csv'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import math
import os
import re
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

LOG_SCALE_CRASH_PLOTS = True


def pct_axis_formatter(x, pos):
    try:
        return f"{x:.0f}%"
    except Exception:
        return ""



DATE_CANDIDATES = ["DATE", "Date", "DATA", "date", "datetime", "DATETIME"]
DEFAULT_COLUMN = "TOTAL_USD_POST_REAL"
CPI_CANDIDATES = ["CPI_US", "CPI_USD", "CPI", "US_CPI"]


def safe_name(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", s.strip())
    return s.strip("_") or "portfolio"


def find_date_col(df: pd.DataFrame) -> str:
    for c in DATE_CANDIDATES:
        if c in df.columns:
            return c
    for c in df.columns:
        if c.upper() in {"DATE", "DATA", "DATETIME"}:
            return c
    raise SystemExit("ERROR: nie znalazłem kolumny daty: DATE/DATA/DATETIME")


def find_cpi_col(df: pd.DataFrame) -> str:
    for c in CPI_CANDIDATES:
        if c in df.columns:
            return c
    for c in df.columns:
        if c.upper() in {"CPI_US", "CPI_USD", "CPI", "US_CPI"}:
            return c
    return ""


def load_ledger(path: str, column: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    dcol = find_date_col(df)
    if column not in df.columns:
        raise SystemExit(f"ERROR: w {path} nie ma kolumny {column}. Dostępne: {list(df.columns)}")
    cols = [dcol, column]
    cpi_col = find_cpi_col(df)
    if cpi_col:
        cols.append(cpi_col)
    out = df[cols].copy()
    out.columns = ["DATE", "VALUE"] + (["CPI"] if cpi_col else [])
    out["DATE"] = pd.to_datetime(out["DATE"])
    out["VALUE"] = pd.to_numeric(out["VALUE"], errors="coerce")
    if "CPI" in out.columns:
        out["CPI"] = pd.to_numeric(out["CPI"], errors="coerce")
    out = out.dropna(subset=["DATE", "VALUE"]).sort_values("DATE").reset_index(drop=True)
    out = out[out["VALUE"] > 0].reset_index(drop=True)
    if len(out) < 2:
        raise SystemExit(f"ERROR: za mało danych w {path}")
    return out


def years_between(a: pd.Timestamp, b: pd.Timestamp) -> float:
    return (b - a).days / 365.25


def max_drawdown_stats(series: pd.Series, dates: pd.Series) -> Dict[str, object]:
    vals = series.astype(float).reset_index(drop=True)
    dts = pd.to_datetime(dates).reset_index(drop=True)
    roll_max = vals.cummax()
    dd = vals / roll_max - 1.0
    trough_idx = int(dd.idxmin())
    maxdd = float(dd.iloc[trough_idx])
    peak_val = float(roll_max.iloc[trough_idx])
    peak_candidates = vals.iloc[: trough_idx + 1]
    peak_idx = int(peak_candidates[peak_candidates == peak_val].index[-1])
    recovery_idx = None
    for i in range(trough_idx + 1, len(vals)):
        if vals.iloc[i] >= peak_val:
            recovery_idx = i
            break
    months_to_recovery = np.nan
    recovery_date = ""
    if recovery_idx is not None:
        months_to_recovery = int(round((dts.iloc[recovery_idx] - dts.iloc[peak_idx]).days / 30.4375))
        recovery_date = dts.iloc[recovery_idx].date().isoformat()
    return {
        "MAXDD_%": maxdd * 100.0,
        "DD_PEAK_DATE": dts.iloc[peak_idx].date().isoformat(),
        "DD_TROUGH_DATE": dts.iloc[trough_idx].date().isoformat(),
        "DD_RECOVERY_DATE": recovery_date,
        "MONTHS_TO_RECOVERY": months_to_recovery,
    }


def full_metrics(label: str, df: pd.DataFrame) -> Dict[str, object]:
    years = years_between(df["DATE"].iloc[0], df["DATE"].iloc[-1])
    v0 = float(df["VALUE"].iloc[0])
    v1 = float(df["VALUE"].iloc[-1])
    cagr = (v1 / v0) ** (1 / years) - 1 if years > 0 else np.nan
    ret = df["VALUE"].pct_change().dropna()
    stdev = ret.std() * math.sqrt(12) if len(ret) else np.nan
    dd = max_drawdown_stats(df["VALUE"], df["DATE"])
    return {
        "LABEL": label,
        "START": df["DATE"].iloc[0].date().isoformat(),
        "END": df["DATE"].iloc[-1].date().isoformat(),
        "ROWS": len(df),
        "CAGR_%": cagr * 100.0,
        "MAXDD_%": dd["MAXDD_%"],
        "DD_PEAK_DATE": dd["DD_PEAK_DATE"],
        "DD_TROUGH_DATE": dd["DD_TROUGH_DATE"],
        "DD_RECOVERY_DATE": dd["DD_RECOVERY_DATE"],
        "MONTHS_TO_RECOVERY": dd["MONTHS_TO_RECOVERY"],
        "STDEV_%": stdev * 100.0,
        "END_VALUE": v1,
    }


def rolling_windows(label: str, df: pd.DataFrame, window_years: int) -> pd.DataFrame:
    rows = []
    dates = df["DATE"].reset_index(drop=True)
    vals = df["VALUE"].reset_index(drop=True)
    for i in range(len(df)):
        target = dates.iloc[i] + pd.DateOffset(years=window_years)
        j_candidates = np.where(dates.values >= np.datetime64(target))[0]
        if len(j_candidates) == 0:
            break
        j = int(j_candidates[0])
        if j <= i:
            continue
        seg_vals = vals.iloc[i : j + 1].reset_index(drop=True)
        seg_dates = dates.iloc[i : j + 1].reset_index(drop=True)
        yrs = years_between(seg_dates.iloc[0], seg_dates.iloc[-1])
        total_return = float(seg_vals.iloc[-1] / seg_vals.iloc[0] - 1.0)
        cagr = (float(seg_vals.iloc[-1] / seg_vals.iloc[0]) ** (1 / yrs) - 1) if yrs > 0 else np.nan
        dd = max_drawdown_stats(seg_vals, seg_dates)
        rows.append({
            "LABEL": label,
            "WINDOW_YEARS": window_years,
            "START": seg_dates.iloc[0].date().isoformat(),
            "END": seg_dates.iloc[-1].date().isoformat(),
            "YEARS": yrs,
            "START_VALUE": float(seg_vals.iloc[0]),
            "END_VALUE": float(seg_vals.iloc[-1]),
            "TOTAL_RETURN_%": total_return * 100.0,
            "CAGR_%": cagr * 100.0,
            "MAXDD_%": dd["MAXDD_%"],
            "DD_PEAK_DATE": dd["DD_PEAK_DATE"],
            "DD_TROUGH_DATE": dd["DD_TROUGH_DATE"],
            "DD_RECOVERY_DATE": dd["DD_RECOVERY_DATE"],
            "MONTHS_TO_RECOVERY": dd["MONTHS_TO_RECOVERY"],
            "LOST_REAL": total_return < 0,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["TOTAL_RETURN_%", "MAXDD_%"], ascending=[True, True]).reset_index(drop=True)
        out.insert(0, "RANK", np.arange(1, len(out) + 1))
    return out


def common_cpi_series(dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    for df in dfs.values():
        if "CPI" in df.columns and df["CPI"].notna().sum() >= 2:
            out = df[["DATE", "CPI"]].dropna().copy().reset_index(drop=True)
            out = out[out["CPI"] > 0].reset_index(drop=True)
            if len(out) >= 2:
                return out
    return pd.DataFrame(columns=["DATE", "CPI"])


def cpi_for_period(dfs: Dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    cpi = common_cpi_series(dfs)
    if cpi.empty:
        return cpi
    out = cpi[(cpi["DATE"] >= start) & (cpi["DATE"] <= end)].copy().reset_index(drop=True)
    out = out.dropna(subset=["CPI"])
    out = out[out["CPI"] > 0].reset_index(drop=True)
    return out


def plot_full(dfs: Dict[str, pd.DataFrame], out_path: str, title: str):
    plt.figure(figsize=(12, 7))
    for label, df in dfs.items():
        y = df["VALUE"] / df["VALUE"].iloc[0] * 100.0
        plt.plot(df["DATE"], y, label=label)
    cpi = common_cpi_series(dfs)
    if not cpi.empty:
        y_cpi = cpi["CPI"] / cpi["CPI"].iloc[0] * 100.0
        plt.plot(cpi["DATE"], y_cpi, label="CPI USA, start = 100", color="blue", linewidth=2.2, linestyle="--")
    plt.title(title)
    plt.xlabel("Data")
    plt.ylabel("Wartość realna / CPI, start = 100")
    plt.grid(True, alpha=0.3)
    plt.yscale("log")
    plt.gca().yaxis.set_major_formatter(FuncFormatter(pct_axis_formatter))
    plt.gca().yaxis.set_minor_formatter(FuncFormatter(pct_axis_formatter))
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_own_worst_no_cpi(dfs: Dict[str, pd.DataFrame], worst: pd.DataFrame, window_years: int, out_path: str):
    # Uwaga: każde portfolio może mieć inne własne najgorsze okno, więc jedna CPI na overlay byłaby myląca.
    plt.figure(figsize=(12, 7))
    for _, row in worst.iterrows():
        label = row["LABEL"]
        df = dfs[label]
        start = pd.to_datetime(row["START"])
        end = pd.to_datetime(row["END"])
        seg = df[(df["DATE"] >= start) & (df["DATE"] <= end)].copy().reset_index(drop=True)
        if seg.empty:
            continue
        y = seg["VALUE"] / seg["VALUE"].iloc[0] * 100.0
        x = np.arange(len(seg))
        plt.plot(x, y, label=f"{label}: {row['START']} → {row['END']}")
    plt.title(f"Najgorsze własne okno {window_years}Y — każde portfolio ma własne daty, start = 100")
    plt.xlabel("Miesiące od startu własnego okna")
    plt.ylabel("Wartość realna, start = 100")
    plt.grid(True, alpha=0.3)
    plt.yscale("log")
    plt.gca().yaxis.set_major_formatter(FuncFormatter(pct_axis_formatter))
    plt.gca().yaxis.set_minor_formatter(FuncFormatter(pct_axis_formatter))
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()

def plot_own_worst_calendar_with_cpi(dfs: Dict[str, pd.DataFrame], worst: pd.DataFrame, window_years: int, out_path: str):
    # Własne najgorsze okna różnych portfeli na jednej osi kalendarzowej.
    # Linie zaczynają i kończą się w swoich faktycznych datach; CPI jest jedna, dla zakresu unii dat.
    if worst.empty:
        return
    starts = [pd.to_datetime(x) for x in worst["START"]]
    ends = [pd.to_datetime(x) for x in worst["END"]]
    union_start = min(starts)
    union_end = max(ends)
    plt.figure(figsize=(12, 7))
    for _, row in worst.iterrows():
        label = row["LABEL"]
        df = dfs[label]
        start = pd.to_datetime(row["START"])
        end = pd.to_datetime(row["END"])
        seg = df[(df["DATE"] >= start) & (df["DATE"] <= end)].copy().reset_index(drop=True)
        if seg.empty:
            continue
        y = seg["VALUE"] / seg["VALUE"].iloc[0] * 100.0
        plt.plot(seg["DATE"], y, label=f"{label}: {row['START']} → {row['END']}")
    cpi = cpi_for_period(dfs, union_start, union_end)
    if not cpi.empty and len(cpi) >= 2:
        y_cpi = cpi["CPI"] / cpi["CPI"].iloc[0] * 100.0
        plt.plot(cpi["DATE"], y_cpi, label=f"CPI USA: {union_start.date()} → {union_end.date()}", color="blue", linewidth=2.0, linestyle="--")
    plt.title(f"Najgorsze własne okna {window_years}Y — oś kalendarzowa, każda linia w swoich datach")
    plt.xlabel("Data")
    plt.ylabel("Wartość realna / CPI, start każdej linii = 100")
    plt.grid(True, alpha=0.3)
    plt.yscale("log")
    plt.gca().yaxis.set_major_formatter(FuncFormatter(pct_axis_formatter))
    plt.gca().yaxis.set_minor_formatter(FuncFormatter(pct_axis_formatter))
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_individual_worst_with_cpi(dfs: Dict[str, pd.DataFrame], worst: pd.DataFrame, window_years: int, out_dir: str):
    # Jeden portfel, jedno okno: oś X = realne daty kalendarzowe.
    for _, row in worst.iterrows():
        label = row["LABEL"]
        df = dfs[label]
        start = pd.to_datetime(row["START"])
        end = pd.to_datetime(row["END"])
        seg = df[(df["DATE"] >= start) & (df["DATE"] <= end)].copy().reset_index(drop=True)
        if seg.empty:
            continue
        plt.figure(figsize=(12, 7))
        y = seg["VALUE"] / seg["VALUE"].iloc[0] * 100.0
        plt.plot(seg["DATE"], y, label=f"{label}: {row['START']} → {row['END']}")
        cpi = cpi_for_period(dfs, start, end)
        if not cpi.empty and len(cpi) >= 2:
            y_cpi = cpi["CPI"] / cpi["CPI"].iloc[0] * 100.0
            plt.plot(cpi["DATE"], y_cpi, label="CPI USA dla tego samego okresu", color="blue", linewidth=2.0, linestyle="--")
        plt.title(f"{label}: najgorsze okno {window_years}Y vs CPI — {row['START']} → {row['END']}")
        plt.xlabel("Data")
        plt.ylabel("Wartość realna / CPI, start = 100")
        plt.grid(True, alpha=0.3)
        plt.yscale("log")
        plt.gca().yaxis.set_major_formatter(FuncFormatter(pct_axis_formatter))
        plt.gca().yaxis.set_minor_formatter(FuncFormatter(pct_axis_formatter))
        plt.legend()
        plt.tight_layout()
        out_path = os.path.join(out_dir, f"plot_worst_own_{window_years}Y_{safe_name(label)}_with_CPI.png")
        plt.savefig(out_path, dpi=160)
        plt.close()


def plot_common_window_all_portfolios_with_cpi(dfs: Dict[str, pd.DataFrame], row: pd.Series, window_years: int, out_dir: str):
    """Rysuje JEDNO okno kalendarzowe: najgorszy okres portfela źródłowego.

    Ważne: benchmarki nie są rozciągane po osi X. Każdy ledger jest cięty po dacie:
    START <= DATE <= END. Jeżeli benchmark ma krótszy zakres, jego linia zaczyna się
    później albo kończy wcześniej na osi kalendarzowej. W etykiecie dostaje znacznik
    INCOMPLETE. To jest poprawne przy różnych zakresach ledgerów.
    """
    source_label = row["LABEL"]
    start = pd.to_datetime(row["START"])
    end = pd.to_datetime(row["END"])
    coverage_rows = []

    plt.figure(figsize=(12, 7))
    for label, df in dfs.items():
        seg = df[(df["DATE"] >= start) & (df["DATE"] <= end)].copy().reset_index(drop=True)
        if seg.empty:
            coverage_rows.append({
                "WINDOW_YEARS": window_years,
                "SOURCE_LABEL": source_label,
                "WINDOW_START": start.date().isoformat(),
                "WINDOW_END": end.date().isoformat(),
                "LABEL": label,
                "PLOT_START": "",
                "PLOT_END": "",
                "ROWS": 0,
                "COVERAGE": "NO_OVERLAP",
            })
            continue

        plot_start = seg["DATE"].iloc[0]
        plot_end = seg["DATE"].iloc[-1]
        start_gap_days = (plot_start - start).days
        end_gap_days = (end - plot_end).days
        complete = start_gap_days <= 35 and end_gap_days <= 35
        coverage = "FULL" if complete else "INCOMPLETE"

        y = seg["VALUE"] / seg["VALUE"].iloc[0] * 100.0
        label_txt = label
        if coverage != "FULL":
            label_txt = f"{label} ({coverage}: {plot_start.date()} → {plot_end.date()})"
        plt.plot(seg["DATE"], y, label=label_txt)

        coverage_rows.append({
            "WINDOW_YEARS": window_years,
            "SOURCE_LABEL": source_label,
            "WINDOW_START": start.date().isoformat(),
            "WINDOW_END": end.date().isoformat(),
            "LABEL": label,
            "PLOT_START": plot_start.date().isoformat(),
            "PLOT_END": plot_end.date().isoformat(),
            "ROWS": len(seg),
            "COVERAGE": coverage,
        })

    cpi = cpi_for_period(dfs, start, end)
    if not cpi.empty and len(cpi) >= 2:
        y_cpi = cpi["CPI"] / cpi["CPI"].iloc[0] * 100.0
        plt.plot(cpi["DATE"], y_cpi, label="CPI USA dla tego samego okresu", color="blue", linewidth=2.0, linestyle="--")

    plt.xlim(start, end)
    plt.title(f"Wspólne okno {window_years}Y: najgorszy okres {source_label} — {row['START']} → {row['END']}")
    plt.xlabel("Data kalendarzowa")
    plt.ylabel("Wartość realna / CPI, start danej linii = 100")
    plt.grid(True, alpha=0.3)
    plt.yscale("log")
    plt.gca().yaxis.set_major_formatter(FuncFormatter(pct_axis_formatter))
    plt.gca().yaxis.set_minor_formatter(FuncFormatter(pct_axis_formatter))
    plt.legend()
    plt.tight_layout()
    out_path = os.path.join(out_dir, f"plot_common_window_{window_years}Y_worst_of_{safe_name(source_label)}_with_CPI.png")
    plt.savefig(out_path, dpi=160)
    plt.close()

    cov_path = os.path.join(out_dir, f"coverage_common_window_{window_years}Y_worst_of_{safe_name(source_label)}.csv")
    pd.DataFrame(coverage_rows).to_csv(cov_path, index=False)


def parse_ledger_arg(arg: str) -> Tuple[str, str]:
    if "=" in arg:
        label, path = arg.split("=", 1)
        return label.strip(), path.strip().strip('"')
    path = arg.strip().strip('"')
    return os.path.splitext(os.path.basename(path))[0], path


def main():
    ap = argparse.ArgumentParser(description="Crash test: rolling windows + wykresy jednego okresu kalendarzowego. Dla najgorszego okresu portfela focus rysuje pozostałe ledgery wyłącznie w tym samym zakresie dat, bez rozciągania osi.")
    ap.add_argument("ledgers", nargs="+", help="Format: LABEL=ledger.csv albo sam ledger.csv")
    ap.add_argument("--column", default=DEFAULT_COLUMN, help=f"Kolumna wartości, domyślnie {DEFAULT_COLUMN}")
    ap.add_argument("--windows", default="10,15,20", help="Okna w latach, np. 5,10,15,20")
    ap.add_argument("--out-dir", default="crash_out", help="Folder wynikowy")
    ap.add_argument("--sort", default="CAGR_%", help="Kolumna sortowania summary_full.csv")
    ap.add_argument("--ascending", action="store_true", help="Sortowanie rosnąco")
    ap.add_argument("--focus", default="", help="Opcjonalnie: generuj common-window tylko dla wskazanego labelu, np. Butterfly. Domyślnie dla każdego portfela.")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    dfs: Dict[str, pd.DataFrame] = {}
    for item in args.ledgers:
        label, path = parse_ledger_arg(item)
        if label in dfs:
            raise SystemExit(f"ERROR: powtórzony label {label}")
        dfs[label] = load_ledger(path, args.column)

    full = pd.DataFrame([full_metrics(label, df) for label, df in dfs.items()])
    if args.sort in full.columns:
        full = full.sort_values(args.sort, ascending=args.ascending).reset_index(drop=True)
    full.to_csv(os.path.join(args.out_dir, "summary_full.csv"), index=False)

    all_worst = []
    for w in windows:
        per_label_best = []
        all_rows = []
        for label, df in dfs.items():
            rw = rolling_windows(label, df, w)
            if rw.empty:
                continue
            rw.to_csv(os.path.join(args.out_dir, f"windows_{safe_name(label)}_{w}Y.csv"), index=False)
            all_rows.append(rw)
            per_label_best.append(rw.iloc[0].to_dict())
        if all_rows:
            concat = pd.concat(all_rows, ignore_index=True)
            concat.to_csv(os.path.join(args.out_dir, f"windows_all_{w}Y.csv"), index=False)
        if per_label_best:
            best = pd.DataFrame(per_label_best).sort_values("TOTAL_RETURN_%", ascending=True).reset_index(drop=True)
            best.to_csv(os.path.join(args.out_dir, f"worst_by_portfolio_{w}Y.csv"), index=False)
            all_worst.append(best)
            # Poprawna logika crash-testu:
            # bierzemy JEDEN okres kalendarzowy: najgorsze okno wskazanego portfela,
            # a następnie w TYM SAMYM okresie rysujemy wszystkie pozostałe portfele oraz jedną CPI.
            rows_to_plot = best
            if args.focus:
                rows_to_plot = best[best["LABEL"].astype(str).str.lower() == args.focus.lower()]
                if rows_to_plot.empty:
                    print(f"WARN: --focus {args.focus} nie znaleziony dla okna {w}Y; dostępne: {list(best['LABEL'])}")
            for _, row in rows_to_plot.iterrows():
                plot_common_window_all_portfolios_with_cpi(dfs, row, w, args.out_dir)

    if all_worst:
        worst_all = pd.concat(all_worst, ignore_index=True)
        worst_all.to_csv(os.path.join(args.out_dir, "worst_by_portfolio_all_windows.csv"), index=False)

    plot_full(dfs, os.path.join(args.out_dir, "plot_full_overlay_with_CPI.png"), f"Pełny okres — {args.column}, start = 100")

    pd.set_option("display.max_columns", 40)
    pd.set_option("display.width", 220)
    print("\n=== FULL SUMMARY ===")
    print(full.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    if all_worst:
        print("\n=== WORST WINDOWS BY PORTFOLIO ===")
        print(pd.concat(all_worst, ignore_index=True).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"\nOK: zapisano wyniki do: {args.out_dir}")


if __name__ == "__main__":
    main()

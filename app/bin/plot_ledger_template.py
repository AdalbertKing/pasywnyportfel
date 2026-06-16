#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-

import argparse
import os
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter


def excel_col_to_idx(col: str) -> int:
    col = str(col).strip().upper()
    if not re.fullmatch(r"[A-Z]{1,3}", col):
        raise ValueError(f"Niepoprawna litera kolumny Excela: {col}")
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def resolve_col(df: pd.DataFrame, spec: str) -> str:
    spec = str(spec).strip()
    if spec in df.columns:
        return spec
    if re.fullmatch(r"[A-Za-z]{1,3}", spec):
        i = excel_col_to_idx(spec)
        if i < 0 or i >= len(df.columns):
            raise ValueError(f"Kolumna {spec} poza zakresem. Plik ma {len(df.columns)} kolumn.")
        return df.columns[i]
    lower = {str(c).lower(): c for c in df.columns}
    if spec.lower() in lower:
        return lower[spec.lower()]
    raise ValueError(f"Nie znaleziono kolumny: {spec}")


def to_num(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    s2 = s.astype(str).str.replace("\u00A0", " ", regex=False).str.strip()
    s2 = s2.str.replace(" ", "", regex=False)
    has_dot = s2.str.contains(r"\.", na=False)
    has_comma = s2.str.contains(",", na=False)
    s2 = np.where(has_comma & ~has_dot, pd.Series(s2, index=s.index).str.replace(",", ".", regex=False), s2)
    return pd.to_numeric(pd.Series(s2, index=s.index), errors="coerce")


def pick_date_col(df: pd.DataFrame, explicit=None) -> str:
    if explicit:
        return resolve_col(df, explicit)
    for c in ["DATE", "Date", "date", "DATA", "Data"]:
        if c in df.columns:
            return c
    return df.columns[0]


def normalize_to_100(s: pd.Series) -> pd.Series:
    valid = s.dropna().astype(float)
    if valid.empty:
        return s * np.nan
    base = float(valid.iloc[0])
    if not np.isfinite(base) or base == 0:
        return s * np.nan
    return s.astype(float) / base * 100.0


def max_drawdown(levels: pd.Series) -> dict:
    s = levels.dropna().astype(float)
    if len(s) < 2:
        return {"dd": np.nan, "peak": None, "trough": None, "peak_val": np.nan, "trough_val": np.nan}
    running_max = s.cummax()
    dd = s / running_max - 1.0
    trough = dd.idxmin()
    peak = s.loc[:trough].idxmax()
    return {
        "dd": float(dd.loc[trough]),
        "peak": peak,
        "trough": trough,
        "peak_val": float(s.loc[peak]),
        "trough_val": float(s.loc[trough]),
    }


def composition_text_from_val_usd(df: pd.DataFrame, max_rows: int = 12) -> str:
    val_cols = [c for c in df.columns if str(c).startswith("VAL_USD_")]
    if not val_cols:
        return "Skład portfela:\nbrak kolumn VAL_USD_*"

    vals = df.iloc[0][val_cols]
    vals = to_num(vals).astype(float)
    vals = vals[vals > 0].sort_values(ascending=False)

    total = float(vals.sum())
    if total <= 0:
        return "Skład portfela:\nbrak dodatnich VAL_USD_* na starcie"

    lines = ["Skład portfela:"]
    for c, v in vals.head(max_rows).items():
        name = str(c).replace("VAL_USD_", "")
        weight = v / total * 100.0
        lines.append(f"{name:<18} {weight:>5.1f}%")

    if len(vals) > max_rows:
        rest = vals.iloc[max_rows:].sum() / total * 100.0
        lines.append(f"{'POZOSTAŁE':<18} {rest:>5.1f}%")

    return "\n".join(lines)


def annotate_dd(ax, dd: dict, y_offset: int = -18, label_prefix: str = ""):
    if dd["peak"] is None or not np.isfinite(dd["dd"]):
        return

    ax.annotate(
        "",
        xy=(dd["trough"], dd["trough_val"]),
        xytext=(dd["peak"], dd["peak_val"]),
        arrowprops=dict(arrowstyle="-|>", color="red", lw=2.4),
        zorder=12,
        clip_on=False
    )
    ax.scatter([dd["peak"], dd["trough"]], [dd["peak_val"], dd["trough_val"]], color="red", s=35, zorder=13)
    ax.annotate(
        f"{label_prefix}max DD = {dd['dd']*100:.1f}%\n"
        f"{dd['peak'].date()} -> {dd['trough'].date()}\n"
        f"{dd['peak_val']:.0f}% -> {dd['trough_val']:.0f}%",
        xy=(dd["trough"], dd["trough_val"]),
        xytext=(12, y_offset),
        textcoords="offset points",
        color="red",
        fontsize=9,
        fontweight="bold",
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.88, edgecolor="none"),
        zorder=14,
        clip_on=False
    )


def main():
    ap = argparse.ArgumentParser(description="Wykres ledgera: 1 lub 2 serie od 100%, CPI, skład, max DD.")
    ap.add_argument("ledger")
    ap.add_argument("--main", required=True, help="Pierwsza kolumna: nazwa albo litera Excela, np. O.")
    ap.add_argument("--main2", default=None, help="Druga kolumna: nazwa albo litera Excela, np. M.")
    ap.add_argument("--main-label", default=None)
    ap.add_argument("--main2-label", default=None)
    ap.add_argument("--cpi", action="append", default=[], help="Kolumna CPI albo none/off. Można podać wiele razy, np. --cpi CPI_US --cpi CPI_PL.")
    ap.add_argument("--date-col", default=None)
    ap.add_argument("--start-date", default=None)
    ap.add_argument("--start-row", type=int, default=0)
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--composition-x", type=float, default=0.055)
    ap.add_argument("--composition-y", type=float, default=0.82)
    ap.add_argument("--composition-max-rows", type=int, default=12)
    ap.add_argument("--dpi", type=int, default=220)
    ap.add_argument("--log-y", action="store_true", help="Ustaw oś Y w skali logarytmicznej.")
    args = ap.parse_args()

    df = pd.read_csv(args.ledger, sep=None, engine="python")
    df.columns = [str(c).strip() for c in df.columns]

    date_col = pick_date_col(df, args.date_col)
    main_col = resolve_col(df, args.main)
    main2_col = resolve_col(df, args.main2) if args.main2 else None

    cpi_cols = []
    for cpi_spec in (args.cpi or []):
        if str(cpi_spec).strip().lower() in ["none", "off", "0", "false"]:
            continue
        cpi_cols.append(resolve_col(df, cpi_spec))

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[main_col] = to_num(df[main_col])
    if main2_col:
        df[main2_col] = to_num(df[main2_col])
    for cpi_col in cpi_cols:
        df[cpi_col] = to_num(df[cpi_col])

    if args.start_row and args.start_row > 0:
        df = df.iloc[args.start_row:].copy()

    df = df[df[date_col].notna()].copy()

    if args.start_date:
        start_dt = pd.to_datetime(args.start_date, errors="coerce")
        if pd.notna(start_dt):
            df = df[df[date_col] >= start_dt].copy()

    # Główne serie muszą mieć wspólny zakres.
    # CPI NIE może filtrować głównych serii, bo np. CPI_PL zwykle startuje dopiero od 1995,
    # a portfel / USD może mieć historię od 1960.
    mask = df[main_col].notna() & (df[main_col] > 0)
    if main2_col:
        mask &= df[main2_col].notna() & (df[main2_col] > 0)

    df = df[mask].copy()
    df.sort_values(date_col, inplace=True)
    df.set_index(date_col, inplace=True)

    if df.empty:
        raise ValueError("Brak danych po filtrach.")

    df["MAIN_NORM"] = normalize_to_100(df[main_col])
    if main2_col:
        df["MAIN2_NORM"] = normalize_to_100(df[main2_col])
    active_cpi_cols = []
    for cpi_col in cpi_cols:
        cpi_raw = df[cpi_col].where(df[cpi_col].notna() & (df[cpi_col] > 0))
        if cpi_raw.dropna().empty:
            print(f"UWAGA: pomijam {cpi_col}, bo nie ma dodatnich danych w wybranym zakresie.")
            continue
        active_cpi_cols.append(cpi_col)
        df[f"CPI_NORM_{len(active_cpi_cols)}"] = normalize_to_100(cpi_raw)
    cpi_cols = active_cpi_cols

    comp_text = composition_text_from_val_usd(df.reset_index(), args.composition_max_rows)

    start_label = df.index[0].date()
    end_label = df.index[-1].date()

    title = args.title or (
        f"{os.path.basename(args.ledger)}\n"
        f"{main_col}" + (f" vs {main2_col}" if main2_col else "") +
        f"; start = {start_label}, end = {end_label}, baza = 100%"
    )

    fig, ax = plt.subplots(figsize=(16, 8))

    ax.plot(df.index, df["MAIN_NORM"], label=args.main_label or main_col, linewidth=2.4, color="orange")

    if main2_col:
        ax.plot(df.index, df["MAIN2_NORM"], label=args.main2_label or main2_col, linewidth=2.2, color="black")

    cpi_colors = ["blue", "green", "purple", "brown"]
    for i, cpi_col in enumerate(cpi_cols, start=1):
        ax.plot(
            df.index,
            df[f"CPI_NORM_{i}"],
            label=cpi_col,
            linewidth=2.0,
            color=cpi_colors[(i - 1) % len(cpi_colors)],
            alpha=0.85
        )

    ax.text(
        args.composition_x,
        args.composition_y,
        comp_text,
        transform=ax.transAxes,
        fontsize=9,
        family="monospace",
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", alpha=0.90, edgecolor="gray"),
        zorder=10
    )

    annotate_dd(ax, max_drawdown(df["MAIN_NORM"]), y_offset=-18, label_prefix=("1: " if main2_col else ""))
    if main2_col:
        annotate_dd(ax, max_drawdown(df["MAIN2_NORM"]), y_offset=28, label_prefix="2: ")

    if args.log_y:
        ax.set_yscale("log")

        ymin, ymax = ax.get_ylim()
        nice_ticks = [
            10, 20, 25, 30, 40, 50, 75,
            100, 125, 150, 200, 250, 300, 400, 500, 750,
            1000, 1250, 1500, 2000, 2500, 3000, 4000, 5000, 7500,
            10000, 20000, 30000, 40000, 50000, 75000,
            100000, 200000, 300000, 400000, 500000
        ]
        ticks = [t for t in nice_ticks if ymin <= t <= ymax]
        if ticks:
            ax.set_yticks(ticks)
            ax.set_yticklabels([f"{t:,.0f}".replace(",", " ") for t in ticks])
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.yaxis.get_offset_text().set_visible(False)

    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Wartość (%; start = 100" + (", log" if args.log_y else "") + ")")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", frameon=True)

    if not args.out:
        stem = os.path.splitext(os.path.basename(args.ledger))[0]
        suffix = f"{main_col}" + (f"_vs_{main2_col}" if main2_col else "")
        args.out = f"plot_{stem}_{suffix}_template.png".replace("/", "_").replace("\\", "_")

    plt.tight_layout()
    plt.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    plt.close()

    print(args.out)


if __name__ == "__main__":
    main()

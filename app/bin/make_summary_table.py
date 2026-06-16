#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-

VERSION = "2.2.8-end-nominal-summary-table"

import argparse
import math
import os
import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_LABEL_MAP = {
    "us6040": "US 60/40",
    "6040": "US 60/40",
    "bfly": "Golden Butterfly",
    "butterfly": "Golden Butterfly",
    "golden": "Golden Butterfly",
    "sp500": "S&P 500",
    "perm": "Permanent",
    "permanent": "Permanent",
    "hist": "ETF hist.",
    "syn": "Synthetic",
    "synthetic": "Synthetic",
    "drift20": "DRIFT20",
    "12m": "12M",
    "net_plntax": "NET PL tax",
    "gross": "Gross",
}


COLUMN_ALIASES = {
    "PORTFEL": "Portfel",
    "START": "Start",
    "END": "End",
    "ROWS": "Rows",
    "DAYS": "Days",
    "YEARS": "Years",
    "NOM_DAYS": "Nom. days",
    "NOM_YEARS": "Nom. years",
    "RETURN_%": "Return real",
    "RETURN_REAL_%": "Return real",
    "RETURN_NOM_%": "Return nominal",
    "CAGR_%": "CAGR real",
    "CAGR_REAL_%": "CAGR real",
    "CAGR_NOM_%": "CAGR nominal",
    "MAXDD_%": "Max DD real",
    "MAXDD_REAL_%": "Max DD real",
    "MAXDD_NOM_%": "Max DD nominal",
    "MONTHS_TO_RECOVERY": "ATH recovery [m]",
    "MONTHS_TO_RECOVERY_REAL": "ATH recovery [m]",
    "MONTHS_TO_RECOVERY_NOM": "ATH recovery nominal [m]",
    "STDEV_%": "Stdev real",
    "STDEV_NOM_%": "Stdev nominal",
    "END_VALUE": "End real",
    "END_REAL": "End real",
    "END_NOM": "End nominal",
    "VALUE_COL": "Value column",
}


DEFAULT_COLUMNS_LONG = [
    "PORTFEL",
    "START",
    "END",
    "CAGR_%",
    "CAGR_NOM_%",
    "MAXDD_%",
    "MAXDD_NOM_%",
    "MONTHS_TO_RECOVERY",
    "STDEV_%",
    "END_VALUE",
    "END_NOM",
]

DEFAULT_COLUMNS_SHORT = [
    "PORTFEL",
    "START",
    "END",
    "DAYS",
    "RETURN_%",
    "RETURN_NOM_%",
    "MAXDD_%",
    "MAXDD_NOM_%",
    "STDEV_%",
    "END_VALUE",
    "END_NOM",
]



def fmt_start_capital_for_note(value: str) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    try:
        x = float(s.replace(" ", "").replace(",", "."))
        if abs(x - round(x)) < 1e-9:
            return f"Start capital: {int(round(x)):,}".replace(",", " ")
        return f"Start capital: {x:,.2f}".replace(",", " ")
    except Exception:
        return f"Start capital: {s}"


def slug_tokens(s: str):
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return [x for x in s.split() if x]


def pretty_portfolio_name(name: str, mode: str = "auto") -> str:
    if mode == "raw":
        return str(name)

    raw = str(name)
    lower = raw.lower()

    base = None
    if "us6040" in lower or "6040" in lower:
        base = "US 60/40"
    elif "bfly" in lower or "butterfly" in lower:
        base = "Golden Butterfly"
    elif "sp500" in lower:
        base = "S&P 500"
    elif "perm" in lower:
        base = "Permanent"
    else:
        base = raw

    tags = []
    if "syn" in lower:
        tags.append("synthetic")
    if "hist" in lower:
        tags.append("ETF hist.")
    if "drift20" in lower:
        tags.append("DRIFT20")
    elif "12m" in lower:
        tags.append("12M")
    if "net_plntax" in lower or "plntax" in lower:
        tags.append("NET PL tax")
    elif "gross" in lower:
        tags.append("gross")

    if tags and mode == "auto":
        return base + "\n" + " / ".join(tags)
    return base


def is_short_period_summary(df: pd.DataFrame) -> bool:
    if "YEARS" in df.columns:
        yrs = pd.to_numeric(df["YEARS"], errors="coerce")
        return yrs.notna().any() and float(yrs.max()) < 1.0
    if "START" in df.columns and "END" in df.columns:
        st = pd.to_datetime(df["START"], errors="coerce")
        en = pd.to_datetime(df["END"], errors="coerce")
        days = (en - st).dt.days
        return days.notna().any() and float(days.max()) < 365.0
    return False


def resolve_columns(df: pd.DataFrame, cols_arg: str | None):
    if cols_arg:
        requested = [c.strip() for c in cols_arg.split(",") if c.strip()]
        if len(requested) == 1 and requested[0].upper() == "AUTO":
            requested = DEFAULT_COLUMNS_SHORT if is_short_period_summary(df) else DEFAULT_COLUMNS_LONG
    else:
        requested = DEFAULT_COLUMNS_SHORT if is_short_period_summary(df) else DEFAULT_COLUMNS_LONG

    out = []
    lower_map = {str(c).lower(): c for c in df.columns}
    for c in requested:
        if c in df.columns:
            out.append(c)
        elif c.lower() in lower_map:
            out.append(lower_map[c.lower()])
        else:
            print(f"WARN: pomijam brakujaca kolumne: {c}")
    return out


def format_number(x, col: str, decimals: int = 2):
    col_u = str(col).upper()
    if pd.isna(x):
        if "MONTHS_TO_RECOVERY" in col_u:
            return "not recovered"
        return ""

    if "DATE" in col_u or col_u in ["START", "END", "DD_PEAK", "DD_TROUGH", "DD_RECOVERY"]:
        return str(x)[:10]

    if "MONTHS" in col_u or col_u == "ROWS":
        try:
            return f"{int(round(float(x)))}"
        except Exception:
            return str(x)

    if "RETURN" in col_u or "CAGR" in col_u or "MAXDD" in col_u or "STDEV" in col_u:
        try:
            return f"{float(x):.{decimals}f}%"
        except Exception:
            return str(x)

    if "END" in col_u or "VALUE" in col_u or "NOM" in col_u:
        try:
            return f"{float(x):,.0f}".replace(",", " ")
        except Exception:
            return str(x)

    try:
        f = float(x)
        if math.isfinite(f):
            return f"{f:,.2f}".replace(",", " ")
    except Exception:
        pass
    return str(x)


def numeric_col(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(dtype=float)


def choose_highlights(df: pd.DataFrame, columns: list[str]):
    highlights = {}

    def mark(col, idx, kind):
        if col in columns and idx is not None:
            highlights[(idx, col)] = kind

    if "RETURN_%" in df.columns and "RETURN_%" in columns:
        s = numeric_col(df, "RETURN_%")
        if s.notna().any():
            mark("RETURN_%", s.idxmax(), "best")
    elif "RETURN_REAL_%" in df.columns and "RETURN_REAL_%" in columns:
        s = numeric_col(df, "RETURN_REAL_%")
        if s.notna().any():
            mark("RETURN_REAL_%", s.idxmax(), "best")
    elif "CAGR_%" in df.columns:
        s = numeric_col(df, "CAGR_%")
        if s.notna().any():
            mark("CAGR_%", s.idxmax(), "best")
    elif "CAGR_REAL_%" in df.columns:
        s = numeric_col(df, "CAGR_REAL_%")
        if s.notna().any():
            mark("CAGR_REAL_%", s.idxmax(), "best")

    if "END_VALUE" in df.columns:
        s = numeric_col(df, "END_VALUE")
        if s.notna().any():
            mark("END_VALUE", s.idxmax(), "best")
    elif "END_REAL" in df.columns:
        s = numeric_col(df, "END_REAL")
        if s.notna().any():
            mark("END_REAL", s.idxmax(), "best")

    if "END_NOM" in df.columns:
        s = numeric_col(df, "END_NOM")
        if s.notna().any():
            mark("END_NOM", s.idxmax(), "best")

    for c in ["MAXDD_%", "MAXDD_REAL_%"]:
        if c in df.columns:
            s = numeric_col(df, c)
            if s.notna().any():
                mark(c, s.idxmax(), "best")  # mniej ujemny jest lepszy

    for c in ["MONTHS_TO_RECOVERY", "MONTHS_TO_RECOVERY_REAL"]:
        if c in df.columns:
            s = numeric_col(df, c)
            if s.notna().any():
                mark(c, s.idxmin(), "best")

    for c in ["STDEV_%", "STDEV_NOM_%"]:
        if c in df.columns:
            s = numeric_col(df, c)
            if s.notna().any():
                mark(c, s.idxmin(), "best")

    return highlights


def load_and_prepare(args):
    df = pd.read_csv(args.csv)
    df.columns = [str(c).strip() for c in df.columns]

    if args.filter:
        # syntax: column~text,column2~text2
        for filt in args.filter:
            if "~" not in filt:
                raise ValueError("--filter oczekuje formatu COL~TEXT")
            col, text = filt.split("~", 1)
            col = col.strip()
            text = text.strip().lower()
            if col not in df.columns:
                raise ValueError(f"Brak kolumny filtrowania: {col}")
            df = df[df[col].astype(str).str.lower().str.contains(text, na=False)].copy()

    if args.top and args.sort and args.sort in df.columns:
        asc = args.ascending
        df[args.sort] = pd.to_numeric(df[args.sort], errors="coerce")
        df = df.sort_values(args.sort, ascending=asc).head(args.top).copy()
    elif args.top:
        df = df.head(args.top).copy()

    if args.only:
        needles = [x.strip().lower() for x in args.only.split(",") if x.strip()]
        if "PORTFEL" not in df.columns:
            raise ValueError("--only wymaga kolumny PORTFEL")
        mask = False
        for n in needles:
            mask = mask | df["PORTFEL"].astype(str).str.lower().str.contains(n, na=False)
        df = df[mask].copy()

    if "PORTFEL" in df.columns:
        df["PORTFEL"] = df["PORTFEL"].map(lambda x: pretty_portfolio_name(x, args.name_mode))

    columns = resolve_columns(df, args.columns)
    if not columns:
        raise ValueError("Brak kolumn do pokazania.")

    return df.reset_index(drop=True), columns



def load_components_lines(path: str | None, max_width: int = 190) -> list[str]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return [f"BRAK PLIKU ZE SKŁADEM PORTFELI: {path}"]
    raw_lines = [x.rstrip() for x in p.read_text(encoding="utf-8", errors="ignore").splitlines()]
    lines = []
    for line in raw_lines:
        if not line.strip():
            lines.append("")
            continue
        if len(line) <= max_width:
            lines.append(line)
        else:
            lines.extend(textwrap.wrap(line, width=max_width, subsequent_indent="    "))
    return lines

def make_table(df: pd.DataFrame, columns: list[str], args):
    nrows = len(df)
    ncols = len(columns)
    if nrows == 0:
        raise ValueError("CSV po filtrach nie ma wierszy.")

    # width heuristic
    col_widths = []
    for col in columns:
        header = COLUMN_ALIASES.get(col, col)
        vals = [format_number(v, col, args.decimals) for v in df[col].tolist()]
        max_len = max([len(str(header))] + [len(str(v)) for v in vals])
        if col == "PORTFEL":
            # 2.2.3: substantially wider first column for long portfolio labels.
            width = max(5.0, min(8.0, max_len * 0.32))
        elif col in ["START", "END"]:
            width = 1.35
        else:
            width = max(1.25, min(2.1, max_len * 0.13))
        col_widths.append(width)

    components_lines = load_components_lines(getattr(args, "components_file", ""))
    footer_lines_count = (1 if args.note else 0) + len(components_lines)

    fig_w = max(args.width, sum(col_widths) + 0.8)
    footer_extra = max(0.0, footer_lines_count * 0.18)
    fig_h = max(args.height, 1.4 + nrows * 0.48 + footer_extra)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=args.dpi)
    ax.axis("off")

    title = args.title or f"Summary table: {os.path.basename(args.csv)}"
    subtitle = args.subtitle or ""

    ax.text(0.5, 0.965, title, ha="center", va="top", fontsize=args.title_size, fontweight="bold", transform=ax.transAxes)
    if subtitle:
        ax.text(0.5, 0.905, subtitle, ha="center", va="top", fontsize=args.subtitle_size, transform=ax.transAxes)

    table_data = []
    for _, row in df.iterrows():
        table_data.append([format_number(row[col], col, args.decimals) for col in columns])

    col_labels = [COLUMN_ALIASES.get(c, c) for c in columns]

    # Matplotlib table gives equal column widths unless colWidths is passed.
    # Use the heuristic widths computed above as relative proportions.
    total_col_width = sum(col_widths) if col_widths else 1.0
    col_width_fracs = [w / total_col_width for w in col_widths]

    bbox_top = 0.84 if subtitle else 0.88
    footer_space = 0.065 + min(0.40, footer_lines_count * 0.040)
    bbox_bottom = footer_space if footer_lines_count else 0.06
    bbox_height = bbox_top - bbox_bottom

    table = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colLoc="center",
        colWidths=col_width_fracs,
        bbox=[0.02, bbox_bottom, 0.96, bbox_height],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(args.font_size)

    # Header
    for j in range(ncols):
        cell = table[0, j]
        cell.set_text_props(weight="bold", color="white")
        cell.set_facecolor("#263238")
        cell.set_edgecolor("#FFFFFF")
        cell.set_linewidth(0.8)

    highlights = choose_highlights(df, columns) if not args.no_highlight else {}

    # Body
    for i in range(nrows):
        for j, col in enumerate(columns):
            cell = table[i + 1, j]
            base = "#F7F9FA" if i % 2 == 0 else "#FFFFFF"
            cell.set_facecolor(base)
            cell.set_edgecolor("#D0D5D8")
            cell.set_linewidth(0.6)

            if (i, col) in highlights:
                cell.set_facecolor("#E8F5E9")
                cell.set_text_props(weight="bold")

            if col == "PORTFEL":
                cell.set_text_props(ha="left")

    # Footer: note + compact portfolio legend.
    # Printed summary PNG must be self-describing, but the footer must stay readable.
    y = bbox_bottom - 0.024
    note_gap = 0.038
    component_gap = 0.034
    if args.note:
        ax.text(0.02, y, args.note, ha="left", va="top", fontsize=args.note_size, transform=ax.transAxes)
        y -= note_gap  # one visual blank line after "Main metrics..."
    for line in components_lines:
        ax.text(0.02, y, line, ha="left", va="top", fontsize=args.components_size, family="sans-serif", fontweight="normal", transform=ax.transAxes)
        y -= component_gap

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.out, bbox_inches="tight", dpi=args.dpi)
    plt.close(fig)
    print(args.out)


def main():
    ap = argparse.ArgumentParser(description="Generuje ladna graficzna tabelke PNG z wynikowego CSV ledger_summary.")
    ap.add_argument("csv", help="CSV z ledger_summary.py")
    ap.add_argument("--out", required=True, help="PNG output")
    ap.add_argument("--columns", default=None, help="Kolumny po przecinku albo AUTO. Domyślnie AUTO: dla krótkich okresów pokazuje RETURN_%, dla długich CAGR_%")
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--start-capital", default="", help="Kapital startowy analizy pokazywany w stopce tabeli PNG")
    ap.add_argument("--components-file", default="", help="TXT ze składem portfeli do pokazania pod tabelą summary PNG")
    ap.add_argument("--note", default=None)
    ap.add_argument("--sort", default=None)
    ap.add_argument("--ascending", action="store_true")
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--only", default=None, help="Pokaz tylko wiersze, których PORTFEL zawiera podane frazy, np. us6040,bfly")
    ap.add_argument("--filter", action="append", default=[], help="Filtr COL~TEXT; mozna podac wiele razy.")
    ap.add_argument("--name-mode", choices=["auto", "raw"], default="auto")
    ap.add_argument("--decimals", type=int, default=2)
    ap.add_argument("--dpi", type=int, default=220)
    ap.add_argument("--width", type=float, default=16.5)
    ap.add_argument("--height", type=float, default=3.8)
    ap.add_argument("--font-size", type=int, default=9)
    ap.add_argument("--title-size", type=int, default=15)
    ap.add_argument("--subtitle-size", type=int, default=10)
    ap.add_argument("--note-size", type=int, default=8)
    ap.add_argument("--components-size", type=int, default=8)
    ap.add_argument("--no-highlight", action="store_true")

    args = ap.parse_args()

    start_capital_note = fmt_start_capital_for_note(args.start_capital)
    if start_capital_note:
        if getattr(args, "note", ""):
            args.note = str(args.note).rstrip() + " | " + start_capital_note
        else:
            args.note = start_capital_note
    df, columns = load_and_prepare(args)
    if is_short_period_summary(df):
        short_note = "Short period: table shows period return, not annualized CAGR."
        if getattr(args, "note", ""):
            if short_note not in args.note:
                args.note = str(args.note).rstrip() + " | " + short_note
        else:
            args.note = short_note
    make_table(df, columns, args)


if __name__ == "__main__":
    main()

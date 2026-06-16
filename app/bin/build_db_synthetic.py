#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ==================================================================
# 1 BEGIN: IMPORTY, STAŁE
# ==================================================================
import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
# 1 END
# ==================================================================


# ==================================================================
# 2 BEGIN: FUNKCJE POMOCNICZE
# ==================================================================
def _pick_col(df: pd.DataFrame, names: List[str], required: bool = True) -> Optional[str]:
    low = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    if required:
        raise ValueError(f"Brak kolumny: jedna z {names}. Dostępne: {list(df.columns)}")
    return None


def _parse_date(x) -> pd.Timestamp:
    d = pd.to_datetime(x, errors="coerce")
    if pd.isna(d):
        raise ValueError(f"Niepoprawna data: {x}")
    return pd.Timestamp(d).normalize()


def _month_end_index(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    start_me = pd.Timestamp(start) + pd.offsets.MonthEnd(0)
    end_me = pd.Timestamp(end) + pd.offsets.MonthEnd(0)
    return pd.date_range(start=start_me, end=end_me, freq="ME")


def _fmt_num(x) -> str:
    if pd.isna(x):
        return ""
    return f"{float(x):.10f}".rstrip("0").rstrip(".")
# 2 END
# ==================================================================


# ==================================================================
# 3 BEGIN: WCZYTYWANIE MAPOWANIA I BIBLIOTEKI
# ==================================================================
def read_mapping(path: str) -> pd.DataFrame:
    m = pd.read_csv(path)
    col_ticker = _pick_col(m, ["Ticker", "TICKER", "Symbol"])
    col_isin = _pick_col(m, ["ISIN"])
    col_asset = _pick_col(m, ["ASSET", "Asset", "Segment"])
    col_weight = _pick_col(m, ["WEIGHT", "Weight", "Weight_%"])
    col_cost = _pick_col(m, ["COST", "Cost", "TER"], required=False)
    col_name = _pick_col(m, ["NAME", "Name", "Instrument"], required=False)
    col_lib = _pick_col(m, ["LIB_COL", "Library", "LIBRARY_COL", "SERIES", "Source", "SOURCE_COL"], required=False)

    out = pd.DataFrame()
    out["Ticker"] = m[col_ticker].astype(str).str.strip()
    out["ISIN"] = m[col_isin].astype(str).str.strip()
    out["ASSET"] = m[col_asset].astype(str).str.strip()
    out["WEIGHT"] = pd.to_numeric(m[col_weight], errors="coerce")
    out["COST"] = pd.to_numeric(m[col_cost], errors="coerce").fillna(0.0) if col_cost else 0.0
    out["NAME"] = m[col_name].astype(str).str.strip() if col_name else ""
    out["LIB_COL"] = m[col_lib].astype(str).str.strip() if col_lib else out["Ticker"]

    out = out.dropna(subset=["WEIGHT"])
    out = out[(out["Ticker"] != "") & (out["ISIN"] != "") & (out["LIB_COL"] != "") & (out["WEIGHT"] > 0)]
    if out.empty:
        raise ValueError("Mapping pusty po walidacji.")

    if out["Ticker"].duplicated().any():
        d = sorted(out.loc[out["Ticker"].duplicated(), "Ticker"].unique())
        raise ValueError(f"Zduplikowane Ticker w mappingu: {d}")
    if out["LIB_COL"].duplicated().any():
        # To nie zawsze musi być błąd, ale dla DB kolumnowej zwykle oznacza pomyłkę.
        d = sorted(out.loc[out["LIB_COL"].duplicated(), "LIB_COL"].unique())
        raise ValueError(f"Zduplikowane LIB_COL w mappingu: {d}")

    return out.reset_index(drop=True)


def read_library(path: str) -> pd.DataFrame:
    lib = pd.read_csv(path)
    date_col = _pick_col(lib, ["DATE", "Date", "data", "Data"])
    lib[date_col] = lib[date_col].apply(_parse_date)
    lib = lib.rename(columns={date_col: "DATE"}).set_index("DATE").sort_index()
    lib = lib[~lib.index.duplicated(keep="last")]
    for c in lib.columns:
        lib[c] = pd.to_numeric(lib[c], errors="coerce")
    return lib
# 3 END
# ==================================================================


# ==================================================================
# 4 BEGIN: BUDOWA DB
# ==================================================================
def build_db(
    mapping_csv: str,
    library_csv: str,
    out_csv: str,
    start: Optional[str],
    end: Optional[str],
    fill_gaps: str,
    diag_csv: Optional[str],
) -> None:
    mp = read_mapping(mapping_csv)
    lib = read_library(library_csv)

    needed = mp["LIB_COL"].tolist()
    missing = [c for c in needed if c not in lib.columns]
    if missing:
        raise ValueError(f"Brak serii w bibliotece: {missing}")

    px = lib[needed].copy()
    px.columns = mp["Ticker"].tolist()

    if start:
        px = px[px.index >= _parse_date(start)]
    if end:
        px = px[px.index <= _parse_date(end)]

    if px.empty:
        raise ValueError("Brak danych po zastosowaniu start/end.")

    # Zakres wspólny: od pierwszego miesiąca z kompletem danych do ostatniego miesiąca z kompletem danych.
    complete_mask = px.notna().all(axis=1)
    if not complete_mask.any():
        per_col = []
        for c in px.columns:
            s = px[c].dropna()
            if s.empty:
                per_col.append(f"{c}: BRAK DANYCH")
            else:
                per_col.append(f"{c}: {s.index.min().date()}..{s.index.max().date()} rows={len(s)}")
        raise ValueError("Brak wspólnego zakresu danych dla mappingu. " + "; ".join(per_col))

    common_start = px.index[complete_mask].min()
    common_end = px.index[complete_mask].max()
    px = px.loc[(px.index >= common_start) & (px.index <= common_end)].copy()

    # Reindeksacja miesięczna i obsługa luk.
    full_idx = _month_end_index(px.index.min(), px.index.max())
    px = px.reindex(full_idx)

    gaps_before = int(px.isna().sum().sum())
    gap_months = px.index[px.isna().any(axis=1)]

    if gaps_before > 0:
        if fill_gaps == "error":
            details = ", ".join([d.strftime("%Y-%m-%d") for d in gap_months[:20]])
            more = "..." if len(gap_months) > 20 else ""
            raise ValueError(f"Są luki w danych po złożeniu DB. Użyj --fill-gaps interpolate/ffill jeśli akceptujesz. Daty: {details}{more}")
        elif fill_gaps == "interpolate":
            px = px.interpolate(method="time", limit_area="inside")
        elif fill_gaps == "ffill":
            px = px.ffill()
        else:
            raise ValueError(f"Nieznane fill_gaps={fill_gaps}")

    if px.isna().any().any():
        bad = px.columns[px.isna().any()].tolist()
        raise ValueError(f"Po fill-gaps nadal są braki w kolumnach: {bad}")

    # Zapis w formacie DB_*.csv używanym przez passive_ledger.
    rows: List[List[str]] = []
    rows.append(["ASSET"] + mp["ASSET"].tolist())
    rows.append(["TICKER"] + mp["Ticker"].tolist())
    rows.append(["ISIN"] + mp["ISIN"].tolist())
    rows.append(["COST"] + [f"{float(x):.6f}" for x in mp["COST"].tolist()])
    rows.append(["NAME"] + mp["NAME"].fillna("").astype(str).tolist())
    rows.append(["LIB_COL"] + mp["LIB_COL"].tolist())

    for d, r in px.iterrows():
        rows.append([pd.Timestamp(d).strftime("%Y-%m-%d")] + [_fmt_num(v) for v in r.tolist()])

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)

    if diag_csv:
        diag_rows = []
        for _, row in mp.iterrows():
            s = lib[row["LIB_COL"]].dropna()
            diag_rows.append({
                "Ticker": row["Ticker"],
                "LIB_COL": row["LIB_COL"],
                "first_source": s.index.min().date() if not s.empty else "",
                "last_source": s.index.max().date() if not s.empty else "",
                "source_rows": len(s),
            })
        diag_rows.append({
            "Ticker": "__DB__",
            "LIB_COL": "COMMON_RANGE",
            "first_source": px.index.min().date(),
            "last_source": px.index.max().date(),
            "source_rows": len(px),
        })
        diag_rows.append({
            "Ticker": "__DB__",
            "LIB_COL": "GAPS_BEFORE_FILL",
            "first_source": gaps_before,
            "last_source": fill_gaps,
            "source_rows": len(gap_months),
        })
        pd.DataFrame(diag_rows).to_csv(diag_csv, index=False, encoding="utf-8")

    print(f"OK: build_db_synthetic.py 1.0")
    print(f"OK: zapisano {out_csv} ({len(px)} wierszy, {len(mp)} instrumentów)")
    print(f"OK: common_range {px.index.min().date()}..{px.index.max().date()}; fill_gaps={fill_gaps}; gaps_before_fill={gaps_before}")
    if diag_csv:
        print(f"OK: zapisano {diag_csv}")
# 4 END
# ==================================================================


# ==================================================================
# 5 BEGIN: CLI
# ==================================================================
def main(argv: List[str]) -> None:
    p = argparse.ArgumentParser(description="Buduje DB_SYNTH_*.csv z SYNTH_LIBRARY_MONTHLY_USD.csv i mappingu syntetycznego.")
    p.add_argument("--mapping", required=True, help="Mapping portfela syntetycznego CSV.")
    p.add_argument("--library", default="SYNTH_LIBRARY_MONTHLY_USD.csv", help="Biblioteka syntetyków miesięcznych.")
    p.add_argument("--out-etf", required=True, help="Wyjściowy DB_SYNTH_*.csv.")
    p.add_argument("--diag", default=None, help="Opcjonalny plik diagnostyczny CSV.")
    p.add_argument("--start", default=None, help="Opcjonalny start YYYY-MM-DD.")
    p.add_argument("--end", default=None, help="Opcjonalny koniec YYYY-MM-DD.")
    p.add_argument("--fill-gaps", choices=["error", "interpolate", "ffill"], default="error", help="Obsługa luk miesięcznych wewnątrz wspólnego zakresu.")
    args = p.parse_args(argv)

    build_db(
        mapping_csv=args.mapping,
        library_csv=args.library,
        out_csv=args.out_etf,
        start=args.start,
        end=args.end,
        fill_gaps=args.fill_gaps,
        diag_csv=args.diag,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
# 5 END
# ==================================================================

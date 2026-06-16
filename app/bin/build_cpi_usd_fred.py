#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import pandas as pd
import requests

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"

def main():
    ap = argparse.ArgumentParser(description="Build CPI_USD.csv from FRED CPIAUCNS.")
    ap.add_argument("--start", default="1960-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--out", default="CPI_USD.csv")
    ap.add_argument("--raw-out", default=None)
    args = ap.parse_args()

    r = requests.get(FRED_CSV_URL, timeout=60)
    r.raise_for_status()
    text = r.text

    if args.raw_out:
        Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.raw_out).write_text(text, encoding="utf-8")

    from io import StringIO
    df = pd.read_csv(StringIO(text))
    if "observation_date" not in df.columns or "CPIAUCNS" not in df.columns:
        raise RuntimeError("Nieoczekiwany format FRED CSV dla CPIAUCNS.")

    out = pd.DataFrame({
        "date": pd.to_datetime(df["observation_date"], errors="coerce"),
        "cpi": pd.to_numeric(df["CPIAUCNS"], errors="coerce"),
    }).dropna().sort_values("date")

    start = pd.to_datetime(args.start)
    out = out[out["date"] >= start]
    if args.end:
        out = out[out["date"] <= pd.to_datetime(args.end)]

    out["infl_mom"] = out["cpi"].pct_change()
    out["infl_yoy"] = out["cpi"].pct_change(12)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"OK: zapisano {args.out}; rows={len(out)}; range={out['date'].iloc[0]}..{out['date'].iloc[-1]}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-

import argparse
import datetime as dt
from pathlib import Path
import time
import pandas as pd
import requests

BASE = "https://api.nbp.pl/api/exchangerates/rates/a/{ccy}/{start}/{end}/?format=json"

def daterange_chunks(start: dt.date, end: dt.date, max_days: int = 367):
    cur = start
    while cur <= end:
        chunk_end = min(end, cur + dt.timedelta(days=max_days - 1))
        yield cur, chunk_end
        cur = chunk_end + dt.timedelta(days=1)

def fetch_rates(ccy: str, start: dt.date, end: dt.date):
    rows = []
    for a, b in daterange_chunks(start, end):
        url = BASE.format(ccy=ccy.lower(), start=a.isoformat(), end=b.isoformat())
        r = requests.get(url, timeout=60)
        if r.status_code == 404:
            print(f"WARN: brak danych NBP dla {ccy} {a}..{b}")
            continue
        r.raise_for_status()
        js = r.json()
        for rate in js.get("rates", []):
            rows.append((rate["effectiveDate"], rate["mid"]))
        time.sleep(0.15)
    return rows

def main():
    ap = argparse.ArgumentParser(description="Build project DB_FX.csv from NBP API table A.")
    ap.add_argument("--ccy", default="USD", help="Currency code, default USD.")
    ap.add_argument("--start", default="2002-01-02", help="NBP API usually covers modern history; for hist ETF use 2005-01-01.")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD, default today.")
    ap.add_argument("--out", default="DB_FX.csv")
    args = ap.parse_args()

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()

    rows = fetch_rates(args.ccy, start, end)
    if not rows:
        raise RuntimeError("Nie pobrano żadnych kursów z NBP.")

    df = pd.DataFrame(rows, columns=["DATE", f"{args.ccy.upper()}/PLN"])
    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.drop_duplicates("DATE").sort_values("DATE")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(f"NAME,{args.ccy.upper()}/PLN\n")
        f.write(f"ISIN,{args.ccy.upper()}PLN\n")
        for _, r in df.iterrows():
            f.write(f"{r['DATE'].strftime('%Y-%m-%d')},{float(r[f'{args.ccy.upper()}/PLN']):.8f}\n")

    print(f"OK: zapisano {args.out}; ccy={args.ccy.upper()}; rows={len(df)}; range={df['DATE'].iloc[0].date()}..{df['DATE'].iloc[-1].date()}")

if __name__ == "__main__":
    main()

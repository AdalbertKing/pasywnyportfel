#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import pandas as pd


def base_name(portfel: str) -> tuple[str, str]:
    s = str(portfel)
    if " SYN /" in s:
        return s.split(" SYN /", 1)[0].strip(), "SYN"
    if " HIST /" in s:
        return s.split(" HIST /", 1)[0].strip(), "HIST"
    if "SYN" in s.upper():
        return s.replace("SYN", "").strip(), "SYN"
    if "HIST" in s.upper():
        return s.replace("HIST", "").strip(), "HIST"
    return s.strip(), ""


def main():
    ap = argparse.ArgumentParser(description="Rankuje rozjazd SYN vs HIST z summary_stage2.")
    ap.add_argument("summary_csv")
    ap.add_argument("--out", default=None)
    ap.add_argument("--metric", default="CAGR_%")
    args = ap.parse_args()

    df = pd.read_csv(args.summary_csv)
    if "PORTFEL" not in df.columns:
        raise SystemExit("Brak kolumny PORTFEL.")
    if args.metric not in df.columns:
        raise SystemExit(f"Brak kolumny {args.metric}.")

    df["_BASE"], df["_KIND"] = zip(*df["PORTFEL"].map(base_name))
    rows = []
    for base, g in df.groupby("_BASE", sort=False):
        syn = g[g["_KIND"] == "SYN"]
        hist = g[g["_KIND"] == "HIST"]
        if syn.empty or hist.empty:
            continue
        syn = syn.iloc[0]
        hist = hist.iloc[0]
        def num(row, col):
            return pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]

        c_syn = num(syn, "CAGR_%")
        c_hist = num(hist, "CAGR_%")
        rows.append({
            "PAIR": base,
            "CAGR_SYN_%": c_syn,
            "CAGR_HIST_%": c_hist,
            "CAGR_GAP_PP": c_syn - c_hist,
            "ABS_CAGR_GAP_PP": abs(c_syn - c_hist),
            "MAXDD_SYN_%": num(syn, "MAXDD_%"),
            "MAXDD_HIST_%": num(hist, "MAXDD_%"),
            "MAXDD_GAP_PP": num(syn, "MAXDD_%") - num(hist, "MAXDD_%"),
            "STDEV_SYN_%": num(syn, "STDEV_%"),
            "STDEV_HIST_%": num(hist, "STDEV_%"),
            "STDEV_GAP_PP": num(syn, "STDEV_%") - num(hist, "STDEV_%"),
            "END_SYN": num(syn, "END_VALUE"),
            "END_HIST": num(hist, "END_VALUE"),
        })

    out = pd.DataFrame(rows)
    if out.empty:
        raise SystemExit("Nie znalazlem par SYN/HIST.")
    out = out.sort_values(["ABS_CAGR_GAP_PP", "PAIR"], ascending=[True, True])

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.out, index=False)
        print(f"OK: zapisano {args.out}")

    cols = ["PAIR","CAGR_SYN_%","CAGR_HIST_%","CAGR_GAP_PP","ABS_CAGR_GAP_PP","MAXDD_SYN_%","MAXDD_HIST_%","STDEV_SYN_%","STDEV_HIST_%"]
    print(out[cols].to_string(index=False))


if __name__ == "__main__":
    main()

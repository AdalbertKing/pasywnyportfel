#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja: refresh_quotes.py 1.3 ANALYSIS_START_CHECK
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.

import argparse
import csv
import sys
import time
import re
import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd

from common import detect_root, rel, task_rel, truthy


DEFAULT_LIBRARY = "data/in/libraries/HIST_LIBRARY_DAILY.csv"
DEFAULT_MANIFEST = "data/in/libraries/HIST_LIBRARY_DAILY_manifest.csv"


def sniff_csv(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        sample = f.read(4096)
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=";,").delimiter
    except Exception:
        delim = ","
    return pd.read_csv(path, sep=delim, dtype=str).fillna("")


def pick_col(df: pd.DataFrame, names: list[str], required: bool = True) -> Optional[str]:
    low = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        c = low.get(n.lower())
        if c:
            return c
    if required:
        raise ValueError(f"Brak kolumny: jedna z {names}; dostępne: {list(df.columns)}")
    return None


def resolve_auto_start(value: str, today: dt.date) -> str:
    raw = str(value or "").strip()
    u = raw.upper().replace("_", "-")
    if raw == "" or u in {"AUTO", "TODAY", "LATEST", "NOW"}:
        return today.isoformat()
    m = re.match(r"^AUTO-(\d+)([DWMY])$", u)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "D":
            return (today - dt.timedelta(days=n)).isoformat()
        if unit == "W":
            return (today - dt.timedelta(weeks=n)).isoformat()
        if unit == "M":
            # no dateutil dependency here
            month = today.month - n
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            day = min(today.day, 28)
            return dt.date(year, month, day).isoformat()
        if unit == "Y":
            return dt.date(today.year - n, today.month, min(today.day, 28)).isoformat()
    # explicit ISO date
    dt.date.fromisoformat(raw)
    return raw


def start_covered(first_date: str, requested_start: str, tolerance_days: int = 7) -> tuple[bool, str]:
    """
    True if library starts on/before requested_start or within tolerance after it.

    Reason: requested_start can be weekend/holiday, e.g. 2026-02-28 Saturday,
    while first Yahoo trading date is 2026-03-02 Monday.
    """
    first = dt.date.fromisoformat(str(first_date))
    req = dt.date.fromisoformat(str(requested_start))
    delta = (first - req).days
    if delta <= 0:
        return True, "covered"
    if delta <= tolerance_days:
        return True, f"first trading date {first.isoformat()} is {delta} day(s) after requested start {req.isoformat()}"
    return False, f"first date {first.isoformat()} is {delta} day(s) after requested start {req.isoformat()}"



def read_settings(path: Path) -> dict:
    """
    Read KEY,VALUE settings. Values may contain commas:
      plot_currencies,USD,PLN
      windows,"3,5,7,10"
    Split only on the first comma/semicolon.
    """
    out = {}
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().replace(" ", "") in {"key,value", "key;value"}:
                continue
            if "," in line:
                key, val = line.split(",", 1)
            elif ";" in line:
                key, val = line.split(";", 1)
            else:
                continue
            key = key.strip().strip('"').strip("'")
            val = val.strip()
            if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
                val = val[1:-1]
            if key:
                out[key] = val
    return out


def read_portfolios(path: Path) -> list[dict]:
    df = sniff_csv(path)
    rows = []
    for _, r in df.iterrows():
        d = {str(c).strip(): str(r[c]).strip() for c in df.columns}
        if truthy(d.get("INCLUDE", "1")):
            rows.append(d)
    return rows

def collect_from_mapping(mapping: Path) -> list[dict]:
    df = sniff_csv(mapping)
    c_ticker = pick_col(df, ["YFTicker", "Ticker", "Symbol"])
    c_isin = pick_col(df, ["ISIN"], required=False)
    c_ccy = pick_col(df, ["Currency", "CCY"], required=False)
    c_asset = pick_col(df, ["ASSET", "Asset"], required=False)
    out = []
    for _, r in df.iterrows():
        ticker = str(r[c_ticker]).strip()
        if not ticker:
            continue
        out.append({
            "Ticker": ticker,
            "ISIN": str(r[c_isin]).strip() if c_isin else "",
            "CCY": str(r[c_ccy]).strip().upper() if c_ccy else "",
            "ASSET": str(r[c_asset]).strip() if c_asset else "",
            "MAP": str(mapping),
        })
    return out


def collect_tasks(root: Path, task_names: list[str], startup: bool, all_tasks: bool) -> tuple[list[dict], str]:
    tasks = []
    if all_tasks:
        for d in sorted((root / "analysis_definitions").iterdir()):
            if d.is_dir() and (d / "settings.csv").exists() and (d / "portfolios.csv").exists():
                tasks.append(d.name)
    elif startup:
        so = root / "analysis_definitions/startup_order.csv"
        if not so.exists():
            raise FileNotFoundError("Brak analysis_definitions/startup_order.csv")
        df = sniff_csv(so)
        c_name = pick_col(df, ["ANALYSIS_FOLDER", "TASK", "TASK_NAME"])
        c_inc = pick_col(df, ["INCLUDE"], required=False)
        for _, r in df.iterrows():
            if c_inc and not truthy(r[c_inc]):
                continue
            tasks.append(str(r[c_name]).strip())
    else:
        tasks = task_names

    if not tasks:
        raise ValueError("Nie wskazano tasków. Użyj: refresh_quotes.cmd <task> albo --startup albo --all-tasks.")

    instruments = []
    context_lines = []
    today = dt.date.today()
    for task in tasks:
        task_dir = root / "analysis_definitions" / task
        settings_path = task_dir / "settings.csv"
        portfolios_path = task_dir / "portfolios.csv"
        if not settings_path.exists() or not portfolios_path.exists():
            raise FileNotFoundError(f"Brak taska albo plików settings/portfolios: {task}")
        settings = read_settings(settings_path)
        # Do walidacji pokrycia biblioteki HIST wymagany jest faktyczny start analizy,
        # a nie techniczny dbstart_hist. W przeciwnym razie task 2005 potrafił żądać
        # notowań od 2000 r. dla ETF-ów, które wtedy jeszcze nie istniały.
        start_raw = settings.get("start") or settings.get("dbstart_hist") or "1900-01-01"
        try:
            req_start = resolve_auto_start(start_raw, today)
        except Exception:
            req_start = "1900-01-01"

        portfolios = read_portfolios(portfolios_path)
        for p in portfolios:
            map_hist = p.get("MAP_HIST", "").strip()
            if not map_hist:
                continue
            mp = task_rel(root, task_dir, map_hist)
            if not mp.exists():
                raise FileNotFoundError(f"Brak MAP_HIST dla taska {task}: {map_hist}")
            for inst in collect_from_mapping(mp):
                inst["TASK"] = task
                inst["REQ_START"] = req_start
                instruments.append(inst)
        context_lines.append(f"{task}: start={req_start}")

    return instruments, "; ".join(context_lines)


def read_library(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="DATE"))
    df = pd.read_csv(path)
    if df.empty or "DATE" not in df.columns:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="DATE"))
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"]).set_index("DATE").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def write_library(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.sort_index().copy()
    out.index = pd.to_datetime(out.index)
    out = out[~out.index.duplicated(keep="last")]
    out = out.reset_index().rename(columns={"index": "DATE"})
    if "DATE" not in out.columns:
        out = out.rename(columns={out.columns[0]: "DATE"})
    out["DATE"] = pd.to_datetime(out["DATE"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, encoding="utf-8")


def extract_adj_close(data: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame) and "Adj Close" in data.columns:
        px = data["Adj Close"]
    else:
        px = data
    if isinstance(px, pd.Series):
        px = px.to_frame(name=tickers[0])
    px.index = pd.to_datetime(px.index)
    return px.sort_index()


def download_prices(tickers: list[str], start: str, end: Optional[str]) -> pd.DataFrame:
    try:
        import yfinance as yf
    except Exception as e:
        raise RuntimeError("Brak modułu yfinance. Uruchom: pip install -r requirements.txt") from e

    errors = []
    for attempt in range(1, 5):
        try:
            data = yf.download(tickers, start=start, end=end, auto_adjust=False, progress=True, threads=False)
            px = extract_adj_close(data, tickers)
            if not px.empty:
                return px
            errors.append(f"batch attempt {attempt}: empty")
        except Exception as e:
            errors.append(f"batch attempt {attempt}: {type(e).__name__}: {e}")
        time.sleep(min(2 * attempt, 8))

    series = {}
    for ticker in tickers:
        terr = []
        for attempt in range(1, 5):
            try:
                data = yf.download([ticker], start=start, end=end, auto_adjust=False, progress=True, threads=False)
                px = extract_adj_close(data, [ticker])
                if ticker in px.columns:
                    s = px[ticker].dropna()
                elif len(px.columns) == 1:
                    s = px.iloc[:, 0].dropna()
                    s.name = ticker
                else:
                    s = pd.Series(dtype=float, name=ticker)
                if not s.empty:
                    series[ticker] = s.rename(ticker)
                    break
                terr.append(f"attempt {attempt}: empty")
            except Exception as e:
                terr.append(f"attempt {attempt}: {type(e).__name__}: {e}")
            time.sleep(min(2 * attempt, 8))
        if ticker not in series:
            errors.append(f"{ticker}: " + " | ".join(terr))

    if series:
        return pd.concat(series.values(), axis=1).sort_index()

    raise RuntimeError("Nie udało się pobrać notowań z Yahoo/yfinance. " + " ; ".join(errors[-10:]))


def update_manifest(path: Path, lib: pd.DataFrame, instruments: list[dict]) -> None:
    rows = []
    meta = {}
    for inst in instruments:
        t = inst["Ticker"]
        meta.setdefault(t, inst)
    now = dt.datetime.now().isoformat(timespec="seconds")
    for ticker in sorted(meta):
        if ticker in lib.columns:
            s = lib[ticker].dropna()
            if not s.empty:
                rows.append({
                    "TICKER": ticker,
                    "SOURCE": "YAHOO_ADJ_CLOSE",
                    "FIRST_DATE": s.index.min().date().isoformat(),
                    "LAST_DATE": s.index.max().date().isoformat(),
                    "LAST_REFRESH": now,
                    "ROWS": len(s),
                    "STATUS": "OK",
                    "COMMENT": f"CCY={meta[ticker].get('CCY','')}; ISIN={meta[ticker].get('ISIN','')}",
                })
            else:
                rows.append({
                    "TICKER": ticker,
                    "SOURCE": "YAHOO_ADJ_CLOSE",
                    "FIRST_DATE": "",
                    "LAST_DATE": "",
                    "LAST_REFRESH": now,
                    "ROWS": 0,
                    "STATUS": "EMPTY",
                    "COMMENT": "",
                })
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["TICKER","SOURCE","FIRST_DATE","LAST_DATE","LAST_REFRESH","ROWS","STATUS","COMMENT"]).to_csv(path, index=False, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Odśwież lokalną bibliotekę dziennych notowań ETF/HIST.")
    ap.add_argument("tasks", nargs="*", help="Nazwy tasków, np. user_template daily_hist_smoke_3m")
    ap.add_argument("--root", default="AUTO")
    ap.add_argument("--startup", action="store_true", help="Czytaj taski z analysis_definitions/startup_order.csv")
    ap.add_argument("--all-tasks", action="store_true", help="Zbierz tickery ze wszystkich tasków w analysis_definitions")
    ap.add_argument("--library", default=DEFAULT_LIBRARY)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--start", default=None, help="Wymuś start pobierania dla wszystkich tickerów.")
    ap.add_argument("--end", default=None, help="Data końca dla yfinance; domyślnie dziś/ostatnie dostępne.")
    ap.add_argument("--check", action="store_true", help="Tylko sprawdź, czy biblioteka pokrywa tickery i zakres. Bez internetu.")
    ap.add_argument("--start-tolerance-days", type=int, default=7, help="Tolerancja dla pierwszej sesji po żądanej dacie startu, np. weekend/święto. Domyślnie 7 dni.")
    args = ap.parse_args()

    root = detect_root(args.root)
    library_path = rel(root, args.library)
    manifest_path = rel(root, args.manifest)

    instruments, context = collect_tasks(root, args.tasks, args.startup, args.all_tasks)
    # de-duplicate by ticker, choose earliest required start
    by_ticker = {}
    for inst in instruments:
        t = inst["Ticker"]
        if t not in by_ticker:
            by_ticker[t] = inst.copy()
        else:
            if inst.get("REQ_START", "9999-12-31") < by_ticker[t].get("REQ_START", "9999-12-31"):
                by_ticker[t]["REQ_START"] = inst.get("REQ_START", by_ticker[t].get("REQ_START"))
    instruments = list(by_ticker.values())
    tickers = sorted(by_ticker)

    if not tickers:
        print("OK: brak tickerów HIST do odświeżenia/sprawdzenia.")
        return 0

    lib = read_library(library_path)

    print("================================================================")
    print("HIST LIBRARY DAILY REFRESH/CHECK")
    print("================================================================")
    print(f"ROOT:      {root}")
    print(f"LIBRARY:   {library_path}")
    print(f"MANIFEST:  {manifest_path}")
    print(f"TICKERS:   {', '.join(tickers)}")
    print(f"CONTEXT:   {context}")
    print("================================================================")

    missing = []
    insufficient = []
    for ticker, inst in by_ticker.items():
        req = args.start or inst.get("REQ_START") or "1900-01-01"
        if ticker not in lib.columns or lib[ticker].dropna().empty:
            missing.append((ticker, req))
        else:
            s = lib[ticker].dropna()
            first = pd.Timestamp(s.index.min()).date().isoformat()
            ok, note = start_covered(first, req, args.start_tolerance_days)
            if not ok:
                insufficient.append((ticker, req, first))
    if args.check:
        if missing or insufficient:
            print("BRAK/ZA KRÓTKIE NOTOWANIA W HIST_LIBRARY_DAILY:")
            for t, req in missing:
                print(f"  BRAK {t}; wymagany start <= {req}")
            for t, req, first in insufficient:
                print(f"  ZA KRÓTKO {t}; wymagany start <= {req}; biblioteka od {first}")
            print("Uruchom:")
            print("  refresh_quotes.cmd " + (" ".join(args.tasks) if args.tasks else "--startup"))
            return 2
        print("OK: biblioteka HIST pokrywa wymagane tickery i starty.")
        print(f"INFO: tolerancja pierwszej sesji po starcie = {args.start_tolerance_days} dni.")
        return 0

    # Download from the earliest required start among tickers or explicit --start.
    starts = [args.start or inst.get("REQ_START") or "1900-01-01" for inst in instruments]
    dl_start = min(starts)
    print(f"DOWNLOAD START: {dl_start}")
    print(f"DOWNLOAD END:   {args.end or 'today'}")

    px = download_prices(tickers, start=dl_start, end=args.end)
    px = px[[c for c in px.columns if c in tickers]].copy()
    if px.empty:
        raise RuntimeError("Pobrane notowania są puste.")

    # Merge with existing library.
    combined = lib.copy()
    if combined.empty:
        combined = px
    else:
        for c in px.columns:
            combined[c] = combined[c] if c in combined.columns else pd.Series(dtype=float)
        combined = combined.combine_first(px)
        combined.update(px)
        combined = combined.sort_index()
    # Keep all historical columns but sort visible columns alphabetically.
    cols = sorted(combined.columns)
    combined = combined[cols]

    write_library(library_path, combined)
    update_manifest(manifest_path, combined, instruments)

    print("OK: zapisano bibliotekę HIST.")
    print(f"  rows={len(combined)} cols={len(combined.columns)}")
    for t in tickers:
        s = combined[t].dropna() if t in combined.columns else pd.Series(dtype=float)
        if s.empty:
            print(f"  {t}: BRAK")
        else:
            print(f"  {t}: {s.index.min().date()}..{s.index.max().date()} rows={len(s)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(1)

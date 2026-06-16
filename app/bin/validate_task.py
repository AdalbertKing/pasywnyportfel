#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, csv, sys, py_compile, os
import datetime as dt
from pathlib import Path
from typing import Optional

from common import detect_root, task_rel, read_settings, resolve_auto_date_token

VERSION = "validate_task.py 1.2 LIBRARY_TICKER_COVERAGE"

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def weight_sum(path):
    rows = read_csv(path)
    if not rows: raise ValueError("pusta mapa")
    cols = {c.upper(): c for c in rows[0].keys()}
    wcol = cols.get("WEIGHT") or cols.get("WEIGHT_%")
    if not wcol: raise ValueError("brak kolumny WEIGHT")
    total = 0.0
    for r in rows:
        total += float(str(r.get(wcol, "0")).replace(",", "."))
    return total, rows[0].keys()

def validate_dates(settings: dict) -> tuple[str, str]:
    """Sprawdza czy start < end po rozwiązaniu tokenów AUTO.

    Zwraca krotkę (resolved_start, resolved_end) przy sukcesie.
    Rzuca ValueError z czytelnym komunikatem przy błędzie.
    """
    today = dt.date.today()
    start_raw = (settings.get("start") or "").strip()
    end_raw   = (settings.get("end")   or "").strip()

    try:
        start_iso, start_desc = resolve_auto_date_token(start_raw or "AUTO", today)
    except Exception as e:
        raise ValueError(f"Nieprawidłowa wartość start={start_raw!r}: {e}") from e

    try:
        end_iso, end_desc = resolve_auto_date_token(end_raw or "AUTO", today)
    except Exception as e:
        raise ValueError(f"Nieprawidłowa wartość end={end_raw!r}: {e}") from e

    start_date = dt.date.fromisoformat(start_iso)
    end_date   = dt.date.fromisoformat(end_iso)

    if start_date >= end_date:
        raise ValueError(
            f"start >= end po rozwiązaniu tokenów:\n"
            f"  start: {start_raw!r} -> {start_iso}\n"
            f"  end:   {end_raw!r} -> {end_iso}\n"
            f"  Wymagane: start < end."
        )

    return start_iso, end_iso


# ---------------------------------------------------------------------------
# Pokrycie tickerów map przez biblioteki SYNTH/HIST
# ---------------------------------------------------------------------------

# Te same aliasy kolumn, co w build_db_synthetic.py (LIB_COL) i
# refresh_quotes.py / build_db_freq.py (YFTicker/Ticker/Symbol).
_SYNTH_LIB_COL_ALIASES = ["LIB_COL", "Library", "LIBRARY_COL", "SERIES", "Source", "SOURCE_COL"]
_TICKER_ALIASES = ["Ticker", "TICKER", "Symbol"]
_HIST_TICKER_ALIASES = ["YFTicker", "Ticker", "Symbol"]

SYNTH_LIBRARY_FILENAME = "SYNTH_LIBRARY_MONTHLY_USD.csv"
HIST_LIBRARY_FILENAME = "HIST_LIBRARY_DAILY.csv"


def _pick_col(columns, names) -> Optional[str]:
    """Case-insensitive wybor pierwszej dopasowanej kolumny."""
    cols_lc = {str(c).strip().lower(): c for c in columns}
    for n in names:
        c = cols_lc.get(n.strip().lower())
        if c:
            return c
    return None


def load_library_columns(root: Path, filename: str) -> Optional[set[str]]:
    """Czyta naglowek pliku biblioteki (DATE,<ticker1>,<ticker2>,...).

    Zwraca zbior nazw tickerow (bez DATE), albo None jesli plik biblioteki
    jeszcze nie istnieje (np. HIST_LIBRARY_DAILY.csv przed pierwszym
    refresh_quotes.cmd). Brak biblioteki nie jest bledem konfiguracji
    taska -- to po prostu sygnal "jeszcze nie wygenerowano".
    """
    path = root / "data" / "in" / "libraries" / filename
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f), [])
    return {c.strip() for c in header[1:] if c.strip()}


def map_ticker_values(map_path: Path, kind: str) -> tuple[Optional[str], list[str]]:
    """Zwraca (nazwa_kolumny, lista_wartosci_tickerow) dla danej mapy.

    kind="synth": kolumna LIB_COL (z fallbackiem na Ticker), tak jak
                  build_db_synthetic.py przy budowie DB z SYNTH_LIBRARY.
    kind="hist":  kolumna YFTicker/Ticker/Symbol, tak jak refresh_quotes.py
                  i build_db_freq.py przy pobieraniu/odczycie HIST_LIBRARY.
    """
    rows = read_csv(map_path)
    if not rows:
        return None, []
    cols = rows[0].keys()
    if kind == "synth":
        col = _pick_col(cols, _SYNTH_LIB_COL_ALIASES) or _pick_col(cols, _TICKER_ALIASES)
    else:
        col = _pick_col(cols, _HIST_TICKER_ALIASES)
    if not col:
        return None, []
    values = [(r.get(col) or "").strip() for r in rows]
    return col, [v for v in values if v]


def validate_task(root, task_name):
    task_dir = root / "analysis_definitions" / task_name
    if not task_dir.exists():
        raise FileNotFoundError(f"brak folderu taska: {task_dir}")
    settings_path = task_dir / "settings.csv"
    portfolios_path = task_dir / "portfolios.csv"
    if not settings_path.exists(): raise FileNotFoundError(f"brak settings.csv: {settings_path}")
    if not portfolios_path.exists(): raise FileNotFoundError(f"brak portfolios.csv: {portfolios_path}")

    settings = read_settings(settings_path)
    start_iso, end_iso = validate_dates(settings)

    synth_lib_cols = load_library_columns(root, SYNTH_LIBRARY_FILENAME)
    hist_lib_cols = load_library_columns(root, HIST_LIBRARY_FILENAME)

    rows = read_csv(portfolios_path)
    if not rows: raise ValueError("portfolios.csv jest pusty")
    included = 0
    checked_maps = []
    warnings: list[str] = []
    for r in rows:
        inc = str(r.get("INCLUDE", "1")).strip().lower()
        if inc in {"0", "false", "no", "nie", "off"}: continue
        included += 1
        pid = r.get("ID", "")
        for col in ["MAP_SYNTH", "MAP_HIST"]:
            v = (r.get(col) or "").strip()
            if not v: continue
            p = task_rel(root, task_dir, v)
            if not p.exists():
                raise FileNotFoundError(f"brak {col} dla {pid}: {v}\n  oczekiwane: {p}")
            total, cols = weight_sum(p)
            if abs(total - 100.0) > 0.05:
                raise ValueError(f"suma wag != 100 w {p}: {total}")
            checked_maps.append((col, pid, v, total))

            # Pokrycie biblioteki -- wykrywa "Brak serii w bibliotece" /
            # "Brak tickerow w bazie cen" PRZED uruchomieniem build_db_*/passive_ledger.
            if col == "MAP_SYNTH":
                ticker_col, values = map_ticker_values(p, "synth")
                if synth_lib_cols is not None and values:
                    missing = sorted({v for v in values if v not in synth_lib_cols})
                    if missing:
                        raise ValueError(
                            f"BRAK SERII W {SYNTH_LIBRARY_FILENAME} dla {pid} ({p.name}), "
                            f"kolumna {ticker_col}: {missing}\n"
                            f"  To jest dokladnie blad, ktory build_db_synthetic.py "
                            f"zglosilby w polowie analizy. Sprawdz literowki w {ticker_col} "
                            f"albo dostepne serie w data/in/libraries/{SYNTH_LIBRARY_FILENAME}."
                        )
            else:  # MAP_HIST
                ticker_col, values = map_ticker_values(p, "hist")
                if hist_lib_cols is None:
                    if values:
                        warnings.append(
                            f"{pid} ({p.name}): {HIST_LIBRARY_FILENAME} nie istnieje -- "
                            f"uruchom refresh_quotes.cmd {task_name}"
                        )
                elif values:
                    missing = sorted({v for v in values if v not in hist_lib_cols})
                    if missing:
                        warnings.append(
                            f"{pid} ({p.name}): brak {missing} w {HIST_LIBRARY_FILENAME} "
                            f"(kolumna {ticker_col}) -- uruchom refresh_quotes.cmd {task_name}"
                        )

    if included == 0: raise ValueError("brak portfeli INCLUDE=1")
    return task_dir, included, checked_maps, start_iso, end_iso, warnings

def main():
    ap = argparse.ArgumentParser(description="Validate one analysis task folder.")
    ap.add_argument("task", help="Folder name under analysis_definitions")
    args = ap.parse_args()
    root = detect_root()
    try:
        task_dir, included, checked_maps, start_iso, end_iso, warns = validate_task(root, args.task)
    except Exception as e:
        print("ERROR:", e)
        return 1
    print(f"OK TASK: {args.task}")
    print(f"  folder: {task_dir}")
    print(f"  period: {start_iso} -> {end_iso}")
    print(f"  portfolios INCLUDE=1: {included}")
    print(f"  checked maps: {len(checked_maps)}")
    for col, pid, path, total in checked_maps:
        print(f"  OK {col:9} {pid:20} {path}  weights={total:.2f}")
    for w in warns:
        print(f"  WARN {w}")
    return 0
if __name__ == "__main__": sys.exit(main())

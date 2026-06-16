#!/usr/bin/env python3
# pasywnyportfel — kontrola stanu pakietu po 1-start_setup.cmd
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
health_check.py — pelna weryfikacja stanu pakietu w czystym Pythonie.

Zastepuje kruchen logike test_after_start.cmd (wieloliniowe `python -c "..."`
nie dzialaja w CMD -- cmd rozbija stringi i probuje wykonac fragmenty jako
komendy). Tutaj cala logika jest w Pythonie, a .cmd tylko uruchamia ten plik.

Fazy:
  1. Srodowisko Python (biblioteki + moduly projektu)
  2. Kompilacja (deleguje do stage1_quick_check przez import)
  3. Dane wspolne CPI/FX (istnienie + swiezosc < 120 dni)
  4. Walidacja wszystkich taskow (start<end, mapy, wagi, pokrycie bibliotek)
  5. Wyniki analiz (analysis_results + reports/analysis_index.csv)
  6. Smoke test CLI (passive_ledger --help, analysis --help)

Exit code = liczba FAIL (0 = OK, ostrzezenia WARN nie licza sie jako FAIL).
"""

import csv
import datetime as dt
import importlib
import subprocess
import sys
from pathlib import Path

from common import detect_root
from task_config import list_tasks
from validate_task import validate_task

VERSION = "health_check.py 1.0 POST_SETUP_HEALTH"

FRESHNESS_DAYS = 120


class Counter:
    def __init__(self):
        self.passed = 0
        self.warned = 0
        self.failed = 0

    def ok(self, msg):
        self.passed += 1
        print(f"  OK   {msg}")

    def warn(self, msg):
        self.warned += 1
        print(f"  WARN {msg}")

    def fail(self, msg):
        self.failed += 1
        print(f"  FAIL {msg}")


def phase_header(title):
    print(f"\n{title}")
    print("-" * 40)


# ---------------------------------------------------------------------------
# FAZA 1 — Srodowisko
# ---------------------------------------------------------------------------

def check_environment(c: Counter):
    phase_header("[FAZA 1] Srodowisko Python i importy")

    libs = ["pandas", "numpy", "matplotlib", "yfinance", "requests", "dateutil"]
    for lib in libs:
        try:
            importlib.import_module(lib)
            c.ok(f"import {lib}")
        except ImportError:
            c.fail(f"import {lib} — brak biblioteki (pip install -r requirements.txt)")

    modules = [
        "common", "task_config", "cmd_builders", "run_logging",
        "create_task", "validate_task", "run_all_tasks", "cleanup_old_results",
        "ledger_primitives", "ledger_io", "ledger_tax", "ledger_engine",
        "passive_ledger", "analysis",
    ]
    for mod in modules:
        try:
            importlib.import_module(mod)
            c.ok(f"import {mod}")
        except Exception as e:
            c.fail(f"import {mod} — {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# FAZA 2 — Kompilacja
# ---------------------------------------------------------------------------

def check_compilation(root: Path, c: Counter):
    phase_header("[FAZA 2] Kompilacja i struktura projektu")
    script = root / "app" / "bin" / "stage1_quick_check.py"
    r = subprocess.run(
        [sys.executable, str(script)], cwd=str(root),
        capture_output=True, text=True, errors="replace",
    )
    if r.returncode == 0:
        c.ok("stage1_quick_check — kompilacja + taski + mapy")
    else:
        c.fail("stage1_quick_check — sa bledy (uruchom: python app/bin/stage1_quick_check.py)")
        tail = "\n".join(r.stdout.strip().splitlines()[-5:])
        print(tail)


# ---------------------------------------------------------------------------
# FAZA 3 — Dane wspolne CPI/FX
# ---------------------------------------------------------------------------

def _last_date_in_csv(path: Path):
    """Ostatnia data ISO w pierwszej kolumnie CSV (obsluguje formaty wide z metadanymi)."""
    last = None
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            try:
                last = dt.date.fromisoformat(row[0].strip()[:10])
            except ValueError:
                continue
    return last


def check_common_data(root: Path, c: Counter):
    phase_header("[FAZA 3] Dane wspolne CPI / FX / biblioteki")

    required = [
        ("data/in/cpi/CPI_USD.csv", "CPI USD"),
        ("data/in/cpi/CPI_PLN_GUS.csv", "CPI PLN GUS"),
        ("data/in/fx/DB_FX.csv", "FX USD/PLN"),
        ("data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv", "SYNTH Library"),
    ]
    for rel_path, label in required:
        p = root / rel_path
        if p.exists():
            c.ok(f"{label} — {rel_path}")
        else:
            c.fail(f"{label} — BRAK: {rel_path}")

    hist = root / "data/in/libraries/HIST_LIBRARY_DAILY.csv"
    if hist.exists():
        c.ok(f"HIST Library — data/in/libraries/HIST_LIBRARY_DAILY.csv")
    else:
        c.warn("HIST Library — brak (uruchom refresh_quotes.cmd <task>)")

    today = dt.date.today()
    freshness_files = [
        ("CPI_USD", "data/in/cpi/CPI_USD.csv"),
        ("CPI_PLN_GUS", "data/in/cpi/CPI_PLN_GUS.csv"),
        ("DB_FX", "data/in/fx/DB_FX.csv"),
    ]
    stale = []
    for label, rel_path in freshness_files:
        p = root / rel_path
        if not p.exists():
            continue
        try:
            last = _last_date_in_csv(p)
            if last is None:
                c.warn(f"{label}: nie znaleziono dat w pliku")
                stale.append(label)
                continue
            age = (today - last).days
            if age < FRESHNESS_DAYS:
                c.ok(f"{label}: ostatnia data {last.isoformat()} ({age} dni temu)")
            else:
                c.warn(f"{label}: ostatnia data {last.isoformat()} ({age} dni temu) — uruchom refresh_data.cmd")
                stale.append(label)
        except OSError as e:
            c.warn(f"{label}: blad odczytu — {e}")
            stale.append(label)


# ---------------------------------------------------------------------------
# FAZA 4 — Walidacja taskow
# ---------------------------------------------------------------------------

def check_tasks(root: Path, c: Counter):
    phase_header("[FAZA 4] Walidacja taskow (start/end, mapy, wagi, pokrycie bibliotek)")
    tasks = list_tasks(root)
    if not tasks:
        c.warn("brak taskow w analysis_definitions")
        return
    for task in tasks:
        try:
            _, included, maps, start_iso, end_iso, warns = validate_task(root, task)
            c.ok(f"{task}: portfolios={included}, maps={len(maps)}, {start_iso} -> {end_iso}")
            for w in warns:
                c.warn(f"  {w}")
        except Exception as e:
            c.fail(f"{task}: {e}")


# ---------------------------------------------------------------------------
# FAZA 5 — Wyniki analiz
# ---------------------------------------------------------------------------

def check_results(root: Path, c: Counter):
    phase_header("[FAZA 5] Wyniki analiz")
    results_dir = root / "analysis_results"
    if not results_dir.exists():
        c.warn("brak katalogu analysis_results — 1-start_setup.cmd nie uruchomil analiz")
    else:
        run_dirs = [p for p in results_dir.iterdir() if p.is_dir() and "__" in p.name]
        if not run_dirs:
            c.warn("analysis_results istnieje, ale jest pusty")
        else:
            for d in sorted(run_dirs):
                if (d / "README_ANALYSIS.txt").exists():
                    c.ok(f"{d.name} — README_ANALYSIS.txt istnieje")
                else:
                    c.warn(f"{d.name} — brak README_ANALYSIS.txt (analiza mogla sie nie dokonczyc)")

    index = root / "reports" / "analysis_index.csv"
    if index.exists():
        try:
            with index.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            c.ok(f"reports/analysis_index.csv — {len(rows)} rekordow")
            for r in rows[-3:]:
                ts = r.get("timestamp", "?")
                folder = (r.get("run_folder", "?") or "?")[:60]
                print(f"       {ts} | {folder}")
        except OSError as e:
            c.warn(f"reports/analysis_index.csv — blad odczytu: {e}")
    else:
        c.warn("brak reports/analysis_index.csv — analizy jeszcze nie byly uruchomione")


# ---------------------------------------------------------------------------
# FAZA 6 — Smoke test CLI
# ---------------------------------------------------------------------------

def check_cli(root: Path, c: Counter):
    phase_header("[FAZA 6] Smoke test CLI (--help)")
    for script in ["passive_ledger.py", "analysis.py", "validate_task.py", "run_all_tasks.py"]:
        path = root / "app" / "bin" / script
        r = subprocess.run(
            [sys.executable, str(path), "--help"],
            capture_output=True, text=True, errors="replace",
        )
        if r.returncode == 0:
            c.ok(f"{script} --help")
        else:
            c.fail(f"{script} --help — kod {r.returncode}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    root = detect_root()
    print("=" * 64)
    print(" KONTROLA STANU PAKIETU  pasywnyportfel")
    print("=" * 64)
    print(f" Python: {sys.executable}")
    print(f" Root:   {root}")
    print("=" * 64)

    c = Counter()
    check_environment(c)
    check_compilation(root, c)
    check_common_data(root, c)
    check_tasks(root, c)
    check_results(root, c)
    check_cli(root, c)

    print("\n" + "=" * 64)
    print(" PODSUMOWANIE")
    print("=" * 64)
    print(f"  OK:   {c.passed}")
    print(f"  WARN: {c.warned}   (nie blokuja dzialania; warto sprawdzic)")
    print(f"  FAIL: {c.failed}   (wymagaja interwencji)")
    print("=" * 64)

    if c.failed == 0:
        if c.warned == 0:
            print(" WYNIK: OK - wszystkie testy zdane.")
        else:
            print(" WYNIK: OK z ostrzezeniami. Projekt dziala.")
    else:
        print(" WYNIK: BLEDY. Sprawdz linie FAIL powyzej.")

    return c.failed


if __name__ == "__main__":
    sys.exit(main())

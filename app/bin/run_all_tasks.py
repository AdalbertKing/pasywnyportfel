#!/usr/bin/env python3
# pasywnyportfel — batchowe uruchamianie wielu taskow
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
run_all_tasks.py — uruchamia analysis.py dla wielu taskow naraz i drukuje
zbiorcze podsumowanie (OK/FAIL + czas trwania dla kazdego).

Uzycie:
    python app/bin/run_all_tasks.py
    python app/bin/run_all_tasks.py --only user_template,daily_hist_smoke_3m
    python app/bin/run_all_tasks.py --exclude daily_hist_smoke_3m
    python app/bin/run_all_tasks.py --startup-only
    python app/bin/run_all_tasks.py --dry-run

Kazdy task jest uruchamiany jako osobny subprocess:
    analysis.py --root <root> --definition analysis_definitions/<task>

dokladnie tak jak robi to run_task.cmd <task> w ostatnim kroku. Ten skrypt
NIE wykonuje walidacji/refresh -- zaklada ze dane wspolne (CPI/FX) i
biblioteka HIST sa juz gotowe. Przed batchem uzyj:
    refresh_data.cmd
    refresh_quotes.cmd --all-tasks
albo uruchom kazdy task choc raz przez run_task.cmd, ktory to zrobi
automatycznie.

Jeden task ktory sie wywali NIE przerywa batcha -- bledy sa zbierane
i raportowane na koniec wraz z czasem trwania kazdego taska.
Exit code = liczba niepowodzen (0 = wszystko OK / DRY-RUN).
"""

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from common import detect_root
from task_config import list_tasks

VERSION = "run_all_tasks.py 1.0 BATCH_RUNNER"


def parse_csv_list(s: Optional[str]) -> set[str]:
    """Parsuje 'a, b,c' -> {'a','b','c'}. None/'' -> zbior pusty."""
    if not s:
        return set()
    return {x.strip() for x in s.split(",") if x.strip()}


def load_startup_tasks(root: Path) -> set[str]:
    """Czyta analysis_definitions/startup_order.csv, zwraca nazwy taskow
    z INCLUDE!=0. Brak pliku -> zbior pusty."""
    path = root / "analysis_definitions" / "startup_order.csv"
    if not path.exists():
        return set()
    out = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("ANALYSIS_FOLDER") or "").strip()
            inc = str(row.get("INCLUDE", "1")).strip().lower()
            if name and inc not in {"0", "false", "no", "nie", "off"}:
                out.add(name)
    return out


def select_tasks(
    all_tasks: list[str],
    only: Optional[str],
    exclude: Optional[str],
    startup_only: bool,
    startup_tasks: set[str],
) -> tuple[list[str], list[str]]:
    """Zwraca (wybrane_taski, nieznane_nazwy_z_--only).

    Kolejnosc filtrow: startup_only -> only -> exclude. Wynik zachowuje
    porzadek z all_tasks (alfabetyczny z list_tasks).
    """
    tasks = list(all_tasks)

    if startup_only:
        tasks = [t for t in tasks if t in startup_tasks]

    only_set = parse_csv_list(only)
    unknown = sorted(only_set - set(all_tasks)) if only_set else []
    if only_set:
        tasks = [t for t in tasks if t in only_set]

    exclude_set = parse_csv_list(exclude)
    tasks = [t for t in tasks if t not in exclude_set]

    return tasks, unknown


def run_one_task(root: Path, task: str, dry_run: bool, analysis_script: Optional[Path] = None) -> dict:
    """Uruchamia analysis.py dla jednego taska, strumieniujac output na konsole.

    Zwraca dict: {task, status, elapsed, error}
        status: "OK" | "DRY-RUN" | "FAIL"
        error:  komunikat (returncode) gdy status=="FAIL", inaczej None

    analysis_script pozwala wstrzyknac inny skrypt (uzywane w testach).
    """
    script = analysis_script or (root / "app" / "bin" / "analysis.py")
    cmd = [
        sys.executable, str(script),
        "--root", str(root),
        "--definition", f"analysis_definitions/{task}",
    ]
    if dry_run:
        cmd.append("--dry-run")

    print(f"\n{'=' * 64}")
    print(f"TASK: {task}")
    print("=" * 64)

    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=str(root), text=True, errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1,
    )
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
    finally:
        proc.stdout.close()
    rc = proc.wait()
    elapsed = time.monotonic() - start

    if rc != 0:
        return {"task": task, "status": "FAIL", "elapsed": elapsed, "error": f"returncode={rc}"}
    return {"task": task, "status": "DRY-RUN" if dry_run else "OK", "elapsed": elapsed, "error": None}


def print_summary(results: list[dict]) -> None:
    print(f"\n{'=' * 64}")
    print("PODSUMOWANIE")
    print("=" * 64)

    width = max((len(r["task"]) for r in results), default=4)
    total_elapsed = 0.0
    for r in results:
        total_elapsed += r["elapsed"]
        line = f"  {r['status']:8} {r['task']:<{width}}  {r['elapsed']:6.1f}s"
        if r["error"]:
            line += f"   {r['error']}"
        print(line)

    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_ok = len(results) - n_fail
    print(f"\n  OK/DRY-RUN: {n_ok}   FAIL: {n_fail}   RAZEM: {len(results)}   CZAS: {total_elapsed:.1f}s")


def main():
    ap = argparse.ArgumentParser(
        description="Run analysis.py for multiple tasks and print a summary table."
    )
    ap.add_argument("--only", default=None, help="Comma-separated task names to run (default: all)")
    ap.add_argument("--exclude", default=None, help="Comma-separated task names to skip")
    ap.add_argument("--startup-only", action="store_true",
                    help="Only run tasks listed in analysis_definitions/startup_order.csv with INCLUDE!=0")
    ap.add_argument("--dry-run", action="store_true", help="Pass --dry-run to analysis.py for each task")
    args = ap.parse_args()

    root = detect_root()
    all_tasks = list_tasks(root)

    if not all_tasks:
        print(f"Brak taskow w {root / 'analysis_definitions'}.")
        return 0

    startup_tasks = load_startup_tasks(root) if args.startup_only else set()
    if args.startup_only and not startup_tasks:
        print("WARN: startup_order.csv nie zawiera zadnych taskow z INCLUDE!=0, "
              "albo plik nie istnieje.")

    tasks, unknown = select_tasks(all_tasks, args.only, args.exclude, args.startup_only, startup_tasks)

    if unknown:
        print(f"ERROR: nieznane taski w --only: {unknown}")
        print(f"Dostepne taski: {all_tasks}")
        return 2

    if not tasks:
        print("Brak taskow do uruchomienia po filtrach --only/--exclude/--startup-only.")
        print(f"Dostepne taski: {all_tasks}")
        return 0

    print(f"BATCH: {len(tasks)} task(i): {', '.join(tasks)}")
    if args.dry_run:
        print("DRY-RUN: komendy analysis.py zostana wypisane, ale ich kroki nie zostana wykonane.")

    results = [run_one_task(root, task, args.dry_run) for task in tasks]
    print_summary(results)

    return sum(1 for r in results if r["status"] == "FAIL")


if __name__ == "__main__":
    sys.exit(main())

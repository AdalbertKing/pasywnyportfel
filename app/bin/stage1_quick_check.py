#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, py_compile, csv
from pathlib import Path
from validate_task import validate_task

from common import detect_root

VERSION = "stage1_quick_check.py 1.0 TASK_MODEL_STAGE1"

def main():
    root = detect_root()
    print("=== STAGE1 QUICK CHECK ===")
    print("ROOT:", root)
    required = [
        "analysis_definitions/common/maps/hist/sp500_hist.csv",
        "analysis_definitions/common/maps/synth/sp500_syn.csv",
        "analysis_definitions/common/task_templates/comparison_2005/settings.csv",
        "analysis_definitions/startup_order.csv",
        "create_task.cmd",
        "run_task.cmd",
        "refresh_quotes.cmd",
        "check_quotes.cmd",
        "refresh_data.cmd",
        "app/bin/analysis.py",
        "app/bin/create_task.py",
        "app/bin/validate_task.py",
    ]
    errors = []
    for rel in required:
        p = root / rel
        print(("OK   " if p.exists() else "BRAK ") + rel)
        if not p.exists(): errors.append(rel)
    # Old global maps folder should not be present in stage1 model
    old_maps = root / "data" / "in" / "maps"
    if old_maps.exists():
        print("WARN: istnieje stary globalny katalog map — stage1 używa analysis_definitions/common/maps oraz task/maps.")
    # compile scripts
    for rel in [
        "app/bin/common.py",
        "app/bin/run_logging.py",
        "app/bin/task_config.py",
        "app/bin/cmd_builders.py",
        "app/bin/analysis.py",
        "app/bin/bootstrap.py",
        "app/bin/create_task.py",
        "app/bin/validate_task.py",
        "app/bin/run_all_tasks.py",
        "app/bin/cleanup_old_results.py",
        "app/bin/health_check.py",
        "app/bin/ledger_primitives.py",
        "app/bin/ledger_io.py",
        "app/bin/ledger_tax.py",
        "app/bin/ledger_engine.py",
        "app/bin/passive_ledger.py",
    ]:
        try:
            py_compile.compile(str(root/rel), doraise=True)
            print("OK COMPILE", rel)
        except Exception as e:
            print("BRAK COMPILE", rel, e); errors.append(rel)
    # startup tasks
    startup = root / "analysis_definitions" / "startup_order.csv"
    tasks = []
    if startup.exists():
        with startup.open("r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if str(r.get("INCLUDE", "1")).strip() not in {"0", "false", "no"}:
                    tasks.append(r.get("ANALYSIS_FOLDER", "").strip())
    tasks += ["user_template", "bfly_10y_vs_vuds_2005", "daily_hist_smoke_3m"]
    seen = []
    for t in tasks:
        if not t or t in seen: continue
        seen.append(t)
        try:
            task_dir, included, checked, start_iso, end_iso, warns = validate_task(root, t)
            print(f"OK TASK {t}: portfolios={included}, maps={len(checked)}, period={start_iso} -> {end_iso}")
            for w in warns:
                print(f"  WARN {w}")
        except Exception as e:
            print(f"BRAK TASK {t}: {e}"); errors.append(t)
    if errors:
        print("WYNIK: ERROR", errors)
        return 1
    print("WYNIK: OK — stage1 task model jest spójny.")
    return 0
if __name__ == "__main__": sys.exit(main())

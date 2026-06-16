#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BANNED = [
    "benchmark_1960_synth_usd_gross",
    "bfly_short_vs_classic_2005",
    "run_bfly_10y_vs_vuds_2005",
    "data/in/maps",
    "data\\in\\maps",
]
SKIP_DIRS = {"analysis_results", "__pycache__", ".git", "runtime"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".pdf", ".pyc", ".zip", ".7z"}

print("=== STAGE1 CLEAN AUDIT ===")
print(f"ROOT: {ROOT}")
errors = []

must_not_exist = [
    ROOT / "run_bfly_10y_vs_vuds_2005.cmd",
    ROOT / "README_BFLY_IB_ACC_MODIFIED.txt",
    ROOT / "README_BFLY_WBUDOWANY.txt",
    ROOT / "README_RUN_BFLY_10Y_VS_VUDS.txt",
    ROOT / "portfolios_rows_to_append.csv",
    ROOT / "data" / "in" / "maps",
]
for p in must_not_exist:
    if p.exists():
        errors.append(f"ISTNIEJE STARY PLIK/KATALOG: {p.relative_to(ROOT)}")

for p in ROOT.rglob("*"):
    if not p.is_file():
        continue
    rel = p.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        continue
    if rel.as_posix() == "app/bin/stage1_clean_audit.py":
        continue
    if p.suffix.lower() in SKIP_SUFFIX:
        continue
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    norm = txt.replace("/", "\\")
    for b in BANNED:
        if b in txt or b in norm:
            errors.append(f"STARA REFERENCJA: {rel} -> {b}")

if errors:
    for e in errors:
        print("ERROR", e)
    print("WYNIK: BŁĄD — są stare referencje.")
    sys.exit(1)

print("OK: brak starych launcherów, dodatków i globalnych map.")
print("WYNIK: OK")

#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-
"""
bootstrap.py 2.0

Bootstrap projektu Analiza Portfeli Pasywnych 1.0.
Nie zastępuje analysis.py. Jego rola:
  - sprawdzić strukturę projektu i moduły Pythona,
  - wygenerować brakujące CPI/FX,
  - jasno zgłosić brak biblioteki syntetyków i map,
  - opcjonalnie uruchomić analysis.py dla podanych par: ustawienia.csv + portfele.csv.
"""

import argparse
import csv
import importlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from common import detect_root, norm_path, rel, task_rel

VERSION = "bootstrap.py 2.4.2 VER_2_2_1_CLEAN_BOOTSTRAP"

PY_MODULES = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("matplotlib", "matplotlib"),
    ("yfinance", "yfinance"),
    ("requests", "requests"),
    ("dateutil", "python-dateutil"),
]

CRITICAL_SCRIPTS = [
    "app/bin/analysis.py",
    "app/bin/passive_ledger.py",
    "app/bin/ledger_summary.py",
    "app/bin/build_db_freq.py",
    "app/bin/build_db_synthetic.py",
    "app/bin/build_cpi_pln_gus.py",
    "app/bin/build_cpi_usd_fred.py",
    "app/bin/build_fx_nbp.py",
    "app/bin/crash_test_windows.py",
    "app/bin/plot_ledger_template.py",
    "app/bin/make_summary_table.py",
]

COMMON_INPUTS = [
    ("data/in/cpi/CPI_USD.csv", "CPI_US", "generowane przez build_cpi_usd_fred.py"),
    ("data/in/cpi/CPI_PLN_GUS.csv", "CPI_PL", "generowane przez build_cpi_pln_gus.py"),
    ("data/in/fx/DB_FX.csv", "FX", "wymagany zakres roboczy dla PLN-real: od 1995-01-01; generator NBP może nie odtworzyć pełnego zakresu"),
    ("data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv", "SYNTH_LIBRARY", "najważniejszy gotowy półprodukt syntetyków; jeśli brak, trzeba go odtworzyć z zatwierdzonych surowców/metodologii"),
]

DEFAULT_ANALYSES = [
    "benchmark_1970_synth_usd_gross",
    "synth_vs_etf_2005_full10",
]


def read_startup_order(root: Path) -> list[str]:
    path = rel(root, "analysis_definitions/startup_order.csv")
    if not path.exists():
        return list(DEFAULT_ANALYSES)
    out = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            inc = str(row.get("INCLUDE", "1")).strip().lower()
            name = str(row.get("ANALYSIS_FOLDER", "")).strip()
            if name and inc not in {"0", "false", "no", "nie", "off"}:
                out.append(name)
    return out or list(DEFAULT_ANALYSES)

def ensure_dirs(root: Path) -> None:
    for d in [
        "app/bin",
        "runtime/python",
        "data/in/cpi",
        "data/in/fx",
        "data/in/libraries",
        "analysis_definitions/common/maps/synth",
        "analysis_definitions/common/maps/hist",
        "analysis_definitions/common/task_templates",
        "analysis_definitions",
        "analysis_results",
        "reports/charts",
        "reports/tables",
    ]:
        rel(root, d).mkdir(parents=True, exist_ok=True)


def status(ok: bool) -> str:
    return "OK" if ok else "BRAK"


def describe_required_file(root: Path, path: str, label: str, note: str, can_generate: bool = False, generator: str = "") -> str:
    full = rel(root, path)
    lines = [
        f"BRAK: {label}",
        f"  wymagany plik: {path}",
        f"  pełna ścieżka:  {full}",
    ]
    if can_generate:
        lines.append(f"  akcja: może zostać wygenerowany przez --generate-missing")
        if generator:
            lines.append(f"  generator: {generator}")
    else:
        lines.append("  akcja: skopiuj / odtwórz ten plik ręcznie przed uruchomieniem analiz")
    if note:
        lines.append(f"  uwaga: {note}")
    return "\n".join(lines)


def print_missing_common_inputs(root: Path) -> None:
    specs = {
        "data/in/cpi/CPI_USD.csv": ("CPI_US", "build_cpi_usd_fred.py", True),
        "data/in/cpi/CPI_PLN_GUS.csv": ("CPI_PL", "build_cpi_pln_gus.py", True),
        "data/in/fx/DB_FX.csv": ("FX_USDPLN", "build_fx_nbp.py", True),
        "data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv": ("SYNTH_LIBRARY", "", False),
    }
    missing = []
    for path, label, note in COMMON_INPUTS:
        if not rel(root, path).exists():
            label2, generator, can_generate = specs.get(path, (label, "", False))
            missing.append(describe_required_file(root, path, label2, note, can_generate, generator))
    if missing:
        print("\n=== BRAKUJĄCE PLIKI — INSTRUKCJE ===")
        print("\n\n".join(missing))


def check_modules():
    rows = []
    for mod, pip_name in PY_MODULES:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "")
            rows.append(("OK", mod, pip_name, ver))
        except Exception as e:
            rows.append(("BRAK", mod, pip_name, str(e)))
    return rows


def run(cmd, cwd: Path, dry_run: bool = False) -> int:
    printable = " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd)
    print("RUN:", printable)
    if dry_run:
        return 0
    r = subprocess.run(cmd, cwd=str(cwd), text=True)
    return int(r.returncode)


def generate_cpi_us(root: Path, dry_run: bool = False, force: bool = False):
    target = rel(root, "data/in/cpi/CPI_USD.csv")
    if target.exists() and not force:
        return True, "istnieje"
    script = rel(root, "app/bin/build_cpi_usd_fred.py")
    if not script.exists():
        return False, "brak generatora app/bin/build_cpi_usd_fred.py"
    raw = rel(root, "data/in/raw/CPI_USD_FRED_raw.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw.parent.mkdir(parents=True, exist_ok=True)
    rc = run([sys.executable, str(script), "--start", "1960-01-01", "--out", str(target), "--raw-out", str(raw)], root, dry_run)
    return (rc == 0 and (target.exists() or dry_run)), f"returncode={rc}"


def generate_cpi_pl(root: Path, dry_run: bool = False, force: bool = False):
    target = rel(root, "data/in/cpi/CPI_PLN_GUS.csv")
    if target.exists() and not force:
        return True, "istnieje"
    script = rel(root, "app/bin/build_cpi_pln_gus.py")
    if not script.exists():
        return False, "brak generatora app/bin/build_cpi_pln_gus.py"
    raw = rel(root, "data/in/raw/CPI_PLN_GUS_raw.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw.parent.mkdir(parents=True, exist_ok=True)
    flash = rel(root, "data/in/cpi/CPI_PLN_FLASH.csv")
    cmd = [sys.executable, str(script), "--start", "1995-01-01", "--out", str(target), "--raw-out", str(raw)]
    if flash.exists():
        cmd += ["--flash-file", str(flash)]
    rc = run(cmd, root, dry_run)
    return (rc == 0 and (target.exists() or dry_run)), f"returncode={rc}"


def fx_first_date(path: Path):
    """Return first data date from project DB_FX.csv, or None if unreadable."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                s = (row[0] or "").strip()
                if len(s) == 10 and s[4] == "-" and s[7] == "-":
                    return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None
    return None


def validate_fx_coverage(root: Path, required_start: str):
    target = rel(root, "data/in/fx/DB_FX.csv")
    first = fx_first_date(target)
    if first is None:
        return False, "brak danych datowanych w DB_FX.csv"
    req = datetime.strptime(required_start, "%Y-%m-%d").date()
    if first > req:
        return False, (
            f"DB_FX.csv zaczyna się {first.isoformat()}, a wymagany start dla tej konkretnej analysis_results to {req.isoformat()}. "
            "Dostarcz pełniejszy plik FX albo ustaw późniejszy start analysis_results PLN-real."
        )
    return True, f"coverage OK: first={first.isoformat()} <= required={req.isoformat()}"


def fx_bootstrap_note(root: Path, requested_start: str):
    """Informacja po wygenerowaniu FX. Nie jest jeszcze decyzją o blokadzie analiz.
    Decyzja o blokadzie zapada per ustawienia.csv, bo analiza 2005 może poprawnie użyć FX od 2002.
    """
    target = rel(root, "data/in/fx/DB_FX.csv")
    first = fx_first_date(target)
    if first is None:
        return False, "brak danych datowanych w DB_FX.csv"
    req = datetime.strptime(requested_start, "%Y-%m-%d").date()
    if first > req:
        return True, (
            f"UWAGA: NBP zwrócił FX od {first.isoformat()}, mimo żądania od {req.isoformat()}. "
            "To jest OK dla analiz zaczynających się nie wcześniej niż pierwszy FX. "
            "Analizy PLN-real od 1995 wymagają osobnego pełniejszego źródła FX."
        )
    return True, f"coverage roboczy OK: first={first.isoformat()} <= requested={req.isoformat()}"


def generate_fx(root: Path, fx_start: str, dry_run: bool = False, force: bool = False):
    target = rel(root, "data/in/fx/DB_FX.csv")
    if target.exists() and not force:
        ok, msg = fx_bootstrap_note(root, fx_start)
        return ok, "istnieje; " + msg
    script = rel(root, "app/bin/build_fx_nbp.py")
    if not script.exists():
        return False, "brak generatora app/bin/build_fx_nbp.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"INFO: próbuję wygenerować FX od {fx_start}. To jest robocza granica PLN-real po denominacji nowego PLN.")
    rc = run([sys.executable, str(script), "--ccy", "USD", "--start", fx_start, "--out", str(target)], root, dry_run)
    if rc != 0:
        return False, f"returncode={rc}"
    if dry_run:
        return True, f"dry-run; żądany start={fx_start}"
    ok, msg = fx_bootstrap_note(root, fx_start)
    return ok, f"returncode={rc}; {msg}"


def read_portfolios(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def read_settings_file(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            k = (row.get("KEY") or row.get("key") or "").strip()
            v = (row.get("VALUE") or row.get("value") or "").strip()
            if k:
                out[k] = v
    return out


def analysis_requires_fx(settings: dict) -> bool:
    # Obecny pipeline używa FX, jeśli w ustawieniach wskazano plik fx albo metryki PLN.
    if str(settings.get("fx", "")).strip():
        return True
    if "PLN" in str(settings.get("value_col_pln", "")).upper():
        return True
    return False


def validate_analysis_data_ranges(root: Path, analysis_results: list[tuple[str, str]]):
    rows = []
    fx_path = rel(root, "data/in/fx/DB_FX.csv")
    first_fx = fx_first_date(fx_path)
    for u, _p in analysis_results:
        settings_path = rel(root, u)
        settings = read_settings_file(settings_path)
        start = settings.get("start", "").strip()
        if analysis_requires_fx(settings):
            if first_fx is None:
                rows.append(("analysis_data", "BRAK", str(settings_path), "Analiza wymaga FX, ale DB_FX.csv nie ma datowanych danych."))
                continue
            if start:
                try:
                    req = datetime.strptime(start, "%Y-%m-%d").date()
                    if first_fx > req:
                        rows.append((
                            "analysis_data", "BRAK", str(settings_path),
                            f"Analiza wymaga FX od start={req.isoformat()}, ale DB_FX.csv zaczyna się {first_fx.isoformat()}."
                        ))
                except Exception:
                    rows.append(("analysis_data", "BRAK", str(settings_path), f"Nie umiem odczytać daty start='{start}' z ustawień."))
    return rows


def check_analysis_files(root: Path, ustawienia: Path, portfele: Path):
    rows = []
    rows.append(("analysis", status(ustawienia.exists()), str(ustawienia), "ustawienia"))
    rows.append(("analysis", status(portfele.exists()), str(portfele), "portfele"))

    if not ustawienia.exists():
        print(f"BRAK ustawienia: {ustawienia}")
    else:
        print(f"OK   ustawienia: {ustawienia}")

    if not portfele.exists():
        print(f"BRAK portfele:   {portfele}")
        return rows
    else:
        print(f"OK   portfele:   {portfele}")

    for row in read_portfolios(portfele):
        if str(row.get("INCLUDE", "1")).strip().lower() in ["0", "false", "no", "nie", "off"]:
            continue
        pid = row.get("ID", "")
        for col in ["MAP_SYNTH", "MAP_HIST"]:
            v = row.get(col, "")
            if not v:
                continue
            p = task_rel(root, portfele.parent, v)
            st = status(p.exists())
            print(f"{st:4} {col:9} {pid:12} {v}")
            if not p.exists():
                print(f"     oczekiwana ścieżka: {p}")
            rows.append(("map", st, v, pid))
    return rows

def write_report(root: Path, rows):
    out = rel(root, "docs/generated/init_check_report.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "section", "status", "item", "details"])
        ts = datetime.now().isoformat(timespec="seconds")
        for section, stat, item, details in rows:
            w.writerow([ts, section, stat, item, details])
    return out


def write_sources(root: Path):
    out = rel(root, "SOURCES.md")
    out.write_text(
        "# Źródła danych Analiza Portfeli Pasywnych 1.0\n\n"
        "Ten plik jest generowany przez `app/bin/bootstrap.py`.\n\n"
        "## Automatycznie generowane\n\n"
        "- `data/in/cpi/CPI_USD.csv` — FRED CPIAUCNS, przez `build_cpi_usd_fred.py`.\n"
        "- `data/in/cpi/CPI_PLN_GUS.csv` — GUS CPI, przez `build_cpi_pln_gus.py`.\n"
        "- `data/in/fx/DB_FX.csv` — USD/PLN. Dla PLN-real roboczą granicą metodologiczną jest 1995-01-01, czyli denominacja nowego PLN. API NBP może zwrócić dane dopiero od 2002-01-02; wtedy analiza 2005 jest dopuszczalna, ale analiza PLN-real od 1995 wymaga osobnego pełniejszego źródła FX.\n\n"
        "## Wymagany półprodukt projektu\n\n"
        "- `data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv` — biblioteka syntetyków miesięcznych USD.\n"
        "  Jeżeli jej brakuje, bootstrap zgłasza błąd. Nie rekonstruować automatycznie bez zatwierdzonego pipeline'u, bo każdy składnik był rzeźbiony inną metodą.\n\n",
        encoding="utf-8",
    )
    return out


def write_user_files_guide(root: Path) -> Path:
    out = rel(root, "docs/generated/README_USER_FILES.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    txt = """# Pliki użytkownika — ver. 2.0

Ten plik jest generowany przez `app/bin/bootstrap.py`.

## Komendy

- `1-start_setup.cmd` — pełny setup i taski z `analysis_definitions/startup_order.csv`.
- `check_project.cmd` — kontrola paczki.
- `refresh_data.cmd` — świadome odświeżenie CPI/FX.
- `refresh_quotes.cmd <task>` — świadome odświeżenie lokalnej biblioteki notowań HIST.
- `run_task.cmd <task>` — uruchomienie wskazanej analizy.
- `create_task.cmd <nazwa>` — tworzy nowy task z czystego szablonu.
- `run_task.cmd <nazwa>` — uruchamia wskazany task.

## Edycja własnego taska

Edytuj lokalne pliki taska:

- `analysis_definitions/<task>/settings.csv`
- `analysis_definitions/<task>/portfolios.csv`
- `analysis_definitions/<task>/maps/hist/*.csv`
- `analysis_definitions/<task>/maps/synth/*.csv`

## Wyniki

`analysis_results/<task>__YYYYMMDD_HHMMSS`

## Wzorce

`analysis_definitions/common/maps/` oraz `analysis_definitions/common/task_templates/`.
"""
    out.write_text(txt, encoding="utf-8")
    return out

def print_user_editing_instructions(root: Path) -> None:
    print("\n================================================================")
    print("PLIKI, KTÓRE UŻYTKOWNIK MOŻE MODYFIKOWAĆ POD SIEBIE")
    print("================================================================")
    print(f"Instrukcja została zapisana do: {rel(root, 'docs/generated/README_USER_FILES.md')}")
    print("")
    print("NAJPROSTSZA WŁASNA ANALIZA:")
    print(f"   {rel(root, 'analysis_definitions/user_template/settings.csv')}")
    print(f"   {rel(root, 'analysis_definitions/user_template/portfolios.csv')}")
    print("")
    print("Domyślnie user_template liczy: My_Portfel_SP500 oraz Benchmark_US_60_40.")
    print("Okres: 2005-01-31 do 2026-03-31. Podatek: gross, czyli bez Belki.")
    print("")
    print("Uruchomienie własnej analizy:")
    print("   run_task.cmd user_template")
    print("")
    print("Pliki startowe w katalogu głównym:")
    print("   1-start_setup.cmd      pełny setup i domyślne analizy")
    print("   check_project.cmd      kontrola paczki")
    print("   refresh_data.cmd       odświeżenie CPI/FX")
    print("   refresh_quotes.cmd     odświeżenie notowań HIST")
    print("   run_task.cmd           uruchomienie taska")
    print("")
    print("Mapy portfeli:")
    print(f"   lokalne taska: analysis_definitions/<task>/maps/synth oraz maps/hist")
    print(f"   wzorce:        {rel(root, 'analysis_definitions/common/maps')}")
    print("")
    print("Wyniki:")
    print(f"   {rel(root, 'analysis_results')}")
    print("================================================================\n")


def main():
    ap = argparse.ArgumentParser(description=f"{VERSION}: bootstrap danych i opcjonalne uruchomienie analiz.")
    ap.add_argument("--root", default="AUTO")
    ap.add_argument("--generate-missing", action="store_true", help="Wygeneruj brakujące CPI/FX. Nie rekonstruuje biblioteki syntetyków.")
    ap.add_argument("--refresh-common", action="store_true", help="Odśwież CPI_USD, CPI_PLN_GUS i DB_FX nawet jeśli pliki już istnieją.")
    ap.add_argument("--fx-start", default="1995-01-01", help="Wymagany start FX USD/PLN. Domyślnie 1995-01-01: od denominacji nowego PLN; wcześniej nie robimy PLN-real.")
    ap.add_argument("--analiza", nargs=2, action="append", metavar=("USTAWIENIA", "PORTFELE"), help="Uruchom analysis.py dla pary plików CSV. Można podać wiele razy.")
    ap.add_argument("--run-default", action="store_true", help="Run startup tasks listed in analysis_definitions/startup_order.csv.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = detect_root(args.root)
    ensure_dirs(root)
    rows = []

    print("\n================================================================")
    print(f"{VERSION}")
    print("================================================================")
    print(f"ROOT: {root}")

    print("\n=== CHECK: Python modules ===")
    for stat, mod, pip_name, details in check_modules():
        print(f"{stat:4} {mod:16} pip={pip_name:20} {details}")
        rows.append(("module", stat, mod, details))

    print("\n=== CHECK: scripts ===")
    for s in CRITICAL_SCRIPTS:
        ok = rel(root, s).exists()
        print(f"{status(ok):4} {s}")
        rows.append(("script", status(ok), s, str(rel(root, s))))

    print("\n=== CHECK: common inputs ===")
    for path, label, note in COMMON_INPUTS:
        ok = rel(root, path).exists()
        print(f"{status(ok):4} {path}  {label}")
        rows.append(("input", status(ok), path, note))

    if args.generate_missing or args.refresh_common:
        force_refresh = bool(args.refresh_common)
        title = "REFRESH: CPI/FX common inputs" if force_refresh else "GENERATE: CPI/FX if missing"
        print(f"\n=== {title} ===")
        for label, func in [
            ("CPI_US", lambda: generate_cpi_us(root, args.dry_run, force=force_refresh)),
            ("CPI_PL", lambda: generate_cpi_pl(root, args.dry_run, force=force_refresh)),
            ("FX", lambda: generate_fx(root, args.fx_start, args.dry_run, force=force_refresh)),
        ]:
            ok, msg = func()
            print(f"{status(ok):4} {label:10} {msg}")
            rows.append(("generate", status(ok), label, msg))

    analysis_results = []
    if args.run_default:
        for task_name in read_startup_order(root):
            u = f"analysis_definitions/{task_name}/settings.csv"
            p = f"analysis_definitions/{task_name}/portfolios.csv"
            if rel(root, u).exists() and rel(root, p).exists():
                analysis_results.append((u, p))
            else:
                print(f"BRAK taska startowego: {task_name}")
    if args.analiza:
        analysis_results.extend(args.analiza)

    if analysis_results:
        print("\n=== CHECK: selected startup tasks ===")
        for u, p in analysis_results:
            rows.extend(check_analysis_files(root, rel(root, u), rel(root, p)))
        range_rows = validate_analysis_data_ranges(root, analysis_results)
        for section, stat, item, details in range_rows:
            print(f"{stat:4} {item}  {details}")
            rows.append((section, stat, item, details))

    sources = write_sources(root)
    user_guide = write_user_files_guide(root)
    report = write_report(root, rows)
    print(f"\nOK SOURCES: {sources}")
    print(f"OK USER GUIDE: {user_guide}")
    print(f"OK REPORT:  {report}")

    fatal = [r for r in rows if r[1] == "BRAK" and r[0] in {"module", "script"}]
    bad_generate = [r for r in rows if r[1] == "BRAK" and r[0] == "generate"]
    bad_analysis_files = [r for r in rows if r[1] == "BRAK" and r[0] in {"analysis", "map"}]
    bad_analysis_data = [r for r in rows if r[1] == "BRAK" and r[0] == "analysis_data"]
    print_missing_common_inputs(root)
    synth_missing = not rel(root, "data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv").exists()
    if synth_missing:
        print("\nUWAGA: brak data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv")
        print("To jest wymagany półprodukt syntetyków. Bootstrap go nie odtwarza automatycznie.")
    if fatal:
        print("\nWYNIK: są braki krytyczne modułów/skryptów. Nie uruchamiam analiz.")
        sys.exit(2)

    if bad_generate:
        print("\nWYNIK: nie wszystkie dane wejściowe zostały poprawnie wygenerowane.")
        for _, _, item, details in bad_generate:
            print(f"  BRAK/PROBLEM: {item} - {details}")
        print("Nie uruchamiam analiz.")
        sys.exit(4)

    if bad_analysis_files:
        print("\nWYNIK: wybrane taski mają brakujące pliki ustawień/portfeli albo map.")
        for section, _, item, details in bad_analysis_files:
            if section == "map":
                print(f"  BRAK MAPY: {item}  portfel={details}")
                print(f"    oczekiwana ścieżka: {rel(root, item)}")
            else:
                print(f"  BRAK: {item}  ({details})")
        print("Nie uruchamiam analiz. Uzupełnij brakujące mapy w data\\in\\maps\\synth / hist / ib.")
        sys.exit(6)

    if bad_analysis_data:
        print("\nWYNIK: wybrane analysis_results wymagają szerszego zakresu danych niż dostępny.")
        for _, _, item, details in bad_analysis_data:
            print(f"  BRAK/PROBLEM: {item} - {details}")
        print("Nie uruchamiam tych analiz, żeby nie liczyć na niepełnych danych.")
        sys.exit(5)

    if analysis_results:
        if synth_missing:
            print("\nWYNIK: nie uruchamiam analiz, bo brakuje biblioteki syntetyków.")
            sys.exit(3)

        analiza_script = rel(root, "app/bin/analysis.py")

        if args.dry_run:
            print("\n=== DRY-RUN: ANALIZY NIE SĄ URUCHAMIANE ===")
            print("To jest tylko kontrola konfiguracji. Poniżej pokazuję, co zostałoby uruchomione w :")
            for u, p in analysis_results:
                task_dir = str(Path(u).parent).replace("\\", "/")
                cmd = [sys.executable, str(analiza_script), "--root", str(root), "--definition", task_dir]
                printable = " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd)
                print("PLAN:", printable)
        else:
            print("\n=== RUN ANALYSES ===")
            for u, p in analysis_results:
                task_dir = str(Path(u).parent).replace("\\", "/")
                rc = run([sys.executable, str(analiza_script), "--root", str(root), "--definition", task_dir], root, False)
                if rc != 0:
                    print(f"ERROR: analiza zakończona kodem {rc}: {u} / {p}")
                    sys.exit(rc)

    print_user_editing_instructions(root)
    print("\nWYNIK: bootstrap zakończony.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# pasywnyportfel — buildery komend CLI i narzędzia raportowania
# Autor koncepcji i projektu: Wojciech Król / email: lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
cmd_builders.py — budowanie list argumentów dla podprocesów,
narzędzia pomocnicze nazw plików i raportów.

Eksportuje:
  run, copy_if_exists, step,
  safe_run_folder_name, safe_token,
  mode_label, file_mode_token, display_name,
  detect_modes, make_run_names, snapshot_configs,
  ledger_cmd, plot_cmd, summary_cmd,
  fmt_weight_for_components, map_components_short, write_components_file,
  summary_actual_range, table_cmd, crash_cmd,
  update_reports_index, write_run_readme
"""

import csv
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from common import rel
from task_config import setting_value, tax_label


# ---------------------------------------------------------------------------
# Uruchamianie podprocesów i operacje na plikach
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path, dry_run=False):
    printable = " ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd)
    print("\nRUN:", printable)
    if dry_run:
        return 0
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), text=True, errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1,
    )
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
    finally:
        proc.stdout.close()
    r = proc.wait()
    if r != 0:
        raise RuntimeError(f"Command failed, returncode={r}: {printable}")
    return r


def copy_if_exists(root: Path, src: str, dst: str) -> bool:
    src_path = rel(root, src)
    dst_path = rel(root, dst)
    if not src_path.exists():
        print(f"WARN: nie znaleziono pliku do skopiowania: {src_path}")
        return False
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dst_path)
    print(f"COPY: {src_path} -> {dst_path}")
    return True


def step(title):
    print("\n" + "-" * 72)
    print(title)
    print("-" * 72)


# ---------------------------------------------------------------------------
# Tokeny nazw i etykiet
# ---------------------------------------------------------------------------

def safe_run_folder_name(run_stamp: str, analysis_id: str) -> str:
    aid = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(analysis_id))
    return f"{run_stamp}_{aid[:48]}"


def safe_token(s: str) -> str:
    s = str(s).strip().lower()
    repl = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ż": "z", "ź": "z",
        " ": "_", "/": "_", "\\": "_", ":": "-", ";": "_", ",": "_", "|": "_",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    out = []
    for ch in s:
        if ch.isalnum() or ch in ["_", "-"]:
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_-")


# ---------------------------------------------------------------------------
# PATCH 2026-06-19/20: REBAL_PERIOD — nowa, OPCJONALNA kolumna portfolios.csv,
# niezależna od REBALANCE/MAX_DRIFT. Pozwala na rebalans okresowy (np. co 6M)
# RAZEM z warunkowym drift-rebalansem w tym samym portfelu — silnik to wspiera
# (ledger_engine.py: is_sched_rebal i is_drift_rebal mogą być oba aktywne, gdy
# --conditional-rebalance NIE jest ustawione), ale REBALANCE jako pojedynczy
# string nigdy takiej kombinacji nie generował.
#
# Wsteczna zgodność: brak kolumny REBAL_PERIOD w pliku (albo pusta wartość)
# => rebal_period="" => zachowanie 1:1 jak przed patchem dla BH/DRIFT/ANNUAL.
_REBAL_BH = {"BH", "B&H", "BUYHOLD", "BUY_AND_HOLD", "NO", "NONE", "NO_REBALANCE"}
_REBAL_DRIFT = {"DRIFT", "D20", "DRIFT20", "CONDITIONAL"}
_REBAL_ANNUAL = {"12M", "ANNUAL", "YEARLY"}
_PERIOD_TOKEN_RE = re.compile(r"^\d+M$")


def _resolve_rebalance(rebalance: str, max_drift, rebal_period: str = ""):
    """
    Rozwiązuje (REBALANCE, MAX_DRIFT, REBAL_PERIOD) na kanoniczny tryb.
    Zwraca (kind, period_token, drift_val):
      kind: "BH" | "DRIFT" | "PERIOD" | "COMBO" | "UNKNOWN"
      period_token: np. "12M"/"6M", albo None gdy brak komponentu okresowego
      drift_val: float >= 0 (0.0 gdy brak komponentu driftu)

    RZUCA ValueError TYLKO gdy REBAL_PERIOD jest podane ale ma zły format —
    to nowe pole, więc nie ma ryzyka złamania istniejących danych. Nie rzuca
    dla nierozpoznanego REBALANCE — to robi dopiero ledger_cmd.
    """
    rb = str(rebalance or "").strip().upper()
    period_raw = str(rebal_period or "").strip().upper()
    try:
        drift_val = float(str(max_drift).strip()) if str(max_drift).strip() else 0.0
    except ValueError:
        drift_val = 0.0

    period_token = None
    if period_raw:
        if not _PERIOD_TOKEN_RE.match(period_raw):
            raise ValueError(f"Zły format REBAL_PERIOD={rebal_period!r}; wymagane np. 12M, 6M, 3M, 1M")
        period_token = period_raw
    elif rb in _REBAL_ANNUAL:
        period_token = "12M"

    drift_on = False if rb in _REBAL_BH else (rb in _REBAL_DRIFT)

    if drift_on and period_token:
        return "COMBO", period_token, drift_val
    if drift_on:
        return "DRIFT", None, drift_val
    if period_token:
        return "PERIOD", period_token, 0.0
    if rb in _REBAL_BH:
        return "BH", None, 0.0
    return "UNKNOWN", None, drift_val


def _resolve_rebalance_safe(rebalance: str, max_drift, rebal_period: str = ""):
    """Wariant non-raising do funkcji WYŚWIETLAJĄCYCH — błąd formatu REBAL_PERIOD
    nie ma prawa wywalić listingu."""
    try:
        return _resolve_rebalance(rebalance, max_drift, rebal_period)
    except ValueError:
        return "UNKNOWN", None, 0.0


def mode_label(rebalance: str, max_drift: str, rebal_period: str = "") -> str:
    rb = str(rebalance).strip().upper()
    md = str(max_drift).strip()
    kind, period_token, _ = _resolve_rebalance_safe(rebalance, max_drift, rebal_period)
    if kind == "BH":
        return "Buy & Hold"
    if kind == "DRIFT":
        return f"Rebalans po DRIFT{md or '20'}"
    if kind == "PERIOD":
        if period_token == "12M":
            return "Rebalans roczny"
        return f"Rebalans co {period_token}"
    if kind == "COMBO":
        base = "roczny" if period_token == "12M" else f"co {period_token}"
        return f"Rebalans {base} + DRIFT{md or '20'}"
    return rb


def file_mode_token(rebalance: str, max_drift: str, rebal_period: str = "") -> str:
    rb = str(rebalance).strip().upper()
    md = str(max_drift).strip()
    kind, period_token, _ = _resolve_rebalance_safe(rebalance, max_drift, rebal_period)
    if kind == "BH":
        return "BH"
    if kind == "DRIFT":
        return f"DRIFT{md or '20'}"
    if kind == "PERIOD":
        if period_token == "12M":
            return "Rebalans roczny"
        return f"PERIOD{period_token}"
    if kind == "COMBO":
        per = "ANNUAL" if period_token == "12M" else f"PERIOD{period_token}"
        return f"DRIFT{md or '20'}_{per}"
    return safe_token(rb or "mode").upper()


def display_name(label: str, dataset: str, rebalance: str, max_drift: str, rebal_period: str = "") -> str:
    return f"{label} {dataset.upper()} / {mode_label(rebalance, max_drift, rebal_period)}"


def detect_modes(portfolios: list[dict]) -> str:
    modes = []
    for p in portfolios:
        rb = str(p.get("REBALANCE", "")).strip().upper()
        md = str(p.get("MAX_DRIFT", "")).strip()
        period = str(p.get("REBAL_PERIOD", "")).strip()
        kind, period_token, _ = _resolve_rebalance_safe(rb, md, period)
        if kind == "BH":
            modes.append("BH")
        elif kind == "DRIFT":
            modes.append(f"DRIFT{md or 'X'}")
        elif kind == "PERIOD":
            modes.append(period_token or "12M")
        elif kind == "COMBO":
            modes.append(f"DRIFT{md or 'X'}+{period_token}")
        else:
            modes.append(rb or "MODE")
    uniq = []
    for m in modes:
        if m and m not in uniq:
            uniq.append(m)
    if not uniq:
        return "mode"
    if len(uniq) == 1:
        return uniq[0]
    return "mixed_" + "_".join(uniq)


def make_run_names(
    settings: dict,
    portfolios: list[dict],
    forced: str | None = None,
    task_name: str | None = None,
) -> tuple[str, str, str]:
    """Tworzy nazwę folderu wynikowego analizy."""
    analysis_id = settings.get("analysis_id", "stage2").strip() or "stage2"
    ts = forced.strip() if forced else datetime.now().strftime("%Y%m%d_%H%M%S")
    base = safe_token(task_name or analysis_id or "stage2")[:64]
    run_folder = f"{base}__{ts}"
    return analysis_id, ts, run_folder


# ---------------------------------------------------------------------------
# Migawka konfiguracji i komendy podprocesów
# ---------------------------------------------------------------------------

def snapshot_configs(
    root: Path,
    settings_path: Path,
    portfolios_path: Path,
    analysis_root: str,
    definition_dir: Path | None = None,
    version: str = "",
):
    cfg_dir = rel(root, f"{analysis_root}/config")
    cfg_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings_path, cfg_dir / "settings.csv")
    shutil.copy2(portfolios_path, cfg_dir / "portfolios.csv")
    if definition_dir is not None and (definition_dir / "maps").exists():
        dst_maps = cfg_dir / "maps"
        if dst_maps.exists():
            shutil.rmtree(dst_maps)
        shutil.copytree(definition_dir / "maps", dst_maps)
    meta = cfg_dir / "run_meta.txt"
    meta.write_text(
        f"{version}\n"
        f"created={datetime.now().isoformat(timespec='seconds')}\n"
        f"definition_dir={definition_dir or ''}\n"
        f"settings_source={settings_path}\n"
        f"portfolios_source={portfolios_path}\n",
        encoding="utf-8",
    )


def ledger_cmd(
    root: Path,
    settings: dict,
    portfolio_map: str,
    db_path: str,
    out_path: str,
    rebalance: str,
    max_drift: str,
    rebal_period: str = "",
):
    cmd = [
        sys.executable,
        str(rel(root, "app/bin/passive_ledger.py")),
        "--portfolio", str(rel(root, portfolio_map)),
        "--prices", str(rel(root, db_path)),
        "--start", settings["start"],
        "--end", settings["end"],
        "--saldo", settings["saldo"],
        "--settle-md", "12-31",
        "--freq", settings.get("freq", "monthly"),
        "--out", str(rel(root, out_path)),
    ]

    fx = setting_value(settings, "fx")
    cpi_us = setting_value(settings, "cpi_us")
    cpi_pl = setting_value(settings, "cpi_pl")
    if fx:
        cmd += ["--fx", str(rel(root, fx))]
    if cpi_us:
        cmd += ["--cpi-us", str(rel(root, cpi_us))]
    if cpi_pl:
        cmd += ["--cpi-pl", str(rel(root, cpi_pl))]

    # PATCH 2026-06-19/20: REBAL_PERIOD dodaje 4. tryb COMBO (rebalans
    # okresowy + warunkowy drift naraz) — potwierdzone w ledger_engine.py,
    # że silnik to wspiera gdy NIE ustawiamy --conditional-rebalance i
    # podajemy realny --period razem z --max-drift>0. Gałęzie BH/DRIFT/
    # PERIOD(=ANNUAL) produkują DOKŁADNIE te same argv co przed patchem.
    kind, period_token, drift_val = _resolve_rebalance(rebalance, max_drift, rebal_period)
    if kind == "BH":
        cmd += ["--period", "9999M", "--max-drift", "0", "--no-rebalance"]
    elif kind == "DRIFT":
        cmd += ["--period", "9999M", "--max-drift", str(max_drift), "--conditional-rebalance"]
    elif kind == "PERIOD":
        cmd += ["--period", period_token, "--max-drift", "0"]
    elif kind == "COMBO":
        cmd += ["--period", period_token, "--max-drift", str(max_drift)]
    else:
        raise ValueError(f"Nieznany REBALANCE={rebalance}")

    tax_mode = settings.get("tax_mode", "gross").strip().lower()
    if tax_mode not in ["gross", "", "none", "off", "0"]:
        tax_base = str(settings.get("tax_base", "")).strip().upper()
        tax_rate = settings.get("tax_rate", "0.19")
        if not tax_base:
            raise ValueError("tax_mode=net wymaga jawnego tax_base=PLN albo tax_base=USD.")
        cmd += ["--tax-mode", "net", "--tax-base", tax_base, "--tax-rate", tax_rate]
        if tax_base == "USD":
            print("  TAX: net/USD — model poglądowy: podatek liczony w USD, nie realna polska Belka.")
        elif tax_base == "PLN":
            print("  TAX: net/PLN — polski model Belki, wymaga FX USD/PLN.")

    return cmd


def plot_cmd(root: Path, ledger: str, out: str, title_prefix: str, ccy: str, settings: dict):
    if ccy.upper() == "USD":
        main = "TOTAL_USD_POST_REAL"
        main2 = "TOTAL_USD_POST"
        cpi = "CPI_US"
        main_label = "USD real"
        main2_label = "USD nominal"
        title = f"{title_prefix} - USD real vs nominal + CPI_US"
    elif ccy.upper() == "PLN":
        main = "TOTAL_PLN_POST_REAL"
        main2 = "TOTAL_PLN_POST"
        cpi = "CPI_PL"
        main_label = "PLN real"
        main2_label = "PLN nominal"
        title = f"{title_prefix} - PLN real vs nominal + CPI_PL"
    else:
        raise ValueError(ccy)

    return [
        sys.executable,
        str(rel(root, "app/bin/plot_ledger_template.py")),
        str(rel(root, ledger)),
        "--main", main,
        "--main2", main2,
        "--cpi", cpi,
        "--start-date", settings["start"],
        "--log-y",
        "--main-label", main_label,
        "--main2-label", main2_label,
        "--title", title,
        "--out", str(rel(root, out)),
    ]


def summary_cmd(root: Path, ledgers: list[str], names: list[str], out: str, value_col: str):
    return [
        sys.executable,
        str(rel(root, "app/bin/ledger_summary.py")),
        *[str(rel(root, x)) for x in ledgers],
        "--out", str(rel(root, out)),
        "--sort", "AUTO",
        "--value-col", value_col,
        "--names", ",".join(names),
    ]


# ---------------------------------------------------------------------------
# Składniki portfela
# ---------------------------------------------------------------------------

def fmt_weight_for_components(x: str) -> str:
    try:
        f = float(str(x).replace("%", "").replace(",", ".").strip())
        if abs(f - round(f)) < 1e-9:
            return f"{int(round(f))}%"
        return f"{f:.2f}%".replace(".00%", "%")
    except Exception:
        return str(x).strip()


def map_components_short(map_path: Path) -> str:
    """Zwraca skrót składu portfela, np. SPY 60%, IEF 40%."""
    if not map_path or not map_path.exists():
        return "BRAK MAPY"
    rows = []
    with map_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sym = (
                row.get("Ticker") or row.get("YFTicker")
                or row.get("Symbol") or row.get("LIB_COL") or ""
            ).strip()
            if sym.upper().startswith("SYNTH_") and (row.get("LIB_COL") or "").strip():
                sym = (row.get("LIB_COL") or "").strip()
            weight = (
                row.get("WEIGHT") or row.get("Weight")
                or row.get("Weight_%") or ""
            ).strip()
            if sym:
                rows.append(f"{sym} {fmt_weight_for_components(weight)}")
    return ", ".join(rows) if rows else "BRAK SKŁADNIKÓW"


def write_components_file(root: Path, out_path: str, component_lines: list[str]) -> None:
    p = rel(root, out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = component_lines or ["BRAK DANYCH O SKŁADZIE"]
    p.write_text("\n".join(text) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tabele i crash-test
# ---------------------------------------------------------------------------

def summary_actual_range(
    root: Path,
    csv_file: str,
    fallback_start: str,
    fallback_end: str,
) -> str:
    path = rel(root, csv_file)
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if "START" in df.columns and "END" in df.columns:
            starts = pd.to_datetime(df["START"], errors="coerce").dropna()
            ends = pd.to_datetime(df["END"], errors="coerce").dropna()
            if len(starts) and len(ends):
                return f"{starts.min().date().isoformat()} to {ends.max().date().isoformat()}"
    except Exception as e:
        print(f"WARN: summary_actual_range fallback for {csv_file}: {e}", file=sys.stderr)
    return f"{fallback_start} to {fallback_end}"


def table_cmd(
    root: Path,
    csv_file: str,
    out: str,
    title: str,
    subtitle: str,
    value_note: str,
    start_capital: str = "",
    components_file: str = "",
):
    return [
        sys.executable,
        str(rel(root, "app/bin/make_summary_table.py")),
        str(rel(root, csv_file)),
        "--out", str(rel(root, out)),
        "--title", title,
        "--subtitle", subtitle,
        "--columns", "AUTO",
        "--sort", "AUTO",
        "--name-mode", "raw",
        "--start-capital", str(start_capital),
        "--components-file", str(rel(root, components_file)) if components_file else "",
        "--note", value_note,
    ]


def crash_cmd(
    root: Path,
    labels_paths: list[tuple[str, str]],
    out_dir: str,
    value_col: str,
    settings: dict,
):
    args = [f"{label}={rel(root, path)}" for label, path in labels_paths]
    focus = settings.get("focus", "").strip()
    focus_arg = ["--focus", focus.upper()] if focus else []
    return [
        sys.executable,
        str(rel(root, "app/bin/crash_by_portfolio.py")),
        *args,
        "--column", value_col,
        "--windows", settings.get("windows", "3,5,7,10,15,20"),
        "--out-dir", str(rel(root, out_dir)),
        *focus_arg,
    ]


# ---------------------------------------------------------------------------
# Indeks raportów i README
# ---------------------------------------------------------------------------

def update_reports_index(
    root: Path,
    analysis_id: str,
    run_folder: str,
    analysis_root: str,
    settings: dict,
):
    reports = rel(root, "reports")
    reports.mkdir(parents=True, exist_ok=True)
    latest = reports / "latest_analysis.txt"
    latest.write_text(f"{run_folder}\n{analysis_root}\n", encoding="utf-8")

    idx = reports / "analysis_index.csv"
    exists = idx.exists()
    with idx.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "analysis_id", "run_folder", "path", "start", "end", "tax_mode", "freq"])
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            analysis_id,
            run_folder,
            analysis_root,
            settings.get("start", ""),
            settings.get("end", ""),
            settings.get("tax_mode", "gross"),
            settings.get("freq", "monthly"),
        ])


def write_run_readme(
    root: Path,
    analysis_root: str,
    charts: str,
    tables: str,
    run_folder: str,
    settings: dict,
    portfolios: list[dict],
):
    lines = []
    lines.append("ANALYSIS SUMMARY")
    lines.append("=" * 72)
    lines.append(f"TASK_NAME: {run_folder.split('__')[0] if '__' in run_folder else run_folder}")
    lines.append(f"ANALYSIS_FOLDER: {run_folder}")
    lines.append(f"PERIOD: {settings.get('start')} -> {settings.get('end')}")
    if settings.get("_start_requested") or settings.get("_end_requested"):
        lines.append(f"START_REQUESTED: {settings.get('_start_requested', '') or 'AUTO'}")
        lines.append(f"END_REQUESTED: {settings.get('_end_requested', '') or 'AUTO'}")
    lines.append(f"TAX_MODE: {settings.get('tax_mode', 'gross')}")
    lines.append(f"FREQ: {settings.get('freq', 'monthly')}")
    lines.append("")
    lines.append("THIS FOLDER IS THE COMPLETE RESULT OF THIS ANALYSIS.")
    lines.append("")
    lines.append("KEY FILES IN THIS FOLDER:")
    tlbl = tax_label(settings)
    for _fname in [
        f"summary_{tlbl}_USD_real.csv",
        f"summary_{tlbl}_USD_real.png",
        f"summary_{tlbl}_PLN_real.csv",
        f"summary_{tlbl}_PLN_real.png",
        "portfolio_components.txt",
    ]:
        if rel(root, f"{analysis_root}/{_fname}").exists():
            lines.append(f"  {_fname}")
    lines.append("")
    lines.append("SUBFOLDERS:")
    lines.append("  config\\   settings.csv and portfolios.csv used for this run")
    lines.append("  synth\\    synthetic DBs and ledgers")
    lines.append("  hist\\     ETF/historical proxy DBs and ledgers")
    lines.append("  crash\\    rolling-window / crash-test outputs")
    lines.append("  charts\\   all chart PNG files")
    lines.append("  tables\\   all auxiliary CSV/PNG tables")
    lines.append("")
    lines.append("PORTFOLIOS:")
    for p in portfolios:
        lines.append(f"  {p.get('ID','')} | {p.get('LABEL','')} | {p.get('REBALANCE','')} {p.get('MAX_DRIFT','')}")
    lines.append("")
    lines.append("TAX NOTE:")
    lines.append("  tax_mode=gross means no Polish Belka tax.")
    lines.append("  tax_mode=net means Polish tax model is enabled; normally tax_base=PLN and tax_rate=0.19.")
    lines.append("  Default benchmark/proxy runs are gross to isolate proxy/ETF/synthetic differences.")
    rel(root, f"{analysis_root}/README_ANALYSIS.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

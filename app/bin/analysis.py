#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# -*- coding: utf-8 -*-
"""
analysis.py — orkiestrator analizy portfela.

Logika pomocnicza wydzielona do:
  common.py       — narzędzia ścieżkowe i bool
  task_config.py  — odczyt i interpretacja settings/portfolios
  cmd_builders.py — budowanie komend CLI i raportów
"""

import argparse
import sys
from pathlib import Path

from common import detect_root, rel, task_rel, bool_setting, read_settings
from run_logging import RunLogger
from task_config import (
    read_portfolios, setting_value,
    is_synth_only, is_hist_only,
    normalize_freq_token, freq_suffix,
    resolve_auto_dates, has_pln_outputs, plot_currencies,
    require_file, require_task_file, validate_tax_settings,
    tax_label,
)
from cmd_builders import (
    run, copy_if_exists, step,
    safe_token, mode_label, file_mode_token, display_name,
    detect_modes, make_run_names, snapshot_configs,
    ledger_cmd, plot_cmd, summary_cmd,
    map_components_short, write_components_file,
    summary_actual_range, table_cmd, crash_cmd,
    update_reports_index, write_run_readme,
)

VERSION = "analysis.py 2.6.1 VER_2_2_2_TRADING_START_TOLERANCE"

def main():
    ap = argparse.ArgumentParser(description="analysis.py 2.2: config-driven analysis from a definition folder or two CSV files.")
    ap.add_argument("--definition", default=None, help=r"Analysis definition folder containing settings.csv and portfolios.csv, e.g. analysis_definitions\synth_vs_etf_2005")
    ap.add_argument("--settings", "--ustawienia", dest="settings", default=None, help=r"Analysis settings CSV. Optional when --definition is used.")
    ap.add_argument("--portfolios", "--portfele", dest="portfolios", default=None, help=r"Portfolios/maps CSV. Optional when --definition is used.")
    ap.add_argument("--root", default="AUTO", help=r"Project root; autodetected from app\bin\analysis.py by default.")
    ap.add_argument("--run-stamp", default=None, help="Optional fixed timestamp/run suffix, e.g. 20260518_181500.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--no-ledger", action="store_true")
    ap.add_argument("--no-plots", action="store_true")
    ap.add_argument("--no-summary", action="store_true")
    ap.add_argument("--no-crash", action="store_true")
    args = ap.parse_args()

    root = detect_root(args.root)

    definition_dir = None
    if args.definition:
        definition_dir = rel(root, args.definition)
        args.settings = str(definition_dir / "settings.csv")
        args.portfolios = str(definition_dir / "portfolios.csv")

    if not args.settings or not args.portfolios:
        raise SystemExit("ERROR: provide --definition or both --settings and --portfolios.")

    settings_path = rel(root, args.settings)
    portfolios_path = rel(root, args.portfolios)
    if definition_dir is None:
        definition_dir = settings_path.parent

    settings_raw = read_settings(settings_path)
    settings = resolve_auto_dates(settings_raw)
    portfolios = read_portfolios(portfolios_path)
    validate_tax_settings(settings, context=str(settings_path))

    task_name = definition_dir.name if definition_dir is not None else None
    analysis_id, ts, run_folder = make_run_names(settings, portfolios, args.run_stamp, task_name=task_name)
    tax_mode = settings.get("tax_mode", "gross")
    tax_lbl = tax_label(settings)

    # analysis_results/<timestamp-analysis>/ is the single complete output folder.
    out_root = f"analysis_results/{run_folder}"
    reports_charts_root = f"{out_root}/charts"
    reports_tables_root = f"{out_root}/tables"

    out_root_path = rel(root, out_root)
    out_root_path.mkdir(parents=True, exist_ok=True)
    log_path = out_root_path / "run.log"

    with RunLogger(log_path):
        print("\n================================================================")
        print(f"ANALYSIS PACKAGE ({VERSION})")
        print("================================================================")
        print(f"ROOT:        {root}")
        print(f"DEFINITION:  {args.definition or '<explicit settings/portfolios>'}")
        print(f"SETTINGS:    {settings_path}")
        print(f"PORTFOLIOS:  {portfolios_path}")
        print(f"TASK_NAME:   {task_name or '<manual>'}")
        print(f"ANALYSIS_ID: {analysis_id}")
        print(f"RUN_STAMP:   {ts}")
        print(f"ANALYSIS_FOLDER: {run_folder}")
        print(f"PERIOD:      {settings.get('start')} -> {settings.get('end')}")
        if settings.get("_start_requested", "") != settings.get("start", "") or settings.get("_end_requested", "") != settings.get("end", ""):
            print(f"START REQUESTED: {settings.get('_start_requested', '') or 'AUTO'}")
            print(f"START RESOLVED:  {settings.get('start')}  ({settings.get('_start_resolved_reason', '')})")
            print(f"END REQUESTED:   {settings.get('_end_requested', '') or 'AUTO'}")
            print(f"END RESOLVED:    {settings.get('end')}  ({settings.get('_end_resolved_reason', '')})")
        print(f"TAX_MODE:    {tax_mode}")
        print(f"PORTFOLIOS:  {len(portfolios)}")
        print("OUTPUTS:")
        print(f"  Tables:     {reports_tables_root}")
        print(f"  Charts:     {reports_charts_root}")
        print(f"  Complete:   {out_root}")
        print("================================================================")

        required_scripts = [
            "app/bin/build_db_synthetic.py",
            "app/bin/build_db_freq.py",
            "app/bin/passive_ledger.py",
            "app/bin/ledger_summary.py",
            "app/bin/plot_ledger_template.py",
            "app/bin/make_summary_table.py",
            "app/bin/crash_test_windows.py",
            "app/bin/crash_by_portfolio.py",
        ]
        for s in required_scripts:
            require_file(root, s, "script")
        hist_only = is_hist_only(settings)
        synth_only = is_synth_only(settings)
        if hist_only and synth_only:
            raise ValueError("analysis_mode nie może być jednocześnie hist_only i synth_only.")
        if not hist_only:
            require_file(root, settings["synth_library"], "synth_library")
        if not synth_only:
            hist_lib_setting = setting_value(settings, "hist_library", "data\\in\\libraries\\HIST_LIBRARY_DAILY.csv")
            require_file(root, hist_lib_setting, "hist_library")
            settings["hist_library"] = hist_lib_setting
        if setting_value(settings, "cpi_us"):
            require_file(root, settings["cpi_us"], "cpi_us")
        for s in ["fx", "cpi_pl"]:
            v = setting_value(settings, s)
            if v:
                require_file(root, v, s)

        out_synth = f"{out_root}/synth"
        out_hist = f"{out_root}/hist"
        out_crash = f"{out_root}/crash"
        charts = reports_charts_root
        tables = reports_tables_root

        for d in [out_synth, out_hist, out_crash, charts, tables]:
            rel(root, d).mkdir(parents=True, exist_ok=True)

        snapshot_configs(root, settings_path, portfolios_path, out_root, definition_dir=definition_dir, version=VERSION)

        all_ledgers = []
        all_names = []
        crash_items = []
        component_lines = []
        fsuf = freq_suffix(settings.get("freq", "monthly"))

        for p in portfolios:
            pid = p["ID"]
            label = p.get("LABEL", pid)
            map_synth = p.get("MAP_SYNTH", "")
            map_hist = p.get("MAP_HIST", "")
            rebalance = p.get("REBALANCE", "DRIFT")
            max_drift = p.get("MAX_DRIFT", "20")
            rebal_period = p.get("REBAL_PERIOD", "")  # PATCH 2026-06-19/20: nowe, opcjonalne pole
            mode_tok = file_mode_token(rebalance, max_drift, rebal_period)

            map_synth_path = None
            if not hist_only:
                if not map_synth:
                    raise ValueError(f"Brak MAP_SYNTH dla {pid}, a analysis_mode nie jest hist_only.")
                map_synth_path = require_task_file(root, definition_dir, map_synth, f"MAP_SYNTH {pid}")
            map_hist_path = None
            if not synth_only:
                if not map_hist:
                    raise ValueError(f"Brak MAP_HIST dla {pid}, a analysis_mode nie jest synth_only.")
                map_hist_path = require_task_file(root, definition_dir, map_hist, f"MAP_HIST {pid}")

            # Portfolio legend for printed summary tables.
            # One line per analyzed portfolio, not per SYN/HIST row.
            # Prefer the HIST map because tickers like SPY/IEF are clearer for printed output.
            footer_map_path = map_hist_path if map_hist_path is not None else map_synth_path
            component_lines.append(f"{label} ({map_components_short(footer_map_path)})")

            synth_dir = f"{out_synth}/{pid}"
            hist_dir = f"{out_hist}/{pid}"
            rel(root, synth_dir).mkdir(parents=True, exist_ok=True)
            if not synth_only:
                rel(root, hist_dir).mkdir(parents=True, exist_ok=True)

            db_synth = f"{synth_dir}/DB_{pid}_syn_M.csv"
            diag_synth = f"{synth_dir}/DB_{pid}_syn_M_diag.csv"
            ledger_synth = f"{synth_dir}/l_{pid}_syn_{mode_tok}.csv"

            db_hist = f"{hist_dir}/DB_{pid}_hist_{fsuf}.csv"
            ledger_hist = f"{hist_dir}/l_{pid}_hist_{mode_tok}.csv"

            name_synth = display_name(label, "SYN", rebalance, max_drift, rebal_period)
            name_hist = display_name(label, "HIST", rebalance, max_drift, rebal_period)

            if not args.no_db:
                if not hist_only:
                    if normalize_freq_token(settings.get("freq", "monthly")) != "monthly":
                        raise ValueError("SYN/SYN+HIST jest obsługiwany tylko dla freq=monthly. Dla daily/weekly użyj analysis_mode=hist_only.")
                    step(f"DB SYNTHETIC: {label}")
                    print("Buduje DB notowań składników portfela z biblioteki syntetyków.")
                    print(f"  MAP: {map_synth}")
                    print(f"  OUT: {db_synth}")
                    run([
                        sys.executable,
                        str(rel(root, "app/bin/build_db_synthetic.py")),
                        "--mapping", str(map_synth_path),
                        "--library", str(rel(root, settings["synth_library"])),
                        "--out-etf", str(rel(root, db_synth)),
                        "--diag", str(rel(root, diag_synth)),
                        "--start", settings.get("dbstart_synth", settings["start"]),
                        "--fill-gaps", settings.get("fill_gaps", "interpolate"),
                    ], root, args.dry_run)

                if not synth_only:
                    step(f"DB ETF HIST: {label}")
                    print("Buduje DB notowań składników portfela z realnych ETF/proxy historycznych.")
                    print(f"  MAP: {map_hist}")
                    print(f"  OUT: {db_hist}")
                    print(f"  LIBRARY: {settings.get('hist_library', 'data\\in\\libraries\\HIST_LIBRARY_DAILY.csv')}")
                    run([
                        sys.executable,
                        str(rel(root, "app/bin/build_db_freq.py")),
                        "--mapping", str(map_hist_path),
                        "--out-etf", str(rel(root, db_hist)),
                        "--start", settings.get("dbstart_hist", settings["start"]),
                        "--freq", settings.get("freq", "monthly"),
                        "--library", str(rel(root, settings.get("hist_library", "data\\in\\libraries\\HIST_LIBRARY_DAILY.csv"))),
                        "--start-tolerance-days", settings.get("start_tolerance_days", "7"),
                    ], root, args.dry_run)

            if not args.no_ledger:
                if not hist_only:
                    step(f"LEDGER SYNTHETIC: {label}")
                    print("Generuje wynikowy ledger z wynikami portfela syntetycznego.")
                    print(f"  MODE: {mode_label(rebalance, max_drift, rebal_period)}")
                    print(f"  OUT: {ledger_synth}")
                    run(ledger_cmd(root, settings, str(map_synth_path), db_synth, ledger_synth, rebalance, max_drift, rebal_period), root, args.dry_run)

                if not synth_only:
                    step(f"LEDGER ETF HIST: {label}")
                    print("Generuje wynikowy ledger z wynikami portfela ETF/proxy historycznego na tym samym okresie.")
                    print(f"  MODE: {mode_label(rebalance, max_drift, rebal_period)}")
                    print(f"  OUT: {ledger_hist}")
                    run(ledger_cmd(root, settings, str(map_hist_path), db_hist, ledger_hist, rebalance, max_drift, rebal_period), root, args.dry_run)

            if not hist_only:
                all_ledgers.append(ledger_synth)
                all_names.append(name_synth)
                crash_items.append((f"{pid}_SYN".upper(), ledger_synth))
            if not synth_only:
                all_ledgers.append(ledger_hist)
                all_names.append(name_hist)
                crash_items.append((f"{pid}_HIST".upper(), ledger_hist))

            if bool_setting(settings, "make_plots", True) and not args.no_plots:
                plot_items = []
                if not hist_only:
                    plot_items.append(("syn", ledger_synth, name_synth))
                if not synth_only:
                    plot_items.append(("hist", ledger_hist, name_hist))
                for dataset, ledger, pretty_name in plot_items:
                    for ccy in plot_currencies(settings):
                        out_plot = f"{charts}/{pid}_{dataset}_{ccy.lower()}_real_nominal_cpi_log.png"
                        step(f"PLOT {pretty_name} {ccy}")
                        print("Generuje wykres portfela: wartość realna i nominalna oraz CPI, w skali logarytmicznej.")
                        print(f"  OUT: {out_plot}")
                        run(plot_cmd(root, ledger, out_plot, pretty_name, ccy, settings), root, args.dry_run)

        if not args.no_summary:
            usd_summary = f"{tables}/summary_{tax_lbl}_USD_real.csv"
            step("SUMMARY USD-REAL")
            print("Generuje tabelę podsumowania w USD-real na podstawie ledgerów portfeli.")
            run(summary_cmd(root, all_ledgers, all_names, usd_summary, settings.get("value_col_usd", "TOTAL_USD_POST_REAL")), root, args.dry_run)

            do_pln = has_pln_outputs(settings)
            pln_summary = f"{tables}/summary_{tax_lbl}_PLN_real.csv"
            if do_pln:
                step("SUMMARY PLN-REAL")
                print("Generuje tabelę podsumowania w PLN-real na podstawie ledgerów portfeli.")
                run(summary_cmd(root, all_ledgers, all_names, pln_summary, settings.get("value_col_pln", "TOTAL_PLN_POST_REAL")), root, args.dry_run)

            if bool_setting(settings, "make_summary_png", True):
                title = settings.get("summary_title", "Portfolio analysis")
                components_file = f"{tables}/portfolio_components.txt"
                write_components_file(root, components_file, component_lines)
                step("SUMMARY PNG USD-REAL")
                run(table_cmd(
                    root,
                    usd_summary,
                    f"{tables}/summary_{tax_lbl}_USD_real.png",
                    title,
                    f"{summary_actual_range(root, usd_summary, settings['start'], settings['end'])} | {settings.get('freq','monthly')} | {tax_lbl} | metrics in USD-real",
                    "Main metrics use TOTAL_USD_POST_REAL. Green cells mark best values. not recovered = no new ATH by end date.",
                    str(settings.get("saldo", "")),
                    components_file,
                ), root, args.dry_run)

                if do_pln:
                    step("SUMMARY PNG PLN-REAL")
                    run(table_cmd(
                        root,
                        pln_summary,
                        f"{tables}/summary_{tax_lbl}_PLN_real.png",
                        title,
                        f"{summary_actual_range(root, pln_summary, settings['start'], settings['end'])} | {settings.get('freq','monthly')} | {tax_lbl} | metrics in PLN-real",
                        "Main metrics use TOTAL_PLN_POST_REAL. Green cells mark best values. not recovered = no new ATH by end date.",
                        str(settings.get("saldo", "")),
                        components_file,
                    ), root, args.dry_run)

                if not args.dry_run:
                    step("COPY KEY FILES TO COMPLETE ANALYSIS FOLDER")
                    print("Kopiuje kluczowe pliki summary CSV/PNG bezpośrednio do kompletnego folderu analysis_results/<timestamp-analysis>.")
                    copy_if_exists(root, usd_summary, f"{out_root}/summary_{tax_lbl}_USD_real.csv")
                    copy_if_exists(root, f"{tables}/summary_{tax_lbl}_USD_real.png", f"{out_root}/summary_{tax_lbl}_USD_real.png")
                    copy_if_exists(root, components_file, f"{out_root}/portfolio_components.txt")
                    if do_pln:
                        copy_if_exists(root, pln_summary, f"{out_root}/summary_{tax_lbl}_PLN_real.csv")
                        copy_if_exists(root, f"{tables}/summary_{tax_lbl}_PLN_real.png", f"{out_root}/summary_{tax_lbl}_PLN_real.png")

        if bool_setting(settings, "make_crash", True) and not args.no_crash:
            step("CRASH USD-REAL")
            print(f"Szuka najgorszych okien czasowych {settings.get('windows', '3,5,7,10,15,20')} lat osobno dla każdego portfela w USD-real, na tle S&P 500 i US 60/40.")
            run(crash_cmd(root, crash_items, f"{out_crash}/USD_real", settings.get("value_col_usd", "TOTAL_USD_POST_REAL"), settings), root, args.dry_run)

            if has_pln_outputs(settings):
                step("CRASH PLN-REAL")
                print(f"Szuka najgorszych okien czasowych {settings.get('windows', '3,5,7,10,15,20')} lat osobno dla każdego portfela w PLN-real, na tle S&P 500 i US 60/40.")
                run(crash_cmd(root, crash_items, f"{out_crash}/PLN_real", settings.get("value_col_pln", "TOTAL_PLN_POST_REAL"), settings), root, args.dry_run)

        if not args.dry_run:
            write_run_readme(root, out_root, charts, tables, run_folder, settings, portfolios)

        update_reports_index(root, analysis_id, run_folder, out_root, settings)

        print("\n================================================================")
        print("GOTOWE")
        print("================================================================")
        print(f"ANALYSIS_FOLDER: {run_folder}")
        print(f"Tables:     {tables}")
        print(f"Charts:     {charts}")
        print(f"Complete:   {out_root}")
        print(f"Key files:  {out_root}\\summary_{tax_lbl}_USD_real.csv / summary_{tax_lbl}_PLN_real.csv")
        print("================================================================")


if __name__ == "__main__":
    main()

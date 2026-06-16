#!/usr/bin/env python3
# pasywnyportfel — konfiguracja i metadane taska
# Autor koncepcji i projektu: Wojciech Król / email: lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
task_config.py — odczyt i interpretacja settings.csv / portfolios.csv.

Eksportuje:
  read_portfolios, setting_value, is_synth_only, is_hist_only,
  normalize_freq_token, freq_suffix, resolve_auto_dates,
  has_pln_outputs, plot_currencies,
  require_file, require_task_file, validate_tax_settings,
  list_tasks
"""

import csv
import datetime as dt
from pathlib import Path

from dateutil.relativedelta import relativedelta

from common import bool_setting, rel, resolve_auto_date_token, task_rel


# ---------------------------------------------------------------------------
# Odczyt portfeli
# ---------------------------------------------------------------------------

def read_portfolios(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku portfeli: {path}\n"
            f"Podaj poprawny plik portfeli CSV przez --portfele."
        )
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("INCLUDE", "1")).strip() in ["1", "yes", "YES", "true", "TRUE", "tak", "TAK"]:
                rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


# ---------------------------------------------------------------------------
# Pomocnicze odczyty ustawień
# ---------------------------------------------------------------------------

def setting_value(settings: dict, key: str, default: str = "") -> str:
    return str(settings.get(key, default) or "").strip()


def is_synth_only(settings: dict) -> bool:
    v = setting_value(settings, "analysis_mode", setting_value(settings, "datasets", "")).lower()
    return v in {"synth", "synthetic", "synth_only", "synthetic_only"}


def is_hist_only(settings: dict) -> bool:
    v = setting_value(settings, "analysis_mode", setting_value(settings, "datasets", "")).lower()
    return v in {"hist", "hist_only", "historical", "historical_only", "etf", "etf_only"}


# ---------------------------------------------------------------------------
# Tokeny częstotliwości
# ---------------------------------------------------------------------------

def normalize_freq_token(freq: str) -> str:
    f = (freq or "monthly").strip().lower()
    aliases = {
        "d": "daily", "daily": "daily",
        "w": "weekly", "weekly": "weekly",
        "m": "monthly", "monthly": "monthly",
    }
    if f not in aliases:
        raise ValueError(f"Nieprawidłowe freq={freq!r}; użyj daily/weekly/monthly albo D/W/M.")
    return aliases[f]


def freq_suffix(freq: str) -> str:
    return {"daily": "D", "weekly": "W", "monthly": "M"}[normalize_freq_token(freq)]


# ---------------------------------------------------------------------------
# Rozwiązywanie dat AUTO
# ---------------------------------------------------------------------------

def _last_day_of_month(d: dt.date) -> dt.date:
    first = d.replace(day=1)
    return first + relativedelta(months=1) - dt.timedelta(days=1)


def resolve_auto_dates(settings: dict) -> dict:
    out = dict(settings)
    today = dt.date.today()
    start_req = setting_value(out, "start", "")
    end_req = setting_value(out, "end", "")
    lookback_months = setting_value(out, "lookback_months", "")

    end_res, end_reason = resolve_auto_date_token(end_req or "AUTO", today)

    if lookback_months and (start_req == "" or start_req.upper().startswith("AUTO")):
        months = int(float(str(lookback_months).replace(",", ".")))
        start_date = dt.date.fromisoformat(end_res) - relativedelta(months=months)
        start_res = start_date.isoformat()
        start_reason = f"lookback_months={months} -> {start_res}"
    else:
        start_res, start_reason = resolve_auto_date_token(start_req, today)

    out["_start_requested"] = start_req
    out["_end_requested"] = end_req
    out["_start_resolved_reason"] = start_reason
    out["_end_resolved_reason"] = end_reason
    out["start"] = start_res
    out["end"] = end_res
    return out


# ---------------------------------------------------------------------------
# Waluty i flagi PLN
# ---------------------------------------------------------------------------

def has_pln_outputs(settings: dict) -> bool:
    if not bool_setting(settings, "make_pln", True):
        return False
    return (
        bool(setting_value(settings, "fx"))
        and bool(setting_value(settings, "cpi_pl"))
        and bool(setting_value(settings, "value_col_pln", "TOTAL_PLN_POST_REAL"))
    )


def plot_currencies(settings: dict) -> list[str]:
    raw = setting_value(settings, "plot_currencies", "")
    if raw:
        vals = [x.strip().upper() for x in raw.split(",") if x.strip()]
    else:
        vals = ["USD"]
        if has_pln_outputs(settings):
            vals.append("PLN")
    out = []
    for v in vals:
        if v in {"USD", "PLN"} and v not in out:
            out.append(v)
    return out or ["USD"]


# ---------------------------------------------------------------------------
# Walidacja plików i ustawień
# ---------------------------------------------------------------------------

def require_file(root: Path, path: str, label: str):
    p = rel(root, path)
    if not p.exists():
        raise FileNotFoundError(f"BRAK {label}: {path}")
    return p


def require_task_file(root: Path, task_dir: Path | None, path: str, label: str):
    p = task_rel(root, task_dir, path)
    if not p.exists():
        raise FileNotFoundError(f"BRAK {label}: {path}\n  oczekiwana ścieżka: {p}")
    return p


def validate_tax_settings(settings: dict, context: str = "analysis") -> None:
    tax_mode = str(settings.get("tax_mode", "gross")).strip().lower()
    if tax_mode in ["", "gross", "none", "off", "0"]:
        return

    if tax_mode != "net":
        raise ValueError(
            f"BŁĄD KONFIGURACJI PODATKU ({context}): tax_mode={tax_mode!r}. "
            "Obsługiwane wartości: gross albo net."
        )

    tax_base_raw = str(settings.get("tax_base", "")).strip().upper()
    if not tax_base_raw:
        raise ValueError(
            "BŁĄD KONFIGURACJI PODATKU: tax_mode=net, ale nie podano tax_base.\n"
            "Wybierz jawnie jedną z opcji:\n"
            "  tax_base=PLN  — realny model polskiej Belki, wymaga FX USD/PLN,\n"
            "  tax_base=USD  — model poglądowy/akademicki, liczony w USD bez FX PLN.\n"
            "Dla benchmarku 1960 USD-real zalecane jest tax_mode=gross albo świadomie tax_base=USD."
        )

    if tax_base_raw not in {"PLN", "USD"}:
        raise ValueError(
            f"BŁĄD KONFIGURACJI PODATKU: tax_base={tax_base_raw!r}. "
            "Obsługiwane wartości: PLN albo USD."
        )

    if tax_base_raw == "PLN" and not str(settings.get("fx", "")).strip():
        raise ValueError(
            "BŁĄD KONFIGURACJI PODATKU: tax_mode=net i tax_base=PLN wymagają ścieżki fx.\n"
            "Dla realnej polskiej Belki ustaw fx=data\\in\\fx\\DB_FX.csv.\n"
            "Dla długiej analizy USD-only użyj tax_base=USD tylko jako wariantu poglądowego."
        )


# ---------------------------------------------------------------------------
# Odkrywanie taskow
# ---------------------------------------------------------------------------

def list_tasks(root: Path) -> list[str]:
    """Lista nazw taskow w analysis_definitions.

    Taskiem jest kazdy folder w analysis_definitions/ posiadajacy zarowno
    settings.csv jak i portfolios.csv, z wyjatkiem folderu "common"
    (zawiera wspolne mapy i szablony, nie jest taskiem).

    Wynik jest sortowany alfabetycznie. Uzywane przez run_all_tasks.py
    do odkrycia co mozna uruchomic w batchu, i przez run_task.cmd do
    wypisania listy dostepnych taskow.
    """
    base = root / "analysis_definitions"
    if not base.exists():
        return []
    out = []
    for p in sorted(base.iterdir()):
        if not p.is_dir() or p.name == "common":
            continue
        if (p / "settings.csv").exists() and (p / "portfolios.csv").exists():
            out.append(p.name)
    return out


# ---------------------------------------------------------------------------
# Etykieta tax_mode do nazw plikow i napisow
# ---------------------------------------------------------------------------

def tax_label(settings: dict) -> str:
    """Zwraca znormalizowana etykiete tax_mode do nazw plikow i podpisow.

    gross / puste / none / off / 0  →  "gross"
    net                             →  "net"
    net + tax_base=PLN              →  "net_PLN"
    net + tax_base=USD              →  "net_USD"

    Uzycie w nazwach: summary_{tax_label}_USD_real.csv
    Uzycie w podpisach: "... | net_PLN | metrics in USD-real"
    """
    mode = setting_value(settings, "tax_mode", "gross").lower()
    if mode in ("", "gross", "none", "off", "0"):
        return "gross"
    base = setting_value(settings, "tax_base", "").upper()
    if base:
        return f"net_{base}"
    return "net"

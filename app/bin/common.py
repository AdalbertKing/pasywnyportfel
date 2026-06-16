#!/usr/bin/env python3
# pasywnyportfel — wspólne narzędzia ścieżkowe
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
common.py — kanoniczne implementacje narzędzi ścieżkowych projektu.

Wszystkie pliki w app/bin/ importują stąd:
    from common import detect_root, norm_path, rel, task_rel

Historia duplikacji:
    - detect_root / norm_path / rel / task_rel były kopiowane osobno
      do analysis.py, bootstrap.py, refresh_quotes.py, create_task.py,
      validate_task.py i stage1_quick_check.py.
    - Ten moduł jest jedynym źródłem prawdy od wersji 2.2.5A.
"""

import csv
import datetime as dt
import os
import re
from pathlib import Path
from typing import Any, Optional

from dateutil.relativedelta import relativedelta


# ---------------------------------------------------------------------------
# norm_path
# ---------------------------------------------------------------------------

def norm_path(s: str) -> str:
    """Normalizuje ścieżkę: usuwa cudzysłowy i ujednolica separatory."""
    return str(s).strip().strip('"').replace("/", os.sep).replace("\\", os.sep)


# ---------------------------------------------------------------------------
# detect_root
# ---------------------------------------------------------------------------

def detect_root(root_arg: str = "AUTO") -> Path:
    """Wykrywa katalog główny projektu.

    Kolejność decyzji:
      1. Jeśli root_arg jest podany i różny od 'AUTO' — użyj go.
      2. Jeśli skrypt leży w app/bin/ — root = parents[2].
      3. Jeśli skrypt leży w bin/       — root = parents[1].
      4. Fallback: bieżący katalog roboczy.

    Obsługuje zarówno wywołania z jawnym --root jak i auto-detekcję
    dla skryptów uruchamianych przez .cmd z dowolnego katalogu.
    """
    if root_arg and root_arg != "AUTO":
        return Path(root_arg).resolve()
    here = Path(__file__).resolve()
    if here.parent.name.lower() == "bin" and here.parent.parent.name.lower() == "app":
        return here.parents[2]
    if here.parent.name.lower() == "bin":
        return here.parents[1]
    return Path.cwd().resolve()


# ---------------------------------------------------------------------------
# rel
# ---------------------------------------------------------------------------

def rel(root: Path, s: str) -> Path:
    r"""Rozwiązuje ścieżkę względem katalogu głównego projektu.

    Obsługuje zarówno stare ścieżki (1.0):
        in\cpi\...      →  data\in\cpi\...
        maps\synth\...  →  data\in\maps\synth\...
    jak i nowe ścieżki (2.0):
        data\in\cpi\...

    Jeśli żaden kandydat nie istnieje na dysku, zwraca candidates[0]
    (root / raw), żeby wywołujący kod mógł sam obsłużyć FileNotFoundError.
    """
    raw = norm_path(s)
    p0 = Path(raw)
    if p0.is_absolute():
        return p0
    candidates = [
        root / raw,
        root / "data" / raw,
        root / "app" / raw,
    ]
    parts = p0.parts
    if parts:
        first = parts[0].lower()
        if first == "in":
            candidates.append(root / "data" / raw)
        if first == "maps":
            # backward compatibility: stare projekty przechowywały mapy
            # w data\in\maps\... zanim przeniesiono je do task-folderów
            candidates.append(root / "data" / "in" / raw)
        if first == "bin":
            candidates.append(root / "app" / raw)
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


# ---------------------------------------------------------------------------
# task_rel
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# truthy / bool_setting
# ---------------------------------------------------------------------------

#: Wartości traktowane jako fałsz niezależnie od kontekstu.
_FALSY = {"0", "false", "no", "nie", "off", ""}


def truthy(x: Any) -> bool:
    """Czy wartość z CSV/słownika jest logicznie prawdziwa?

    Fałsz: puste string, "0", "false", "no", "nie", "off" (case-insensitive).
    Prawda: wszystko inne, w tym "1", "yes", "tak", "true".

    Używane do kolumny INCLUDE w portfolios.csv i mappingach.
    """
    return str(x).strip().lower() not in _FALSY


def bool_setting(settings: dict, key: str, default: bool = True) -> bool:
    """Odczytuje flagę boolowską z słownika ustawień (settings.csv).

    Obsługuje trzy przypadki:
      - klucz nieobecny w słowniku  → zwraca ``default``
      - klucz obecny, VALUE puste   → zwraca ``default``
      - klucz obecny, VALUE "0"/"false"/"no"/"nie"/"off" → False
      - klucz obecny, VALUE "1"/"true"/"yes"/cokolwiek innego → True

    Poprzednia wersja (bez "" w zbiorze fałszywych wartości) traktowała
    puste VALUE jako True, ignorując ``default``. Poprawka: puste VALUE
    jest teraz traktowane tak samo jak brak klucza.
    """
    raw = settings.get(key)
    if raw is None:
        return default
    v = str(raw).strip().lower()
    if v == "":
        return default
    return v not in _FALSY


# ---------------------------------------------------------------------------
# resolve_auto_date_token / read_settings
# ---------------------------------------------------------------------------

def resolve_auto_date_token(token: str, today: dt.date) -> tuple[str, str]:
    """Rozwiązuje token daty na konkretną datę ISO.

    Obsługiwane formaty:
      - puste / "AUTO" / "TODAY" / "LATEST" / "NOW"  → dzisiaj
      - "AUTO-Nd"  → dziś minus N dni
      - "AUTO-Nw"  → dziś minus N tygodni
      - "AUTO-Nm"  → dziś minus N miesięcy
      - "AUTO-Ny"  → dziś minus N lat
      - "YYYY-MM-DD"                                  → data explicite

    Zwraca krotkę (iso_string, opis_rozwiązania).
    Rzuca ValueError przy nieznanym formacie.
    """
    raw = str(token or "").strip()
    u = raw.upper().replace("_", "-")
    if raw == "" or u in {"AUTO", "TODAY", "LATEST", "NOW"}:
        return today.isoformat(), f"{raw or 'AUTO'} -> today={today.isoformat()}"
    m = re.match(r"^AUTO-(\d+)([DWMY])$", u)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "D":
            d = today - dt.timedelta(days=n)
        elif unit == "W":
            d = today - dt.timedelta(weeks=n)
        elif unit == "M":
            d = today - relativedelta(months=n)
        elif unit == "Y":
            d = today - relativedelta(years=n)
        else:
            raise ValueError(raw)
        return d.isoformat(), f"{raw} -> {d.isoformat()}"
    # explicita data ISO — walidacja przez fromisoformat
    dt.date.fromisoformat(raw)
    return raw, f"{raw} -> explicit"


def read_settings(path: Path) -> dict:
    """Czyta plik settings.csv (format KEY,VALUE) do słownika.

    Obsługuje BOM (utf-8-sig). Klucze i wartości są strip-owane.
    Jeśli plik nie istnieje, rzuca FileNotFoundError.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku ustawień: {path}"
        )
    out = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            k = (row.get("KEY") or "").strip()
            v = (row.get("VALUE") or "").strip()
            if k:
                out[k] = v
    return out


def task_rel(root: Path, task_dir: Optional[Path], s: str) -> Path:
    """Rozwiązuje ścieżki map/plików w kontekście konkretnego taska.

    Ścieżki względne są najpierw sprawdzane względem folderu taska
    (analysis_definitions/<task>/), co umożliwia self-contained taski:
        maps/hist/...
        maps/synth/...

    Ścieżki projektowe (data\\in\\cpi\\...) są następnie sprawdzane
    względem root przez standardowe kandydaty rel().

    Parametr task_dir może być None — wtedy szukanie zaczyna się od root.
    """
    raw = norm_path(s)
    p = Path(raw)
    if p.is_absolute():
        return p
    candidates: list[Path] = []
    if task_dir is not None:
        candidates.append(task_dir / raw)
    candidates.extend([
        root / raw,
        root / "data" / raw,
        root / "app" / raw,
    ])
    parts = p.parts
    if parts:
        first = parts[0].lower()
        if first == "in":
            candidates.append(root / "data" / raw)
        if first == "maps":
            # backward compatibility dla starych projektów
            candidates.append(root / "data" / "in" / raw)
        if first == "bin":
            candidates.append(root / "app" / raw)
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

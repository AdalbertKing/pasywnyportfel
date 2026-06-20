"""
gui.py — pasywnyportfel GUI (CustomTkinter)
[USER] Desktop GUI dla pakietu pasywnyportfel.

ETAP 0 — SZKIELET (zrobione)
ETAP 1 — ZAKŁADKA URUCHOM (ten plik)
=====================================
Etap 0: okno, sidebar, 4 zakładki, konsola, statusbar — patrz GUI_PROJECT_SPEC.md.

Etap 1 dopina zakładkę Uruchom zgodnie z GUI_PROJECT_SPEC.md §6:
  - Parametry taska (siatka klucz-wartość, odczyt z settings.csv)
  - Portfele w analizie (lista z checkboxami INCLUDE/SYNTH/HIST, skład,
    ostrzeżenia HIST)
  - Akcje: Uruchom / Dry-run / Refresh HIST / Waliduj
  - Ostatnie przebiegi (lista z folderu analysis_results)
  - Realne wiązanie z task_config / common / cmd_builders / validate_task
    (z degradacją do danych demo gdy moduły silnika nie są dostępne —
    np. podczas testowania GUI poza repo)

Pozostałe 3 zakładki (Konfiguracja/Wyniki/Portfele) — nadal placeholder,
do Etapów 2-4.

Uruchamianie: dwuklik na gui.cmd w katalogu głównym repo.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Lokalizacja katalogu głównego repo (app/bin/gui.py -> root = parent.parent)
# ---------------------------------------------------------------------------
GUI_DIR = Path(__file__).resolve().parent          # .../app/bin (katalog tego pliku)
ROOT = GUI_DIR.parent.parent                        # korzeń repo (.../pasywnyportfel)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def find_script(name: str) -> Path:
    """
    Zwraca BEZWZGLĘDNĄ ścieżkę do skryptu/binarki (analysis.py, refresh_data.cmd,
    itd.). Sprawdza kilka możliwych lokalizacji po kolei (układ repo zmieniał
    się przy refaktoryzacji), zamiast zakładać sztywno jedno miejsce — to był
    błąd w poprzedniej wersji (analysis.py szukany relatywnie do ROOT, a leży
    w app/bin). Gdy nic nie istnieje, zwraca pierwszą kandydatkę — błąd i tak
    wypłynie czytelnie w konsoli, zamiast cichego złego zachowania.
    """
    candidates = [GUI_DIR / name, ROOT / name]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

# ---------------------------------------------------------------------------
# Import modułów silnika. Każdy osobno w try/except — częściowy brak (np.
# zła sygnatura jednej funkcji) nie wywala całego GUI, tylko ta jedna
# funkcjonalność spada do trybu demo i mówi o tym w konsoli (Etap 1 to
# pierwsze realne wiązanie — sygnatury "z dokumentu" mogą wymagać korekty
# po pierwszym teście na prawdziwym repo).
# ---------------------------------------------------------------------------
try:
    import task_config
except ImportError:
    task_config = None

try:
    import common
except ImportError:
    common = None

try:
    import cmd_builders
except ImportError:
    cmd_builders = None

try:
    import validate_task as validate_task_mod
except ImportError:
    validate_task_mod = None

ENGINE_AVAILABLE = all([task_config, common, cmd_builders, validate_task_mod])

#: Zgodne z common.truthy() w realnym repo — wartości traktowane jako fałsz.
_FALSY = {"0", "false", "no", "nie", "off", ""}


def truthy_like(x) -> bool:
    """Lokalna kopia common.truthy() — używana zanim/jeśli common nie jest
    zaimportowane, i dla spójności z prawdziwą logiką kolumny INCLUDE."""
    return str(x).strip().lower() not in _FALSY


# ---------------------------------------------------------------------------
# Stałe wizualne — zgodnie z GUI_PROJECT_SPEC.md §3 (Standard wizualny)
#
# JEDEN WSPÓLNY MNOŻNIK: UI_SCALE napędza zarówno fonty (_px) jak i WSZYSTKIE
# wymiary — wysokości przycisków, szerokości paneli, odstępy (_dim). Wartości
# "base*" poniżej to rozmiary logiczne przy scale=1.0 (mniej więcej zgodne
# z surowymi liczbami ze specu); UI_SCALE=1.45 to korekta wynikająca z testu
# na realnym 24" FHD (7-9px dosłownych pikseli okazało się nieczytelne).
# Żeby przeskalować całe okno na nowo — zmień TYLKO UI_SCALE.
#
# Wyjątek świadomy: rozmiar i minrozmiar GŁÓWNEGO OKNA (patrz geometry/minsize
# w PasywnyPortfelGUI) NIE przechodzi przez UI_SCALE — to przestrzeń ekranu,
# którą user kontroluje sam (resize/maximize), nie element UI do przeskalowania.
# ---------------------------------------------------------------------------
UI_SCALE = 1.45
FONT_SCALE = UI_SCALE  # alias zachowany dla czytelności w komentarzach o fontach


def _px(base: float) -> int:
    """Rozmiar fontu w px (ujemny = dosłowne piksele w Tkinter, bez DPI scalingu)."""
    return -round(base * UI_SCALE)


def _dim(base: float) -> int:
    """Wymiar (wysokość/szerokość/odstęp) w px, przeskalowany tym samym knobem co fonty."""
    return round(base * UI_SCALE)


# -- odstępy (spacing tokens) — wszystkie padx/pady w pliku korzystają z tych trzech ----
PAD = _dim(3)         # standardowy odstęp (~4px @1.45)
PAD_TIGHT = _dim(1.5)  # ciasne odstępy, np. między kropką statusu a nazwą (~2px)
PAD_LOOSE = _dim(6)    # luźniejsze odstępy, np. statusbar / nagłówek konsoli (~9px)

# -- sidebar (zakres 140-160px ze specu, przeskalowany razem z resztą) -----------------
SIDEBAR_WIDTH = _dim(110)      # ~160px @1.45 — startowa szerokość panelu
SIDEBAR_MIN_WIDTH = _dim(97)   # ~140px @1.45 — dolna granica ze specu, sash nie zwęzi bardziej
SIDEBAR_MAX_WIDTH = _dim(290)  # ~420px @1.45 — sufit, żeby nie dało się "zjeść" całej zakładki

# -- pozostałe wymiary używane przez widgety poniżej ------------------------------------
BTN_HEIGHT = _dim(21)        # główne przyciski sidebaru (+ Nowy task, Odśwież...)
CONSOLE_BTN_WIDTH = _dim(59)   # przyciski w nagłówku konsoli (rozwiń / kopiuj)
CONSOLE_BTN_HEIGHT = _dim(17)
CONSOLE_LINE_HEIGHT = _dim(16)  # wysokość jednej linii konsoli (mnożona przez liczbę linii)
CONSOLE_LINE_OFFSET = _dim(8)   # stały narzut (marginesy wewnętrzne textboxa)
STATUSBAR_HEIGHT = _dim(18)
TASK_DOT_WIDTH = _dim(11)     # szerokość kolumny z kropką statusu w sidebarze
SASH_WIDTH = _dim(3)          # grubość uchwytu PanedWindow

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

F_LABEL = (FONT_FAMILY, _px(9))            # etykiety, tekst główny, inputy, dropdowny
F_LABEL_B = (FONT_FAMILY, _px(9), "bold")
F_SECTION = (FONT_FAMILY, _px(8), "bold")  # nagłówki sekcji (uppercase)
F_HINT = (FONT_FAMILY, _px(7))             # hinty, ścieżki, tagi
F_HINT8 = (FONT_FAMILY, _px(8))
F_SIDEBAR_TITLE = (FONT_FAMILY, _px(7), "bold")
F_SIDEBAR_TASK = (FONT_FAMILY, _px(9))
F_CONSOLE = (MONO_FAMILY, _px(8))
F_STATUSBAR = (FONT_FAMILY, _px(7))

COL_BG = "#1e1e1e"
COL_PANEL = "#252526"
COL_SIDEBAR = "#202020"
COL_CONSOLE_BG = "#101010"
COL_BORDER = "#3a3a3a"
COL_TEXT = "#d4d4d4"
COL_TEXT_DIM = "#8a8a8a"
COL_OK = "#5DCAA5"
COL_WARN = "#EF9F27"
COL_FAIL = "#E5534B"
COL_FLAG = "#EF9F27"     # kolorowanie flag w konsoli (pomarańczowe)
COL_VALUE = "#5DCAA5"    # kolorowanie wartości w konsoli (zielone)
COL_ACCENT = "#3B7DD8"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# Dane przykładowe — fallback gdy silnik niedostępny LUB gdy realne wywołanie
# się wysypie (np. zła sygnatura). Kształt zgodny z tym czego oczekują widgety,
# żeby przełączenie real/demo było niewidoczne dla warstwy UI.
# ---------------------------------------------------------------------------
DEMO_TASKS = [
    {"name": "demo_60_40", "status": "ok"},
    {"name": "demo_permanent_portfolio", "status": "ok"},
    {"name": "demo_zlote_motyle", "status": "warn"},
]

# Kształt 1:1 z prawdziwym settings.csv (KEY,VALUE) — potwierdzone z realnego
# repo (common.read_settings, task_config.py, validate_tax_settings).
# Realne klucze: start/end/saldo/freq/tax_mode/tax_base/tax_rate/
# plot_currencies/analysis_mode — NIE "capital"/"valuation"/"currencies"/
# "drift" jak w pierwszej (zgadywanej) wersji.
DEMO_SETTINGS = {
    "start": "2000-01-01", "end": "2024-12-31", "saldo": "100000",
    "freq": "monthly", "tax_mode": "net", "tax_base": "PLN", "tax_rate": "0.19",
    "plot_currencies": "USD,PLN", "analysis_mode": "synth_only",
}

# Kształt 1:1 z prawdziwym portfolios.csv: ID,LABEL,MAP_SYNTH,MAP_HIST,
# REBALANCE,MAX_DRIFT,INCLUDE. Rebalans jest PER PORTFEL, nie per task —
# to było źle założone w pierwszej wersji (ParamsGrid miał jedno globalne
# pole "Rebalans", co nie odpowiada silnikowi).
DEMO_PORTFOLIOS = [
    {
        "ID": "us6040", "LABEL": "US 60/40", "INCLUDE": "1",
        "MAP_SYNTH": "maps\\synth\\us6040_syn.csv", "MAP_HIST": "",
        "REBALANCE": "DRIFT", "MAX_DRIFT": "20",
    },
    {
        "ID": "permanent", "LABEL": "Permanent Portfolio", "INCLUDE": "1",
        "MAP_SYNTH": "maps\\synth\\permanent_syn.csv", "MAP_HIST": "maps\\hist\\permanent_etf.csv",
        "REBALANCE": "ANNUAL", "MAX_DRIFT": "0",
    },
    {
        "ID": "zlote_motyle", "LABEL": "Złote Motyle", "INCLUDE": "0",
        "MAP_SYNTH": "", "MAP_HIST": "maps\\hist\\zlote_motyle_etf.csv",
        "REBALANCE": "BH", "MAX_DRIFT": "0",
    },
]

DEMO_RUNS = [
    {"status": "ok", "timestamp": "2026-06-18 20:53", "duration": "2m14s",
     "tax_label": "net_PLN", "n_portfolios": 3, "folder": str(ROOT)},
    {"status": "fail", "timestamp": "2026-06-17 09:12", "duration": "0m08s",
     "tax_label": "gross", "n_portfolios": 2, "folder": str(ROOT)},
]

DEMO_STATUSBAR_LEFT = "FAIL:0  WARN:0  OK:42"
DEMO_STATUSBAR_RIGHT = "Python 3.13 | 402 testów | gui branch"


class Engine:
    """
    Cienka warstwa nad task_config/common/cmd_builders/validate_task.
    Każda metoda: próbuje realnego wywołania, przy wyjątku/braku modułu
    zwraca dane demo + komunikat diagnostyczny (logged), żeby UI nigdy
    się nie wywaliło z powodu niezgodnej sygnatury — tylko pokaże że
    działa w trybie demo dla tej jednej rzeczy.
    """

    def __init__(self, log_fn=print):
        self._log = log_fn

    def _warn(self, where: str, exc: Exception):
        self._log(f"[DEMO] {where}: {type(exc).__name__}: {exc} — pokazuję dane przykładowe")

    def list_tasks(self) -> list[dict]:
        # POPRAWKA: task_config.list_tasks() NIE ISTNIEJE w realnym repo
        # (sprawdzone bezpośrednio w pliku użytkownika) — to była funkcja
        # zaproponowana w innej, nigdy niewdrożonej sesji. Implementujemy
        # odkrywanie tasków tu, identyczną logiką jaką widziałem proponowaną:
        # foldery w analysis_definitions/ z settings.csv + portfolios.csv,
        # z pominięciem folderu "common" (mapy/szablony, nie task).
        definitions_dir = ROOT / "analysis_definitions"
        if not definitions_dir.exists():
            return DEMO_TASKS
        try:
            names = []
            for d in sorted(definitions_dir.iterdir()):
                if not d.is_dir() or d.name == "common":
                    continue
                if (d / "settings.csv").exists() and (d / "portfolios.csv").exists():
                    names.append(d.name)
            if not names:
                return DEMO_TASKS
            tasks = []
            for n in names:
                status = "ok"
                if validate_task_mod:
                    try:
                        validate_task_mod.validate_task(ROOT, n)
                    except Exception:  # noqa: BLE001 — sama walidacja decyduje co jest błędem
                        status = "warn"
                tasks.append({"name": n, "status": status})
            return tasks
        except Exception as exc:  # noqa: BLE001 — celowo szerokie, patrz docstring klasy
            self._warn("odkrywanie tasków w analysis_definitions/", exc)
            return DEMO_TASKS

    def load_task(self, task_name: str) -> dict:
        """Zwraca dict: settings, portfolios, tax_label, validation_error, demo."""
        if not (common and task_config):
            return self._demo_task()
        try:
            settings_path = ROOT / "analysis_definitions" / task_name / "settings.csv"
            portfolios_path = ROOT / "analysis_definitions" / task_name / "portfolios.csv"
            settings = common.read_settings(settings_path)
            # Potwierdzone: read_portfolios jest w task_config, NIE w common.
            # Realne kolumny (sprawdzone w pliku użytkownika): ID, LABEL,
            # MAP_SYNTH, MAP_HIST, REBALANCE, MAX_DRIFT, INCLUDE.
            raw_portfolios = task_config.read_portfolios(portfolios_path)
            portfolios = [self._adapt_portfolio_row(r) for r in raw_portfolios]
            # tax_label(): funkcja NIE ISTNIEJE w realnym repo — budujemy
            # etykietę inline z potwierdzonych kluczy tax_mode/tax_base/tax_rate.
            tax_label = self._build_tax_label(settings)

            validation_error = None
            if validate_task_mod:
                try:
                    # Potwierdzona sygnatura: validate_task(root, task_name) —
                    # RZUCA wyjątek przy błędzie (FileNotFoundError/ValueError).
                    validate_task_mod.validate_task(ROOT, task_name)
                except Exception as exc:  # noqa: BLE001
                    validation_error = str(exc)

            return {
                "settings": settings, "portfolios": portfolios,
                "tax_label": tax_label, "validation_error": validation_error, "demo": False,
            }
        except Exception as exc:  # noqa: BLE001
            self._warn(f"wczytanie taska '{task_name}'", exc)
            return self._demo_task()

    @staticmethod
    def _build_tax_label(settings: dict) -> str:
        """
        Brak funkcji tax_label() w realnym repo — etykieta budowana inline
        z potwierdzonych kluczy settings.csv: tax_mode (gross/net),
        tax_base (PLN/USD), tax_rate (np. 0.19). Logika zgodna z
        task_config.validate_tax_settings(): gross nie wymaga tax_base/tax_rate.
        """
        mode = str(settings.get("tax_mode", "gross")).strip().lower()
        if mode in ("", "gross", "none", "off", "0"):
            return "gross"
        base = str(settings.get("tax_base", "")).strip().upper()
        rate = str(settings.get("tax_rate", "")).strip()
        rate_pct = f" {float(rate) * 100:.0f}%" if rate else ""
        return f"net_{base or '?'}{rate_pct}"

    #: Potwierdzone wprost w cmd_builders.py (mode_label/file_mode_token/
    #: ledger_cmd) — trzy realne tryby. Trzeci ("roczny") to NIE jest
    #: edytowalny interwał [N] miesięcy jak sugerował pierwotny spec — silnik
    #: akceptuje go tylko jako sztywno "co 12 miesięcy", bez parametru.
    _REBAL_BH = {"BH", "B&H", "BUYHOLD", "BUY_AND_HOLD", "NO", "NONE", "NO_REBALANCE"}
    _REBAL_DRIFT = {"DRIFT", "D20", "DRIFT20", "CONDITIONAL"}
    _REBAL_ANNUAL = {"12M", "ANNUAL", "YEARLY"}

    @classmethod
    def _classify_rebalance(cls, rebalance: str) -> str:
        """Zwraca 'BH' / 'DRIFT' / 'ANNUAL' / 'UNKNOWN' — kanoniczny kubełek
        do kolorowania tagu, niezależnie od tego którego synonimu użyto."""
        rb = str(rebalance).strip().upper()
        if rb in cls._REBAL_BH:
            return "BH"
        if rb in cls._REBAL_DRIFT:
            return "DRIFT"
        if rb in cls._REBAL_ANNUAL:
            return "ANNUAL"
        return "UNKNOWN"

    @staticmethod
    def _adapt_portfolio_row(raw: dict) -> dict:
        """
        Tłumaczy surowy wiersz z task_config.read_portfolios() — kolumny
        potwierdzone wprost z pliku użytkownika: ID, LABEL, MAP_SYNTH,
        MAP_HIST, REBALANCE, MAX_DRIFT, INCLUDE. REBALANCE/MAX_DRIFT są
        PER PORTFEL (nie per task — to było źle założone w pierwszej wersji,
        gdzie ParamsGrid miał jedno globalne pole "Rebalans").
        Skład portfela (np. "Gold 20%, Stocks 60%") wymaga doczytania pliku
        spod MAP_SYNTH/MAP_HIST (kolumna WEIGHT w TYM pliku, potwierdzone w
        validate_task.py: weight_sum()) — jeszcze nieobsłużone (TODO),
        więc pokazujemy ścieżki wprost zamiast zmyślać czytelny opis.
        """
        included = truthy_like(raw.get("INCLUDE", "1"))
        map_synth = raw.get("MAP_SYNTH", "")
        map_hist = raw.get("MAP_HIST", "")
        rebalance = raw.get("REBALANCE", "—")
        max_drift = raw.get("MAX_DRIFT", "")
        mode = Engine._classify_rebalance(rebalance)
        # Wolimy realny cmd_builders.mode_label() (autorytatywny tekst) gdy
        # moduł jest dostępny; fallback lokalny gdy nie (tryb demo).
        if cmd_builders:
            try:
                rebal_label = cmd_builders.mode_label(rebalance, max_drift)
            except Exception:  # noqa: BLE001
                rebal_label = rebalance
        elif mode == "BH":
            rebal_label = "Buy & Hold"
        elif mode == "DRIFT":
            rebal_label = f"DRIFT {max_drift or '20'}%"
        elif mode == "ANNUAL":
            rebal_label = "Rebalans roczny"
        else:
            rebal_label = rebalance
        return {
            "name": raw.get("LABEL") or raw.get("ID") or "(brak LABEL)",
            "include": included,
            "synth": bool(map_synth),
            "hist": bool(map_hist),
            "hist_warning": False,  # TODO: wymaga sprawdzenia pokrycia dat w pliku MAP_HIST
            "rebalans": rebal_label,
            "rebalans_mode": mode,
            "composition": f"MAP_SYNTH={map_synth or '—'}  ·  MAP_HIST={map_hist or '—'}",
            "etfs": "",
        }

    def _demo_task(self) -> dict:
        return {
            "settings": DEMO_SETTINGS,
            "portfolios": [self._adapt_portfolio_row(r) for r in DEMO_PORTFOLIOS],
            "tax_label": self._build_tax_label(DEMO_SETTINGS),
            "validation_error": None, "demo": True,
        }

    def build_command_preview(self, task_name: str, settings, dry_run: bool = False):
        """
        Zwraca (prefix, flags, values) do kolorowania konsoli — realna komenda
        orkiestratora potwierdzona w poprzedniej sesji (rzeczywiste odpalenie
        `analysis.py --help` i testowy `--dry-run` na repo):

            python app/bin/analysis.py --root <ROOT> --definition
            analysis_definitions/<task> [--dry-run]

        UWAGA: cmd_builders.ledger_cmd() buduje WEWNĘTRZNE wywołanie
        passive_ledger używane PRZEZ analysis.py w trakcie jego działania —
        to NIE jest komenda, którą ma odpalić GUI, dlatego tu jej nie używamy
        (wcześniejsza wersja błędnie po nią sięgała).
        """
        prefix = f"python {find_script('analysis.py')}"
        flags = ["--root", "--definition"]
        values = [str(ROOT), f"analysis_definitions/{task_name}"]
        if dry_run:
            flags.append("--dry-run")
            values.append("")
        return prefix, flags, values

    def validate(self, task_name: str) -> tuple[bool, str]:
        """Woła validate_task(ROOT, task_name) — potwierdzone: rzuca wyjątek
        przy błędzie, zwraca krotkę szczegółów przy sukcesie."""
        if not validate_task_mod:
            return True, "(tryb demo — walidacja niedostępna)"
        try:
            task_dir, included, checked_maps, start_iso, end_iso = validate_task_mod.validate_task(
                ROOT, task_name,
            )
            return True, f"OK — {included} portfeli, okres {start_iso} → {end_iso}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def list_runs(self, task_name: str) -> list[dict]:
        # [TODO Etap 1+] realne czytanie analysis_results/<task>/*/run.log —
        # zostawione demo na razie, bo wymaga znajomości dokładnej struktury
        # folderów wynikowych (poza tym co jest w changelogu/spec).
        return DEMO_RUNS

    def run_async(self, task_name: str, dry_run: bool, on_line, on_done, proc_holder: dict):
        """
        Uruchamia analysis.py w wątku BEZ auto-odświeżania HIST — używane przez
        przycisk Dry-run (ma być szybkim podglądem, nie operacją sieciową).
        Realny przycisk ▶ Uruchom używa run_pipeline() poniżej.
        proc_holder: dict wypełniany kluczem 'proc' po starcie subprocess —
        pozwala wywołującemu (RunTab) przerwać przez proc_holder['proc'].terminate().
        """
        script_path = find_script("analysis.py")
        argv = [
            sys.executable, str(script_path),
            "--root", str(ROOT),
            "--definition", f"analysis_definitions/{task_name}",
        ]
        if dry_run:
            argv.append("--dry-run")

        def worker():
            try:
                proc = subprocess.Popen(
                    argv, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                )
                proc_holder["proc"] = proc
                for line in proc.stdout:
                    on_line(line.rstrip("\n"))
                proc.wait()
                on_done(proc.returncode == 0)
            except Exception as exc:  # noqa: BLE001
                on_line(f"[BŁĄD] Nie udało się uruchomić: {exc}")
                on_done(False)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def _stream_subprocess(argv: list[str], on_line, proc_holder: dict) -> int:
        """Odpala subprocess, strumieniuje stdout do on_line, zwraca returncode.
        Aktualizuje proc_holder['proc'] żeby wołający mógł przerwać (terminate)."""
        proc = subprocess.Popen(
            argv, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        proc_holder["proc"] = proc
        for line in proc.stdout:
            on_line(line.rstrip("\n"))
        proc.wait()
        return proc.returncode

    def run_pipeline(self, task_name: str, on_line, on_done, proc_holder: dict):
        """
        Realne zachowanie przycisku ▶ Uruchom — GUI_PROJECT_SPEC.md §6:
        "GUI widzi HIST ⚠ → automatycznie pobiera brakujące → potem uruchamia
        analizę". Sekwencja (potwierdzona sygnatura refresh_quotes.py):
          1. refresh_quotes.py <task> --root <ROOT> --check  (offline, zwraca
             0=pokryte, 2=brakuje/za krótko)
          2. jeśli brakuje: refresh_quotes.py <task> --root <ROOT>  (realny
             fetch przez yfinance, wymaga internetu)
             — jeśli to też się nie powiedzie (brak internetu) → PRZERYWA
               i mówi o tym wprost w konsoli, nie próbuje zgadywać dalej
               (docelowo: pytanie "Uruchomić bez HIST?" — na razie wymaga
               ręcznej decyzji użytkownika, patrz TODO niżej)
          3. analysis.py --root <ROOT> --definition analysis_definitions/<task>
        Wszystko w JEDNYM wątku w tle, jeden ciągły strumień do konsoli.
        """
        refresh_script = find_script("refresh_quotes.py")
        analysis_script = find_script("analysis.py")

        def worker():
            try:
                on_line(f"$ refresh_quotes.py {task_name} --check  (sprawdzam pokrycie HIST, offline)")
                check_argv = [
                    sys.executable, str(refresh_script), task_name,
                    "--root", str(ROOT), "--check",
                ]
                check_rc = self._stream_subprocess(check_argv, on_line, proc_holder)

                if check_rc != 0:
                    on_line(f"[INFO] Brakuje danych HIST — pobieram (refresh_quotes.py {task_name})...")
                    refresh_argv = [
                        sys.executable, str(refresh_script), task_name, "--root", str(ROOT),
                    ]
                    refresh_rc = self._stream_subprocess(refresh_argv, on_line, proc_holder)
                    if refresh_rc != 0:
                        # TODO: docelowo modal "Uruchomić bez HIST?" zamiast
                        # twardego przerwania — wymaga wywołania z wątku tła
                        # do głównego wątku Tkinter (np. queue + after()).
                        on_line(
                            "[BŁĄD] Odświeżenie HIST nie powiodło się (brak internetu albo "
                            "błąd źródła danych). Przerywam — sprawdź połączenie i kliknij "
                            "▶ Uruchom ponownie, albo użyj Dry-run żeby zobaczyć resztę planu."
                        )
                        on_done(False)
                        return
                    on_line("[OK] Dane HIST odświeżone.")
                else:
                    on_line("[OK] Biblioteka HIST już pokrywa wymagane tickery.")

                argv = [
                    sys.executable, str(analysis_script),
                    "--root", str(ROOT),
                    "--definition", f"analysis_definitions/{task_name}",
                ]
                on_line("$ " + " ".join(argv))
                rc = self._stream_subprocess(argv, on_line, proc_holder)
                on_done(rc == 0)
            except Exception as exc:  # noqa: BLE001
                on_line(f"[BŁĄD] {exc}")
                on_done(False)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread

    def refresh_quotes_async(self, task_name: str, on_line, on_done, proc_holder: dict):
        """Samodzielne odświeżenie HIST — przycisk 'Refresh HIST' w toolbarze."""
        refresh_script = find_script("refresh_quotes.py")
        argv = [sys.executable, str(refresh_script), task_name, "--root", str(ROOT)]

        def worker():
            try:
                on_line("$ " + " ".join(argv))
                rc = self._stream_subprocess(argv, on_line, proc_holder)
                on_done(rc == 0)
            except Exception as exc:  # noqa: BLE001
                on_line(f"[BŁĄD] {exc}")
                on_done(False)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()



class TaskRow(ctk.CTkFrame):
    """Pojedynczy wiersz taska w sidebarze: kropka statusu + nazwa."""

    DOT_COLOR = {"ok": COL_OK, "warn": COL_WARN, "fail": COL_FAIL}

    def __init__(self, master, task: dict, on_click, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._task = task
        self._on_click = on_click

        self.grid_columnconfigure(1, weight=1)

        dot = ctk.CTkLabel(
            self, text="●", text_color=self.DOT_COLOR.get(task["status"], COL_TEXT_DIM),
            font=F_SIDEBAR_TASK, width=TASK_DOT_WIDTH,
        )
        dot.grid(row=0, column=0, padx=(PAD, PAD_TIGHT), pady=1, sticky="w")

        name = ctk.CTkLabel(
            self, text=task["name"], font=F_SIDEBAR_TASK, text_color=COL_TEXT, anchor="w",
        )
        name.grid(row=0, column=1, padx=(0, PAD), pady=1, sticky="ew")

        for widget in (self, dot, name):
            widget.bind("<Button-1>", self._handle_click)
        self.configure(cursor="hand2")

    def _handle_click(self, _event=None):
        self._on_click(self._task)

    def set_active(self, active: bool):
        self.configure(fg_color=COL_ACCENT if active else "transparent")


class Sidebar(ctk.CTkFrame):
    """Lista tasków + akcje globalne. Wspólny dla wszystkich zakładek."""

    def __init__(self, master, on_task_selected, tasks: list[dict], **kwargs):
        super().__init__(master, fg_color=COL_SIDEBAR, corner_radius=0, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._on_task_selected = on_task_selected
        self._rows: list[TaskRow] = []
        self._active_row: TaskRow | None = None

        title = ctk.CTkLabel(
            self, text="TASKI", font=F_SIDEBAR_TITLE, text_color=COL_TEXT_DIM, anchor="w",
        )
        title.grid(row=0, column=0, padx=PAD + PAD_TIGHT, pady=(PAD + PAD_TIGHT, PAD_TIGHT), sticky="ew")

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._list_frame.grid(row=1, column=0, rowspan=2, padx=PAD, pady=(0, PAD), sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

        self.set_tasks(tasks)

        btn_new = ctk.CTkButton(
            self, text="+ Nowy task", font=F_HINT8, height=BTN_HEIGHT, command=self._stub_new_task,
        )
        btn_new.grid(row=3, column=0, padx=PAD, pady=(PAD_TIGHT, PAD_TIGHT), sticky="ew")

        btn_refresh = ctk.CTkButton(
            self, text="⟳ Odśwież dane CPI/FX", font=F_HINT8, height=BTN_HEIGHT,
            fg_color="transparent", border_width=1, border_color=COL_BORDER,
            command=self._stub_refresh_data,
        )
        btn_refresh.grid(row=4, column=0, padx=PAD, pady=(0, PAD), sticky="ew")

    def set_tasks(self, tasks: list[dict]):
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        for i, task in enumerate(tasks):
            row = TaskRow(self._list_frame, task, self._handle_select)
            row.grid(row=i, column=0, sticky="ew", pady=1)
            self._rows.append(row)
        if self._rows:
            self._handle_select(tasks[0])

    def _handle_select(self, task: dict):
        for row in self._rows:
            row.set_active(row._task is task or row._task["name"] == task["name"])
        self._on_task_selected(task)

    # -- akcje zaślepkowe (logika w kolejnym etapie) ------------------------
    def _stub_new_task(self):
        print("[TODO] Dialog 'Nowy task' (GUI_PROJECT_SPEC.md §12)")

    def _stub_refresh_data(self):
        print("[TODO] refresh_data.cmd w wątku")


class PlaceholderTab(ctk.CTkFrame):
    """Zawartość zakładki w Etapie 0 — sama struktura, bez logiki."""

    def __init__(self, master, tab_name: str, etap_label: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        box = ctk.CTkFrame(self, fg_color=COL_PANEL, border_width=1, border_color=COL_BORDER)
        box.grid(row=0, column=0, padx=PAD * 2, pady=PAD * 2, sticky="nsew")
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.grid(row=0, column=0)

        ctk.CTkLabel(inner, text=tab_name.upper(), font=F_SECTION, text_color=COL_TEXT_DIM).pack(pady=(0, PAD_TIGHT))
        ctk.CTkLabel(
            inner, text=f"Zawartość zakładki — {etap_label}", font=F_LABEL, text_color=COL_TEXT,
        ).pack()


class ParamsGrid(ctk.CTkFrame):
    """Siatka klucz-wartość 'Parametry taska' — GUI_PROJECT_SPEC.md §6. Tylko odczyt
    (edycja jest w zakładce Konfiguracja, Etap 2).

    UWAGA: pierwsza wersja miała pole "Rebalans" jako parametr taska — to było
    błędne założenie. W realnym repo REBALANCE/MAX_DRIFT są kolumnami PER
    PORTFEL w portfolios.csv (potwierdzone w analysis.py), nie kluczem w
    settings.csv. Rebalans pokazywany jest teraz przy każdym portfelu
    (PortfolioRow), nie tutaj. To miejsce zajął "Tryb" (analysis_mode).
    """

    ROWS = [
        ("Okres", "period"),
        ("Saldo startowe", "saldo"),
        ("Wyceny", "freq"),
        ("Waluty wykresów", "plot_currencies"),
        ("Podatek", "tax_label"),
        ("Tryb", "analysis_mode"),
    ]

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        self._value_labels: dict[str, ctk.CTkLabel] = {}
        for i, (label_text, key) in enumerate(self.ROWS):
            lbl = ctk.CTkLabel(self, text=label_text, font=F_HINT8, text_color=COL_TEXT_DIM, anchor="w")
            lbl.grid(row=i, column=0, padx=(0, PAD_LOOSE), pady=PAD_TIGHT, sticky="w")
            val = ctk.CTkLabel(self, text="—", font=F_LABEL, text_color=COL_TEXT, anchor="w")
            val.grid(row=i, column=1, pady=PAD_TIGHT, sticky="w")
            self._value_labels[key] = val

        # Podpowiedź łącząca Wyceny z czułością DRIFT — bez tego te dwie
        # rzeczy żyją w różnych miejscach ekranu (Parametry vs Portfele) i
        # związek między nimi jest niewidoczny. Sprawdzone w ledger_engine.py:
        # is_drift_breached() jest liczone WYŁĄCZNIE na datach zresamplowanych
        # do Wycen — przy monthly portfel może przejechać próg MAX_DRIFT
        # nawet o miesiąc zanim ledger to zauważy i skoryguje.
        self._freq_hint = ctk.CTkLabel(
            self, text="", font=F_HINT, text_color=COL_FLAG, anchor="w", justify="left",
            wraplength=_dim(520),
        )
        self._freq_hint.grid(
            row=len(self.ROWS), column=0, columnspan=2, sticky="w", pady=(PAD_TIGHT, 0),
        )

    def update_values(self, settings: dict, tax_label: str):
        # Klucze potwierdzone wprost w settings.csv użytkownika: start, end,
        # saldo (NIE "capital"), freq (NIE "valuation"), plot_currencies
        # (NIE "currencies"), analysis_mode. "capital"/"valuation"/"currencies"
        # z pierwszej wersji nie istniały w realnym pliku — zawsze dawały "—".
        freq = settings.get("freq", "—")
        mapping = {
            "period": f"{settings.get('start', '—')} → {settings.get('end', '—')}",
            "saldo": settings.get("saldo", "—"),
            "freq": freq,
            "plot_currencies": settings.get("plot_currencies", "—"),
            "tax_label": tax_label or "—",
            "analysis_mode": settings.get("analysis_mode", "—"),
        }
        for key, val_label in self._value_labels.items():
            val_label.configure(text=str(mapping.get(key, "—")))

        self._freq_hint.configure(
            text=(
                f"ⓘ Wyceny ({freq}) ustalają jak często sprawdzany jest próg DRIFT "
                f"poniżej — przy rzadszych Wycenach portfel może przejechać próg "
                f"zanim zostanie skorygowany"
            )
        )


class PortfolioRow(ctk.CTkFrame):
    """Pojedynczy portfel w analizie — GUI_PROJECT_SPEC.md §6."""

    def __init__(self, master, portfolio: dict, **kwargs):
        super().__init__(master, fg_color=COL_PANEL, border_width=1, border_color=COL_BORDER, **kwargs)
        self.grid_columnconfigure(1, weight=1)

        included = portfolio.get("include", True)
        text_color = COL_TEXT if included else COL_TEXT_DIM

        self.include_var = tk.BooleanVar(value=included)
        cb_include = ctk.CTkCheckBox(
            self, text="", variable=self.include_var, width=_dim(14), height=_dim(14),
            command=self._on_toggle_include,
        )
        cb_include.grid(row=0, column=0, rowspan=2, padx=PAD, pady=PAD, sticky="n")

        self._name_lbl = ctk.CTkLabel(
            self, text=portfolio["name"], font=F_LABEL_B, text_color=text_color, anchor="w",
        )
        self._name_lbl.grid(row=0, column=1, padx=(0, PAD), pady=(PAD_TIGHT, 0), sticky="w")

        badges = ctk.CTkFrame(self, fg_color="transparent")
        badges.grid(row=0, column=2, padx=PAD, pady=(PAD_TIGHT, 0), sticky="e")

        rebal_text = portfolio.get("rebalans", "—")
        rebal_mode = portfolio.get("rebalans_mode", "UNKNOWN")
        rebal_color = {
            "BH": COL_TEXT_DIM, "DRIFT": COL_FLAG, "ANNUAL": COL_ACCENT,
        }.get(rebal_mode, COL_FAIL)  # UNKNOWN -> czerwone, sygnał że REBALANCE w CSV jest nierozpoznane
        ctk.CTkLabel(
            badges, text=rebal_text, font=F_HINT8, text_color=rebal_color,
            fg_color=COL_BG, corner_radius=4, width=_dim(72),
        ).pack(side="left", padx=(0, PAD_LOOSE))

        self.synth_var = tk.BooleanVar(value=bool(portfolio.get("synth")))
        ctk.CTkCheckBox(
            badges, text="SYNTH", variable=self.synth_var, font=F_HINT8,
            width=_dim(14), height=_dim(14),
        ).pack(side="left", padx=(0, PAD))

        self.hist_var = tk.BooleanVar(value=bool(portfolio.get("hist")))
        ctk.CTkCheckBox(
            badges, text="HIST", variable=self.hist_var, font=F_HINT8,
            width=_dim(14), height=_dim(14),
        ).pack(side="left")

        detail_text = portfolio.get("composition", "—")
        ctk.CTkLabel(
            self, text=detail_text, font=F_HINT, text_color=COL_TEXT_DIM, anchor="w",
        ).grid(row=1, column=1, columnspan=2, padx=(0, PAD), pady=(0, PAD_TIGHT), sticky="ew")

        if portfolio.get("hist_warning"):
            warn = ctk.CTkFrame(self, fg_color="transparent")
            warn.grid(row=2, column=0, columnspan=3, padx=PAD, pady=(0, PAD_TIGHT), sticky="ew")
            ctk.CTkLabel(
                warn, text="⚠ brak danych HIST dla części okresu", font=F_HINT, text_color=COL_WARN,
            ).pack(side="left")
            ctk.CTkButton(
                warn, text="Pobierz brakujące", font=F_HINT, height=_dim(14),
                command=self._stub_fetch_hist,
            ).pack(side="right")

    def _on_toggle_include(self):
        included = self.include_var.get()
        self._name_lbl.configure(text_color=COL_TEXT if included else COL_TEXT_DIM)
        print(f"[TODO Etap 2] zapis include={included} do portfolios.csv (na razie tylko w pamięci)")

    @staticmethod
    def _stub_fetch_hist():
        print("[TODO] Pobierz brakujące dane HIST (refresh_quotes.py w wątku)")


class RunHistoryRow(ctk.CTkFrame):
    """Jeden wiersz w 'Ostatnie przebiegi' — GUI_PROJECT_SPEC.md §6."""

    STATUS_COLOR = {"ok": COL_OK, "fail": COL_FAIL}

    def __init__(self, master, run: dict, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=run["status"].upper(), font=F_HINT8,
            text_color=self.STATUS_COLOR.get(run["status"], COL_TEXT_DIM), width=_dim(36), anchor="w",
        ).grid(row=0, column=0, padx=(0, PAD), sticky="w")

        summary = (
            f"{run['timestamp']}  ·  {run['duration']}  ·  "
            f"{run['tax_label']}  ·  {run['n_portfolios']} portfeli"
        )
        ctk.CTkLabel(self, text=summary, font=F_HINT8, text_color=COL_TEXT, anchor="w").grid(
            row=0, column=1, sticky="ew",
        )

        ctk.CTkButton(
            self, text="📂 otwórz", font=F_HINT, width=_dim(50), height=_dim(14),
            fg_color="transparent", text_color=COL_TEXT_DIM, border_width=1, border_color=COL_BORDER,
            command=lambda: self._open_folder(run["folder"]),
        ).grid(row=0, column=2, padx=(PAD, 0))

    @staticmethod
    def _open_folder(folder: str):
        try:
            import os
            os.startfile(folder)  # type: ignore[attr-defined]  # tylko Windows
        except AttributeError:
            print(f"[INFO] os.startfile niedostępne na tym OS — folder: {folder}")
        except Exception as exc:  # noqa: BLE001
            print(f"[BŁĄD] Nie udało się otworzyć folderu: {exc}")


class RunTab(ctk.CTkFrame):
    """
    Zakładka 'Uruchom' — GUI_PROJECT_SPEC.md §6. Etap 1.
    Górny panel (parametry + portfele + toolbar akcji) i dolny panel
    (ostatnie przebiegi) rozdzielone przeciąganym sashem — zgodnie ze
    standardem projektowym (PanedWindow wszędzie tam gdzie sensowny podział).
    """

    def __init__(self, master, gui: "PasywnyPortfelGUI", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.gui = gui
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._paned = tk.PanedWindow(
            self, orient="vertical", sashwidth=SASH_WIDTH, sashrelief="flat",
            sashpad=0, bd=0, bg=COL_BORDER, opaqueresize=True,
        )
        self._paned.grid(row=0, column=0, sticky="nsew")

        # -- górny panel: scroll (parametry + portfele) + toolbar akcji (pinned) --
        top = ctk.CTkFrame(self._paned, fg_color="transparent")
        top.grid_columnconfigure(0, weight=1)
        top.grid_rowconfigure(0, weight=1)
        self._paned.add(top, minsize=_dim(180), height=_dim(420))

        self._scroll = ctk.CTkScrollableFrame(top, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=PAD, pady=PAD)
        self._scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._scroll, text="PARAMETRY TASKA", font=F_SECTION, text_color=COL_TEXT_DIM, anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, PAD_TIGHT))
        self._params = ParamsGrid(self._scroll)
        self._params.grid(row=1, column=0, sticky="ew", pady=(0, PAD_LOOSE))

        ctk.CTkLabel(
            self._scroll, text="PORTFELE W ANALIZIE", font=F_SECTION, text_color=COL_TEXT_DIM, anchor="w",
        ).grid(row=2, column=0, sticky="w", pady=(0, PAD_TIGHT))
        self._portfolios_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._portfolios_frame.grid(row=3, column=0, sticky="ew")
        self._portfolios_frame.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(top, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=PAD, pady=(0, PAD))
        for i in range(4):
            toolbar.grid_columnconfigure(i, weight=1)

        self._run_btn = ctk.CTkButton(
            toolbar, text="▶ Uruchom", font=F_LABEL_B, height=BTN_HEIGHT,
            fg_color=COL_OK, hover_color="#4CB592", text_color="#0a0a0a",
            command=self._on_run_clicked,
        )
        self._run_btn.grid(row=0, column=0, padx=(0, PAD_TIGHT), sticky="ew")

        self._dryrun_btn = ctk.CTkButton(
            toolbar, text="Dry-run", font=F_LABEL, height=BTN_HEIGHT,
            fg_color="transparent", border_width=1, border_color=COL_BORDER,
            command=lambda: self._on_run_clicked(dry_run=True),
        )
        self._dryrun_btn.grid(row=0, column=1, padx=PAD_TIGHT, sticky="ew")

        self._refresh_btn = ctk.CTkButton(
            toolbar, text="Refresh HIST", font=F_LABEL, height=BTN_HEIGHT,
            fg_color="transparent", border_width=1, border_color=COL_BORDER,
            command=self._stub_refresh_hist,
        )
        self._refresh_btn.grid(row=0, column=2, padx=PAD_TIGHT, sticky="ew")

        self._validate_btn = ctk.CTkButton(
            toolbar, text="Waliduj", font=F_LABEL, height=BTN_HEIGHT,
            fg_color="transparent", border_width=1, border_color=COL_BORDER,
            command=self._on_validate_clicked,
        )
        self._validate_btn.grid(row=0, column=3, padx=(PAD_TIGHT, 0), sticky="ew")

        self._action_buttons = [self._dryrun_btn, self._refresh_btn, self._validate_btn]

        # -- dolny panel: ostatnie przebiegi --------------------------------------
        bottom = ctk.CTkFrame(self._paned, fg_color="transparent")
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(1, weight=1)
        self._paned.add(bottom, minsize=_dim(80), height=_dim(160))

        ctk.CTkLabel(
            bottom, text="OSTATNIE PRZEBIEGI", font=F_SECTION, text_color=COL_TEXT_DIM, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=PAD, pady=(PAD, PAD_TIGHT))
        self._runs_scroll = ctk.CTkScrollableFrame(bottom, fg_color="transparent")
        self._runs_scroll.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(0, PAD))
        self._runs_scroll.grid_columnconfigure(0, weight=1)

        self._current_task_name: str | None = None
        self._is_running = False
        self._proc_holder: dict = {}
        self._portfolio_rows: list[PortfolioRow] = []

    # -- API wywoływane z PasywnyPortfelGUI po wyborze taska w sidebarze --------
    def load_task(self, task_name: str, data: dict):
        self._current_task_name = task_name
        self._params.update_values(data.get("settings") or {}, data.get("tax_label", "—"))
        self._set_portfolios(data.get("portfolios") or [])
        self._set_runs(self.gui.engine.list_runs(task_name))
        validation_error = data.get("validation_error")
        if validation_error:
            self.gui.console.append_stdout_line(f"[WARN] walidacja: {validation_error}")

    def _set_portfolios(self, portfolios: list[dict]):
        for row in self._portfolio_rows:
            row.destroy()
        self._portfolio_rows.clear()
        for i, p in enumerate(portfolios):
            row = PortfolioRow(self._portfolios_frame, p)
            row.grid(row=i, column=0, sticky="ew", pady=(0, PAD_TIGHT))
            self._portfolio_rows.append(row)

    def _set_runs(self, runs: list[dict]):
        for child in self._runs_scroll.winfo_children():
            child.destroy()
        for i, run in enumerate(runs):
            row = RunHistoryRow(self._runs_scroll, run)
            row.grid(row=i, column=0, sticky="ew", pady=PAD_TIGHT)

    # -- akcje --------------------------------------------------------------
    def _on_validate_clicked(self):
        if not self._current_task_name:
            return
        self.gui.console.append_stdout_line(f"$ waliduj {self._current_task_name}")
        ok, message = self.gui.engine.validate(self._current_task_name)
        tag = "OK" if ok else "BŁĄD"
        self.gui.console.append_stdout_line(f"[{tag}] {message}")

    def _stub_refresh_hist(self):
        if not self._current_task_name:
            return
        if self._is_running:
            return
        self._is_running = True
        self._proc_holder = {}
        for btn in [self._run_btn, self._dryrun_btn, self._refresh_btn, self._validate_btn]:
            btn.configure(state="disabled")
        if not self.gui.console._expanded:
            self.gui.console._toggle()

        def on_line(line: str):
            self.after(0, self.gui.console.append_stdout_line, line)

        def on_done(success: bool):
            self.after(0, self._on_refresh_finished, success)

        self.gui.engine.refresh_quotes_async(
            self._current_task_name, on_line, on_done, self._proc_holder,
        )

    def _on_refresh_finished(self, success: bool):
        self._is_running = False
        for btn in [self._run_btn, self._dryrun_btn, self._refresh_btn, self._validate_btn]:
            btn.configure(state="normal")
        tag = "OK" if success else "FAIL"
        self.gui.console.append_stdout_line(f"$ refresh HIST zakończony — {tag}")

    def _on_run_clicked(self, dry_run: bool = False):
        if self._is_running:
            self._abort_run()
            return
        if not self._current_task_name:
            return

        self._is_running = True
        self._proc_holder = {}
        self._run_btn.configure(text="■ Przerwij", fg_color=COL_FAIL, hover_color="#C94840")
        for btn in self._action_buttons:
            btn.configure(state="disabled")
        if not self.gui.console._expanded:
            self.gui.console._toggle()

        prefix, flags, values = self.gui.engine.build_command_preview(
            self._current_task_name, None, dry_run=dry_run,
        )
        self.gui.console.set_command_preview(prefix, flags, values)

        def on_line(line: str):
            self.after(0, self.gui.console.append_stdout_line, line)

        def on_done(success: bool):
            self.after(0, self._on_run_finished, success)

        if dry_run:
            # Dry-run: szybki podgląd, BEZ auto-odświeżania HIST (operacja
            # sieciowa nie pasuje do "szybkiego podglądu komendy").
            self.gui.engine.run_async(
                self._current_task_name, dry_run, on_line, on_done, self._proc_holder,
            )
        else:
            # ▶ Uruchom: pełny pipeline — sprawdź HIST, dociągnij brakujące,
            # potem dopiero analiza. Zgodnie z GUI_PROJECT_SPEC.md §6.
            self.gui.engine.run_pipeline(
                self._current_task_name, on_line, on_done, self._proc_holder,
            )

    def _on_run_finished(self, success: bool):
        self._is_running = False
        self._run_btn.configure(text="▶ Uruchom", fg_color=COL_OK, hover_color="#4CB592")
        for btn in self._action_buttons:
            btn.configure(state="normal")
        tag = "OK" if success else "FAIL"
        self.gui.console.append_stdout_line(f"$ zakończono — {tag}")

    def _abort_run(self):
        proc = self._proc_holder.get("proc")
        if proc is not None:
            proc.terminate()
            self.gui.console.append_stdout_line("$ przerwano przez użytkownika")
        else:
            self.gui.console.append_stdout_line("$ (proces jeszcze się nie uruchomił — czekaj)")



class ConsolePanel(ctk.CTkFrame):
    """
    Stały panel 'Podgląd komendy' — GUI_PROJECT_SPEC.md §4.
    Domyślnie 3 linie, rozwijalny do pełnej wysokości, mono, kolorowanie
    flag (pomarańczowe) / wartości (zielone), przycisk kopiowania.
    """

    COLLAPSED_LINES = 3
    EXPANDED_LINES = 14

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COL_PANEL, corner_radius=0, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._expanded = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD_TIGHT, 0))
        header.grid_columnconfigure(1, weight=1)

        self._toggle_btn = ctk.CTkButton(
            header, text="▼ rozwiń", font=F_HINT8, width=CONSOLE_BTN_WIDTH, height=CONSOLE_BTN_HEIGHT,
            fg_color="transparent", text_color=COL_TEXT_DIM, hover_color=COL_BORDER,
            command=self._toggle,
        )
        self._toggle_btn.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="PODGLĄD KOMENDY", font=F_SIDEBAR_TITLE, text_color=COL_TEXT_DIM,
        ).grid(row=0, column=1, sticky="w", padx=(PAD_LOOSE, 0))

        copy_btn = ctk.CTkButton(
            header, text="📋 kopiuj", font=F_HINT8, width=CONSOLE_BTN_WIDTH, height=CONSOLE_BTN_HEIGHT,
            fg_color="transparent", text_color=COL_TEXT_DIM, border_width=1, border_color=COL_BORDER,
            command=self._copy_to_clipboard,
        )
        copy_btn.grid(row=0, column=2, sticky="e")

        self._textbox = ctk.CTkTextbox(
            self, font=F_CONSOLE, fg_color=COL_CONSOLE_BG, text_color=COL_TEXT,
            wrap="none", height=self._lines_to_px(self.COLLAPSED_LINES), activate_scrollbars=True,
        )
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(PAD_TIGHT, PAD))

        # Celowo BEZ state="disabled": w Tkinter to blokuje też zaznaczanie
        # myszką, nie tylko edycję (zgłoszone jako bug). Zamiast tego textbox
        # zostaje "normal" na stałe, a blokujemy tylko wpisywanie z klawiatury
        # — zaznaczanie myszką i Ctrl+C/Ctrl+A działają natywnie.
        self._textbox._textbox.bind("<Key>", self._block_typing)

        # tagi kolorowania zgodne ze spec: flagi pomarańczowe, wartości zielone
        self._textbox._textbox.tag_config("flag", foreground=COL_FLAG)
        self._textbox._textbox.tag_config("value", foreground=COL_VALUE)
        self._textbox._textbox.tag_config("dim", foreground=COL_TEXT_DIM)

        self.set_placeholder()

    @staticmethod
    def _block_typing(event):
        """Przepuszcza nawigację i Ctrl+C/Ctrl+A, blokuje wpisywanie/usuwanie."""
        ctrl_held = bool(event.state & 0x4)
        if ctrl_held and event.keysym.lower() in ("c", "a"):
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Tab"):
            return None
        return "break"

    @staticmethod
    def _lines_to_px(lines: int) -> int:
        return CONSOLE_LINE_HEIGHT * lines + CONSOLE_LINE_OFFSET

    def _toggle(self):
        self._expanded = not self._expanded
        lines = self.EXPANDED_LINES if self._expanded else self.COLLAPSED_LINES
        self._textbox.configure(height=self._lines_to_px(lines))
        self._toggle_btn.configure(text="▲ zwiń" if self._expanded else "▼ rozwiń")

    def _copy_to_clipboard(self):
        content = self._textbox.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)

    def set_placeholder(self):
        self._textbox.delete("1.0", "end")
        self._textbox.insert("end", "$ ", "dim")
        self._textbox.insert("end", "(podgląd komendy pojawi się tutaj po wybraniu taska — Etap 1)", "dim")

    def set_command_preview(self, prefix: str, flags: list[str], values: list[str]):
        """Buduje kolorowaną linię komendy: flagi pomarańczowe, wartości zielone."""
        self._textbox.delete("1.0", "end")
        self._textbox.insert("end", prefix + " ")
        for flag, value in zip(flags, values):
            self._textbox.insert("end", flag + " ", "flag")
            self._textbox.insert("end", value + " ", "value")
        self._textbox.insert("end", "\n")

    def append_stdout_line(self, line: str):
        self._textbox.insert("end", line + "\n")
        self._textbox.see("end")


class StatusBar(ctk.CTkFrame):
    """Jedna linia na dole: health check (lewa) / wersja (prawa) — §5."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COL_SIDEBAR, corner_radius=0, height=STATUSBAR_HEIGHT, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._left = ctk.CTkLabel(
            self, text=DEMO_STATUSBAR_LEFT, font=F_STATUSBAR, text_color=COL_TEXT_DIM, anchor="w",
        )
        self._left.grid(row=0, column=0, sticky="w", padx=PAD_LOOSE)

        self._right = ctk.CTkLabel(
            self, text=DEMO_STATUSBAR_RIGHT, font=F_STATUSBAR, text_color=COL_TEXT_DIM, anchor="e",
        )
        self._right.grid(row=0, column=1, sticky="e", padx=PAD_LOOSE)

    def set_left(self, text: str):
        self._left.configure(text=text)

    def set_right(self, text: str):
        self._right.configure(text=text)


class PasywnyPortfelGUI(ctk.CTk):
    TAB_NAMES = ["Uruchom", "Konfiguracja", "Wyniki", "Portfele"]
    TAB_ETAP = {
        "Konfiguracja": "TODO — Etap 2",
        "Wyniki": "TODO — Etap 3",
        "Portfele": "TODO — Etap 4",
    }

    def __init__(self):
        super().__init__()
        self.title("pasywnyportfel — GUI")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(fg_color=COL_BG)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self._current_task: dict | None = None
        self.run_tab: "RunTab | None" = None

        # -- konsola i statusbar tworzone NAJPIERW (jako obiekty — grid()
        # wywołany niżej we właściwej kolejności), bo Engine loguje do
        # konsoli już podczas wczytywania listy tasków -------------------
        self.console = ConsolePanel(self)
        self.statusbar = StatusBar(self)

        self.engine = Engine(log_fn=self._log_to_console)

        # -- row 0: sidebar + tabview (rozsuwane via PanedWindow) -----------
        self.paned = tk.PanedWindow(
            self, orient="horizontal", sashwidth=SASH_WIDTH, sashrelief="flat",
            sashpad=0, bd=0, bg=COL_BORDER, opaqueresize=True,
        )
        self.paned.grid(row=0, column=0, sticky="nsew")

        tasks = self.engine.list_tasks()
        self.sidebar = Sidebar(self.paned, on_task_selected=self._on_task_selected, tasks=tasks)
        self.paned.add(self.sidebar, width=SIDEBAR_WIDTH, minsize=SIDEBAR_MIN_WIDTH)

        tab_holder = ctk.CTkFrame(self.paned, fg_color=COL_BG, corner_radius=0)
        tab_holder.grid_columnconfigure(0, weight=1)
        tab_holder.grid_rowconfigure(0, weight=1)
        self.paned.add(tab_holder, minsize=400)

        self.tabview = ctk.CTkTabview(
            tab_holder, fg_color=COL_BG, segmented_button_selected_color=COL_ACCENT,
            text_color=COL_TEXT,
        )
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=(PAD, 0))
        self.tabview._segmented_button.configure(font=F_LABEL)

        for name in self.TAB_NAMES:
            tab = self.tabview.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            if name == "Uruchom":
                self.run_tab = RunTab(tab, gui=self)
                content = self.run_tab
            else:
                content = PlaceholderTab(tab, name, self.TAB_ETAP[name])
            content.grid(row=0, column=0, sticky="nsew")

        # Sufit szerokości sidebaru — PanedWindow nie ma natywnego maxsize,
        # więc pilnujemy górnej granicy ręcznie przy każdym przeciągnięciu.
        self.paned.bind("<B1-Motion>", self._clamp_sidebar_width)

        # -- row 1: console panel ---------------------------------------------
        self.console.grid(row=1, column=0, sticky="ew")

        # -- row 2: statusbar ---------------------------------------------------
        self.statusbar.grid(row=2, column=0, sticky="ew")

        # Sidebar już wybrał pierwszy task w trakcie swojej konstrukcji
        # (zanim run_tab istniał) — domykamy synchronizację teraz.
        if self._current_task and self.run_tab:
            self._load_task_into_ui(self._current_task["name"])

        if not ENGINE_AVAILABLE:
            self._log_to_console(
                "[INFO] Moduły silnika (task_config/common/cmd_builders/validate_task) "
                "nie są zaimportowane — GUI działa w trybie demo. Uruchom z katalogu "
                "głównego repo (D:\\analises\\pasywnyportfel) żeby spięło się z prawdziwymi danymi."
            )

        analysis_path = find_script("analysis.py")
        exists = "✓ istnieje" if analysis_path.exists() else "✗ NIE ZNALEZIONO"
        self._log_to_console(f"[INFO] analysis.py: {analysis_path}  ({exists})")

    def _log_to_console(self, line: str):
        self.console.append_stdout_line(line)

    def _clamp_sidebar_width(self, _event=None):
        try:
            x = self.paned.sash_coord(0)[0]
        except (tk.TclError, IndexError):
            return
        if x > SIDEBAR_MAX_WIDTH:
            self.paned.sash_place(0, SIDEBAR_MAX_WIDTH, 0)

    def _on_task_selected(self, task: dict):
        self._current_task = task
        if self.run_tab is not None:
            self._load_task_into_ui(task["name"])
        # gdy run_tab jeszcze nie istnieje (pierwsze auto-zaznaczenie podczas
        # konstrukcji Sidebar) — domknięte później w __init__

    def _load_task_into_ui(self, task_name: str):
        data = self.engine.load_task(task_name)
        self.run_tab.load_task(task_name, data)
        prefix, flags, values = self.engine.build_command_preview(task_name, data.get("settings"))
        self.console.set_command_preview(prefix, flags, values)


def main():
    app = PasywnyPortfelGUI()
    app.mainloop()


if __name__ == "__main__":
    main()

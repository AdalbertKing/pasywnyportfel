"""
gui.py — pasywnyportfel GUI (CustomTkinter)
[USER] Desktop GUI dla pakietu pasywnyportfel.

ETAP 0 — SZKIELET
==================
Ten plik implementuje wyłącznie szkielet okna zgodnie z GUI_PROJECT_SPEC.md:
  - okno główne
  - sidebar (lista tasków, placeholder)
  - 4 zakładki: Uruchom / Konfiguracja / Wyniki / Portfele (zawartość TODO)
  - stały panel konsoli (podgląd komendy / stdout) na dole, zwijany/rozwijany
  - statusbar (health check + wersja)

Logika (import task_config / common / cmd_builders / validate_task,
wczytywanie settings.csv / portfolios.csv, uruchamianie analysis.py
w wątku, itd.) zostanie dopięta w kolejnych etapach (1-4) zgodnie
z planem w GUI_PROJECT_SPEC.md §17.

Uruchamianie: dwuklik na gui.cmd w katalogu głównym repo.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Lokalizacja katalogu głównego repo (app/bin/gui.py -> root = parent.parent)
# Gdy moduły silnika (task_config, common, cmd_builders, validate_task)
# istnieją w ROOT, zostaną zaimportowane w Etapie 1+. W Etapie 0 GUI działa
# w trybie szkieletowym (dane przykładowe) niezależnie od ich obecności.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Stałe wizualne — zgodnie z GUI_PROJECT_SPEC.md §3 (Standard wizualny)
# ---------------------------------------------------------------------------
SIDEBAR_WIDTH = 160  # górna granica zakresu 140-160px ze specu — więcej miejsca dla większej czcionki
PAD = 4

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

# Uwaga: w Tkinter dodatni rozmiar = punkty, UJEMNY = piksele (1:1 z ekranem,
# BEZ skalowania DPI). Wartości bazowe poniżej to "logiczne" rozmiary ze
# specu (§3); FONT_SCALE mnoży je do rozmiaru faktycznie czytelnego na
# fizycznym monitorze. Pierwsza wersja (scale=1.0 => 7-9px) okazała się
# nieczytelna na 24" FHD bez okularów — stąd 1.45. Jedna liczba do zmiany,
# jeśli trzeba skorygować ponownie.
FONT_SCALE = 1.45


def _px(base: float) -> int:
    return -round(base * FONT_SCALE)


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
# Dane przykładowe — wyłącznie do czasu spięcia z task_config.list_tasks()
# w Etapie 1. Zachowują kształt zgodny z prawdziwym API (lista taski o polach
# name/status), żeby podmiana w kolejnym etapie była mechaniczna.
# ---------------------------------------------------------------------------
DEMO_TASKS = [
    {"name": "demo_60_40", "status": "ok"},
    {"name": "demo_permanent_portfolio", "status": "ok"},
    {"name": "demo_zlote_motyle", "status": "warn"},
]

DEMO_STATUSBAR_LEFT = "FAIL:0  WARN:0  OK:42"
DEMO_STATUSBAR_RIGHT = "Python 3.13 | 402 testów | gui branch"


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
            font=F_SIDEBAR_TASK, width=16,
        )
        dot.grid(row=0, column=0, padx=(4, 2), pady=1, sticky="w")

        name = ctk.CTkLabel(
            self, text=task["name"], font=F_SIDEBAR_TASK, text_color=COL_TEXT, anchor="w",
        )
        name.grid(row=0, column=1, padx=(0, 4), pady=1, sticky="ew")

        for widget in (self, dot, name):
            widget.bind("<Button-1>", self._handle_click)
        self.configure(cursor="hand2")

    def _handle_click(self, _event=None):
        self._on_click(self._task)

    def set_active(self, active: bool):
        self.configure(fg_color=COL_ACCENT if active else "transparent")


class Sidebar(ctk.CTkFrame):
    """Lista tasków + akcje globalne. Wspólny dla wszystkich zakładek."""

    def __init__(self, master, on_task_selected, **kwargs):
        super().__init__(master, width=SIDEBAR_WIDTH, fg_color=COL_SIDEBAR, corner_radius=0, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._on_task_selected = on_task_selected
        self._rows: list[TaskRow] = []
        self._active_row: TaskRow | None = None

        title = ctk.CTkLabel(
            self, text="TASKI", font=F_SIDEBAR_TITLE, text_color=COL_TEXT_DIM, anchor="w",
        )
        title.grid(row=0, column=0, padx=PAD + 2, pady=(PAD + 2, 2), sticky="ew")

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._list_frame.grid(row=1, column=0, rowspan=2, padx=PAD, pady=(0, PAD), sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

        self.set_tasks(DEMO_TASKS)

        btn_new = ctk.CTkButton(
            self, text="+ Nowy task", font=F_HINT8, height=30, command=self._stub_new_task,
        )
        btn_new.grid(row=3, column=0, padx=PAD, pady=(2, 2), sticky="ew")

        btn_refresh = ctk.CTkButton(
            self, text="⟳ Odśwież dane CPI/FX", font=F_HINT8, height=30,
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

    # -- akcje zaślepkowe (logika w Etapie 1) ------------------------------
    def _stub_new_task(self):
        print("[TODO Etap 1] Dialog 'Nowy task'")

    def _stub_refresh_data(self):
        print("[TODO Etap 1] refresh_data.cmd w wątku")


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

        ctk.CTkLabel(inner, text=tab_name.upper(), font=F_SECTION, text_color=COL_TEXT_DIM).pack(pady=(0, 4))
        ctk.CTkLabel(
            inner, text=f"Zawartość zakładki — {etap_label}", font=F_LABEL, text_color=COL_TEXT,
        ).pack()


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
        header.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(2, 0))
        header.grid_columnconfigure(1, weight=1)

        self._toggle_btn = ctk.CTkButton(
            header, text="▼ rozwiń", font=F_HINT8, width=86, height=24,
            fg_color="transparent", text_color=COL_TEXT_DIM, hover_color=COL_BORDER,
            command=self._toggle,
        )
        self._toggle_btn.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="PODGLĄD KOMENDY", font=F_SIDEBAR_TITLE, text_color=COL_TEXT_DIM,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        copy_btn = ctk.CTkButton(
            header, text="📋 kopiuj", font=F_HINT8, width=86, height=24,
            fg_color="transparent", text_color=COL_TEXT_DIM, border_width=1, border_color=COL_BORDER,
            command=self._copy_to_clipboard,
        )
        copy_btn.grid(row=0, column=2, sticky="e")

        self._textbox = ctk.CTkTextbox(
            self, font=F_CONSOLE, fg_color=COL_CONSOLE_BG, text_color=COL_TEXT,
            wrap="none", height=self._lines_to_px(self.COLLAPSED_LINES), activate_scrollbars=True,
        )
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(2, PAD))
        self._textbox.configure(state="normal")

        # tagi kolorowania zgodne ze spec: flagi pomarańczowe, wartości zielone
        self._textbox._textbox.tag_config("flag", foreground=COL_FLAG)
        self._textbox._textbox.tag_config("value", foreground=COL_VALUE)
        self._textbox._textbox.tag_config("dim", foreground=COL_TEXT_DIM)

        self.set_placeholder()

    @staticmethod
    def _lines_to_px(lines: int) -> int:
        return 23 * lines + 12

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
        self._textbox.configure(state="disabled")

    def set_command_preview(self, prefix: str, flags: list[str], values: list[str]):
        """Przykładowe API kolorowania — dopięte realnie w Etapie 1."""
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.insert("end", prefix + " ")
        for flag, value in zip(flags, values):
            self._textbox.insert("end", flag + " ", "flag")
            self._textbox.insert("end", value + " ", "value")
        self._textbox.configure(state="disabled")

    def append_stdout_line(self, line: str):
        self._textbox.configure(state="normal")
        self._textbox.insert("end", line + "\n")
        self._textbox.see("end")
        self._textbox.configure(state="disabled")


class StatusBar(ctk.CTkFrame):
    """Jedna linia na dole: health check (lewa) / wersja (prawa) — §5."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COL_SIDEBAR, corner_radius=0, height=26, **kwargs)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._left = ctk.CTkLabel(
            self, text=DEMO_STATUSBAR_LEFT, font=F_STATUSBAR, text_color=COL_TEXT_DIM, anchor="w",
        )
        self._left.grid(row=0, column=0, sticky="w", padx=8)

        self._right = ctk.CTkLabel(
            self, text=DEMO_STATUSBAR_RIGHT, font=F_STATUSBAR, text_color=COL_TEXT_DIM, anchor="e",
        )
        self._right.grid(row=0, column=1, sticky="e", padx=8)

    def set_left(self, text: str):
        self._left.configure(text=text)

    def set_right(self, text: str):
        self._right.configure(text=text)


class PasywnyPortfelGUI(ctk.CTk):
    TAB_NAMES = ["Uruchom", "Konfiguracja", "Wyniki", "Portfele"]
    TAB_ETAP = {
        "Uruchom": "TODO — Etap 1",
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

        # -- row 0: sidebar + tabview --------------------------------------
        body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(body, on_task_selected=self._on_task_selected)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        self.tabview = ctk.CTkTabview(
            body, fg_color=COL_BG, segmented_button_selected_color=COL_ACCENT,
            text_color=COL_TEXT,
        )
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=(PAD, 0))
        self.tabview._segmented_button.configure(font=F_LABEL)

        for name in self.TAB_NAMES:
            tab = self.tabview.add(name)
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            content = PlaceholderTab(tab, name, self.TAB_ETAP[name])
            content.grid(row=0, column=0, sticky="nsew")

        # -- row 1: console panel -------------------------------------------
        self.console = ConsolePanel(self)
        self.console.grid(row=1, column=0, sticky="ew")

        # -- row 2: statusbar -------------------------------------------------
        self.statusbar = StatusBar(self)
        self.statusbar.grid(row=2, column=0, sticky="ew")

        self._current_task: dict | None = None

    def _on_task_selected(self, task: dict):
        self._current_task = task
        print(f"[TODO Etap 1] Wczytaj settings/portfolios dla taska: {task['name']}")
        # W Etapie 1: read_settings, read_portfolios, validate_task,
        # przebudowa konsoli przez cmd_builders.ledger_cmd()


def main():
    app = PasywnyPortfelGUI()
    app.mainloop()


if __name__ == "__main__":
    main()

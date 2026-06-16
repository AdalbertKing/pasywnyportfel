#!/usr/bin/env python3
# pasywnyportfel — logowanie przebiegow do pliku
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
run_logging.py — zapis pelnego outputu dlugich przebiegow do run.log.

Uzycie (analysis.py):
    log_path = out_root_path / "run.log"
    with RunLogger(log_path):
        ... caly przebieg analizy ...

Wszystko co normalnie szlo tylko na konsole (print() z analysis.py,
output podprocesow przez run() z cmd_builders.py) ladowane jest
ROWNOLEGLE na konsole i do run.log. Jesli przebieg sie wywali,
pelny traceback trafia do logu razem z FAILED markerem -- mozna
analizowac awarie po fakcie bez przewijania konsoli.

RunLogger jest odporny na bledy I/O: jesli plik logu nie da sie
otworzyc lub zapis do jednego ze strumieni zawiedzie (np. problem
z kodowaniem konsoli), przebieg dziala dalej bez logu / bez tego
strumienia -- logowanie nigdy nie jest powodem przerwania analizy.
"""

import datetime as dt
import sys
import time
import traceback
from pathlib import Path
from typing import Optional, TextIO


class _Tee:
    """Strumien pisujacy do wielu strumieni naraz, odporny na bledy zapisu."""

    def __init__(self, *streams: Optional[TextIO]):
        self._streams = [s for s in streams if s is not None]

    def write(self, data: str) -> int:
        for s in self._streams:
            try:
                s.write(data)
            except Exception:
                pass
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        if not self._streams:
            return False
        try:
            return bool(self._streams[0].isatty())
        except Exception:
            return False

    @property
    def encoding(self) -> str:
        if self._streams:
            return getattr(self._streams[0], "encoding", "utf-8") or "utf-8"
        return "utf-8"


class RunLogger:
    """
    Context manager: zapisuje caly stdout/stderr biezacego procesu do pliku
    `log_path`, jednoczesnie przepuszczajac go na oryginalna konsole.

    Przy wejsciu:
      - tworzy katalog nadrzedny log_path (jesli nie istnieje),
      - otwiera log_path do zapisu (UTF-8),
      - podmienia sys.stdout / sys.stderr na Tee(original, log_file),
      - pisze naglowek "RUN LOG START ...".

    Przy wyjsciu:
      - jesli wystapil wyjatek, dopisuje pelny traceback i marker FAILED,
      - inaczej dopisuje marker OK,
      - przywraca oryginalne sys.stdout / sys.stderr,
      - zamyka plik logu.

    Nie tlumi wyjatkow (zwraca False z __exit__) -- przebieg konczy sie
    tak jak bez RunLoggera, tylko z dodatkowym zapisem do pliku.

    Jesli otwarcie log_path zawiedzie (np. brak praw zapisu), RunLogger
    dziala jak no-op: stdout/stderr nie sa modyfikowane, ostrzezenie idzie
    na oryginalny stderr.
    """

    def __init__(self, log_path: Path | str):
        self.log_path = Path(log_path)
        self._log_file: Optional[TextIO] = None
        self._old_stdout: Optional[TextIO] = None
        self._old_stderr: Optional[TextIO] = None
        self._start: Optional[float] = None

    def __enter__(self) -> "RunLogger":
        self._start = time.monotonic()
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(self.log_path, "w", encoding="utf-8", newline="\n")
        except OSError as e:
            print(f"WARN: nie mozna otworzyc pliku logu {self.log_path}: {e}", file=sys.stderr)
            self._log_file = None
            return self

        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = _Tee(self._old_stdout, self._log_file)
        sys.stderr = _Tee(self._old_stderr, self._log_file)

        ts = dt.datetime.now().isoformat(timespec="seconds")
        print(f"=== RUN LOG START {ts} ===")
        print(f"=== LOG FILE: {self.log_path} ===")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._log_file is None:
            return False

        elapsed = time.monotonic() - (self._start or time.monotonic())
        ts = dt.datetime.now().isoformat(timespec="seconds")

        if exc_type is not None:
            tb_text = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            if not tb_text.endswith("\n"):
                tb_text += "\n"
            print(tb_text, end="")
            print(
                f"=== RUN LOG END {ts} -- FAILED after {elapsed:.1f}s: "
                f"{exc_type.__name__}: {exc_val} ==="
            )
        else:
            print(f"=== RUN LOG END {ts} -- OK after {elapsed:.1f}s ===")

        if self._old_stdout is not None:
            sys.stdout = self._old_stdout
        if self._old_stderr is not None:
            sys.stderr = self._old_stderr

        try:
            self._log_file.close()
        except OSError:
            pass
        self._log_file = None

        return False

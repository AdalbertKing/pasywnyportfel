# pasywnyportfel — testy run_logging.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
Testy dla app/bin/run_logging.py — Tee + RunLogger.

RunLogger jest uzywany w analysis.py do zapisu run.log dla kazdej
analizy (analysis_results/<run_folder>/run.log). Te testy pokrywaja:
  - normalny przebieg (OK marker, zawartosc logu, przywrocenie streamow)
  - przebieg z wyjatkiem (FAILED marker + pelny traceback w logu,
    wyjatek nie jest tlumiony)
  - odpornosc na bledy I/O (zly log_path, strumien ktory rzuca przy write)
"""

import io
import sys
from pathlib import Path

import pytest

from run_logging import RunLogger, _Tee


# ---------------------------------------------------------------------------
# _Tee
# ---------------------------------------------------------------------------

class TestTee:
    def test_write_goes_to_all_streams(self):
        a, b = io.StringIO(), io.StringIO()
        tee = _Tee(a, b)
        tee.write("hello")
        assert a.getvalue() == "hello"
        assert b.getvalue() == "hello"

    def test_returns_length_of_data(self):
        tee = _Tee(io.StringIO())
        assert tee.write("abcde") == 5

    def test_none_streams_filtered_out(self):
        a = io.StringIO()
        tee = _Tee(a, None)
        tee.write("x")
        assert a.getvalue() == "x"

    def test_failing_stream_does_not_break_others(self):
        class Boom:
            def write(self, data):
                raise IOError("boom")

            def flush(self):
                raise IOError("boom")

        good = io.StringIO()
        tee = _Tee(Boom(), good)
        tee.write("ok")  # nie rzuca
        tee.flush()      # nie rzuca
        assert good.getvalue() == "ok"

    def test_isatty_delegates_to_first_stream(self):
        class Fake:
            def isatty(self):
                return True

            def write(self, data):
                pass

        tee = _Tee(Fake())
        assert tee.isatty() is True

    def test_isatty_false_when_no_streams(self):
        assert _Tee().isatty() is False

    def test_isatty_false_on_error(self):
        class Boom:
            def isatty(self):
                raise RuntimeError("nope")

            def write(self, data):
                pass

        assert _Tee(Boom()).isatty() is False

    def test_encoding_delegates_to_first_stream(self):
        class FakeStream:
            encoding = "cp1250"

            def write(self, data):
                pass

        tee = _Tee(FakeStream())
        assert tee.encoding == "cp1250"

    def test_encoding_default_when_missing(self):
        tee = _Tee(io.StringIO())
        assert tee.encoding == "utf-8"

    def test_encoding_default_when_no_streams(self):
        assert _Tee().encoding == "utf-8"


# ---------------------------------------------------------------------------
# RunLogger — przebieg poprawny
# ---------------------------------------------------------------------------

class TestRunLoggerSuccess:
    def test_creates_log_file_and_parent_dirs(self, tmp_path: Path):
        log_path = tmp_path / "nested" / "run.log"
        with RunLogger(log_path):
            print("hello world")
        assert log_path.exists()

    def test_log_contains_start_and_end_markers(self, tmp_path: Path):
        log_path = tmp_path / "run.log"
        with RunLogger(log_path):
            print("content line")
        text = log_path.read_text(encoding="utf-8")
        assert "RUN LOG START" in text
        assert "RUN LOG END" in text
        assert "OK after" in text
        assert "content line" in text

    def test_prints_still_go_to_console(self, tmp_path: Path, capsys):
        log_path = tmp_path / "run.log"
        with RunLogger(log_path):
            print("visible on console too")
        captured = capsys.readouterr()
        assert "visible on console too" in captured.out

    def test_restores_stdout_stderr_after_exit(self, tmp_path: Path):
        old_out, old_err = sys.stdout, sys.stderr
        with RunLogger(tmp_path / "run.log"):
            assert sys.stdout is not old_out
            assert sys.stderr is not old_err
        assert sys.stdout is old_out
        assert sys.stderr is old_err

    def test_stderr_also_logged(self, tmp_path: Path):
        log_path = tmp_path / "run.log"
        with RunLogger(log_path):
            print("err message", file=sys.stderr)
        text = log_path.read_text(encoding="utf-8")
        assert "err message" in text

    def test_log_file_closed_after_exit(self, tmp_path: Path):
        log_path = tmp_path / "run.log"
        logger = RunLogger(log_path)
        with logger:
            print("x")
        assert logger._log_file is None


# ---------------------------------------------------------------------------
# RunLogger — przebieg z wyjatkiem
# ---------------------------------------------------------------------------

class TestRunLoggerFailure:
    def test_exception_propagates(self, tmp_path: Path):
        with pytest.raises(RuntimeError, match="boom"):
            with RunLogger(tmp_path / "run.log"):
                raise RuntimeError("boom")

    def test_log_contains_failed_marker_and_traceback(self, tmp_path: Path):
        log_path = tmp_path / "run.log"
        try:
            with RunLogger(log_path):
                print("before crash")
                raise ValueError("something went wrong")
        except ValueError:
            pass

        text = log_path.read_text(encoding="utf-8")
        assert "before crash" in text
        assert "FAILED after" in text
        assert "ValueError: something went wrong" in text
        assert "Traceback (most recent call last)" in text

    def test_restores_streams_even_on_exception(self, tmp_path: Path):
        old_out, old_err = sys.stdout, sys.stderr
        try:
            with RunLogger(tmp_path / "run.log"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert sys.stdout is old_out
        assert sys.stderr is old_err

    def test_subprocess_style_failure_logged(self, tmp_path: Path):
        """Symulacja sceniariusza analysis.py: run() rzuca RuntimeError
        z komunikatem o nieudanym podprocesie -- musi trafic do logu w pelni."""
        log_path = tmp_path / "run.log"
        cmd_msg = (
            'Command failed, returncode=1: python app/bin/passive_ledger.py '
            '--portfolio maps/synth/sp500_syn.csv --out l_sp500_syn_BH.csv'
        )
        try:
            with RunLogger(log_path):
                print("RUN: python app/bin/passive_ledger.py ...")
                raise RuntimeError(cmd_msg)
        except RuntimeError:
            pass

        text = log_path.read_text(encoding="utf-8")
        assert "RUN: python app/bin/passive_ledger.py" in text
        assert cmd_msg in text
        assert "FAILED after" in text


# ---------------------------------------------------------------------------
# RunLogger — odpornosc na bledy I/O
# ---------------------------------------------------------------------------

class TestRunLoggerErrorResilience:
    def test_unwritable_log_path_does_not_crash(self, tmp_path: Path):
        """Jesli log_path.parent nie da sie utworzyc / otworzyc (tu: parent
        jest plikiem, nie katalogiem), RunLogger dziala jako no-op."""
        blocker = tmp_path / "blocker"
        blocker.write_text("im a file not a dir", encoding="utf-8")
        bad_log_path = blocker / "run.log"  # parent "blocker" to plik

        old_out = sys.stdout
        with RunLogger(bad_log_path):
            print("still works")
        assert sys.stdout is old_out  # nic nie zostalo zamienione

    def test_noop_logger_does_not_swallow_exceptions(self, tmp_path: Path):
        blocker = tmp_path / "blocker"
        blocker.write_text("x", encoding="utf-8")
        bad_log_path = blocker / "run.log"

        with pytest.raises(RuntimeError, match="boom"):
            with RunLogger(bad_log_path):
                raise RuntimeError("boom")

    def test_double_exit_is_safe(self, tmp_path: Path):
        """__exit__ wywolane drugi raz (np. przez zagniezdzone with) nie crashuje."""
        log_path = tmp_path / "run.log"
        logger = RunLogger(log_path)
        logger.__enter__()
        logger.__exit__(None, None, None)
        # druga proba na juz-zamknietym loggerze
        logger.__exit__(None, None, None)

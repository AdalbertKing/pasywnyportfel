# pasywnyportfel — testy cmd_builders.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
Testy dla app/bin/cmd_builders.py — przede wszystkim run().

run() zostal zmieniony z subprocess.run(...) (dziedziczace fd konsoli)
na subprocess.Popen + strumieniowanie linia-po-linii przez sys.stdout.
Dzieki temu output podprocesow (build_db_*, passive_ledger, itp.)
trafia do RunLoggera razem z printami analysis.py.

Te testy weryfikuja:
  - dry_run nic nie wykonuje
  - output podprocesu trafia do biezacego sys.stdout (czyli zostalby
    zlogowany przez RunLogger, gdyby byl aktywny)
  - stderr podprocesu jest scalany do tego samego strumienia (stdout)
  - niezerowy kod wyjscia podprocesu -> RuntimeError z returncode w komunikacie
  - integracja end-to-end z RunLogger: output podprocesu faktycznie
    ladowany jest do run.log
"""

import io
import sys
from pathlib import Path

import pytest

from cmd_builders import run
from run_logging import RunLogger


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------

class TestRunDryRun:
    def test_dry_run_returns_zero_without_executing(self, tmp_path: Path):
        # Polecenie ktore zawalilo by sie, gdyby bylo wykonane
        cmd = [sys.executable, "-c", "import sys; sys.exit(7)"]
        rc = run(cmd, tmp_path, dry_run=True)
        assert rc == 0

    def test_dry_run_prints_run_line(self, tmp_path: Path, capsys):
        marker_file = tmp_path / "executed.txt"
        cmd = [sys.executable, "-c", f"open(r'{marker_file}', 'w').close()"]
        run(cmd, tmp_path, dry_run=True)
        captured = capsys.readouterr()
        assert "RUN:" in captured.out
        assert not marker_file.exists()  # podproces nie zostal wykonany


# ---------------------------------------------------------------------------
# Streaming output przez sys.stdout
# ---------------------------------------------------------------------------

class TestRunStreaming:
    def test_subprocess_stdout_appears_on_sys_stdout(self, tmp_path: Path):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            cmd = [sys.executable, "-c", "print('hello-from-subprocess')"]
            run(cmd, tmp_path)
        finally:
            sys.stdout = old_stdout

        assert "hello-from-subprocess" in buf.getvalue()

    def test_subprocess_stderr_merged_into_stdout(self, tmp_path: Path):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            cmd = [sys.executable, "-c", "import sys; print('err-line', file=sys.stderr)"]
            run(cmd, tmp_path)
        finally:
            sys.stdout = old_stdout

        assert "err-line" in buf.getvalue()

    def test_multiline_output_all_captured(self, tmp_path: Path):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            cmd = [sys.executable, "-c", "for i in range(5): print(f'line-{i}')"]
            run(cmd, tmp_path)
        finally:
            sys.stdout = old_stdout

        out = buf.getvalue()
        for i in range(5):
            assert f"line-{i}" in out

    def test_run_returns_zero_on_success(self, tmp_path: Path):
        cmd = [sys.executable, "-c", "print('ok')"]
        assert run(cmd, tmp_path) == 0


# ---------------------------------------------------------------------------
# Bledny kod wyjscia
# ---------------------------------------------------------------------------

class TestRunFailure:
    def test_nonzero_exit_raises_runtime_error(self, tmp_path: Path):
        cmd = [sys.executable, "-c", "import sys; sys.exit(3)"]
        with pytest.raises(RuntimeError, match="returncode=3"):
            run(cmd, tmp_path)

    def test_failure_message_includes_command(self, tmp_path: Path):
        cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]
        with pytest.raises(RuntimeError, match="python"):
            run(cmd, tmp_path)

    def test_output_before_failure_is_still_streamed(self, tmp_path: Path):
        """Output wypisany przed sys.exit(1) musi byc widoczny mimo wyjatku."""
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            cmd = [sys.executable, "-c", "print('partial output'); import sys; sys.exit(1)"]
            with pytest.raises(RuntimeError):
                run(cmd, tmp_path)
        finally:
            sys.stdout = old_stdout

        assert "partial output" in buf.getvalue()


# ---------------------------------------------------------------------------
# Integracja z RunLogger — to jest realny scenariusz analysis.py
# ---------------------------------------------------------------------------

class TestRunWithRunLogger:
    def test_subprocess_output_lands_in_run_log(self, tmp_path: Path):
        log_path = tmp_path / "run.log"
        cmd = [sys.executable, "-c", "print('synth db zapisana')"]

        with RunLogger(log_path):
            run(cmd, tmp_path)

        text = log_path.read_text(encoding="utf-8")
        assert "synth db zapisana" in text
        assert "RUN:" in text

    def test_subprocess_failure_traceback_lands_in_run_log(self, tmp_path: Path):
        """
        Odtworzenie sceniariusza VER 2.2.5A: passive_ledger.py rzuca
        NameError -> run() przeklada na RuntimeError -> analysis.py
        propaguje wyjatek -> RunLogger zapisuje FAILED + pelny traceback.
        """
        log_path = tmp_path / "run.log"
        cmd = [sys.executable, "-c", "raise NameError(\"name 'Path' is not defined\")"]

        try:
            with RunLogger(log_path):
                run(cmd, tmp_path)
        except RuntimeError:
            pass

        text = log_path.read_text(encoding="utf-8")
        assert "NameError" in text
        assert "Path" in text
        assert "FAILED after" in text
        assert "Command failed, returncode=1" in text

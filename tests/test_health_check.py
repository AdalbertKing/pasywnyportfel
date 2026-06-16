# pasywnyportfel — testy health_check.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
Testy dla app/bin/health_check.py — kontrola stanu pakietu.

Skupiaja sie na testowalnych jednostkach (Counter, _last_date_in_csv)
oraz na pelnym smoke-tescie main() na prawdziwym projekcie. Calosc
zastapila krucha test_after_start.cmd (wieloliniowe python -c nie
dzialaja w CMD).
"""

import datetime as dt
from pathlib import Path

import pytest

import health_check as hc


# ---------------------------------------------------------------------------
# Counter
# ---------------------------------------------------------------------------

class TestCounter:
    def test_ok_increments(self, capsys):
        c = hc.Counter()
        c.ok("test message")
        assert c.passed == 1
        assert "OK   test message" in capsys.readouterr().out

    def test_warn_increments(self, capsys):
        c = hc.Counter()
        c.warn("warning")
        assert c.warned == 1
        assert "WARN warning" in capsys.readouterr().out

    def test_fail_increments(self, capsys):
        c = hc.Counter()
        c.fail("failure")
        assert c.failed == 1
        assert "FAIL failure" in capsys.readouterr().out

    def test_independent_counts(self):
        c = hc.Counter()
        c.ok("a"); c.ok("b"); c.warn("c"); c.fail("d")
        assert (c.passed, c.warned, c.failed) == (2, 1, 1)


# ---------------------------------------------------------------------------
# _last_date_in_csv
# ---------------------------------------------------------------------------

class TestLastDateInCsv:
    def test_standard_format(self, tmp_path: Path):
        p = tmp_path / "cpi.csv"
        p.write_text("date,cpi\n2020-01-01,100\n2020-02-01,101\n", encoding="utf-8")
        assert hc._last_date_in_csv(p) == dt.date(2020, 2, 1)

    def test_wide_format_with_metadata_rows(self, tmp_path: Path):
        """Format DB_FX.csv: pierwsze wiersze to NAME/ISIN, potem daty."""
        p = tmp_path / "fx.csv"
        p.write_text("NAME,USD/PLN\nISIN,USDPLN\n2002-01-02,3.94\n2026-05-28,3.71\n", encoding="utf-8")
        assert hc._last_date_in_csv(p) == dt.date(2026, 5, 28)

    def test_returns_latest_not_last_row(self, tmp_path: Path):
        """Bierze ostatnia PARSOWALNA date — tu ostatni wiersz."""
        p = tmp_path / "x.csv"
        p.write_text("date,v\n2020-01-01,1\n2020-06-01,2\n", encoding="utf-8")
        assert hc._last_date_in_csv(p) == dt.date(2020, 6, 1)

    def test_no_dates_returns_none(self, tmp_path: Path):
        p = tmp_path / "x.csv"
        p.write_text("header,only\nfoo,bar\n", encoding="utf-8")
        assert hc._last_date_in_csv(p) is None

    def test_real_cpi_usd(self, project_root: Path):
        p = project_root / "data" / "in" / "cpi" / "CPI_USD.csv"
        last = hc._last_date_in_csv(p)
        assert last is not None
        assert last.year >= 2025


# ---------------------------------------------------------------------------
# Fazy na prawdziwym projekcie
# ---------------------------------------------------------------------------

class TestCheckPhases:
    def test_check_common_data_no_fail_on_real_project(self, project_root: Path):
        c = hc.Counter()
        hc.check_common_data(project_root, c)
        # CPI/FX/SYNTH istnieja w repo -> brak FAIL (HIST moze byc WARN)
        assert c.failed == 0

    def test_check_tasks_no_fail_on_real_project(self, project_root: Path):
        c = hc.Counter()
        hc.check_tasks(project_root, c)
        # wszystkie shipped taski przechodza walidacje (HIST gaps to tylko WARN)
        assert c.failed == 0
        assert c.passed >= 6  # 6 taskow

    def test_check_cli_all_help_ok(self, project_root: Path):
        c = hc.Counter()
        hc.check_cli(project_root, c)
        assert c.failed == 0

    def test_check_results_handles_missing_dir(self, tmp_path: Path):
        """Bez analysis_results -> WARN, nie FAIL."""
        c = hc.Counter()
        hc.check_results(tmp_path, c)
        assert c.failed == 0
        assert c.warned >= 1


class TestCheckCommonDataFreshness:
    def _make_data(self, tmp_path: Path, fx_last_date: str):
        for sub in ["cpi", "fx", "libraries"]:
            (tmp_path / "data" / "in" / sub).mkdir(parents=True, exist_ok=True)
        (tmp_path / "data/in/cpi/CPI_USD.csv").write_text(
            f"date,cpi\n2020-01-01,100\n{fx_last_date},120\n", encoding="utf-8")
        (tmp_path / "data/in/cpi/CPI_PLN_GUS.csv").write_text(
            f"date,cpi\n2020-01-01,100\n{fx_last_date},120\n", encoding="utf-8")
        (tmp_path / "data/in/fx/DB_FX.csv").write_text(
            f"NAME,USD/PLN\nISIN,USDPLN\n2002-01-02,3.9\n{fx_last_date},3.7\n", encoding="utf-8")
        (tmp_path / "data/in/libraries/SYNTH_LIBRARY_MONTHLY_USD.csv").write_text(
            "DATE,US_STOCKS_TR\n2020-01-31,100\n", encoding="utf-8")

    def test_fresh_data_is_ok(self, tmp_path: Path):
        recent = (dt.date.today() - dt.timedelta(days=10)).isoformat()
        self._make_data(tmp_path, recent)
        c = hc.Counter()
        hc.check_common_data(tmp_path, c)
        assert c.failed == 0
        # swiezosc < 120 dni -> 3 OK z fazy swiezosci (plus OK za istnienie plikow)

    def test_stale_data_warns(self, tmp_path: Path):
        old = (dt.date.today() - dt.timedelta(days=200)).isoformat()
        self._make_data(tmp_path, old)
        c = hc.Counter()
        hc.check_common_data(tmp_path, c)
        assert c.failed == 0
        assert c.warned >= 3  # 3 pliki przestarzale


# ---------------------------------------------------------------------------
# main() — pelny smoke test
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_returns_fail_count(self, project_root: Path, monkeypatch, capsys):
        """
        main() uruchomione na prawdziwym projekcie. Zwraca liczbe FAIL.
        W srodowisku z kompletem bibliotek powinno byc 0; tutaj moze byc
        >0 jesli np. yfinance nie jest zainstalowany (sandbox offline),
        wiec sprawdzamy tylko ze main() konczy sie i zwraca int oraz ze
        wydrukowal podsumowanie.
        """
        monkeypatch.chdir(project_root)
        rc = hc.main()
        out = capsys.readouterr().out
        assert isinstance(rc, int)
        assert "PODSUMOWANIE" in out
        assert "FAZA 1" in out
        assert "FAZA 6" in out
        assert rc == out.count("\n  FAIL ")

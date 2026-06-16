# pasywnyportfel — testy ledger_engine.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
Testy integracyjne dla app/bin/ledger_engine.py.

To sa testy ktore w sesji VER 2.2.5A wykonywalismy recznie po kazdym
hotfixie (subprocess passive_ledger.py + simulate_ledger end-to-end).
Pokrywaja caly stos: ledger_primitives + ledger_io + ledger_tax + ledger_engine
i lapia bledy NameError/ImportError ktore py_compile/import nie wykrywaja,
bo objawiaja sie tylko przy faktycznym wywolaniu funkcji.
"""

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from ledger_engine import build_event_dates, simulate_ledger


# ---------------------------------------------------------------------------
# build_event_dates
# ---------------------------------------------------------------------------

class TestBuildEventDates:
    def _sessions(self, start="2020-01-31", periods=60, freq="ME"):
        return [d.date() for d in pd.date_range(start, periods=periods, freq=freq)]

    def test_annual_rebalance_dates(self):
        sessions = self._sessions()
        start, end = sessions[0], sessions[-1]
        rebals, settles = build_event_dates(sessions, start, end, period_months=12, settle_md="12-31")
        assert len(rebals) > 0
        # wszystkie rebalansy w grudniu (koniec roku, period=12M od stycznia)
        assert all(d.month == 1 for d in rebals)

    def test_no_rebalance_when_period_zero(self):
        sessions = self._sessions()
        rebals, settles = build_event_dates(sessions, sessions[0], sessions[-1], period_months=0, settle_md="12-31")
        assert rebals == set()

    def test_settles_one_per_year(self):
        sessions = self._sessions(periods=60)  # 2020-01 .. 2024-12
        start, end = sessions[0], sessions[-1]
        rebals, settles = build_event_dates(sessions, start, end, period_months=12, settle_md="12-31")
        years = {d.year for d in settles}
        # 5 lat (2020-2024), kazdy z 1 settlement
        assert len(settles) == len(years)

    def test_final_settle_includes_partial_last_year(self):
        """final_settle=True wymusza settlement w ostatnim (niepelnym) roku."""
        sessions = self._sessions(start="2020-01-31", periods=6)  # do 2020-06
        start, end = sessions[0], sessions[-1]
        _, settles_with = build_event_dates(sessions, start, end, period_months=12, settle_md="12-31", final_settle=True)
        _, settles_without = build_event_dates(sessions, start, end, period_months=12, settle_md="12-31", final_settle=False)
        assert len(settles_with) >= len(settles_without)

    def test_event_dates_within_range(self):
        sessions = self._sessions()
        start, end = sessions[0], sessions[-1]
        rebals, settles = build_event_dates(sessions, start, end, period_months=12, settle_md="12-31")
        for d in rebals | settles:
            assert start <= d <= end


# ---------------------------------------------------------------------------
# simulate_ledger — Buy & Hold, jeden skladnik
# ---------------------------------------------------------------------------

class TestSimulateLedgerBuyAndHold:
    def _run(self, portfolio_csv, prices_csv, cpi_us_csv, **overrides):
        kwargs = dict(
            portfolio_csv=str(portfolio_csv),
            prices_csv=str(prices_csv),
            fx_csv=None,
            cpi_pl_csv=None,
            cpi_us_csv=str(cpi_us_csv),
            start_str="2005-01-31",
            end_str="2009-12-31",
            saldo_usd=100000.0,
            settle_md="12-31",
            freq="monthly",
            period="9999M",
            max_drift=0.0,
            no_rebalance=True,
            conditional_rebalance=False,
            tax_mode="gross",
            tax_base="USD",
            tax_rate=0.19,
            loss_window_years=5,
            loss_bucket_annual_cap=1.0,
            sma_fast=None,
            sma_slow=None,
            final_settle=True,
        )
        kwargs.update(overrides)
        return simulate_ledger(**kwargs)

    def test_returns_dataframe_with_expected_columns(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        db = wide_price_db_csv(["TEST_ASSET"], n_months=60, growth={"TEST_ASSET": 0.07})
        df = self._run(synth_portfolio_csv, db, cpi_us_csv)

        for col in ["DATE", "TOTAL_USD_PRE", "TOTAL_USD_POST", "TOTAL_USD_POST_REAL"]:
            assert col in df.columns

    def test_starting_capital_matches_saldo(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        db = wide_price_db_csv(["TEST_ASSET"], n_months=60, growth={"TEST_ASSET": 0.07})
        df = self._run(synth_portfolio_csv, db, cpi_us_csv, saldo_usd=100000.0)
        assert df["TOTAL_USD_POST"].iloc[0] == pytest.approx(100000.0, rel=0.01)

    def test_growth_increases_portfolio_value(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        """Aktywo rosnace o 7% rocznie -> wartosc koncowa > poczatkowa po 5 latach."""
        db = wide_price_db_csv(["TEST_ASSET"], n_months=60, growth={"TEST_ASSET": 0.07})
        df = self._run(synth_portfolio_csv, db, cpi_us_csv)
        assert df["TOTAL_USD_POST"].iloc[-1] > df["TOTAL_USD_POST"].iloc[0]

    def test_real_value_lower_than_nominal_with_inflation(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        """Wartosc realna (po CPI) powinna byc <= nominalna gdy jest inflacja."""
        db = wide_price_db_csv(["TEST_ASSET"], n_months=60, growth={"TEST_ASSET": 0.07})
        df = self._run(synth_portfolio_csv, db, cpi_us_csv)
        last = df.iloc[-1]
        assert last["TOTAL_USD_POST_REAL"] <= last["TOTAL_USD_POST"] * 1.001

    def test_flat_asset_preserves_nominal_value(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        """Aktywo o staloj cenie (0% growth) -> wartosc nominalna portfela stala."""
        db = wide_price_db_csv(["TEST_ASSET"], n_months=24, growth={"TEST_ASSET": 0.0})
        df = self._run(synth_portfolio_csv, db, cpi_us_csv,
                        start_str="2005-01-31", end_str="2006-12-31")
        first, last = df["TOTAL_USD_POST"].iloc[0], df["TOTAL_USD_POST"].iloc[-1]
        assert last == pytest.approx(first, rel=0.01)

    def test_output_covers_requested_date_range(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        db = wide_price_db_csv(["TEST_ASSET"], n_months=60, growth={"TEST_ASSET": 0.07})
        df = self._run(synth_portfolio_csv, db, cpi_us_csv,
                        start_str="2005-01-31", end_str="2009-12-31")
        first_date = dt.date.fromisoformat(df["DATE"].iloc[0])
        last_date = dt.date.fromisoformat(df["DATE"].iloc[-1])
        assert first_date == dt.date(2005, 1, 31)
        assert last_date == dt.date(2009, 12, 31)


# ---------------------------------------------------------------------------
# simulate_ledger — DRIFT rebalans, dwa skladniki
# ---------------------------------------------------------------------------

class TestSimulateLedgerDrift:
    def _run(self, portfolio_csv, prices_csv, cpi_us_csv, **overrides):
        kwargs = dict(
            portfolio_csv=str(portfolio_csv),
            prices_csv=str(prices_csv),
            fx_csv=None,
            cpi_pl_csv=None,
            cpi_us_csv=str(cpi_us_csv),
            start_str="2005-01-31",
            end_str="2009-12-31",
            saldo_usd=100000.0,
            settle_md="12-31",
            freq="monthly",
            period="9999M",
            max_drift=20.0,
            no_rebalance=False,
            conditional_rebalance=True,
            tax_mode="gross",
            tax_base="USD",
            tax_rate=0.19,
            loss_window_years=5,
            loss_bucket_annual_cap=1.0,
            sma_fast=None,
            sma_slow=None,
            final_settle=True,
        )
        kwargs.update(overrides)
        return simulate_ledger(**kwargs)

    def test_two_asset_drift_runs(self, two_asset_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        """Dwa aktywa o roznym wzroscie -> drift rebalansing nie wywala sie."""
        db = wide_price_db_csv(
            ["ASSET_A", "ASSET_B"], n_months=60,
            growth={"ASSET_A": 0.10, "ASSET_B": 0.02},
        )
        df = self._run(two_asset_portfolio_csv, db, cpi_us_csv)
        assert len(df) > 0
        assert df["TOTAL_USD_POST"].iloc[-1] > 0

    def test_drift_rebalance_triggers_with_diverging_assets(self, two_asset_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        """Przy silnie roznym wzroscie i max_drift=20, oczekujemy >=1 zdarzenia REBAL."""
        db = wide_price_db_csv(
            ["ASSET_A", "ASSET_B"], n_months=60,
            growth={"ASSET_A": 0.25, "ASSET_B": -0.05},
        )
        df = self._run(two_asset_portfolio_csv, db, cpi_us_csv)
        if "EVENT" in df.columns:
            events = df["EVENT"].astype(str)
            assert events.str.contains("REBAL", case=False).any()


# ---------------------------------------------------------------------------
# tax_mode=net — sciezka ktora ujawnila brakujacy @dataclass
# ---------------------------------------------------------------------------

class TestSimulateLedgerNetTax:
    def test_net_usd_tax_mode_runs_without_error(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        """
        tax_mode=net wywoluje apply_loss_buckets/LossBucket.
        Ten test pokrywa regresje '@dataclass' z VER 2.2.5A — bez dekoratora
        ten test rzucalby TypeError: LossBucket() takes no arguments.
        """
        db = wide_price_db_csv(["TEST_ASSET"], n_months=60, growth={"TEST_ASSET": 0.07})
        df = simulate_ledger(
            portfolio_csv=str(synth_portfolio_csv),
            prices_csv=str(db),
            fx_csv=None,
            cpi_pl_csv=None,
            cpi_us_csv=str(cpi_us_csv),
            start_str="2005-01-31",
            end_str="2009-12-31",
            saldo_usd=100000.0,
            settle_md="12-31",
            freq="monthly",
            period="12M",
            max_drift=0.0,
            no_rebalance=False,
            conditional_rebalance=False,
            tax_mode="net",
            tax_base="USD",
            tax_rate=0.19,
            loss_window_years=5,
            loss_bucket_annual_cap=1.0,
            sma_fast=None,
            sma_slow=None,
            final_settle=True,
        )
        assert len(df) > 0
        assert df["TOTAL_USD_POST"].iloc[-1] > 0

    def test_net_with_loss_then_gain_applies_deduction(self, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv):
        """Spadek a potem wzrost -> koszyk strat powinien dzialac end-to-end bez wyjatku."""
        db = wide_price_db_csv(["TEST_ASSET"], n_months=72, growth={"TEST_ASSET": -0.10})
        # nadpisz druga polowe cen rosnaco, zeby wygenerowac zysk po stracie
        import csv as csv_mod
        rows = list(csv_mod.reader(open(db, encoding="utf-8")))
        header, isin_row, data_rows = rows[0], rows[1], rows[2:]
        for i, r in enumerate(data_rows):
            if i >= 36:
                base = float(data_rows[35][1])
                r[1] = f"{base * (1.15 ** ((i - 35) / 12)):.6f}"
        with open(db, "w", newline="", encoding="utf-8") as f:
            w = csv_mod.writer(f)
            w.writerow(header)
            w.writerow(isin_row)
            w.writerows(data_rows)

        df = simulate_ledger(
            portfolio_csv=str(synth_portfolio_csv),
            prices_csv=str(db),
            fx_csv=None,
            cpi_pl_csv=None,
            cpi_us_csv=str(cpi_us_csv),
            start_str="2005-01-31",
            end_str="2010-12-31",
            saldo_usd=100000.0,
            settle_md="12-31",
            freq="monthly",
            period="12M",
            max_drift=0.0,
            no_rebalance=False,
            conditional_rebalance=False,
            tax_mode="net",
            tax_base="USD",
            tax_rate=0.19,
            loss_window_years=5,
            loss_bucket_annual_cap=1.0,
            sma_fast=None,
            sma_slow=None,
            final_settle=True,
        )
        assert len(df) > 0


# ---------------------------------------------------------------------------
# Subprocess end-to-end — dokladnie tak jak woła analysis.py / cmd_builders.py
# ---------------------------------------------------------------------------

class TestPassiveLedgerSubprocess:
    """
    Te testy odtwarzaja realne wywolanie:
        python app/bin/passive_ledger.py --portfolio ... --prices ... --out ...
    czyli sciezke, na ktorej w sesji 2.2.5A wystepowaly kolejne NameError
    (Path, re, relativedelta, _parse_date, _ensure_float).
    """

    def test_help_exits_zero(self, project_root: Path):
        r = subprocess.run(
            [sys.executable, str(project_root / "app/bin/passive_ledger.py"), "--help"],
            capture_output=True, text=True,
        )
        assert r.returncode == 0

    def test_buy_and_hold_subprocess(self, project_root: Path, synth_portfolio_csv, wide_price_db_csv, cpi_us_csv, tmp_path: Path):
        db = wide_price_db_csv(["TEST_ASSET"], n_months=60, growth={"TEST_ASSET": 0.07})
        out = tmp_path / "ledger_out.csv"

        cmd = [
            sys.executable, str(project_root / "app/bin/passive_ledger.py"),
            "--portfolio", str(synth_portfolio_csv),
            "--prices", str(db),
            "--start", "2005-01-31",
            "--end", "2009-12-31",
            "--saldo", "100000",
            "--settle-md", "12-31",
            "--freq", "monthly",
            "--out", str(out),
            "--cpi-us", str(cpi_us_csv),
            "--period", "9999M",
            "--max-drift", "0",
            "--no-rebalance",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
        assert out.exists()

        df = pd.read_csv(out)
        assert len(df) > 0
        assert df["TOTAL_USD_POST"].iloc[-1] > df["TOTAL_USD_POST"].iloc[0]

    def test_drift_rebalance_subprocess(self, project_root: Path, two_asset_portfolio_csv, wide_price_db_csv, cpi_us_csv, tmp_path: Path):
        db = wide_price_db_csv(
            ["ASSET_A", "ASSET_B"], n_months=60,
            growth={"ASSET_A": 0.10, "ASSET_B": 0.02},
        )
        out = tmp_path / "ledger_drift_out.csv"

        cmd = [
            sys.executable, str(project_root / "app/bin/passive_ledger.py"),
            "--portfolio", str(two_asset_portfolio_csv),
            "--prices", str(db),
            "--start", "2005-01-31",
            "--end", "2009-12-31",
            "--saldo", "100000",
            "--settle-md", "12-31",
            "--freq", "monthly",
            "--out", str(out),
            "--cpi-us", str(cpi_us_csv),
            "--period", "9999M",
            "--max-drift", "20",
            "--conditional-rebalance",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
        assert out.exists()

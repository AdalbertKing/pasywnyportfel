# pasywnyportfel — testy ledger_primitives.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""Testy dla app/bin/ledger_primitives.py — prymitywy dat, cen, resampligu."""

import datetime as dt

import pandas as pd
import pytest

from ledger_primitives import (
    _attach_fx_to_prices,
    _effective_ledger_end,
    _ensure_float,
    _freq_rank,
    _infer_price_freq,
    _last_day_of_month,
    _normalize_freq,
    _parse_date,
    _pick_last_available_in_period,
    _previous_month_end,
    _resample_prices_to_freq,
    _safe_div,
)


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_valid_iso_date(self):
        assert _parse_date("2005-01-31") == dt.date(2005, 1, 31)

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_wrong_format_returns_none(self):
        assert _parse_date("31-01-2005") is None
        assert _parse_date("2005/01/31") is None

    def test_whitespace_stripped(self):
        assert _parse_date("  2005-01-31  ") == dt.date(2005, 1, 31)

    def test_invalid_calendar_date_returns_none(self):
        """2005-02-30 ma poprawny format regex, ale nie istnieje jako data."""
        assert _parse_date("2005-02-30") is None


# ---------------------------------------------------------------------------
# _last_day_of_month / _previous_month_end
# ---------------------------------------------------------------------------

class TestMonthBoundaries:
    @pytest.mark.parametrize("inp,expected", [
        (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),   # leap year
        (dt.date(2023, 2, 15), dt.date(2023, 2, 28)),  # non-leap
        (dt.date(2024, 12, 1), dt.date(2024, 12, 31)),
        (dt.date(2024, 4, 30), dt.date(2024, 4, 30)),
    ])
    def test_last_day_of_month(self, inp, expected):
        assert _last_day_of_month(inp) == expected

    def test_previous_month_end(self):
        assert _previous_month_end(dt.date(2024, 3, 15)) == dt.date(2024, 2, 29)
        assert _previous_month_end(dt.date(2024, 1, 1)) == dt.date(2023, 12, 31)


# ---------------------------------------------------------------------------
# _ensure_float / _safe_div
# ---------------------------------------------------------------------------

class TestEnsureFloat:
    def test_int_to_float(self):
        assert _ensure_float(5) == 5.0

    def test_float_unchanged(self):
        assert _ensure_float(3.14) == 3.14

    def test_string_number(self):
        assert _ensure_float("12.5") == 12.5

    def test_none_returns_none(self):
        assert _ensure_float(None) is None

    def test_empty_string_returns_none(self):
        assert _ensure_float("") is None

    def test_whitespace_string_returns_none(self):
        assert _ensure_float("   ") is None

    def test_invalid_string_returns_none(self):
        assert _ensure_float("not_a_number") is None

    def test_strips_whitespace(self):
        assert _ensure_float("  42 ") == 42.0


class TestSafeDiv:
    def test_normal_division(self):
        assert _safe_div(10.0, 2.0) == 5.0

    def test_division_by_zero_returns_zero(self):
        assert _safe_div(10.0, 0.0) == 0.0

    def test_zero_numerator(self):
        assert _safe_div(0.0, 5.0) == 0.0


# ---------------------------------------------------------------------------
# _normalize_freq / _freq_rank
# ---------------------------------------------------------------------------

class TestNormalizeFreq:
    @pytest.mark.parametrize("inp,expected", [
        ("daily", "daily"), ("D", "daily"), ("d", "daily"),
        ("weekly", "weekly"), ("W", "weekly"),
        ("monthly", "monthly"), ("M", "monthly"),
        ("", "daily"),  # default w ledger_primitives jest "daily" (inny niz task_config!)
    ])
    def test_normalize(self, inp, expected):
        assert _normalize_freq(inp) == expected

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _normalize_freq("yearly")

    def test_freq_rank_ordering(self):
        assert _freq_rank("daily") < _freq_rank("weekly") < _freq_rank("monthly")


# ---------------------------------------------------------------------------
# _infer_price_freq
# ---------------------------------------------------------------------------

class TestInferPriceFreq:
    def test_daily_index(self):
        idx = pd.date_range("2024-01-01", periods=30, freq="D")
        assert _infer_price_freq(idx) == "daily"

    def test_weekly_index(self):
        idx = pd.date_range("2024-01-01", periods=20, freq="7D")
        assert _infer_price_freq(idx) == "weekly"

    def test_monthly_index(self):
        idx = pd.date_range("2020-01-31", periods=24, freq="ME")
        assert _infer_price_freq(idx) == "monthly"

    def test_too_short_index_is_unknown(self):
        idx = pd.DatetimeIndex(["2024-01-01", "2024-01-02"])
        assert _infer_price_freq(idx) == "unknown"

    def test_empty_index_is_unknown(self):
        idx = pd.DatetimeIndex([])
        assert _infer_price_freq(idx) == "unknown"


# ---------------------------------------------------------------------------
# _resample_prices_to_freq — zasada zakazu upsamplingu
# ---------------------------------------------------------------------------

class TestResamplePricesToFreq:
    def _monthly_df(self, n=24):
        idx = pd.date_range("2020-01-31", periods=n, freq="ME")
        return pd.DataFrame({"A": range(n)}, index=idx)

    def _daily_df(self, n=400):
        idx = pd.date_range("2020-01-01", periods=n, freq="D")
        return pd.DataFrame({"A": range(n)}, index=idx)

    def test_daily_passthrough(self):
        df = self._daily_df()
        out = _resample_prices_to_freq(df, ["A"], "daily")
        assert len(out) == len(df)

    def test_monthly_resample_from_daily(self):
        df = self._daily_df()
        out = _resample_prices_to_freq(df, ["A"], "monthly")
        # ~13 miesiecy w 400 dniach
        assert 12 <= len(out) <= 14
        # kazdy index jest koncem miesiaca z dostepnych danych
        assert out.index.is_monotonic_increasing

    def test_monthly_db_cannot_serve_weekly(self):
        """Zakaz upsamplingu: DB monthly nie moze udawac weekly."""
        df = self._monthly_df()
        with pytest.raises(ValueError, match="upsamplingu"):
            _resample_prices_to_freq(df, ["A"], "weekly")

    def test_monthly_db_cannot_serve_daily(self):
        df = self._monthly_df()
        with pytest.raises(ValueError, match="upsamplingu"):
            _resample_prices_to_freq(df, ["A"], "daily")

    def test_monthly_db_serves_monthly(self):
        df = self._monthly_df()
        out = _resample_prices_to_freq(df, ["A"], "monthly")
        assert len(out) == len(df)

    def test_daily_db_can_serve_monthly_and_weekly(self):
        df = self._daily_df()
        out_m = _resample_prices_to_freq(df, ["A"], "monthly")
        out_w = _resample_prices_to_freq(df, ["A"], "weekly")
        assert len(out_w) > len(out_m)


# ---------------------------------------------------------------------------
# _pick_last_available_in_period / _effective_ledger_end
# ---------------------------------------------------------------------------

class TestPickLastAvailable:
    def test_finds_last_date_in_range(self):
        idx = pd.DatetimeIndex(["2024-01-05", "2024-01-15", "2024-01-25", "2024-02-05"])
        result = _pick_last_available_in_period(idx, dt.date(2024, 1, 1), dt.date(2024, 1, 31))
        assert result == dt.date(2024, 1, 25)

    def test_no_dates_in_range_returns_none(self):
        idx = pd.DatetimeIndex(["2024-02-05"])
        result = _pick_last_available_in_period(idx, dt.date(2024, 1, 1), dt.date(2024, 1, 31))
        assert result is None


class TestEffectiveLedgerEnd:
    def test_daily_picks_last_available_before_end_ref(self):
        idx = pd.date_range("2024-01-01", "2024-01-10", freq="D")
        result = _effective_ledger_end(idx, "daily", dt.date(2024, 1, 8))
        assert result == dt.date(2024, 1, 8)

    def test_daily_end_ref_after_last_data(self):
        idx = pd.date_range("2024-01-01", "2024-01-10", freq="D")
        result = _effective_ledger_end(idx, "daily", dt.date(2024, 1, 31))
        assert result == dt.date(2024, 1, 10)

    def test_monthly_complete_month(self):
        idx = pd.date_range("2024-01-01", "2024-03-31", freq="D")
        result = _effective_ledger_end(idx, "monthly", dt.date(2024, 3, 15))
        # 15 marca nie jest koncem miesiaca -> bierzemy ostatni pelny miesiac (luty)
        assert result == dt.date(2024, 2, 29)

    def test_monthly_at_month_end(self):
        idx = pd.date_range("2024-01-01", "2024-03-31", freq="D")
        result = _effective_ledger_end(idx, "monthly", dt.date(2024, 3, 31))
        assert result == dt.date(2024, 3, 31)

    def test_empty_index_raises(self):
        with pytest.raises(ValueError, match="Brak dat"):
            _effective_ledger_end(pd.DatetimeIndex([]), "daily", dt.date(2024, 1, 1))


# ---------------------------------------------------------------------------
# _attach_fx_to_prices
# ---------------------------------------------------------------------------

class TestAttachFxToPrices:
    def _prices(self, freq="ME", n=12, start="2020-01-31"):
        idx = pd.date_range(start, periods=n, freq=freq)
        idx.name = "DATE"
        return pd.DataFrame({"A": [100.0 + i for i in range(n)]}, index=idx)

    def _fx(self, n=400, start="2020-01-01"):
        idx = pd.date_range(start, periods=n, freq="D")
        idx.name = "DATE"
        return pd.DataFrame({"USD/PLN": [4.0 + i * 0.001 for i in range(n)]}, index=idx)

    def test_daily_inner_join(self):
        prices = self._prices(freq="D", n=10, start="2020-01-01")
        fx = self._fx(n=10, start="2020-01-01")
        out = _attach_fx_to_prices(prices, fx, ["A"], "daily")
        assert "USD/PLN" in out.columns
        assert len(out) == 10

    def test_daily_no_overlap_raises(self):
        prices = self._prices(freq="D", n=5, start="2020-01-01")
        fx = self._fx(n=5, start="2021-01-01")
        with pytest.raises(ValueError, match="wspólnych sesji"):
            _attach_fx_to_prices(prices, fx, ["A"], "daily")

    def test_monthly_uses_last_known_fx_no_lookahead(self):
        """FX musi byc <= data wyceny (merge_asof backward)."""
        prices = self._prices(freq="ME", n=3, start="2020-01-31")
        fx = self._fx(n=400, start="2020-01-01")
        out = _attach_fx_to_prices(prices, fx, ["A"], "monthly")
        assert len(out) == 3
        assert "USD/PLN" in out.columns
        # Sprawdz no-lookahead: FX dla 2020-01-31 nie moze byc z przyszlosci
        for date, row in out.iterrows():
            matching_fx = fx[fx.index <= date]
            assert row["USD/PLN"] == matching_fx["USD/PLN"].iloc[-1]

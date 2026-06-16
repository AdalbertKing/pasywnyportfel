# pasywnyportfel — testy ledger_tax.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
Testy dla app/bin/ledger_tax.py — model opodatkowania strat (Belka).

UWAGA: te testy zlapaly regresje VER 2.2.5A — podczas podzialu modulow
zniknal dekorator @dataclass z LossBucket, co czynilo klase nie-instancjonowalna
("LossBucket() takes no arguments"). Test test_lossbucket_is_constructable
pilnuje tego na przyszlosc.
"""

import pytest

from ledger_tax import LossBucket, apply_loss_buckets


# ---------------------------------------------------------------------------
# LossBucket — regresja @dataclass
# ---------------------------------------------------------------------------

class TestLossBucketConstruction:
    def test_lossbucket_is_constructable(self):
        """Regresja: @dataclass musi byc obecny, inaczej LossBucket() nie przyjmuje argumentow."""
        b = LossBucket(year=2020, original=1000.0, remaining=1000.0, used_this_year={})
        assert b.year == 2020
        assert b.original == 1000.0
        assert b.remaining == 1000.0
        assert b.used_this_year == {}

    def test_lossbucket_fields_mutable(self):
        b = LossBucket(year=2020, original=1000.0, remaining=1000.0, used_this_year={})
        b.remaining -= 300.0
        assert b.remaining == 700.0

    def test_lossbucket_repr_contains_fields(self):
        """@dataclass generuje __repr__ — bez niego repr() byloby <ledger_tax.LossBucket object at ...>."""
        b = LossBucket(year=2020, original=1000.0, remaining=1000.0, used_this_year={})
        r = repr(b)
        assert "year=2020" in r
        assert "original=1000.0" in r


# ---------------------------------------------------------------------------
# apply_loss_buckets
# ---------------------------------------------------------------------------

class TestApplyLossBuckets:
    def test_no_buckets_no_deduction(self):
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=1000.0, buckets=[],
            window_years=5, annual_cap_frac=1.0,
        )
        assert deducted == 0.0
        assert taxable == 1000.0

    def test_full_deduction_within_cap(self):
        buckets = [LossBucket(year=2020, original=500.0, remaining=500.0, used_this_year={})]
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=1000.0, buckets=buckets,
            window_years=5, annual_cap_frac=1.0,
        )
        assert deducted == 500.0
        assert taxable == 500.0
        # Koszyk w pelni zuzyty (remaining<=1e-9) jest usuwany z listy przez funkcje
        assert buckets == []

    def test_partial_deduction_limited_by_taxable(self):
        buckets = [LossBucket(year=2020, original=2000.0, remaining=2000.0, used_this_year={})]
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=300.0, buckets=buckets,
            window_years=5, annual_cap_frac=1.0,
        )
        assert deducted == 300.0
        assert taxable == 0.0
        assert buckets[0].remaining == pytest.approx(1700.0)

    def test_annual_cap_limits_single_year_deduction(self):
        """annual_cap_frac=0.5 -> max 50% z original w jednym roku."""
        buckets = [LossBucket(year=2020, original=1000.0, remaining=1000.0, used_this_year={})]
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=1000.0, buckets=buckets,
            window_years=5, annual_cap_frac=0.5,
        )
        assert deducted == 500.0
        assert taxable == 500.0
        assert buckets[0].remaining == 500.0

    def test_cannot_deduct_in_same_year_as_loss(self):
        """Strata z roku Y nie moze byc odliczona w roku Y (year <= b.year -> skip)."""
        buckets = [LossBucket(year=2021, original=1000.0, remaining=1000.0, used_this_year={})]
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=1000.0, buckets=buckets,
            window_years=5, annual_cap_frac=1.0,
        )
        assert deducted == 0.0
        assert taxable == 1000.0

    def test_bucket_expires_after_window_years(self):
        """Koszyk z 2015 r. z window_years=5 nie zyje juz w 2021."""
        buckets = [LossBucket(year=2015, original=1000.0, remaining=1000.0, used_this_year={})]
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=1000.0, buckets=buckets,
            window_years=5, annual_cap_frac=1.0,
        )
        assert deducted == 0.0
        assert taxable == 1000.0
        assert len(buckets) == 0  # wygasly koszyk usuniety

    def test_bucket_alive_at_exactly_window_boundary(self):
        """year <= b.year + window_years -> 2015+5=2020, rok 2020 wciaz zywy."""
        buckets = [LossBucket(year=2015, original=1000.0, remaining=1000.0, used_this_year={})]
        deducted, taxable = apply_loss_buckets(
            year=2020, positive_net=1000.0, buckets=buckets,
            window_years=5, annual_cap_frac=1.0,
        )
        assert deducted == 1000.0

    def test_fifo_order_across_multiple_buckets(self):
        """Starsza strata (2018) odliczana przed nowsza (2020)."""
        buckets = [
            LossBucket(year=2020, original=500.0, remaining=500.0, used_this_year={}),
            LossBucket(year=2018, original=300.0, remaining=300.0, used_this_year={}),
        ]
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=400.0, buckets=buckets,
            window_years=5, annual_cap_frac=1.0,
        )
        # 2018 (300, starszy) zuzyty w calosci jako pierwszy -> usuniety z listy.
        # Pozostale 100 odliczone z 2020 (500 -> 400).
        assert deducted == 400.0
        assert taxable == 0.0
        assert len(buckets) == 1
        assert buckets[0].year == 2020
        assert buckets[0].remaining == pytest.approx(400.0)

    def test_used_this_year_tracked_across_calls(self):
        """Limit roczny obowiazuje sumarycznie, nawet przy wielu wywolaniach w tym samym roku."""
        buckets = [LossBucket(year=2018, original=1000.0, remaining=1000.0, used_this_year={})]
        d1, _ = apply_loss_buckets(2021, 400.0, buckets, window_years=5, annual_cap_frac=0.5)
        d2, _ = apply_loss_buckets(2021, 400.0, buckets, window_years=5, annual_cap_frac=0.5)
        # cap=500 (50% z 1000); pierwsze wywolanie zuzywa 400, drugie max 100
        assert d1 == 400.0
        assert d2 == 100.0
        assert buckets[0].used_this_year[2021] == 500.0

    def test_zero_or_negative_positive_net(self):
        buckets = [LossBucket(year=2020, original=500.0, remaining=500.0, used_this_year={})]
        deducted, taxable = apply_loss_buckets(
            year=2021, positive_net=0.0, buckets=buckets,
            window_years=5, annual_cap_frac=1.0,
        )
        assert deducted == 0.0
        assert taxable == 0.0
        assert buckets[0].remaining == 500.0  # nic nie zuzyte

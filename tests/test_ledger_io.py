# pasywnyportfel — testy ledger_io.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""Testy dla app/bin/ledger_io.py — odczyt baz cen i CPI."""

import csv
from pathlib import Path

import pandas as pd
import pytest

from ledger_io import read_cpi_csv, read_wide_db_csv


# ---------------------------------------------------------------------------
# read_wide_db_csv
# ---------------------------------------------------------------------------

class TestReadWideDbCsv:
    def test_basic_nam_isin_format(self, tmp_path: Path):
        """Format jak DB_FX.csv: NAME/ISIN + daty (brak wiersza TICKER -> fallback do header)."""
        p = tmp_path / "db.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["NAME", "ASSET_A", "ASSET_B"])
            w.writerow(["ISIN", "A001", "B001"])
            w.writerow(["2020-01-31", "100.0", "200.0"])
            w.writerow(["2020-02-29", "101.0", "202.0"])

        meta, df = read_wide_db_csv(str(p))
        assert meta["TICKER"] == ["ASSET_A", "ASSET_B"]
        assert list(df.columns) == ["ASSET_A", "ASSET_B"]
        assert len(df) == 2
        assert df.iloc[0]["ASSET_A"] == 100.0
        assert df.iloc[1]["ASSET_B"] == 202.0

    def test_explicit_ticker_row(self, tmp_path: Path):
        p = tmp_path / "db.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["NAME", "Asset A", "Asset B"])
            w.writerow(["TICKER", "AAA", "BBB"])
            w.writerow(["2020-01-31", "100.0", "200.0"])

        meta, df = read_wide_db_csv(str(p))
        assert meta["TICKER"] == ["AAA", "BBB"]
        assert list(df.columns) == ["AAA", "BBB"]

    def test_missing_values_become_nan(self, tmp_path: Path):
        p = tmp_path / "db.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["NAME", "A", "B"])
            w.writerow(["2020-01-31", "100.0", ""])
            w.writerow(["2020-02-29", "", "202.0"])

        meta, df = read_wide_db_csv(str(p))
        assert pd.isna(df.iloc[0]["B"])
        assert pd.isna(df.iloc[1]["A"])

    def test_index_is_datetime(self, tmp_path: Path):
        p = tmp_path / "db.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["NAME", "A"])
            w.writerow(["2020-01-31", "100.0"])

        _, df = read_wide_db_csv(str(p))
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_no_metadata_rows_raises(self, tmp_path: Path):
        p = tmp_path / "db.csv"
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["2020-01-31", "100.0"])

        with pytest.raises(ValueError, match="metadanych"):
            read_wide_db_csv(str(p))

    def test_real_synth_library(self, project_root: Path):
        p = project_root / "data" / "in" / "libraries" / "SYNTH_LIBRARY_MONTHLY_USD.csv"
        meta, df = read_wide_db_csv(str(p))
        assert "US_STOCKS_TR" in meta["TICKER"]
        assert "US_STOCKS_TR" in df.columns
        assert len(df) > 1000  # dane od 1833

    def test_real_db_fx(self, project_root: Path):
        p = project_root / "data" / "in" / "fx" / "DB_FX.csv"
        meta, df = read_wide_db_csv(str(p))
        assert "USD/PLN" in df.columns


# ---------------------------------------------------------------------------
# read_cpi_csv
# ---------------------------------------------------------------------------

class TestReadCpiCsv:
    def _write_cpi(self, tmp_path, rows, extra_cols=""):
        p = tmp_path / "cpi.csv"
        header = "date,cpi" + extra_cols
        body = "\n".join(",".join(map(str, r)) for r in rows)
        p.write_text(header + "\n" + body + "\n", encoding="utf-8")
        return p

    def test_basic_format(self, tmp_path: Path):
        p = self._write_cpi(tmp_path, [
            ("2020-01-01", 100.0),
            ("2020-02-01", 101.0),
            ("2020-03-01", 102.0),
        ])
        cpi = read_cpi_csv(str(p))
        assert list(cpi.columns) == ["cpi", "infl_mom", "infl_yoy"]
        assert len(cpi) == 3

    def test_computes_infl_mom_when_missing(self, tmp_path: Path):
        p = self._write_cpi(tmp_path, [
            ("2020-01-01", 100.0),
            ("2020-02-01", 102.0),
        ])
        cpi = read_cpi_csv(str(p))
        assert cpi["infl_mom"].iloc[1] == pytest.approx(0.02)

    def test_computes_infl_yoy_when_missing(self, tmp_path: Path):
        rows = [(f"2020-{m:02d}-01", 100.0 + m) for m in range(1, 13)]
        rows.append(("2021-01-01", 113.0))
        p = self._write_cpi(tmp_path, rows)
        cpi = read_cpi_csv(str(p))
        # 13ty wiersz (2021-01) ma 12-miesieczny pct_change wzgledem 2020-01 (=101)
        assert cpi["infl_yoy"].iloc[-1] == pytest.approx((113.0 - 101.0) / 101.0)

    def test_sorted_by_date(self, tmp_path: Path):
        p = self._write_cpi(tmp_path, [
            ("2020-03-01", 102.0),
            ("2020-01-01", 100.0),
            ("2020-02-01", 101.0),
        ])
        cpi = read_cpi_csv(str(p))
        assert list(cpi.index) == sorted(cpi.index)

    def test_missing_required_columns_raises(self, tmp_path: Path):
        p = tmp_path / "cpi.csv"
        p.write_text("date,value\n2020-01-01,100\n", encoding="utf-8")
        with pytest.raises(ValueError, match="date,cpi"):
            read_cpi_csv(str(p))

    def test_ffill_on_nonnumeric_cpi(self, tmp_path: Path):
        p = tmp_path / "cpi.csv"
        p.write_text("date,cpi\n2020-01-01,100\n2020-02-01,N/A\n2020-03-01,102\n", encoding="utf-8")
        cpi = read_cpi_csv(str(p))
        assert cpi["cpi"].iloc[1] == 100.0  # forward-filled

    def test_real_cpi_usd(self, project_root: Path):
        p = project_root / "data" / "in" / "cpi" / "CPI_USD.csv"
        cpi = read_cpi_csv(str(p))
        assert len(cpi) > 100
        assert cpi["cpi"].iloc[-1] > cpi["cpi"].iloc[0]  # inflacja dlugoterminowo > 0

    def test_real_cpi_pln(self, project_root: Path):
        p = project_root / "data" / "in" / "cpi" / "CPI_PLN_GUS.csv"
        if not p.exists():
            pytest.skip("brak CPI_PLN_GUS.csv")
        cpi = read_cpi_csv(str(p))
        assert len(cpi) > 100

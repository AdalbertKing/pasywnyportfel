# pasywnyportfel — konfiguracja testow pytest
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
conftest.py — wspolna konfiguracja dla wszystkich testow.

Dodaje app/bin do sys.path, dzieki czemu testy moga robic:
    from common import bool_setting
    from ledger_engine import simulate_ledger
bez wzgledu na to skad pytest jest odpalany.
"""

import csv
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = ROOT / "app" / "bin"

if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Sciezka do katalogu glownego projektu."""
    return ROOT


@pytest.fixture(scope="session")
def cpi_us_csv(project_root: Path) -> Path:
    """Prawdziwy plik CPI USD z projektu (uzywany w testach ledger_engine)."""
    p = project_root / "data" / "in" / "cpi" / "CPI_USD.csv"
    if not p.exists():
        pytest.skip(f"brak {p} — uruchom refresh_data.cmd")
    return p


@pytest.fixture()
def synth_portfolio_csv(tmp_path: Path) -> Path:
    """Minimalny portfel 1-skladnikowy w formacie maps/synth/*.csv."""
    p = tmp_path / "portfolio.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Ticker", "ISIN", "ASSET", "CCY", "WEIGHT", "COST", "LIB_COL", "NAME"])
        w.writerow(["TEST_ASSET", "TEST001", "SHARES", "USD", "100", "0", "", "Test Asset"])
    return p


@pytest.fixture()
def two_asset_portfolio_csv(tmp_path: Path) -> Path:
    """Portfel 2-skladnikowy 50/50, do testow rebalansu DRIFT."""
    p = tmp_path / "portfolio_2.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Ticker", "ISIN", "ASSET", "CCY", "WEIGHT", "COST", "LIB_COL", "NAME"])
        w.writerow(["ASSET_A", "A001", "SHARES", "USD", "50", "0", "", "Asset A"])
        w.writerow(["ASSET_B", "B001", "SHARES", "USD", "50", "0", "", "Asset B"])
    return p


@pytest.fixture()
def wide_price_db_csv(tmp_path: Path):
    """
    Generator: zwraca funkcje budujaca wide-format DB cen
    (format jak na wyjsciu build_db_synthetic.py).

    Uzycie:
        path = wide_price_db_csv(["TEST_ASSET"], n_months=60, start="2005-01-31",
                                  growth={"TEST_ASSET": 0.07})
    """
    def _make(tickers, n_months=60, start="2005-01-31", growth=None, base=100.0):
        growth = growth or {t: 0.07 for t in tickers}
        dates = pd.date_range(start, periods=n_months, freq="ME")
        path = tmp_path / ("DB_" + "_".join(tickers) + ".csv")
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["NAME"] + tickers)
            w.writerow(["ISIN"] + [f"{t}_ISIN" for t in tickers])
            for i, d in enumerate(dates):
                row = [d.strftime("%Y-%m-%d")]
                for t in tickers:
                    g = growth.get(t, 0.07)
                    row.append(f"{base * (1.0 + g) ** (i / 12):.6f}")
                w.writerow(row)
        return path

    return _make

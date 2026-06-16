# pasywnyportfel — testy task_config.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""Testy dla app/bin/task_config.py — odczyt i interpretacja konfiguracji taska."""

import datetime as dt
from pathlib import Path

import pytest

from task_config import (
    freq_suffix,
    has_pln_outputs,
    is_hist_only,
    is_synth_only,
    normalize_freq_token,
    plot_currencies,
    read_portfolios,
    require_file,
    require_task_file,
    resolve_auto_dates,
    setting_value,
    validate_tax_settings,
)


# ---------------------------------------------------------------------------
# setting_value
# ---------------------------------------------------------------------------

class TestSettingValue:
    def test_returns_value(self):
        assert setting_value({"k": "v"}, "k") == "v"

    def test_returns_default_when_missing(self):
        assert setting_value({}, "k", "default") == "default"

    def test_strips_whitespace(self):
        assert setting_value({"k": "  v  "}, "k") == "v"

    def test_present_none_value_returns_empty_not_default(self):
        """
        Brzegowy przypadek: gdy klucz ISTNIEJE z wartoscia None, funkcja zwraca ""
        a nie default — `settings.get(key, default) or ""` zwraca "" dla None.
        Default dziala tylko gdy klucza brak. W praktyce read_settings() nigdy
        nie produkuje None (zawsze str), wiec ten przypadek nie wystepuje
        w realnych ustawieniach — test dokumentuje obecne zachowanie.
        """
        assert setting_value({"k": None}, "k", "default") == ""


# ---------------------------------------------------------------------------
# is_synth_only / is_hist_only
# ---------------------------------------------------------------------------

class TestAnalysisMode:
    @pytest.mark.parametrize("mode", ["synth", "synthetic", "synth_only", "SYNTH"])
    def test_synth_only_true(self, mode):
        assert is_synth_only({"analysis_mode": mode}) is True

    @pytest.mark.parametrize("mode", ["hist", "etf", "historical", "HIST_ONLY"])
    def test_hist_only_true(self, mode):
        assert is_hist_only({"analysis_mode": mode}) is True

    def test_default_settings_neither(self):
        assert is_synth_only({}) is False
        assert is_hist_only({}) is False

    def test_falls_back_to_datasets_key(self):
        assert is_synth_only({"datasets": "synth_only"}) is True

    def test_full_mode_neither(self):
        assert is_synth_only({"analysis_mode": "full"}) is False
        assert is_hist_only({"analysis_mode": "full"}) is False


# ---------------------------------------------------------------------------
# normalize_freq_token / freq_suffix
# ---------------------------------------------------------------------------

class TestFreqTokens:
    @pytest.mark.parametrize("inp,expected", [
        ("daily", "daily"), ("D", "daily"), ("d", "daily"),
        ("weekly", "weekly"), ("W", "weekly"),
        ("monthly", "monthly"), ("M", "monthly"), ("m", "monthly"),
        ("", "monthly"),  # default
    ])
    def test_normalize(self, inp, expected):
        assert normalize_freq_token(inp) == expected

    def test_invalid_freq_raises(self):
        with pytest.raises(ValueError):
            normalize_freq_token("yearly")

    @pytest.mark.parametrize("inp,expected", [
        ("daily", "D"), ("weekly", "W"), ("monthly", "M"), ("D", "D"),
    ])
    def test_freq_suffix(self, inp, expected):
        assert freq_suffix(inp) == expected


# ---------------------------------------------------------------------------
# resolve_auto_dates
# ---------------------------------------------------------------------------

class TestResolveAutoDates:
    def test_explicit_dates_pass_through(self):
        out = resolve_auto_dates({"start": "2005-01-31", "end": "2026-03-31"})
        assert out["start"] == "2005-01-31"
        assert out["end"] == "2026-03-31"

    def test_records_requested_values(self):
        out = resolve_auto_dates({"start": "2005-01-31", "end": "2026-03-31"})
        assert out["_start_requested"] == "2005-01-31"
        assert out["_end_requested"] == "2026-03-31"

    def test_auto_end_resolves_to_today(self):
        out = resolve_auto_dates({"start": "2005-01-31", "end": "AUTO"})
        assert out["end"] == dt.date.today().isoformat()

    def test_lookback_months_with_auto_start(self):
        out = resolve_auto_dates({"start": "AUTO", "end": "2026-06-30", "lookback_months": "3"})
        assert out["start"] == "2026-03-30"
        assert "lookback_months" in out["_start_resolved_reason"]

    def test_lookback_months_with_empty_start(self):
        out = resolve_auto_dates({"start": "", "end": "2026-06-30", "lookback_months": "12"})
        assert out["start"] == "2025-06-30"

    def test_lookback_ignored_when_start_explicit(self):
        out = resolve_auto_dates({"start": "2000-01-01", "end": "2026-06-30", "lookback_months": "12"})
        assert out["start"] == "2000-01-01"

    def test_auto_minus_n_start(self):
        """AUTO-1Y dla start jest rozwiazywane wzgledem dzisiejszej daty, nie wzgledem end."""
        from dateutil.relativedelta import relativedelta
        out = resolve_auto_dates({"start": "AUTO-1Y", "end": "2026-06-12"})
        expected = (dt.date.today() - relativedelta(years=1)).isoformat()
        assert out["start"] == expected


# ---------------------------------------------------------------------------
# has_pln_outputs / plot_currencies
# ---------------------------------------------------------------------------

class TestPlnOutputs:
    def test_full_pln_config(self):
        settings = {
            "fx": "data/in/fx/DB_FX.csv",
            "cpi_pl": "data/in/cpi/CPI_PLN_GUS.csv",
        }
        assert has_pln_outputs(settings) is True

    def test_make_pln_false_disables(self):
        settings = {
            "make_pln": "0",
            "fx": "data/in/fx/DB_FX.csv",
            "cpi_pl": "data/in/cpi/CPI_PLN_GUS.csv",
        }
        assert has_pln_outputs(settings) is False

    def test_missing_fx_disables(self):
        assert has_pln_outputs({"cpi_pl": "x.csv"}) is False

    def test_empty_settings_disables(self):
        assert has_pln_outputs({}) is False


class TestPlotCurrencies:
    def test_default_usd_only(self):
        assert plot_currencies({}) == ["USD"]

    def test_usd_and_pln_when_pln_available(self):
        settings = {"fx": "x.csv", "cpi_pl": "y.csv"}
        assert plot_currencies(settings) == ["USD", "PLN"]

    def test_explicit_list(self):
        assert plot_currencies({"plot_currencies": "PLN,USD"}) == ["PLN", "USD"]

    def test_explicit_list_dedup_and_filter_invalid(self):
        out = plot_currencies({"plot_currencies": "USD,EUR,USD,PLN"})
        assert out == ["USD", "PLN"]

    def test_explicit_empty_falls_back_to_default(self):
        assert plot_currencies({"plot_currencies": "EUR"}) == ["USD"]


# ---------------------------------------------------------------------------
# read_portfolios
# ---------------------------------------------------------------------------

class TestReadPortfolios:
    def _write(self, tmp_path, rows):
        p = tmp_path / "portfolios.csv"
        header = "ID,LABEL,REBALANCE,MAX_DRIFT,MAP_SYNTH,MAP_HIST,INCLUDE\n"
        body = "".join(",".join(r) + "\n" for r in rows)
        p.write_text(header + body, encoding="utf-8")
        return p

    def test_reads_included_rows(self, tmp_path):
        p = self._write(tmp_path, [
            ("a", "A", "BH", "", "maps/synth/a.csv", "maps/hist/a.csv", "1"),
            ("b", "B", "DRIFT", "20", "maps/synth/b.csv", "maps/hist/b.csv", "1"),
        ])
        rows = read_portfolios(p)
        assert len(rows) == 2
        assert rows[0]["ID"] == "a"

    def test_excludes_include_zero(self, tmp_path):
        p = self._write(tmp_path, [
            ("a", "A", "BH", "", "x.csv", "y.csv", "0"),
            ("b", "B", "BH", "", "x.csv", "y.csv", "1"),
        ])
        rows = read_portfolios(p)
        assert len(rows) == 1
        assert rows[0]["ID"] == "b"

    def test_default_include_is_one(self, tmp_path):
        """Brak kolumny INCLUDE / brak wartosci traktowane jako wlaczone."""
        p = tmp_path / "portfolios.csv"
        p.write_text("ID,LABEL\na,Portfel A\n", encoding="utf-8")
        rows = read_portfolios(p)
        assert len(rows) == 1

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_portfolios(tmp_path / "nope.csv")

    def test_real_project_file(self, project_root: Path):
        p = project_root / "analysis_definitions" / "user_template" / "portfolios.csv"
        rows = read_portfolios(p)
        assert len(rows) >= 1
        assert "MAP_SYNTH" in rows[0]


# ---------------------------------------------------------------------------
# require_file / require_task_file
# ---------------------------------------------------------------------------

class TestRequireFile:
    def test_existing_file(self, project_root: Path):
        p = require_file(project_root, "data/in/cpi/CPI_USD.csv", "CPI USD")
        assert p.exists()

    def test_missing_file_raises_with_label(self, project_root: Path):
        with pytest.raises(FileNotFoundError, match="MOJA_ETYKIETA"):
            require_file(project_root, "no/such/file.csv", "MOJA_ETYKIETA")

    def test_require_task_file_existing(self, project_root: Path):
        task_dir = project_root / "analysis_definitions" / "user_template"
        p = require_task_file(project_root, task_dir, r"maps\synth\my_portfolio_sp500_syn.csv", "MAP_SYNTH")
        assert p.exists()

    def test_require_task_file_missing_includes_expected_path(self, project_root: Path):
        task_dir = project_root / "analysis_definitions" / "user_template"
        with pytest.raises(FileNotFoundError, match="oczekiwana"):
            require_task_file(project_root, task_dir, "maps/synth/nope.csv", "MAP_SYNTH")


# ---------------------------------------------------------------------------
# validate_tax_settings
# ---------------------------------------------------------------------------

class TestValidateTaxSettings:
    @pytest.mark.parametrize("tax_mode", ["", "gross", "none", "off", "0"])
    def test_gross_modes_pass(self, tax_mode):
        validate_tax_settings({"tax_mode": tax_mode})  # nie rzuca

    def test_net_without_tax_base_raises(self):
        with pytest.raises(ValueError, match="tax_base"):
            validate_tax_settings({"tax_mode": "net"})

    def test_net_with_invalid_tax_base_raises(self):
        with pytest.raises(ValueError, match="PLN albo USD"):
            validate_tax_settings({"tax_mode": "net", "tax_base": "EUR"})

    def test_net_pln_without_fx_raises(self):
        with pytest.raises(ValueError, match="fx"):
            validate_tax_settings({"tax_mode": "net", "tax_base": "PLN"})

    def test_net_pln_with_fx_passes(self):
        validate_tax_settings({"tax_mode": "net", "tax_base": "PLN", "fx": "data/in/fx/DB_FX.csv"})

    def test_net_usd_passes_without_fx(self):
        """tax_base=USD to model pogladowy — nie wymaga fx."""
        validate_tax_settings({"tax_mode": "net", "tax_base": "USD"})

    def test_invalid_tax_mode_raises(self):
        with pytest.raises(ValueError, match="tax_mode"):
            validate_tax_settings({"tax_mode": "weird"})

# pasywnyportfel — testy common.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""Testy dla app/bin/common.py — narzedzia sciezkowe i bool."""

import datetime as dt
import os
from pathlib import Path

import pytest

from common import (
    bool_setting,
    detect_root,
    norm_path,
    read_settings,
    rel,
    resolve_auto_date_token,
    task_rel,
    truthy,
)


# ---------------------------------------------------------------------------
# norm_path
# ---------------------------------------------------------------------------

class TestNormPath:
    def test_backslash_to_separator(self):
        expected = f"data{os.sep}in{os.sep}cpi{os.sep}CPI_USD.csv"
        assert norm_path(r"data\in\cpi\CPI_USD.csv") == expected

    def test_forward_slash_to_separator(self):
        expected = f"data{os.sep}in{os.sep}cpi{os.sep}CPI_USD.csv"
        assert norm_path("data/in/cpi/CPI_USD.csv") == expected

    def test_strips_quotes(self):
        expected = f"data{os.sep}in{os.sep}cpi{os.sep}CPI_USD.csv"
        assert norm_path('"data/in/cpi/CPI_USD.csv"') == expected

    def test_strips_whitespace(self):
        expected = f"data{os.sep}in{os.sep}cpi.csv"
        assert norm_path("  data/in/cpi.csv  ") == expected

    def test_empty_string(self):
        assert norm_path("") == ""


# ---------------------------------------------------------------------------
# detect_root
# ---------------------------------------------------------------------------

class TestDetectRoot:
    def test_default_auto_returns_project_root(self, project_root: Path):
        root = detect_root()
        assert root == project_root

    def test_explicit_auto(self, project_root: Path):
        assert detect_root("AUTO") == project_root

    def test_explicit_path(self, tmp_path: Path):
        result = detect_root(str(tmp_path))
        assert result == tmp_path.resolve()


# ---------------------------------------------------------------------------
# rel — rozwiazywanie sciezek projektowych z backward compat
# ---------------------------------------------------------------------------

class TestRel:
    def test_new_style_path_exists(self, project_root: Path):
        p = rel(project_root, "data/in/cpi/CPI_USD.csv")
        assert p.exists(), f"oczekiwany plik nie istnieje: {p}"

    def test_old_style_in_prefix_backward_compat(self, project_root: Path):
        """Stara sciezka in\\cpi\\... powinna trafic do data\\in\\cpi\\..."""
        p = rel(project_root, r"in\cpi\CPI_USD.csv")
        assert p.exists()
        assert p == project_root / "data" / "in" / "cpi" / "CPI_USD.csv"

    def test_absolute_path_returned_as_is(self, project_root: Path, tmp_path: Path):
        abs_path = tmp_path / "somefile.csv"
        result = rel(project_root, str(abs_path))
        assert result == abs_path

    def test_nonexistent_path_returns_first_candidate(self, project_root: Path):
        p = rel(project_root, "no/such/file.csv")
        assert p == project_root / "no/such/file.csv"


# ---------------------------------------------------------------------------
# task_rel — rozwiazywanie sciezek w kontekscie taska
# ---------------------------------------------------------------------------

class TestTaskRel:
    def test_map_in_task_dir(self, project_root: Path):
        task_dir = project_root / "analysis_definitions" / "user_template"
        p = task_rel(project_root, task_dir, r"maps\synth\my_portfolio_sp500_syn.csv")
        assert p.exists()
        assert p.parent.parent.parent == task_dir

    def test_project_level_path_via_root(self, project_root: Path):
        task_dir = project_root / "analysis_definitions" / "user_template"
        p = task_rel(project_root, task_dir, "data/in/cpi/CPI_USD.csv")
        assert p.exists()

    def test_none_task_dir_falls_back_to_root(self, project_root: Path):
        p = task_rel(project_root, None, "data/in/cpi/CPI_USD.csv")
        assert p.exists()


# ---------------------------------------------------------------------------
# truthy
# ---------------------------------------------------------------------------

class TestTruthy:
    @pytest.mark.parametrize("value", ["1", "yes", "tak", "TRUE", "true", "On", "anything"])
    def test_truthy_values(self, value):
        assert truthy(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "no", "nie", "off", "", "  "])
    def test_falsy_values(self, value):
        assert truthy(value) is False


# ---------------------------------------------------------------------------
# bool_setting — w tym poprawka buga z VER 2.2.5A
# ---------------------------------------------------------------------------

class TestBoolSetting:
    def test_missing_key_returns_default_true(self):
        assert bool_setting({}, "make_plots", True) is True

    def test_missing_key_returns_default_false(self):
        assert bool_setting({}, "make_plots", False) is False

    def test_empty_value_returns_default_true(self):
        """Regresja: puste VALUE w settings.csv musi zwracac default, nie True."""
        assert bool_setting({"make_plots": ""}, "make_plots", True) is True

    def test_empty_value_returns_default_false(self):
        """Regresja: ten przypadek byl zlamany przed poprawka VER 2.2.5A."""
        assert bool_setting({"make_plots": ""}, "make_plots", False) is False

    @pytest.mark.parametrize("value", ["0", "false", "False", "nie", "off", "NO"])
    def test_falsy_strings(self, value):
        assert bool_setting({"k": value}, "k", True) is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "tak"])
    def test_truthy_strings(self, value):
        assert bool_setting({"k": value}, "k", False) is True

    def test_whitespace_value_returns_default(self):
        assert bool_setting({"k": "   "}, "k", True) is True


# ---------------------------------------------------------------------------
# resolve_auto_date_token
# ---------------------------------------------------------------------------

class TestResolveAutoDateToken:
    TODAY = dt.date(2026, 6, 12)

    def test_explicit_iso_date(self):
        iso, _ = resolve_auto_date_token("2005-01-31", self.TODAY)
        assert iso == "2005-01-31"

    @pytest.mark.parametrize("token", ["", "AUTO", "TODAY", "LATEST", "NOW", "auto", "today"])
    def test_auto_tokens_resolve_to_today(self, token):
        iso, _ = resolve_auto_date_token(token, self.TODAY)
        assert iso == self.TODAY.isoformat()

    def test_auto_minus_days(self):
        iso, _ = resolve_auto_date_token("AUTO-10D", self.TODAY)
        assert iso == (self.TODAY - dt.timedelta(days=10)).isoformat()

    def test_auto_minus_weeks(self):
        iso, _ = resolve_auto_date_token("AUTO-2W", self.TODAY)
        assert iso == (self.TODAY - dt.timedelta(weeks=2)).isoformat()

    def test_auto_minus_months(self):
        iso, _ = resolve_auto_date_token("AUTO-3M", self.TODAY)
        assert iso == "2026-03-12"

    def test_auto_minus_years(self):
        iso, _ = resolve_auto_date_token("AUTO-1Y", self.TODAY)
        assert iso == "2025-06-12"

    def test_case_insensitive_and_underscore(self):
        iso, _ = resolve_auto_date_token("auto_3m", self.TODAY)
        assert iso == "2026-03-12"

    def test_invalid_token_raises(self):
        with pytest.raises(ValueError):
            resolve_auto_date_token("NIEZNANY_TOKEN", self.TODAY)

    def test_invalid_date_format_raises(self):
        with pytest.raises(ValueError):
            resolve_auto_date_token("31-01-2005", self.TODAY)


# ---------------------------------------------------------------------------
# read_settings
# ---------------------------------------------------------------------------

class TestReadSettings:
    def test_reads_key_value_csv(self, tmp_path: Path):
        p = tmp_path / "settings.csv"
        p.write_text("KEY,VALUE\nstart,2005-01-31\nend,2026-03-31\n", encoding="utf-8")
        settings = read_settings(p)
        assert settings["start"] == "2005-01-31"
        assert settings["end"] == "2026-03-31"

    def test_strips_whitespace_from_values(self, tmp_path: Path):
        p = tmp_path / "settings.csv"
        p.write_text("KEY,VALUE\nstart, 2005-01-31 \n", encoding="utf-8")
        assert read_settings(p)["start"] == "2005-01-31"

    def test_skips_rows_without_key(self, tmp_path: Path):
        p = tmp_path / "settings.csv"
        p.write_text("KEY,VALUE\n,ignored\nstart,2005-01-31\n", encoding="utf-8")
        settings = read_settings(p)
        assert "" not in settings
        assert settings["start"] == "2005-01-31"

    def test_handles_bom(self, tmp_path: Path):
        p = tmp_path / "settings.csv"
        p.write_bytes(b"\xef\xbb\xbfKEY,VALUE\nstart,2005-01-31\n")
        assert read_settings(p)["start"] == "2005-01-31"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_settings(tmp_path / "nope.csv")

    def test_real_project_settings(self, project_root: Path):
        p = project_root / "analysis_definitions" / "user_template" / "settings.csv"
        settings = read_settings(p)
        assert "start" in settings
        assert "end" in settings

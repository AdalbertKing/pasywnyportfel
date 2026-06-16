# pasywnyportfel — testy validate_task.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""Testy dla app/bin/validate_task.py — walidacja folderow taskow."""

import datetime as dt
import shutil
from pathlib import Path

import pytest

from validate_task import (
    _pick_col,
    load_library_columns,
    map_ticker_values,
    validate_dates,
    validate_task,
    weight_sum,
)


# ---------------------------------------------------------------------------
# validate_dates — start < end po rozwiazaniu tokenow AUTO
# ---------------------------------------------------------------------------

class TestValidateDates:
    def test_normal_explicit_dates(self):
        s, e = validate_dates({"start": "2005-01-31", "end": "2026-03-31"})
        assert s == "2005-01-31"
        assert e == "2026-03-31"

    def test_auto_tokens_always_valid(self):
        """AUTO-3M -> AUTO: 3 miesiace temu < dzis, zawsze OK."""
        s, e = validate_dates({"start": "AUTO-3M", "end": "AUTO"})
        assert dt.date.fromisoformat(s) < dt.date.fromisoformat(e)

    def test_both_empty_means_today_equals_today_fails(self):
        """Puste start i end -> oba AUTO -> dzis == dzis -> start >= end."""
        with pytest.raises(ValueError, match="start >= end"):
            validate_dates({"start": "", "end": ""})

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="start >= end"):
            validate_dates({"start": "2026-03-31", "end": "2005-01-31"})

    def test_start_equals_end_raises(self):
        with pytest.raises(ValueError, match="start >= end"):
            validate_dates({"start": "2026-03-31", "end": "2026-03-31"})

    def test_invalid_start_format_raises(self):
        with pytest.raises(ValueError, match="start"):
            validate_dates({"start": "31-01-2005", "end": "2026-03-31"})

    def test_unknown_end_token_raises(self):
        with pytest.raises(ValueError, match="end"):
            validate_dates({"start": "2005-01-31", "end": "NIEZNANY"})

    def test_error_message_shows_both_resolved_values(self):
        try:
            validate_dates({"start": "2026-06-01", "end": "2005-01-01"})
            pytest.fail("powinien rzucic ValueError")
        except ValueError as e:
            msg = str(e)
            assert "2026-06-01" in msg
            assert "2005-01-01" in msg


# ---------------------------------------------------------------------------
# weight_sum
# ---------------------------------------------------------------------------

class TestWeightSum:
    def test_weight_column_sums_to_100(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,WEIGHT\nA,60\nB,40\n", encoding="utf-8")
        total, cols = weight_sum(p)
        assert total == pytest.approx(100.0)

    def test_accepts_comma_decimal(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,WEIGHT\nA,33,3\nB,66,7\n", encoding="utf-8")
        # uwaga: ta sama linia z "," jako separator dziesietny i kolumn
        # tutaj testujemy realny przypadek z jedna kolumna WEIGHT, wartosci z przecinkiem
        p.write_text("Ticker,WEIGHT\nA,\"33,3\"\nB,\"66,7\"\n", encoding="utf-8")
        total, cols = weight_sum(p)
        assert total == pytest.approx(100.0)

    def test_weight_percent_column_name(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,Weight_%\nA,50\nB,50\n", encoding="utf-8")
        total, cols = weight_sum(p)
        assert total == pytest.approx(100.0)

    def test_empty_map_raises(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,WEIGHT\n", encoding="utf-8")
        with pytest.raises(ValueError, match="pusta"):
            weight_sum(p)

    def test_missing_weight_column_raises(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,SHARES\nA,1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="WEIGHT"):
            weight_sum(p)


# ---------------------------------------------------------------------------
# validate_task — pelna walidacja folderu taska
# ---------------------------------------------------------------------------

class TestValidateTask:
    def test_real_user_template(self, project_root: Path):
        task_dir, included, maps, start_iso, end_iso, warns = validate_task(project_root, "user_template")
        assert included == 2
        assert len(maps) == 4
        assert start_iso == "2005-01-31"
        assert end_iso == "2026-03-31"
        for col, pid, path, total in maps:
            assert total == pytest.approx(100.0, abs=0.05)

    @pytest.mark.parametrize("task_name", [
        "user_template",
        "bfly_10y_vs_vuds_2005",
        "benchmark_1970_synth_usd_gross",
        "synth_vs_etf_2005_full10",
        "golden_butterfly_proxy_review_2005",
        "daily_hist_smoke_3m",
    ])
    def test_all_shipped_tasks_validate(self, project_root: Path, task_name: str):
        task_dir, included, maps, start_iso, end_iso, warns = validate_task(project_root, task_name)
        assert included > 0
        assert dt.date.fromisoformat(start_iso) < dt.date.fromisoformat(end_iso)

    def test_nonexistent_task_raises(self, project_root: Path):
        with pytest.raises(FileNotFoundError, match="folderu taska"):
            validate_task(project_root, "no_such_task_xyz")

    def test_bad_dates_in_settings_raise(self, tmp_path: Path, project_root: Path):
        """Skopiowany task z odwrotnymi datami powinien polec na validate_dates."""
        import shutil
        src = project_root / "analysis_definitions" / "user_template"
        task_root = tmp_path / "analysis_definitions"
        dst = task_root / "user_template_badtest"
        shutil.copytree(src, dst)

        settings = dst / "settings.csv"
        text = settings.read_text(encoding="utf-8")
        text = text.replace("start,2005-01-31", "start,2030-01-01")
        settings.write_text(text, encoding="utf-8")

        with pytest.raises(ValueError, match="start >= end"):
            validate_task(tmp_path, "user_template_badtest")


# ---------------------------------------------------------------------------
# _pick_col — case-insensitive wybor kolumny (alias matching)
# ---------------------------------------------------------------------------

class TestPickCol:
    def test_exact_match(self):
        assert _pick_col(["Ticker", "WEIGHT"], ["Ticker"]) == "Ticker"

    def test_case_insensitive(self):
        assert _pick_col(["ticker", "weight"], ["Ticker"]) == "ticker"

    def test_first_alias_wins(self):
        assert _pick_col(["Ticker", "LIB_COL"], ["LIB_COL", "Ticker"]) == "LIB_COL"

    def test_fallback_to_second_alias(self):
        assert _pick_col(["Ticker", "WEIGHT"], ["LIB_COL", "Ticker"]) == "Ticker"

    def test_no_match_returns_none(self):
        assert _pick_col(["Foo", "Bar"], ["LIB_COL", "Ticker"]) is None


# ---------------------------------------------------------------------------
# load_library_columns
# ---------------------------------------------------------------------------

class TestLoadLibraryColumns:
    def test_real_synth_library(self, project_root: Path):
        cols = load_library_columns(project_root, "SYNTH_LIBRARY_MONTHLY_USD.csv")
        assert cols is not None
        assert "US_STOCKS_TR" in cols
        assert "DATE" not in cols  # pierwsza kolumna (DATE) jest wylaczona

    def test_real_hist_library(self, project_root: Path):
        p = project_root / "data" / "in" / "libraries" / "HIST_LIBRARY_DAILY.csv"
        cols = load_library_columns(project_root, "HIST_LIBRARY_DAILY.csv")
        if not p.exists():
            # Na CI plik jest w .gitignore — load_library_columns zwraca None
            assert cols is None
        else:
            assert cols is not None

    def test_missing_library_returns_none(self, tmp_path: Path):
        cols = load_library_columns(tmp_path, "NO_SUCH_LIBRARY.csv")
        assert cols is None

    def test_parses_header_correctly(self, tmp_path: Path):
        libs = tmp_path / "data" / "in" / "libraries"
        libs.mkdir(parents=True)
        (libs / "TEST_LIB.csv").write_text("DATE,AAA,BBB,CCC\n2020-01-01,1,2,3\n", encoding="utf-8")
        cols = load_library_columns(tmp_path, "TEST_LIB.csv")
        assert cols == {"AAA", "BBB", "CCC"}


# ---------------------------------------------------------------------------
# map_ticker_values
# ---------------------------------------------------------------------------

class TestMapTickerValues:
    def test_synth_uses_lib_col(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,LIB_COL,WEIGHT\nSYNTH_X,US_STOCKS_TR,100\n", encoding="utf-8")
        col, values = map_ticker_values(p, "synth")
        assert col == "LIB_COL"
        assert values == ["US_STOCKS_TR"]

    def test_synth_falls_back_to_ticker_without_lib_col(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,WEIGHT\nUS_STOCKS_TR,100\n", encoding="utf-8")
        col, values = map_ticker_values(p, "synth")
        assert col == "Ticker"
        assert values == ["US_STOCKS_TR"]

    def test_hist_uses_yfticker(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,YFTicker,WEIGHT\nSPY_LOCAL,SPY,100\n", encoding="utf-8")
        col, values = map_ticker_values(p, "hist")
        assert col == "YFTicker"
        assert values == ["SPY"]

    def test_hist_falls_back_to_ticker(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,WEIGHT\nSPY,100\n", encoding="utf-8")
        col, values = map_ticker_values(p, "hist")
        assert col == "Ticker"
        assert values == ["SPY"]

    def test_empty_values_filtered_out(self, tmp_path: Path):
        p = tmp_path / "map.csv"
        p.write_text("Ticker,YFTicker,WEIGHT\nA,SPY,50\nB,,50\n", encoding="utf-8")
        col, values = map_ticker_values(p, "hist")
        assert values == ["SPY"]

    def test_real_synth_map(self, project_root: Path):
        p = project_root / "analysis_definitions/user_template/maps/synth/my_portfolio_sp500_syn.csv"
        col, values = map_ticker_values(p, "synth")
        assert col == "LIB_COL"
        assert values == ["US_STOCKS_TR"]

    def test_real_hist_map(self, project_root: Path):
        p = project_root / "analysis_definitions/user_template/maps/hist/my_portfolio_sp500_hist.csv"
        col, values = map_ticker_values(p, "hist")
        assert values == ["SPY"]


# ---------------------------------------------------------------------------
# validate_task — pokrycie tickerow przez biblioteki SYNTH/HIST
# ---------------------------------------------------------------------------

class TestValidateTaskLibraryCoverage:

    def _copy_task(self, project_root: Path, tmp_path: Path, src_name="user_template", dst_name="lib_coverage_test"):
        src = project_root / "analysis_definitions" / src_name
        task_root = tmp_path / "analysis_definitions"
        dst = task_root / dst_name
        shutil.copytree(src, dst)
        return tmp_path, dst

    def test_real_tasks_synth_coverage_ok(self, project_root: Path):
        """Wszystkie shipped taski maja SYNTH LIB_COL pokryte przez SYNTH_LIBRARY -- nie raise."""
        for task_name in ["user_template", "benchmark_1970_synth_usd_gross", "synth_vs_etf_2005_full10"]:
            task_dir, included, maps, start_iso, end_iso, warns = validate_task(project_root, task_name)
            # gdyby SYNTH coverage failowal, validate_task rzucilby ValueError wczesniej
            assert included > 0

    def test_synth_typo_in_lib_col_raises(self, project_root: Path, tmp_path: Path):
        """Literowka w LIB_COL mapy SYNTH -> ValueError 'BRAK SERII', zlapane
        PRZED uruchomieniem build_db_synthetic.py / passive_ledger.py."""
        tmp_root, dst = self._copy_task(project_root, tmp_path)

        map_path = dst / "maps" / "synth" / "my_portfolio_sp500_syn.csv"
        text = map_path.read_text(encoding="utf-8")
        text = text.replace("US_STOCKS_TR", "US_STOCKS_TR_TYPO")
        map_path.write_text(text, encoding="utf-8")

        # przekopiuj prawdziwa SYNTH_LIBRARY, zeby test mial co sprawdzac
        libs_src = project_root / "data" / "in" / "libraries"
        libs_dst = tmp_root / "data" / "in" / "libraries"
        libs_dst.mkdir(parents=True)
        shutil.copy2(libs_src / "SYNTH_LIBRARY_MONTHLY_USD.csv", libs_dst / "SYNTH_LIBRARY_MONTHLY_USD.csv")

        with pytest.raises(ValueError, match="BRAK SERII"):
            validate_task(tmp_root, "lib_coverage_test")

    def test_synth_typo_error_mentions_column_and_value(self, project_root: Path, tmp_path: Path):
        tmp_root, dst = self._copy_task(project_root, tmp_path)
        map_path = dst / "maps" / "synth" / "my_portfolio_sp500_syn.csv"
        map_path.write_text(
            map_path.read_text(encoding="utf-8").replace("US_STOCKS_TR", "NIEISTNIEJACA_SERIA"),
            encoding="utf-8",
        )
        libs_src = project_root / "data" / "in" / "libraries"
        libs_dst = tmp_root / "data" / "in" / "libraries"
        libs_dst.mkdir(parents=True)
        shutil.copy2(libs_src / "SYNTH_LIBRARY_MONTHLY_USD.csv", libs_dst / "SYNTH_LIBRARY_MONTHLY_USD.csv")

        try:
            validate_task(tmp_root, "lib_coverage_test")
            pytest.fail("powinien rzucic ValueError")
        except ValueError as e:
            msg = str(e)
            assert "NIEISTNIEJACA_SERIA" in msg
            assert "LIB_COL" in msg

    def test_missing_synth_library_skips_check(self, project_root: Path, tmp_path: Path):
        """Gdy SYNTH_LIBRARY_MONTHLY_USD.csv nie istnieje, sprawdzanie LIB_COL jest pomijane (brak crashu)."""
        tmp_root, dst = self._copy_task(project_root, tmp_path)
        # tmp_root/data/in/libraries nie istnieje -> load_library_columns zwraca None
        task_dir, included, maps, start_iso, end_iso, warns = validate_task(tmp_root, "lib_coverage_test")
        assert included > 0

    def test_missing_hist_library_produces_warning_not_error(self, project_root: Path, tmp_path: Path):
        """Brak HIST_LIBRARY_DAILY.csv -> WARN w liscie warnings, nie ValueError."""
        tmp_root, dst = self._copy_task(project_root, tmp_path)
        # bez data/in/libraries -> hist_lib_cols=None -> warning "nie istnieje"
        task_dir, included, maps, start_iso, end_iso, warns = validate_task(tmp_root, "lib_coverage_test")
        hist_warns = [w for w in warns if "HIST_LIBRARY_DAILY.csv nie istnieje" in w]
        assert len(hist_warns) >= 1
        assert "refresh_quotes.cmd" in hist_warns[0]

    def test_hist_ticker_not_in_library_produces_warning(self, project_root: Path, tmp_path: Path):
        """HIST_LIBRARY istnieje ale nie zawiera tickera z mapy -> warning z refresh_quotes hint."""
        tmp_root, dst = self._copy_task(project_root, tmp_path)

        libs_dst = tmp_root / "data" / "in" / "libraries"
        libs_dst.mkdir(parents=True)
        # biblioteka HIST bez kolumny SPY (uzywanej w user_template/maps/hist)
        (libs_dst / "HIST_LIBRARY_DAILY.csv").write_text("DATE,IEF,TLT\n2020-01-01,100,100\n", encoding="utf-8")

        task_dir, included, maps, start_iso, end_iso, warns = validate_task(tmp_root, "lib_coverage_test")
        assert any("SPY" in w and "refresh_quotes.cmd" in w for w in warns)

    def test_hist_ticker_in_library_no_warning(self, project_root: Path, tmp_path: Path):
        """HIST_LIBRARY zawiera SPY -> brak ostrzezenia dla tego portfela."""
        tmp_root, dst = self._copy_task(project_root, tmp_path)

        libs_dst = tmp_root / "data" / "in" / "libraries"
        libs_dst.mkdir(parents=True)
        (libs_dst / "HIST_LIBRARY_DAILY.csv").write_text("DATE,SPY\n2020-01-01,100\n", encoding="utf-8")

        task_dir, included, maps, start_iso, end_iso, warns = validate_task(tmp_root, "lib_coverage_test")
        assert not any("SPY" in w for w in warns)

    def test_real_bfly_task_reports_known_hist_gaps(self, project_root: Path):
        """
        Z placeholder HIST_LIBRARY_DAILY.csv w repo (GLD,IEF,IJS,SPY,TLT),
        bfly_10y_vs_vuds_2005 odwoluje sie m.in. do IAU/SHY/VBR/VTI ktorych
        tam nie ma -- to powinno wygenerowac warningi, nie blad.
        """
        task_dir, included, maps, start_iso, end_iso, warns = validate_task(project_root, "bfly_10y_vs_vuds_2005")
        assert len(warns) > 0
        assert all("refresh_quotes.cmd" in w for w in warns)

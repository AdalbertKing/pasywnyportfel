# pasywnyportfel — testy create_task.py
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
Testy dla app/bin/create_task.py — tworzenie nowego taska z szablonu
i automatyczna walidacja (auto-walidacja po create_task.cmd).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from create_task import TaskCreationError, create_task, print_validation_summary


# ---------------------------------------------------------------------------
# Fixtures lokalne dla tego modulu
# ---------------------------------------------------------------------------

@pytest.fixture()
def template_root(tmp_path: Path, project_root: Path) -> Path:
    """tmp_path z kopia szablonu comparison_2005 (bez bibliotek SYNTH/HIST)."""
    src = project_root / "analysis_definitions" / "common" / "task_templates" / "comparison_2005"
    dst = tmp_path / "analysis_definitions" / "common" / "task_templates" / "comparison_2005"
    shutil.copytree(src, dst)
    return tmp_path


@pytest.fixture()
def template_root_with_libraries(template_root: Path, project_root: Path) -> Path:
    """template_root + skopiowane biblioteki SYNTH/HIST z prawdziwego projektu."""
    libs_src = project_root / "data" / "in" / "libraries"
    libs_dst = template_root / "data" / "in" / "libraries"
    libs_dst.mkdir(parents=True)
    shutil.copy2(libs_src / "SYNTH_LIBRARY_MONTHLY_USD.csv", libs_dst / "SYNTH_LIBRARY_MONTHLY_USD.csv")
    hist = libs_src / "HIST_LIBRARY_DAILY.csv"
    if hist.exists():
        shutil.copy2(hist, libs_dst / "HIST_LIBRARY_DAILY.csv")
    return template_root


# ---------------------------------------------------------------------------
# Bledy konfiguracji wejscia
# ---------------------------------------------------------------------------

class TestCreateTaskInputErrors:
    @pytest.mark.parametrize("bad_name", ["bad name", "bad/name", "bad!name", "", "  "])
    def test_invalid_name_raises_code_2(self, template_root: Path, bad_name: str):
        with pytest.raises(TaskCreationError) as exc_info:
            create_task(template_root, bad_name)
        assert exc_info.value.code == 2

    def test_missing_template_raises_code_3(self, template_root: Path):
        with pytest.raises(TaskCreationError) as exc_info:
            create_task(template_root, "my_task", template="no_such_template")
        assert exc_info.value.code == 3
        assert "no_such_template" in str(exc_info.value)

    def test_existing_task_without_force_raises_code_4(self, template_root: Path):
        create_task(template_root, "my_task")
        with pytest.raises(TaskCreationError) as exc_info:
            create_task(template_root, "my_task")
        assert exc_info.value.code == 4
        assert "--force" in str(exc_info.value)

    def test_existing_task_with_force_overwrites(self, template_root: Path):
        create_task(template_root, "my_task")
        # zmodyfikuj plik, zeby sprawdzic ze --force faktycznie nadpisuje
        marker = template_root / "analysis_definitions" / "my_task" / "MARKER.txt"
        marker.write_text("stale content", encoding="utf-8")

        create_task(template_root, "my_task", force=True)

        assert not marker.exists()
        assert (template_root / "analysis_definitions" / "my_task" / "settings.csv").exists()

    def test_valid_names_with_underscore_and_dash(self, template_root: Path):
        result = create_task(template_root, "bfly_10y-vs-vuds_2005")
        assert result["task_dir"].exists()


# ---------------------------------------------------------------------------
# Tworzenie plikow
# ---------------------------------------------------------------------------

class TestCreateTaskFiles:
    def test_creates_task_directory(self, template_root: Path):
        result = create_task(template_root, "my_task")
        assert result["task_dir"] == template_root / "analysis_definitions" / "my_task"
        assert result["task_dir"].is_dir()

    def test_copies_settings_and_portfolios(self, template_root: Path):
        result = create_task(template_root, "my_task")
        assert (result["task_dir"] / "settings.csv").exists()
        assert (result["task_dir"] / "portfolios.csv").exists()

    def test_copies_maps_subdirectories(self, template_root: Path):
        result = create_task(template_root, "my_task")
        assert (result["task_dir"] / "maps" / "synth").is_dir()
        assert (result["task_dir"] / "maps" / "hist").is_dir()

    def test_creates_readme_with_task_name_and_run_hint(self, template_root: Path):
        result = create_task(template_root, "my_special_task")
        readme = (result["task_dir"] / "README_TASK.txt").read_text(encoding="utf-8")
        assert "my_special_task" in readme
        assert "run_task.cmd my_special_task" in readme
        assert "settings.csv" in readme
        assert "portfolios.csv" in readme

    def test_readme_mentions_template_name(self, template_root: Path):
        result = create_task(template_root, "my_task", template="comparison_2005")
        readme = (result["task_dir"] / "README_TASK.txt").read_text(encoding="utf-8")
        assert "comparison_2005" in readme


# ---------------------------------------------------------------------------
# Auto-walidacja — happy path
# ---------------------------------------------------------------------------

class TestAutoValidationHappyPath:
    def test_validation_runs_and_succeeds(self, template_root: Path):
        result = create_task(template_root, "my_task")
        assert result["validation_error"] is None
        assert result["validation"] is not None

    def test_validation_reports_correct_period(self, template_root: Path):
        result = create_task(template_root, "my_task")
        task_dir, included, checked_maps, start_iso, end_iso, warns = result["validation"]
        assert start_iso == "2005-01-31"
        assert end_iso == "2026-03-31"

    def test_validation_reports_two_portfolios_four_maps(self, template_root: Path):
        result = create_task(template_root, "my_task")
        _, included, checked_maps, _, _, _ = result["validation"]
        assert included == 2
        assert len(checked_maps) == 4

    def test_validation_weights_sum_to_100(self, template_root: Path):
        result = create_task(template_root, "my_task")
        _, _, checked_maps, _, _, _ = result["validation"]
        for col, pid, path, total in checked_maps:
            assert total == pytest.approx(100.0, abs=0.05)

    def test_warnings_when_no_hist_library_exists(self, template_root: Path):
        """Bez pliku HIST_LIBRARY_DAILY.csv validate_task ostrzega, ze trzeba
        uruchomic refresh_quotes.cmd -- to jest oczekiwane na czystym checkout."""
        result = create_task(template_root, "my_task")
        _, _, _, _, _, warns = result["validation"]
        assert len(warns) == 2  # po jednym na portfel z MAP_HIST
        for w in warns:
            assert "HIST_LIBRARY_DAILY.csv nie istnieje" in w
            assert "refresh_quotes.cmd my_task" in w

    def test_print_validation_summary_happy_path(self, template_root_with_libraries: Path, capsys):
        result = create_task(template_root_with_libraries, "my_task")
        print_validation_summary("my_task", result)
        out = capsys.readouterr().out
        assert "OK   period: 2005-01-31 -> 2026-03-31" in out
        assert "OK   portfolios INCLUDE=1: 2" in out
        assert "WARN" not in out


# ---------------------------------------------------------------------------
# Auto-walidacja — biblioteki SYNTH/HIST
# ---------------------------------------------------------------------------

class TestAutoValidationWithLibraries:
    def test_synth_coverage_ok_with_real_library(self, template_root_with_libraries: Path):
        """Template comparison_2005 uzywa US_STOCKS_TR -- jest w prawdziwej SYNTH_LIBRARY."""
        result = create_task(template_root_with_libraries, "my_task")
        assert result["validation_error"] is None

    def test_hist_coverage_ok_with_real_library(self, template_root_with_libraries: Path):
        """Template uzywa SPY -- jest w HIST_LIBRARY_DAILY (placeholder)."""
        result = create_task(template_root_with_libraries, "my_task")
        _, _, _, _, _, warns = result["validation"]
        assert warns == []

    def test_synth_typo_after_creation_is_caught(self, template_root_with_libraries: Path):
        """
        Literowka w LIB_COL skopiowanej mapy SYNTH -> validation_error
        z 'BRAK SERII', ale task jest juz utworzony na dysku (pliki istnieja).
        """
        result = create_task(template_root_with_libraries, "my_task")
        task_dir = result["task_dir"]

        map_path = task_dir / "maps" / "synth" / "my_portfolio_sp500_syn.csv"
        text = map_path.read_text(encoding="utf-8")
        text = text.replace("US_STOCKS_TR", "US_STOCKS_TR_TYPO")
        map_path.write_text(text, encoding="utf-8")

        # validate_task wywolane recznie po "recznej" edycji, jak check_task.cmd by zrobil
        from validate_task import validate_task
        with pytest.raises(ValueError, match="BRAK SERII"):
            validate_task(template_root_with_libraries, "my_task")

    def test_hist_gap_produces_warning_not_error(self, template_root: Path, project_root: Path):
        """HIST_LIBRARY bez SPY -> warning z refresh_quotes hint, validation_error=None."""
        libs_dst = template_root / "data" / "in" / "libraries"
        libs_dst.mkdir(parents=True)
        (libs_dst / "HIST_LIBRARY_DAILY.csv").write_text("DATE,IEF,TLT\n2020-01-01,100,100\n", encoding="utf-8")
        # bez SYNTH_LIBRARY -- synth check pomijany

        result = create_task(template_root, "my_task")
        assert result["validation_error"] is None
        _, _, _, _, _, warns = result["validation"]
        assert any("SPY" in w and "refresh_quotes.cmd" in w for w in warns)

    def test_print_validation_summary_with_warnings(self, template_root: Path, capsys):
        libs_dst = template_root / "data" / "in" / "libraries"
        libs_dst.mkdir(parents=True)
        (libs_dst / "HIST_LIBRARY_DAILY.csv").write_text("DATE,IEF,TLT\n2020-01-01,100,100\n", encoding="utf-8")

        result = create_task(template_root, "my_task")
        print_validation_summary("my_task", result)
        out = capsys.readouterr().out

        assert "WARN" in out
        assert "refresh_quotes.cmd my_task" in out
        assert "Task jest gotowy do uruchomienia" in out


# ---------------------------------------------------------------------------
# Auto-walidacja — task z bledna konfiguracja (start >= end)
# ---------------------------------------------------------------------------

class TestAutoValidationBadConfig:
    def test_bad_dates_in_template_caught_as_validation_error(self, template_root: Path):
        """
        Jesli (zmodyfikowany) szablon ma start >= end, create_task() i tak
        tworzy task na dysku, ale zwraca validation_error a nie podnosi
        wyjatku -- uzytkownik dostaje gotowe pliki + czytelna diagnoze.
        """
        template_settings = (
            template_root / "analysis_definitions" / "common" / "task_templates"
            / "comparison_2005" / "settings.csv"
        )
        text = template_settings.read_text(encoding="utf-8")
        text = text.replace("start,2005-01-31", "start,2030-01-01")
        template_settings.write_text(text, encoding="utf-8")

        result = create_task(template_root, "my_broken_task")

        assert result["task_dir"].exists()
        assert (result["task_dir"] / "settings.csv").exists()
        assert result["validation"] is None
        assert "start >= end" in result["validation_error"]

    def test_print_validation_summary_bad_config(self, template_root: Path, capsys):
        template_settings = (
            template_root / "analysis_definitions" / "common" / "task_templates"
            / "comparison_2005" / "settings.csv"
        )
        text = template_settings.read_text(encoding="utf-8")
        text = text.replace("start,2005-01-31", "start,2030-01-01")
        template_settings.write_text(text, encoding="utf-8")

        result = create_task(template_root, "my_broken_task")
        print_validation_summary("my_broken_task", result)
        out = capsys.readouterr().out

        assert "WARN: walidacja nie przeszla" in out
        assert "start >= end" in out
        assert "check_task.cmd my_broken_task" in out


# ---------------------------------------------------------------------------
# Subprocess smoke test — pelne wywolanie CLI na prawdziwym projekcie
# ---------------------------------------------------------------------------

class TestCreateTaskCli:
    def test_cli_happy_path_on_real_project(self, project_root: Path):
        """
        End-to-end: python app/bin/create_task.py <name> na prawdziwym
        projekcie. Tworzy task w analysis_definitions/, sprawdza output,
        i czysci po sobie niezaleznie od wyniku.
        """
        task_name = "pytest_tmp_create_task_check"
        task_dir = project_root / "analysis_definitions" / task_name
        if task_dir.exists():
            shutil.rmtree(task_dir)

        try:
            r = subprocess.run(
                [sys.executable, str(project_root / "app/bin/create_task.py"), task_name],
                capture_output=True, text=True, cwd=str(project_root),
            )
            assert r.returncode == 0, f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
            assert "OK: utworzono task" in r.stdout
            assert "Walidacja nowego taska" in r.stdout
            assert "OK   period:" in r.stdout
            assert task_dir.exists()
            assert (task_dir / "settings.csv").exists()
        finally:
            if task_dir.exists():
                shutil.rmtree(task_dir)

    def test_cli_rejects_invalid_name(self, project_root: Path):
        r = subprocess.run(
            [sys.executable, str(project_root / "app/bin/create_task.py"), "bad name!"],
            capture_output=True, text=True, cwd=str(project_root),
        )
        assert r.returncode == 2
        assert "ERROR" in r.stdout

    def test_cli_rejects_existing_task_without_force(self, project_root: Path):
        """user_template juz istnieje w prawdziwym projekcie -- bez --force musi sie nie udac."""
        r = subprocess.run(
            [sys.executable, str(project_root / "app/bin/create_task.py"), "user_template"],
            capture_output=True, text=True, cwd=str(project_root),
        )
        assert r.returncode == 4
        assert "--force" in r.stdout
        # upewnijmy sie ze nie nadpisalo prawdziwego user_template
        assert (project_root / "analysis_definitions" / "user_template" / "settings.csv").exists()

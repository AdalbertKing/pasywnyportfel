# pasywnyportfel — testy narzedzi batchowych
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
Testy dla wsadowego doszlifowania:
  - task_config.list_tasks
  - run_all_tasks: parse_csv_list, load_startup_tasks, select_tasks,
                   run_one_task, print_summary
  - cleanup_old_results: find_run_dirs, group_by_task, plan_cleanup, human_size
"""

import shutil
import sys
from pathlib import Path

import pytest

from task_config import list_tasks
import run_all_tasks as rat
import cleanup_old_results as cor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_project(tmp_path: Path) -> Path:
    """Minimalny projekt z 3 taskami + folderem common (nie-task)."""
    defs = tmp_path / "analysis_definitions"
    for name in ["alpha", "beta", "gamma"]:
        d = defs / name
        d.mkdir(parents=True)
        (d / "settings.csv").write_text("KEY,VALUE\nstart,2005-01-31\nend,2026-03-31\n", encoding="utf-8")
        (d / "portfolios.csv").write_text("ID,LABEL\np1,P1\n", encoding="utf-8")
    # common nie jest taskiem
    common = defs / "common"
    common.mkdir()
    (common / "settings.csv").write_text("KEY,VALUE\n", encoding="utf-8")
    (common / "portfolios.csv").write_text("ID,LABEL\n", encoding="utf-8")
    # folder bez wymaganych plikow -> nie task
    (defs / "incomplete").mkdir()
    return tmp_path


@pytest.fixture()
def results_tree(tmp_path: Path) -> Path:
    """analysis_results z 5 przebiegami taskA, 2 taskB, 1 folder nie-pasujacy."""
    res = tmp_path / "analysis_results"
    res.mkdir()
    for ts in ["20260101_000000", "20260102_000000", "20260103_000000",
               "20260104_000000", "20260105_000000"]:
        d = res / f"taskA__{ts}"
        d.mkdir()
        (d / "out.csv").write_text("x" * 100, encoding="utf-8")
    for ts in ["20260101_000000", "20260201_000000"]:
        (res / f"taskB__{ts}").mkdir()
    (res / "_manual_notes").mkdir()  # nie pasuje do wzorca
    return tmp_path


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    def test_lists_valid_tasks_sorted(self, fake_project: Path):
        assert list_tasks(fake_project) == ["alpha", "beta", "gamma"]

    def test_excludes_common(self, fake_project: Path):
        assert "common" not in list_tasks(fake_project)

    def test_excludes_incomplete_folders(self, fake_project: Path):
        assert "incomplete" not in list_tasks(fake_project)

    def test_empty_when_no_definitions_dir(self, tmp_path: Path):
        assert list_tasks(tmp_path) == []

    def test_real_project_tasks(self, project_root: Path):
        tasks = list_tasks(project_root)
        assert "user_template" in tasks
        assert "common" not in tasks


# ---------------------------------------------------------------------------
# run_all_tasks: helpery selekcji
# ---------------------------------------------------------------------------

class TestParseCsvList:
    def test_basic(self):
        assert rat.parse_csv_list("a,b,c") == {"a", "b", "c"}

    def test_strips_whitespace(self):
        assert rat.parse_csv_list("a, b , c") == {"a", "b", "c"}

    def test_none_is_empty(self):
        assert rat.parse_csv_list(None) == set()

    def test_empty_string_is_empty(self):
        assert rat.parse_csv_list("") == set()

    def test_skips_empty_items(self):
        assert rat.parse_csv_list("a,,b,") == {"a", "b"}


class TestLoadStartupTasks:
    def test_reads_included(self, tmp_path: Path):
        defs = tmp_path / "analysis_definitions"
        defs.mkdir()
        (defs / "startup_order.csv").write_text(
            "ANALYSIS_FOLDER,INCLUDE\nalpha,1\nbeta,1\n", encoding="utf-8"
        )
        assert rat.load_startup_tasks(tmp_path) == {"alpha", "beta"}

    def test_excludes_include_zero(self, tmp_path: Path):
        defs = tmp_path / "analysis_definitions"
        defs.mkdir()
        (defs / "startup_order.csv").write_text(
            "ANALYSIS_FOLDER,INCLUDE\nalpha,1\nbeta,0\n", encoding="utf-8"
        )
        assert rat.load_startup_tasks(tmp_path) == {"alpha"}

    def test_missing_file_empty(self, tmp_path: Path):
        assert rat.load_startup_tasks(tmp_path) == set()

    def test_real_project_startup(self, project_root: Path):
        startup = rat.load_startup_tasks(project_root)
        assert "benchmark_1970_synth_usd_gross" in startup


class TestSelectTasks:
    ALL = ["alpha", "beta", "gamma", "delta"]

    def test_default_all(self):
        tasks, unknown = rat.select_tasks(self.ALL, None, None, False, set())
        assert tasks == self.ALL
        assert unknown == []

    def test_only_filter(self):
        tasks, unknown = rat.select_tasks(self.ALL, "alpha,gamma", None, False, set())
        assert tasks == ["alpha", "gamma"]
        assert unknown == []

    def test_only_preserves_source_order(self):
        tasks, _ = rat.select_tasks(self.ALL, "gamma,alpha", None, False, set())
        assert tasks == ["alpha", "gamma"]  # kolejnosc z ALL, nie z --only

    def test_only_unknown_reported(self):
        tasks, unknown = rat.select_tasks(self.ALL, "alpha,zeta", None, False, set())
        assert unknown == ["zeta"]
        assert tasks == ["alpha"]

    def test_exclude_filter(self):
        tasks, _ = rat.select_tasks(self.ALL, None, "beta,delta", False, set())
        assert tasks == ["alpha", "gamma"]

    def test_startup_only(self):
        tasks, _ = rat.select_tasks(self.ALL, None, None, True, {"alpha", "delta"})
        assert tasks == ["alpha", "delta"]

    def test_startup_then_exclude(self):
        tasks, _ = rat.select_tasks(self.ALL, None, "delta", True, {"alpha", "delta"})
        assert tasks == ["alpha"]

    def test_only_and_exclude_combined(self):
        tasks, _ = rat.select_tasks(self.ALL, "alpha,beta,gamma", "beta", False, set())
        assert tasks == ["alpha", "gamma"]


# ---------------------------------------------------------------------------
# run_all_tasks: run_one_task (subprocess) + print_summary
# ---------------------------------------------------------------------------

class TestRunOneTask:
    def _make_fake_analysis(self, tmp_path: Path, exit_code: int) -> Path:
        """Tworzy zastepczy analysis.py ktory wypisuje cos i konczy danym kodem."""
        script = tmp_path / "fake_analysis.py"
        script.write_text(
            "import sys\n"
            "print('fake analysis output line')\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )
        return script

    def test_successful_task(self, tmp_path: Path):
        script = self._make_fake_analysis(tmp_path, 0)
        result = rat.run_one_task(tmp_path, "mytask", dry_run=False, analysis_script=script)
        assert result["status"] == "OK"
        assert result["error"] is None
        assert result["elapsed"] >= 0

    def test_dry_run_status(self, tmp_path: Path):
        script = self._make_fake_analysis(tmp_path, 0)
        result = rat.run_one_task(tmp_path, "mytask", dry_run=True, analysis_script=script)
        assert result["status"] == "DRY-RUN"

    def test_failed_task_captured_not_raised(self, tmp_path: Path):
        script = self._make_fake_analysis(tmp_path, 1)
        result = rat.run_one_task(tmp_path, "mytask", dry_run=False, analysis_script=script)
        assert result["status"] == "FAIL"
        assert "returncode=1" in result["error"]

    def test_output_streamed_to_stdout(self, tmp_path: Path, capsys):
        script = self._make_fake_analysis(tmp_path, 0)
        rat.run_one_task(tmp_path, "mytask", dry_run=False, analysis_script=script)
        out = capsys.readouterr().out
        assert "fake analysis output line" in out
        assert "TASK: mytask" in out


class TestPrintSummary:
    def test_summary_counts(self, capsys):
        results = [
            {"task": "a", "status": "OK", "elapsed": 1.0, "error": None},
            {"task": "b", "status": "FAIL", "elapsed": 2.0, "error": "returncode=1"},
            {"task": "c", "status": "OK", "elapsed": 3.0, "error": None},
        ]
        rat.print_summary(results)
        out = capsys.readouterr().out
        assert "OK/DRY-RUN: 2" in out
        assert "FAIL: 1" in out
        assert "RAZEM: 3" in out
        assert "returncode=1" in out


# ---------------------------------------------------------------------------
# cleanup_old_results
# ---------------------------------------------------------------------------

class TestFindRunDirs:
    def test_finds_matching_dirs(self, results_tree: Path):
        dirs = cor.find_run_dirs(results_tree)
        names = {p.name for p in dirs}
        assert "taskA__20260101_000000" in names
        assert "taskB__20260201_000000" in names

    def test_ignores_non_matching(self, results_tree: Path):
        dirs = cor.find_run_dirs(results_tree)
        assert all(p.name != "_manual_notes" for p in dirs)

    def test_empty_when_no_results_dir(self, tmp_path: Path):
        assert cor.find_run_dirs(tmp_path) == []


class TestGroupByTask:
    def test_groups_and_sorts(self, results_tree: Path):
        groups = cor.group_by_task(cor.find_run_dirs(results_tree))
        assert set(groups.keys()) == {"taskA", "taskB"}
        assert len(groups["taskA"]) == 5
        # posortowane rosnaco po timestampie
        names = [p.name for p in groups["taskA"]]
        assert names == sorted(names)


class TestPlanCleanup:
    def test_keeps_n_newest_per_task(self, results_tree: Path):
        to_delete = cor.plan_cleanup(results_tree, keep=3)
        names = {p.name for p in to_delete}
        # taskA ma 5 -> usun 2 najstarsze
        assert "taskA__20260101_000000" in names
        assert "taskA__20260102_000000" in names
        assert "taskA__20260103_000000" not in names  # zachowany
        # taskB ma 2 -> nic nie usuwaj
        assert not any(n.startswith("taskB") for n in names)

    def test_keep_larger_than_count_deletes_nothing(self, results_tree: Path):
        assert cor.plan_cleanup(results_tree, keep=100) == []

    def test_task_filter(self, results_tree: Path):
        to_delete = cor.plan_cleanup(results_tree, keep=1, task="taskB")
        names = {p.name for p in to_delete}
        assert names == {"taskB__20260101_000000"}
        assert not any(n.startswith("taskA") for n in names)

    def test_keep_1_leaves_exactly_newest(self, results_tree: Path):
        to_delete = cor.plan_cleanup(results_tree, keep=1)
        deleted_a = sorted(p.name for p in to_delete if p.name.startswith("taskA"))
        # z 5 zostaje najnowszy (20260105), usuwane 4 najstarsze
        assert deleted_a == [
            "taskA__20260101_000000",
            "taskA__20260102_000000",
            "taskA__20260103_000000",
            "taskA__20260104_000000",
        ]


class TestHumanSize:
    @pytest.mark.parametrize("num,expected", [
        (0, "0.0 B"),
        (512, "512.0 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1048576, "1.0 MB"),
        (1073741824, "1.0 GB"),
    ])
    def test_formatting(self, num, expected):
        assert cor.human_size(num) == expected


class TestDirSize:
    def test_sums_file_sizes(self, results_tree: Path):
        d = results_tree / "analysis_results" / "taskA__20260101_000000"
        # plik out.csv ma 100 znakow
        assert cor.dir_size(d) == 100

    def test_empty_dir_zero(self, results_tree: Path):
        d = results_tree / "analysis_results" / "taskB__20260101_000000"
        assert cor.dir_size(d) == 0


# ---------------------------------------------------------------------------
# Integracja: faktyczne usuwanie
# ---------------------------------------------------------------------------

class TestCleanupIntegration:
    def test_actual_deletion(self, results_tree: Path):
        to_delete = cor.plan_cleanup(results_tree, keep=3)
        for p in to_delete:
            shutil.rmtree(p, ignore_errors=True)
        remaining = {p.name for p in cor.find_run_dirs(results_tree)}
        assert "taskA__20260105_000000" in remaining
        assert "taskA__20260101_000000" not in remaining
        assert len([n for n in remaining if n.startswith("taskA")]) == 3

    def test_manual_dir_survives(self, results_tree: Path):
        to_delete = cor.plan_cleanup(results_tree, keep=1)
        for p in to_delete:
            shutil.rmtree(p, ignore_errors=True)
        assert (results_tree / "analysis_results" / "_manual_notes").exists()

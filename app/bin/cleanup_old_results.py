#!/usr/bin/env python3
# pasywnyportfel — retencja analysis_results
# Autor koncepcji i projektu: Wojciech Krol / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""
cleanup_old_results.py — usuwa stare przebiegi z analysis_results/,
zachowujac N najnowszych per task.

Uzycie:
    python app/bin/cleanup_old_results.py --dry-run
    python app/bin/cleanup_old_results.py
    python app/bin/cleanup_old_results.py --keep 10
    python app/bin/cleanup_old_results.py --task user_template

Foldery wynikowe maja format <task>__<YYYYMMDD_HHMMSS> (patrz
cmd_builders.make_run_names). Ten skrypt grupuje je po <task>,
sortuje po timestampie i usuwa wszystkie ponad `--keep` najnowszych
w kazdej grupie.

Bezpieczenstwo:
  - --keep musi byc >= 1. Skoro reports/latest_analysis.txt zawsze
    wskazuje na najnowszy przebieg jakiegokolwiek taska, a ten jest
    z definicji najnowszy w swojej grupie, --keep>=1 gwarantuje ze
    latest_analysis.txt nigdy nie wskaze na usuniety folder.
  - foldery nie pasujace do wzorca <prefix>__<8cyfr>_<6cyfr> sa
    ignorowane (nie usuwane) -- np. reki utworzone podkatalogi.
  - reports/analysis_index.csv NIE jest modyfikowany -- to jest
    historyczny rejestr wszystkich przebiegow, niezalezny od tego
    czy folder z wynikami wciaz istnieje na dysku.
  - --dry-run pokazuje co by zostalo usuniete, bez usuwania.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from common import detect_root

VERSION = "cleanup_old_results.py 1.0 RESULTS_RETENTION"

RUN_DIR_RE = re.compile(r"^(?P<prefix>.+)__(?P<ts>\d{8}_\d{6})$")


def find_run_dirs(root: Path) -> list[Path]:
    """Wszystkie foldery <task>__<YYYYMMDD_HHMMSS> w analysis_results/.

    Foldery nie pasujace do wzorca (np. _batch_logs, recznie tworzone
    podkatalogi) sa ignorowane.
    """
    base = root / "analysis_results"
    if not base.exists():
        return []
    out = []
    for p in sorted(base.iterdir()):
        if p.is_dir() and RUN_DIR_RE.match(p.name):
            out.append(p)
    return out


def group_by_task(run_dirs: list[Path]) -> dict[str, list[Path]]:
    """Grupuje foldery po prefiksie (nazwie taska), sortuje rosnaco po timestampie.

    Sortowanie lexykograficzne nazwy folderu jest rownowazne sortowaniu po
    czasie, bo timestamp ma stala dlugosc i format YYYYMMDD_HHMMSS.
    """
    groups: dict[str, list[Path]] = {}
    for p in run_dirs:
        m = RUN_DIR_RE.match(p.name)
        assert m is not None
        groups.setdefault(m.group("prefix"), []).append(p)
    for prefix in groups:
        groups[prefix].sort(key=lambda p: p.name)
    return groups


def plan_cleanup(root: Path, keep: int, task: Optional[str] = None) -> list[Path]:
    """Zwraca liste folderow ktore zostalyby usuniete (najstarsze ponad `keep` per task).

    `task`, jesli podany, ogranicza plan do jednej grupy (prefiksu).
    Wynik jest w kolejnosci od najstarszego do najnowszego.
    """
    groups = group_by_task(find_run_dirs(root))
    if task is not None:
        groups = {k: v for k, v in groups.items() if k == task}

    to_delete: list[Path] = []
    for dirs in groups.values():
        if keep > 0 and len(dirs) > keep:
            to_delete.extend(dirs[:-keep])
        elif keep <= 0:
            to_delete.extend(dirs)
    return to_delete


def dir_size(path: Path) -> int:
    """Sumaryczny rozmiar plikow w katalogu (rekursywnie), w bajtach.

    Bledy odczytu pojedynczych plikow (np. usuniete w trakcie skanowania)
    sa ignorowane -- nie przerywaja liczenia.
    """
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def human_size(num_bytes: float) -> str:
    """Formatuje liczbe bajtow jako '12.3 MB' itp."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def main():
    ap = argparse.ArgumentParser(
        description="Remove old analysis_results runs, keeping N most recent per task."
    )
    ap.add_argument("--keep", type=int, default=5,
                    help="Number of most recent runs to keep per task (default: 5, minimum: 1)")
    ap.add_argument("--task", default=None,
                    help="Limit cleanup to one task (folder name prefix before '__')")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be deleted without deleting anything")
    args = ap.parse_args()

    if args.keep < 1:
        print("ERROR: --keep musi byc >= 1 (zawsze zachowujemy co najmniej najnowszy przebieg).")
        return 2

    root = detect_root()
    to_delete = plan_cleanup(root, args.keep, task=args.task)

    if not to_delete:
        scope = f" dla taska {args.task}" if args.task else ""
        print(f"Nic do usuniecia (--keep {args.keep}{scope}).")
        return 0

    verb = "USUNĄŁBYM" if args.dry_run else "USUWAM   "
    total_size = 0
    for p in to_delete:
        size = dir_size(p)
        total_size += size
        print(f"  {verb} {p.relative_to(root)}  ({human_size(size)})")

    summary_verb = "Zwolniono by" if args.dry_run else "Zwolniono"
    print(f"\n{summary_verb}: {human_size(total_size)} ({len(to_delete)} folder(y))")

    if not args.dry_run:
        for p in to_delete:
            shutil.rmtree(p, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())

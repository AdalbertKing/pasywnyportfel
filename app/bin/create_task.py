#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, re, shutil, sys
from pathlib import Path

from common import detect_root
from validate_task import validate_task

VERSION = "create_task.py 1.1 AUTO_VALIDATE_AFTER_CREATE"


class TaskCreationError(Exception):
    """Blad konfiguracji wejscia create_task (zla nazwa / szablon / istniejacy task).

    Atrybut `code` odpowiada koncowemu exit code skryptu CLI.
    """

    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(message)


def create_task(root: Path, name: str, template: str = "comparison_2005", force: bool = False) -> dict:
    """Tworzy nowy task z szablonu i natychmiast go waliduje.

    Zwraca dict:
        {
            "task_dir": Path,
            "validation": (task_dir, included, checked_maps, start_iso, end_iso, warns) | None,
            "validation_error": str | None,
        }

    "validation" jest wynikiem validate_task(root, name) gdy walidacja przeszla.
    "validation_error" jest komunikatem bledu gdy walidacja sie nie powiodla
    (np. start >= end w skopiowanym/zmodyfikowanym szablonie, literowka w LIB_COL).
    W obu przypadkach task jest juz utworzony na dysku -- walidacja jest
    diagnostyka, nie warunkiem powodzenia create_task.

    Rzuca TaskCreationError dla bledow konfiguracji samego create_task
    (zla nazwa, brak szablonu, istniejacy task bez --force).
    """
    name = name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise TaskCreationError(
            2,
            "nazwa taska może zawierać tylko litery ASCII, cyfry, _ i -.\n"
            "Przykład: bfly_10y_vs_vuds_2005",
        )

    src = root / "analysis_definitions" / "common" / "task_templates" / template
    dst = root / "analysis_definitions" / name

    if not src.exists():
        raise TaskCreationError(3, f"brak szablonu: {src}")

    if dst.exists():
        if not force:
            raise TaskCreationError(
                4,
                f"task już istnieje: {dst}\nUżyj innej nazwy albo --force.",
            )
        shutil.rmtree(dst)

    shutil.copytree(src, dst)

    readme = dst / "README_TASK.txt"
    readme.write_text(
        f"Task: {name}\n"
        f"Utworzony z szablonu: {template}\n\n"
        "Edytuj lokalne pliki w tym folderze:\n"
        "- settings.csv\n"
        "- portfolios.csv\n"
        "- maps\\hist\\*.csv\n"
        "- maps\\synth\\*.csv\n\n"
        f"Uruchomienie:\nrun_task.cmd {name}\n",
        encoding="utf-8",
    )

    result: dict = {"task_dir": dst, "validation": None, "validation_error": None}
    try:
        result["validation"] = validate_task(root, name)
    except Exception as e:
        result["validation_error"] = str(e)
    return result


def print_validation_summary(name: str, result: dict) -> None:
    """Drukuje wynik walidacji w formacie zgodnym z check_task.cmd."""
    print("\n--- Walidacja nowego taska (validate_task.py) ---")

    if result["validation"] is not None:
        task_dir, included, checked_maps, start_iso, end_iso, warns = result["validation"]
        print(f"OK   period: {start_iso} -> {end_iso}")
        print(f"OK   portfolios INCLUDE=1: {included}")
        print(f"OK   checked maps: {len(checked_maps)}")
        for col, pid, path, total in checked_maps:
            print(f"OK   {col:9} {pid:20} {path}  weights={total:.2f}")
        for w in warns:
            print(f"WARN {w}")
        if warns:
            print("\nTask jest gotowy do uruchomienia, ale powyzsze ostrzezenia")
            print("oznaczaja brakujace notowania HIST -- uruchom refresh_quotes.cmd")
            print(f"zanim odpalisz run_task.cmd {name}, albo usun MAP_HIST z portfolios.csv")
            print("jesli interesuje Cie tylko wariant syntetyczny.")
    else:
        print(f"WARN: walidacja nie przeszla: {result['validation_error']}")
        print("Task zostal utworzony, ale wymaga poprawek w settings.csv / portfolios.csv")
        print("przed uruchomieniem. Po edycji sprawdz ponownie:")
        print(f"  check_task.cmd {name}")


def main():
    ap = argparse.ArgumentParser(description="Create a new analysis task from a clean template.")
    ap.add_argument("name", help="Task name, e.g. bfly_10y_vs_vuds_2005. Allowed: A-Z a-z 0-9 _ -")
    ap.add_argument("--template", default="comparison_2005", help="Template name from analysis_definitions/common/task_templates")
    ap.add_argument("--force", action="store_true", help="Overwrite existing task folder")
    args = ap.parse_args()
    root = detect_root()

    try:
        result = create_task(root, args.name, template=args.template, force=args.force)
    except TaskCreationError as e:
        print(f"ERROR: {e}")
        return e.code

    name = args.name.strip()
    print("OK: utworzono task:", result["task_dir"])

    # Auto-walidacja: ten sam check co check_task.cmd, wykonany od razu.
    # Dla szablonow z paczki zwykle przechodzi bez ostrzezen; jesli template
    # zostal zmodyfikowany albo biblioteka HIST jest niekompletna, uzytkownik
    # widzi to natychmiast, a nie po pol-godzinnym 1-start_setup.cmd.
    print_validation_summary(name, result)

    print("\nNastępnie edytuj pliki w tym folderze i uruchom:")
    print(f"  run_task.cmd {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

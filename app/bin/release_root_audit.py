#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import sys

ROOT_ALLOWED_FILES = {
    "1-start_setup.cmd",
    "ABOUT.txt",
    "INSTRUKCJA_START.txt",
    "README.md",
    "SOURCES.md",
    "VERSION.txt",
    "check_common_data.cmd",
    "check_project.cmd",
    "check_stage1.cmd",
    "check_stage1_clean.cmd",
    "check_task.cmd",
    "check_quotes.cmd",
    "create_task.cmd",
    "refresh_data.cmd",
    "refresh_quotes.cmd",
    "requirements.txt",
    "run_task.cmd",
}
ROOT_ALLOWED_DIRS = {
    "analysis_definitions",
    "analysis_results",
    "app",
    "data",
    "docs",
    "reports",
    "runtime",
}

def main():
    root = Path(__file__).resolve().parents[2]
    errors = []
    for p in root.iterdir():
        if p.is_file():
            if p.name not in ROOT_ALLOWED_FILES:
                errors.append(f"unexpected root file: {p.name}")
            if p.name.startswith("_"):
                errors.append(f"root build/local artifact: {p.name}")
        elif p.is_dir():
            if p.name not in ROOT_ALLOWED_DIRS:
                errors.append(f"unexpected root dir: {p.name}")
    # Runtime/output directories are allowed in a working installation.
    # Build artifacts and local helper files in root are still blocked.
    if (root / "_python_cmd.txt").exists():
        errors.append("_python_cmd.txt must not be shipped in release zip")
    if errors:
        print("RELEASE ROOT AUDIT: ERROR")
        for e in errors:
            print(" -", e)
        return 1
    print("RELEASE ROOT AUDIT: OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())

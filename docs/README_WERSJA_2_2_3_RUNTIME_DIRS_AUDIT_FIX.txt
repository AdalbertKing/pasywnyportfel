# pasywnyportfel ver. 2.2.3 — runtime dirs audit fix

## Problem

Po uruchomieniu analiz `check_project.cmd` zgłaszał:

```text
RELEASE ROOT AUDIT: ERROR
 - unexpected root dir: analysis_results
 - unexpected root dir: reports
```

## Diagnoza

To nie był błąd analizy. `analysis_results` i `reports` są normalnymi katalogami roboczymi tworzonymi po przebiegach.

## Poprawka

`release_root_audit.py` dopuszcza teraz:

```text
analysis_results
reports
```

Dalej blokuje śmieci w root, np. `_VER_*`, `_STAGE*`, `_init_check_report.csv`, `_python_cmd.txt`.

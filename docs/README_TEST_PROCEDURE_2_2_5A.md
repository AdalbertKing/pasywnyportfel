# Procedura testowa — VER 2.2.5A

Autor: Wojciech Król, lurk@lurk.com.pl  
Dotyczy: refaktoring modularny (common.py, task_config.py, cmd_builders.py,
ledger_primitives/io/tax/engine), poprawka bool_setting, walidacja start < end,
requirements.txt.

---

## Kiedy uruchamiać testy

| Sytuacja | Testy |
|---|---|
| Po rozpakowaniu nowej wersji | Faza 1 → 4 (minimum) |
| Po `1-start_setup.cmd` | Wszystkie fazy (1–7) |
| Po edycji `settings.csv` lub `portfolios.csv` | Faza 4 (`check_task`) |
| Po `refresh_data.cmd` | Faza 3 |
| Po `refresh_quotes.cmd` | Faza 5 |
| Po modyfikacji kodu w `app\bin\` | Faza 1 + 2 + wybrany task |
| Podejrzenie uszkodzenia środowiska | Faza 1 |

---

## Szybka ścieżka — jeden skrypt

```cmd
test_after_start.cmd
```

Uruchamia automatycznie wszystkie 7 faz (patrz niżej) i drukuje podsumowanie:

```text
PODSUMOWANIE
  OK:   24
  WARN: 1    (nie blokują działania; warto sprawdzić)
  FAIL: 0    (wymagają interwencji)
WYNIK: OK z ostrzeżeniami. Projekt działa.
```

`WARN` nie blokuje analiz. `FAIL > 0` oznacza problem wymagający interwencji.  
Skrypt zwraca `%ERRORLEVEL%` równy liczbie FAILów — można go wpinać w automatyzację.

---

## Fazy szczegółowo

### Faza 1 — Środowisko Python

**Co sprawdza:** czy wszystkie biblioteki zewnętrzne są zainstalowane i czy
wszystkie moduły projektu importują się bez błędu.

```cmd
python -c "import pandas, numpy, matplotlib, yfinance, dateutil; print('OK biblioteki')"
```

Moduły projektu (wszystkie muszą importować się bez błędu):

```cmd
python -c "import sys; sys.path.insert(0,'app/bin'); import common;           print('OK common')"
python -c "import sys; sys.path.insert(0,'app/bin'); import task_config;      print('OK task_config')"
python -c "import sys; sys.path.insert(0,'app/bin'); import cmd_builders;     print('OK cmd_builders')"
python -c "import sys; sys.path.insert(0,'app/bin'); import ledger_primitives; print('OK ledger_primitives')"
python -c "import sys; sys.path.insert(0,'app/bin'); import ledger_io;        print('OK ledger_io')"
python -c "import sys; sys.path.insert(0,'app/bin'); import ledger_tax;       print('OK ledger_tax')"
python -c "import sys; sys.path.insert(0,'app/bin'); import ledger_engine;    print('OK ledger_engine')"
python -c "import sys; sys.path.insert(0,'app/bin'); import passive_ledger;   print('OK passive_ledger')"
python -c "import sys; sys.path.insert(0,'app/bin'); import analysis;         print('OK analysis')"
```

**Oczekiwane:** każda linia drukuje `OK <nazwa>`.  
**Jeśli FAIL:** `pip install -r requirements.txt` i uruchom ponownie.

---

### Faza 2 — Kompilacja i struktura projektu

**Co sprawdza:** składnię Pythona wszystkich 12 modułów, strukturę plików
projektu (startup_order.csv, .cmd, mapy), walidację wszystkich tasków.

```cmd
check_stage1.cmd
```

lub bezpośrednio:

```cmd
python app\bin\stage1_quick_check.py
```

**Oczekiwane:**

```text
OK COMPILE app/bin/common.py
OK COMPILE app/bin/task_config.py
OK COMPILE app/bin/cmd_builders.py
OK COMPILE app/bin/analysis.py
OK COMPILE app/bin/ledger_primitives.py
OK COMPILE app/bin/ledger_io.py
OK COMPILE app/bin/ledger_tax.py
OK COMPILE app/bin/ledger_engine.py
OK COMPILE app/bin/passive_ledger.py
...
OK TASK benchmark_1970_synth_usd_gross: portfolios=10, maps=10, period=1970-01-31 -> 2026-03-31
...
WYNIK: OK — stage1 task model jest spójny.
```

**Jeśli FAIL:** sprawdź który moduł nie kompiluje i szukaj błędu składni
(brakujący nawias, cudzysłów, wcięcie).

---

### Faza 3 — Dane wspólne CPI / FX / biblioteki

**Co sprawdza:** istnienie i świeżość plików wejściowych używanych
przez wszystkie analizy.

```cmd
check_common_data.cmd
```

Szczegółowe sprawdzenie świeżości (ostatnia data w każdym pliku):

```cmd
python -c "
import csv, datetime as dt
files = {'CPI_USD': 'data/in/cpi/CPI_USD.csv', 'CPI_PLN': 'data/in/cpi/CPI_PLN_GUS.csv', 'FX': 'data/in/fx/DB_FX.csv'}
today = dt.date.today()
for label, path in files.items():
    last = None
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.reader(f):
            if row:
                try: last = dt.date.fromisoformat(row[0].strip()[:10])
                except: pass
    if last:
        age = (today - last).days
        print(f'  {\"OK  \" if age < 120 else \"WARN\"} {label}: {last} ({age}d temu)')
"
```

**Oczekiwane:** `OK` dla każdego pliku, wiek danych poniżej 120 dni.  
**Jeśli WARN:** `refresh_data.cmd` odświeży CPI i FX.  
**Jeśli BRAK:** plik nie istnieje — `run_task.cmd` spróbuje go wygenerować
automatycznie przez `bootstrap.py --generate-missing`.

---

### Faza 4 — Walidacja tasków

**Co sprawdza:** poprawność `settings.csv` i `portfolios.csv` każdego taska:
istnienie plików map, sumy wag = 100%, `start < end` po rozwiązaniu tokenów AUTO.

Jeden task:

```cmd
check_task.cmd user_template
check_task.cmd bfly_10y_vs_vuds_2005
check_task.cmd daily_hist_smoke_3m
```

Wszystkie taski naraz:

```cmd
for /d %D in (analysis_definitions\*) do (
    if exist "%D\settings.csv" python app\bin\validate_task.py "%~nxD"
)
```

**Oczekiwane:**

```text
OK TASK: user_template
  period: 2005-01-31 -> 2026-03-31
  portfolios INCLUDE=1: 2
  checked maps: 4
  OK MAP_SYNTH my_portfolio_sp500  ...  weights=100.00
  OK MAP_HIST  my_portfolio_sp500  ...  weights=100.00
```

**Jeśli FAIL — start >= end:**

```text
ERROR: start >= end po rozwiązaniu tokenów:
  start: '2026-06-01' -> 2026-06-01
  end:   '2026-03-31' -> 2026-03-31
```

Popraw daty w `settings.csv` taska.

**Jeśli FAIL — brak mapy:**

```text
ERROR: brak MAP_HIST dla my_portfolio_sp500: maps\hist\...
```

Sprawdź czy plik mapy istnieje w folderze taska.

---

### Faza 5 — Pokrycie notowań HIST

**Co sprawdza:** czy lokalna biblioteka ETF (`HIST_LIBRARY_DAILY.csv`)
pokrywa wymagany zakres dat dla każdego taska.

```cmd
check_quotes.cmd user_template
check_quotes.cmd bfly_10y_vs_vuds_2005
check_quotes.cmd --startup
```

**Oczekiwane:** `OK` lub informacja o pokrytym zakresie.  
**Jeśli WARN/FAIL:** biblioteka jest pusta lub zbyt krótka.

```cmd
refresh_quotes.cmd user_template
```

Pobiera brakujące notowania z Yahoo Finance (wymaga internetu).

> Uwaga: task `daily_hist_smoke_3m` wymaga danych za ostatnie 3 miesiące —
> po dłuższej przerwie może potrzebować `refresh_quotes.cmd`.

---

### Faza 6 — Wyniki analiz

**Co sprawdza:** czy `1-start_setup.cmd` wyprodukował wyniki.

```cmd
dir analysis_results\
```

Każdy folder wynikowy powinien zawierać `README_ANALYSIS.txt`:

```cmd
for /d %D in (analysis_results\*) do (
    if exist "%D\README_ANALYSIS.txt" (echo OK   %~nxD) else (echo WARN %~nxD — brak README)
)
```

Indeks wszystkich uruchomień:

```cmd
type reports\analysis_index.csv
```

**Oczekiwane po `1-start_setup.cmd`:**

```text
analysis_results\benchmark_1970_synth_usd_gross__20260610_143022\
analysis_results\synth_vs_etf_2005_full10__20260610_143158\
```

**Jeśli brak folderów:** `1-start_setup.cmd` nie ukończył analiz.
Sprawdź logi — zwykle jest to brak danych HIST lub błąd pobierania.

---

### Faza 7 — Smoke test CLI

**Co sprawdza:** czy główne punkty wejścia CLI uruchamiają się bez błędu.

```cmd
python app\bin\passive_ledger.py --help
python app\bin\analysis.py --help
python app\bin\refresh_quotes.py --help
python app\bin\validate_task.py --help
python app\bin\bootstrap.py --help
```

**Oczekiwane:** każde polecenie drukuje help i kończy się kodem 0.

---

## Testy dla nowych funkcji VER 2.2.5A

### Test bool_setting — puste VALUE

Weryfikuje poprawkę buga: puste `VALUE` w `settings.csv` musi zwracać `default`,
a nie zawsze `True`.

```cmd
python -c "
import sys; sys.path.insert(0,'app/bin')
from common import bool_setting
assert bool_setting({'k': ''},  'k', True)  == True,  'puste VALUE + default=True'
assert bool_setting({'k': ''},  'k', False) == False, 'puste VALUE + default=False'
assert bool_setting({'k': '0'}, 'k', True)  == False, '0 -> False'
assert bool_setting({},         'k', True)  == True,  'brak klucza -> default'
print('OK bool_setting')
"
```

### Test validate_dates — start < end

Weryfikuje walidację zakresu dat, w tym tokeny AUTO.

```cmd
python -c "
import sys; sys.path.insert(0,'app/bin')
from validate_task import validate_dates
try:
    validate_dates({'start': '2026-06-01', 'end': '2005-01-01'})
    print('ERR — powinien rzucic ValueError')
except ValueError as e:
    print('OK validate_dates wykryl start > end')
s, e = validate_dates({'start': 'AUTO-3M', 'end': 'AUTO'})
print(f'OK AUTO tokeny: {s} -> {e}')
"
```

### Test modularnosci — zadna stara funkcja nie znikna

Weryfikuje że `analysis` nadal eksportuje wszystkie funkcje używane przez
zewnętrzne skrypty.

```cmd
python -c "
import sys; sys.path.insert(0,'app/bin')
import analysis
required = ['run','step','ledger_cmd','plot_cmd','summary_cmd','table_cmd',
            'crash_cmd','make_run_names','read_portfolios','setting_value',
            'resolve_auto_dates','has_pln_outputs','detect_root','rel']
missing = [f for f in required if not hasattr(analysis, f)]
print('FAIL brak:', missing) if missing else print(f'OK wszystkie {len(required)} funkcji dostepne')
"
```

---

## Typowe problemy i rozwiązania

| Objaw | Przyczyna | Rozwiązanie |
|---|---|---|
| `ModuleNotFoundError: No module named 'common'` | skrypt uruchomiony spoza katalogu projektu | `cd /d D:\analises\pasywnyportfel` |
| `ModuleNotFoundError: No module named 'yfinance'` | brak biblioteki | `pip install -r requirements.txt` |
| `start >= end` w validate_task | złe daty w settings.csv | popraw `start` i `end` |
| `HIST_LIBRARY_DAILY.csv` pusta | pierwsze uruchomienie lub długa przerwa | `refresh_quotes.cmd <task>` |
| `analysis_results` pusty po setup | błąd podczas analizy | sprawdź output `1-start_setup.cmd` |
| WARN świeżość CPI > 120 dni | stare dane | `refresh_data.cmd` |
| `yfinance` błąd pobierania | zmiana API | `pip install --upgrade yfinance` |

---

## Środowisko reprodukowalne

Jeśli coś działa inaczej niż oczekiwano po aktualizacji bibliotek:

```cmd
pip install -r requirements-lock.txt
```

Przywraca dokładnie przetestowane wersje z VER 2.2.5A.

---

## Hierarchia modułów (dla debugowania)

```text
passive_ledger.py  →  ledger_engine.py  →  ledger_primitives.py
                                        →  ledger_io.py
                                        →  ledger_tax.py

analysis.py        →  task_config.py   →  common.py
                   →  cmd_builders.py  →  task_config.py
                   →  common.py

validate_task.py   →  common.py
stage1_quick_check →  validate_task.py
```

Jeśli moduł wyżej w hierarchii nie importuje się, błąd leży w module
niżej (np. błąd w `ledger_primitives.py` zepsuje import `ledger_engine.py`
i `passive_ledger.py`).

---

*Poprzednia wersja procedury: `docs\README_TEST_PROCEDURE_STAGE1.txt`*  
*Autor: Wojciech Król, lurk@lurk.com.pl*

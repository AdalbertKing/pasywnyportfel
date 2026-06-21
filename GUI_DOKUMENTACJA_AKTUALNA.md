# pasywnyportfel GUI — Dokumentacja referencyjna

Data: 2026-06-21
Status: Etap 0 + Etap 1 ZBUDOWANE i PRZETESTOWANE na realnych danych użytkownika.
Branch: `GUI` (osobny od `main` — `main` ma TYLKO silnik, nigdy `gui.py`).

## 0. Jak korzystać z tego dokumentu

To jest **jedyne aktualne źródło prawdy** o GUI. Zastępuje `docs/GUI_PROJECT_SPEC.md`
i `docs/GUI_REFERENCE.md` — oba miały błędne założenie (REBALANCE jako parametr
taska, nie portfela) i nieistniejące funkcje silnika (`tax_label()`,
wcześniejsza wersja `validate_task()`). Wszystko poniżej zweryfikowane
bezpośrednio w kodzie repo i realnym uruchomieniem, nie zgadywane.

Jeśli zaczynasz nową rozmowę o tym projekcie — wklej ten plik na start.

---

## 1. Architektura

- **CustomTkinter** (`pip install customtkinter`) + `tkinter.PanedWindow`
- Plik: `app/bin/gui.py` (jeden plik, ~1500 linii) + launcher `gui.cmd` (CRLF!)
- GUI **importuje moduły silnika bezpośrednio** (`common`, `task_config`,
  `cmd_builders`, `validate_task`) — zero subprocess dla odczytu danych.
  Subprocess (w wątku) tylko dla: `analysis.py`, `refresh_quotes.py`.
- `ROOT` i `GUI_DIR` wykrywane relatywnie do położenia `gui.py`:
  `GUI_DIR = Path(__file__).resolve().parent` (czyli `app/bin`),
  `ROOT = GUI_DIR.parent.parent`.
- `find_script(name)` — resolver lokalizujący pliki wykonywalne (`analysis.py`,
  `refresh_quotes.py`), sprawdza `GUI_DIR` i `ROOT`, zwraca bezwzględną ścieżkę.
  Powód istnienia: pierwsza wersja patcha zakładała `analysis.py` w `ROOT`,
  realnie jest w `app/bin` — stąd resolver zamiast sztywnej ścieżki.
- Wszystkie importy modułów silnika owinięte w `try/except ImportError` —
  `ENGINE_AVAILABLE` flaguje tryb demo gdy moduły niedostępne (np. testowanie
  GUI poza repo). Każda metoda `Engine` ma fallback do danych demo.

## 2. Standard wizualny

- **`UI_SCALE = 1.45`** — JEDEN wspólny mnożnik napędzający i fonty (`_px()`,
  ujemne = piksele dosłowne w Tkinter), i wymiary (`_dim()`). Historia: pierwsza
  wersja użyła dosłownie 7-9px ze specu — nieczytelne na 24" FHD bez okularów.
  Zmiana skali = zmiana JEDNEJ liczby, zweryfikowane testem (UI_SCALE=1.0
  skalowało całość proporcjonalnie, łącznie z wymiarami nie tylko fontami).
- Bazowe wartości (×UI_SCALE): główny tekst 9px, nagłówki sekcji 8px (caps),
  hinty/tagi 7px, konsola mono 8px, statusbar 7px.
- Trzy tokeny odstępów: `PAD`, `PAD_TIGHT`, `PAD_LOOSE` — wszystkie `padx`/`pady`
  w pliku przez nie, nie gołe liczby.
- Paleta: stałe `COL_BG/COL_PANEL/COL_ACCENT/COL_OK/COL_WARN/COL_FAIL/COL_FLAG/
  COL_TEXT/COL_TEXT_DIM/COL_BORDER`.
- **Standard PanedWindow**: każdy podział lista/treść (sidebar↔zakładki, i każdy
  przyszły podział w Wyniki/Portfele) — `tkinter.PanedWindow` z przeciąganym
  sashem, min/max pilnowane ręcznie (PanedWindow nie ma natywnego maxsize).
- Zero kafelków/kart. Checkboxy, radio, dropdown, listy.
- **Czcionki w polach edycyjnych = ten sam rozmiar co etykiety obok** (jawny
  `font=(...)`, bo domyślne potrafią się nie zgadzać).

## 3. Stałe elementy okna — Etap 0 (zbudowane, przetestowane)

- **Sidebar**: PanedWindow, zakres 140–420px (domyślnie 160px), lista tasków
  z kolorowymi kropkami statusu, przyciski "+ Nowy task" / "⟳ Odśwież dane
  CPI/FX" (oba wciąż stuby — TODO).
- **4 zakładki**: Uruchom (zbudowane), Konfiguracja / Wyniki / Portfele
  (placeholder, czeka na Etap 2-4).
- **Konsola komendy** (dół, zawsze widoczna): 3↔14 linii (rozwiń/zwiń),
  mono, kolorowanie (flagi pomarańczowe, wartości zielone), przycisk kopiuj.
  Tekst **zaznaczalny myszą + Ctrl+C**, ale nie edytowalny (key-blocking
  zamiast `state="disabled"` — to drugie blokowało też zaznaczanie myszą,
  prawdziwy bug znaleziony i naprawiony).
- **Statusbar**: FAIL/WARN/OK po lewej (demo), wersja Python/testów/brancha
  po prawej (demo).

## 4. Zakładka Uruchom — Etap 1 (zbudowane, przetestowane na realnych danych)

### Parametry taska
Siatka klucz-wartość, **tylko odczyt** (edycja w przyszłej Konfiguracji):
Okres, Saldo startowe, Wyceny, Waluty wykresów, Podatek, Tryb.
Pod siatką: hint (kolor ostrzegawczy) o sprzężeniu Wyceny↔czułość DRIFT
(patrz §6 — dotyczy WYŁĄCZNIE trybu DRIFT, nie ANNUAL).

**Klucze potwierdzone w `settings.csv`** (KEY,VALUE format, czytane przez
`common.read_settings()` via `csv.DictReader` — **WIELOWARTOŚCIOWE POLA
MUSZĄ BYĆ CYTOWANE** np. `plot_currencies,"USD,PLN"`, inaczej parser urywa
po pierwszym przecinku — realny bug znaleziony w `daily_hist_smoke_3m`):
`start`, `end`, `saldo` (NIE "capital"), `freq` (NIE "valuation"),
`plot_currencies` (NIE "currencies"), `tax_mode`/`tax_base`/`tax_rate`,
`analysis_mode` (`synth_only`/`hist_only`/puste lub `both`=oba).

### Portfele w analizie
Lista **klikalnych** kart (`PortfolioRow`) — klik = focus (niebieska ramka
2px), pierwszy portfel auto-zaznaczony po wczytaniu taska. Nawigacja
**strzałkami Góra/Dół** (bindowane na głównym oknie przez `bind_all`,
ograniczone do aktywnej zakładki Uruchom — `CTkFrame` NIE wspiera
`takefocus`, więc `self.bind()`/`self.focus_set()` bezpośrednio na widgecie
nigdy realnie nie łapie klawiatury — potwierdzone `ValueError` przy próbie
`cget('takefocus')`). Scroll kółkiem: `yscrollincrement` podbity ręcznie
(domyślne 1px w CTk na Windows jest za mało czułe).

Per portfel:
- Checkbox **INCLUDE** — jedyny faktycznie klikalny, niebieski gdy zaznaczony
- **4 checkboxy informacyjne** (nieklikalne, `state="disabled"`,
  **jednolicie szare niezależnie od stanu** — świadoma decyzja, żeby nie
  wyglądały jak coś klikalnego, w odróżnieniu od INCLUDE):
  `DRIFT [%]`, `Autorebalans [okres]`, `SYNTH`, `HIST`
- Ostrzeżenie ⚠ HIST — **realne**, z `validate_task()` (6. element zwrotki:
  `warnings`), zmapowane po ID portfela. Sprawdza WYŁĄCZNIE czy ticker
  istnieje w `HIST_LIBRARY_DAILY.csv` — NIE pokrycie zakresu dat. Przycisk
  "Pobierz brakujące" wciąż stub (TODO — wymaga przekazania `gui`/nazwy
  taska do `PortfolioRow`, czego dziś nie ma).
- Panel szczegółów zaznaczonego portfela (pod zwężonymi przyciskami akcji,
  po prawej): pusty kwadrat (rezerwacja pod przyszły wykres kołowy składu —
  świadomie pusty, wymaga doczytania `MAP_SYNTH`/`MAP_HIST`, TODO) + nazwa +
  rebalans + ścieżki map, aktualizuje się przy każdym zaznaczeniu.

### Akcje (przyciski zwężone, wyrównane do lewej)
- **▶ Uruchom** — pełny pipeline w jednym wątku: `refresh_quotes.py --check`
  (offline) → jeśli braki, realny `refresh_quotes.py` → `analysis.py`. Jeden
  ciągły strumień stdout do konsoli. Jeśli refresh padnie (brak neta) —
  przerywa z czytelnym komunikatem (TODO: docelowo modal "Uruchomić bez
  HIST?" zamiast twardego przerwania — wymaga kolejki wątek→główny wątek).
- **Dry-run** — ŚWIADOMIE bez auto-refresh (ma być szybkim podglądem).
- **Refresh HIST** — samodzielne odświeżenie, real.
- **Waliduj** — realne `validate_task()`, pokazuje `OK — N portfeli, okres
  X→Y` plus ewentualne ostrzeżenia.

### Ostatnie przebiegi
Lista OK/FAIL — **wciąż dane demo**, `list_runs()` nie czyta jeszcze
prawdziwego `analysis_results/` (TODO, wymaga znajomości struktury folderów
wynikowych poza tym co już potwierdzone w §5).

---

## 5. Potwierdzony interfejs silnika — NIE zgadywać, tu jest prawda

**KRYTYCZNE: repo ma DWIE różne wersje** w obiegu. Zip `FINAL3_2` (pierwszy
przesłany) jest STARSZY niż branch `GUI` — brakuje mu `run_logging.py`,
`health_check.py`, `task_config.list_tasks()`, `validate_task._pick_col()`.
**Zawsze weryfikuj na `git show HEAD:app/bin/<plik>`, nie na starym zipie.**

```python
# common.py
read_settings(path: Path) -> dict          # KEY,VALUE csv, csv.DictReader
detect_root(...), rel(...), task_rel(...), bool_setting(...), truthy(...)

# task_config.py
read_portfolios(path: Path) -> list[dict]  # surowe kolumny CSV
list_tasks(root: Path) -> list[str]        # bierze root jako argument!
setting_value(settings, key, default="") -> str
is_synth_only(settings) -> bool            # "synth"/"synthetic"/"synth_only"/"synthetic_only"
is_hist_only(settings) -> bool             # "hist"/"hist_only"/"historical"/"historical_only"/"etf"/"etf_only"
has_pln_outputs(settings) -> bool          # fx+cpi_pl+value_col_pln wszystkie ustawione
plot_currencies(settings) -> list[str]     # domyślnie ["USD"]+["PLN"] jeśli has_pln_outputs
# UWAGA: tax_label() NIE ISTNIEJE — GUI buduje etykietę sam z tax_mode/tax_base/tax_rate

# validate_task.py
validate_task(root: Path, task_name: str)
  -> (task_dir, included: int, checked_maps: list, start_iso: str, end_iso: str, warnings: list[str])
  # RZUCA wyjątek przy błędzie krytycznym. 6 WARTOŚCI, nie 5!
  # warnings: string format "<ID> (<plik>): brak [...] w HIST_LIBRARY_DAILY.csv (kolumna YFTicker) — uruchom refresh_quotes.cmd <task>"
  # Sprawdza TYLKO obecność tickera w bibliotece, NIE pokrycie dat.
_pick_col(columns, names) -> Optional[str]

# cmd_builders.py
run(cmd, root, dry_run) -> int
mode_label(rebalance, max_drift, rebal_period="") -> str       # "Buy & Hold" / "Rebalans po DRIFT20" / "Rebalans roczny" / "Rebalans co 6M + DRIFT20"
file_mode_token(rebalance, max_drift, rebal_period="") -> str  # "BH" / "DRIFT20" / "Rebalans roczny" (sic, ma spację — legacy, nie zmieniać) / "DRIFT20_PERIOD6M"
display_name(label, dataset, rebalance, max_drift, rebal_period="") -> str
detect_modes(portfolios: list[dict]) -> str
ledger_cmd(root, settings, portfolio_map, db_path, out_path, rebalance, max_drift, rebal_period="") -> list[str]
  # BH:     --period 9999M --max-drift 0 --no-rebalance
  # DRIFT:  --period 9999M --max-drift NN --conditional-rebalance
  # PERIOD: --period NM --max-drift 0                              (legacy ANNUAL = period_token "12M")
  # COMBO:  --period NM --max-drift NN                              (BEZ conditional-rebalance/no-rebalance!)

# analysis.py — prawdziwa komenda CLI (NIE --task/--tax/--drift, te nigdy nie istniały)
python app/bin/analysis.py --root <ROOT> --definition analysis_definitions/<task> [--dry-run]
# --root domyślnie "AUTO" (autodetekcja), --definition akceptuje ścieżkę względną do root

# refresh_quotes.py
python app/bin/refresh_quotes.py <task_name> --root <ROOT> [--check]
# --check: offline, exit 0=pokryte / 2=brakuje. Bez --check: realny fetch (yfinance, wymaga neta).
```

### Format `settings.csv` (potwierdzony)
`KEY,VALUE` (2 kolumny), BOM (`utf-8-sig`). **Wielowartościowe pola MUSZĄ być
cytowane**: `"USD,PLN"` nie `USD,PLN` — inaczej `csv.DictReader` z 2-kolumnowym
nagłówkiem urywa po pierwszym przecinku (prawdziwy bug znaleziony i
naprawiony w `daily_hist_smoke_3m`).

### Format `portfolios.csv` (potwierdzony)
`ID, LABEL, MAP_SYNTH, MAP_HIST, REBALANCE, MAX_DRIFT, REBAL_PERIOD, INCLUDE`
(REBAL_PERIOD dodane patchem 2026-06-19/20, opcjonalne, wstecznie zgodne).
**Brak kolumny `WEIGHT`** — skład procentowy żyje WEWNĄTRZ plików pod
`MAP_SYNTH`/`MAP_HIST` (potwierdzone w `validate_task.py: weight_sum()`),
nie w `portfolios.csv` samym. GUI tego jeszcze nie czyta (TODO).

---

## 6. Model REBALANCE — najważniejsza korekta całego projektu

**REBALANCE/MAX_DRIFT/REBAL_PERIOD to atrybuty PER PORTFEL** (kolumny w
`portfolios.csv`), **NIE ustawienie taska**. Pierwsza wersja specu (i GUI)
zakładała jedno globalne pole "Rebalans" w Parametrach taska — błędne,
poprawione po przeczytaniu realnego kodu silnika.

**Cztery tryby**, potwierdzone w `cmd_builders._resolve_rebalance()` i
zweryfikowane realnym uruchomieniem (zdarzenia `REBAL`/`REBAL_DRIFT` w
wynikowych ledgerach):

| Tryb | REBALANCE | MAX_DRIFT | REBAL_PERIOD | Zachowanie silnika |
|---|---|---|---|---|
| BH | `BH` | — | — | nigdy nie rebalansuje |
| DRIFT | `DRIFT` | np. `20` | — | rebalans WYŁĄCZNIE gdy przekroczony próg |
| PERIOD | dowolne (legacy: `ANNUAL`/`12M`) | — | np. `6M` | rebalans wyłącznie na harmonogram, próg ignorowany |
| COMBO | `DRIFT` | np. `20` | np. `6M` | OBA mechanizmy naraz (potwierdzone: 112 `REBAL` + 1 `REBAL_DRIFT` w realnym teście) |

**Sprzężenie Wyceny↔DRIFT** (NIE dotyczy PERIOD): próg sprawdzany TYLKO na
zresamplowanych datach (`_resample_prices_to_freq`, `ledger_engine.py:148`,
`is_drift_breached` linia 335) — przy `freq=monthly` portfel może realnie
przekroczyć próg między sprawdzeniami, przy `daily`/`weekly` rzadziej.
Zweryfikowane empirycznie: monthly złapał 2 zdarzenia `REBAL_DRIFT` vs 4 przy
daily/weekly na tym samym portfelu/oknie.

**Format `--period`**: WYŁĄCZNIE miesiące, regex `^\d+M$`
(`ledger_engine.py:291`) — żadnych tygodni/dni. To inny wymiar niż `freq`
(Wyceny: daily/weekly/monthly) — nie mylić.

**Status patcha**: `cmd_builders.py`/`analysis.py` z obsługą REBAL_PERIOD
zacommitowane, 430/431 testów przechodzi (jedyny fail to nieaktualne
założenie testu wobec już-uzupełnionej biblioteki HIST użytkownika, nie
regresja). 7 plików `portfolios.csv` (6 realnych tasków + 1 szablon
`common/task_templates/comparison_2005/`) ma już kolumnę `REBAL_PERIOD`
(pustą poza przykładem w `us6040`).

**GUI dziś**: pokazuje 2 niezależne checkboxy (DRIFT+%, Autorebalans+okres)
w Uruchom — **tylko podgląd, nieklikalne**. Edycja (Konfiguracja, Etap 2)
jeszcze niezbudowana.

---

## 7. Pozostałe zakładki — zaprojektowane, NIEZBUDOWANE (Etap 2-4)

### Konfiguracja (Etap 2)
Sekcje: Okres analizy / Podatek (gross↔net wyszarza pola) / Dane wejściowe /
Opcje wyjścia / **Portfele w analizie z EDYTOWALNYM rebalansem per portfel**
(te same 2 checkboxy co Uruchom, ale klikalne: radio/checkbox DRIFT+pole %,
checkbox Autorebalans+pole okres). Dolny pasek: Cofnij zmiany / Waliduj /
Zapisz.

### Wyniki (Etap 3)
Eksplorator przebiegów (max 4 zaznaczone checkboxy) → tryb pojedynczy
(najlepszy portfel wg kryterium, ranking z presetami kolumn, eksplorator
wykresów-miniaturek, run.log) albo tryb porównania (parametry obok siebie,
żółty pasek różnic, porównanie per portfel — **rebalans jako część tego**,
nie osobna wartość taska, zgodnie z §6).

### Portfele — konstruktor (Etap 4)
Dwa tryby: Indeksy historyczne (katalog sektorowy + tort kołowy) / Tickery
Yahoo. **Rebalans edytowalny TUTAJ TEŻ** (przy tworzeniu portfela — to też
pisze do tych samych kolumn `portfolios.csv`, drugie wejście do tych samych
danych co Konfiguracja). Auto-start date na najwcześniejszą wspólną datę.

### Ekran powitalny (Etap 5)
Przy pierwszym otwarciu, link do akademia.atlasetf.pl, nie pojawia się
ponownie.

---

## 8. Workflow gita

- **`main`** = TYLKO silnik (CLI, testy) — `gui.py` NIGDY tam nie trafia.
- **`GUI`** = pełny branch z `gui.py` + silnikiem.
- Poprawki silnika (np. patch REBAL_PERIOD) robione na `GUI`, potem
  przenoszone na `main` osobnym commitem (`git checkout main && git
  checkout GUI -- app/bin/cmd_builders.py app/bin/analysis.py ... && git
  commit`), NIE merge całego brancha.
- `.gitattributes` (`* text=auto eol=lf`, `*.cmd text eol=crlf`) — rozwiązuje
  realny bug: 116 plików pokazywało się jako "zmienione" w `git status` przez
  same końce linii (LF↔CRLF), nie treść.

## 9. Metodologia weryfikacji (trzymać się tego nadal)

Każda zmiana w `gui.py`: (1) syntax check (`ast.parse`), (2) deploy do
realnej kopii repo użytkownika (nie sandbox-zip), (3) uruchomienie pod Xvfb,
(4) zrzut ekranu + realne kliknięcie/klawiatura (nie tylko "się nie wywala"),
(5) dla zmian silnika: dodatkowo `pytest tests/` na realnym repo. Kopiowanie
plików ZAWSZE jako pojedyncza atomowa komenda `cp X Y && diff X Y` —
oddzielne wywołania `cp` i `diff` w osobnych krokach raz po raz pokazywały
nieaktualny stan (race condition w wykonaniu poleceń).

## 10. Znane TODO (jawnie, nie ukrywać)

- `list_runs()` — dane demo, nie czyta `analysis_results/`
- Skład portfela (% per asset) — wymaga doczytania `MAP_SYNTH`/`MAP_HIST`
- Przycisk "Pobierz brakujące" przy ostrzeżeniu HIST — stub
- Modal "Uruchomić bez HIST?" przy braku neta — dziś twarde przerwanie
- Ostrzeżenie HIST sprawdza tylko obecność tickera, nie pokrycie dat
- Wykres kołowy składu portfela — pusty kwadrat-placeholder, logika niezrobiona
- Etapy 2-4 (Konfiguracja/Wyniki/Portfele) — niezbudowane
- "+ Nowy task" / "Odśwież dane CPI/FX" w sidebarze — stuby

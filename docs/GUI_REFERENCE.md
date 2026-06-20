# pasywnyportfel GUI — Kompletna esencja projektu

Autor koncepcji: Wojciech Król (lurk@lurk.com.pl)
Data: 2026-06-20
Status: ZAAKCEPTOWANY — gotowy do implementacji

---

## A. KONTEKST PROJEKTU

### Co to jest
Desktop GUI (CustomTkinter) nad istniejącym silnikiem wsadowym (CLI)
do backtestowania portfeli pasywnych ETF. Silnik (VER 2.2.5A) jest zamknięty
i stabilny — 402 testy, CI zielone na GitHub.

### Zasada architektury
GUI **importuje** moduły silnika bezpośrednio (zero subprocess dla logiki):
- `task_config.list_tasks()` → lista tasków
- `validate_task()` → walidacja
- `read_settings()` / `read_portfolios()` → odczyt CSV
- `tax_label()` → etykieta podatkowa
- `cmd_builders.ledger_cmd()` → podgląd komendy

Długie operacje (analiza, refresh) → subprocess w wątku, stdout do konsoli.

### Technologia
- Python 3.13, CustomTkinter, tkinter.PanedWindow
- Plik: `app/bin/gui.py` + launcher `gui.cmd`
- Branch: `gui` (main = stabilny batch)
- Portable — dwuklik, zero serwera

---

## B. STANDARD WIZUALNY

### Kontrolki
- Checkboxy, radio buttony, dropdowny, listy
- **ŻADNYCH kafelków/kart** — user nie toleruje "kafelkozy"
- Inspiracja: Turbo Vision (DOS), CRM
- PanedWindow wszędzie (draggable splittery)

### Czcionki (kompaktowy CRM-style)
| Element | Rozmiar |
|---|---|
| Tekst główny, etykiety, inputy, dropdowny | 9px |
| Nagłówki sekcji | 8px uppercase |
| Hinty, ścieżki, tagi | 7-8px |
| Konsola komendy | 7-8px mono |
| Statusbar, sidebar tytuł | 7-8px |
| Pola wag | 9px |
| Tort kołowy — procenty | 7px |

### WAŻNE: tekst wewnątrz inputów = ten sam rozmiar co etykieta obok
(Był problem: przeglądarka nadpisywała domyślnym 14px. W Tkinter:
`font=("Segoe UI", 8)` explicit.)

### Layout
- Sidebar: 140-160px
- Padding: 2-6px
- Tort kołowy: 100px, bez etykiet % (są w liście)

### Etykiety (ustalone)
- "Wyceny" (nie "Częstotliwość")
- "Najgorsze okresy" (nie "Okna crash-test")
- "Indeksy historyczne" (nie "Z katalogu aktywów" / "syntetyczne")

---

## C. STAŁE ELEMENTY OKNA

### Sidebar (lewy panel, wszystkie zakładki)
- Lista tasków z kropkami: zielona = OK, żółta = WARN
- Kliknięcie → ładuje task do wszystkich zakładek
- Przyciski: "+ Nowy task", "Odśwież dane CPI/FX"

### Zakładki (góra)
- Uruchom | Konfiguracja | Wyniki | Portfele

### Konsola komendy (dół, zawsze widoczna)
- Mono 7-8px, ciemne tło
- Kolory: flagi pomarańczowe, wartości zielone, ścieżki szare
- Domyślnie 3 linie, scrollowalne
- "▼ rozwiń" / "▲ zwiń" jednym kliknięciem
- "📋 kopiuj" do schowka
- Przed uruchomieniem: podgląd składanej komendy (aktualizowany na żywo)
- Po kliknięciu Uruchom: stdout z subprocess na żywo
- Po zakończeniu: log zostaje

### Statusbar (sam dół)
- Lewa: ✓ FAIL:0 WARN:0 OK:42
- Prawa: Python 3.13 | 402 testów | gui branch

---

## D. ZAKŁADKA: URUCHOM

### Parametry taska (siatka klucz-wartość)
- Okres, Kapitał, Wyceny (dropdown)
- Waluty wynikowe: USD / USD+PLN
- Podatek: tag net_PLN 19% / gross
- Rebalans: ☑ Drift 20% ☐ Auto co — mies.

### Portfele w analizie (lista)
- Pełna nazwa (nie kody techniczne!)
- Checkbox INCLUDE (lewy) — wyłączenie wyszarza, BEZ skreślenia
- Checkboxy SYNTH / HIST per wariant:
  - ☑ zaznaczony = uruchom
  - ☐ odznaczony = pomiń (user decyzja)
  - wyszarzony = mapa nie istnieje
- Skład po ludzku: Gold 20%, US Stocks 20%...
- ETF-y: GLD, SPY, IJS...
- Ostrzeżenie HIST ⚠ + przycisk "Pobierz brakujące" (in-place)

### Akcje
- ▶ Uruchom (zielony), Dry-run, Refresh HIST, Waliduj

### Ostatnie przebiegi
- Tag OK (zielony) / FAIL (czerwony)
- Timestamp, czas, tax_mode, drift, portfele
- Link "📂 otwórz"

---

## E. ZAKŁADKA: KONFIGURACJA

Jeden ekran, sekcje przewijane:

1. **Okres analizy**: Start, End (z walidacją ✓), Kapitał, Wyceny
2. **Podatek**: Tryb (dropdown gross/net) → gdy net: waluta, stawka
   Gdy gross → waluta i stawka wyszarzone
3. **Rebalansowanie**: ☑ Drift [20] % ☐ Auto rebalans co [12] mies.
   Dwa checkboxy, pole aktywne tylko gdy zaznaczone
   Kombinacje: oba puste=BH, drift=drift, auto=kalendarzowy, oba=combo
4. **Dane wejściowe**: ścieżki read-only, ✓ przy istniejących
5. **Opcje wyjścia**: ☑ Wykresy ☑ Tabela summary ☑ Najgorsze okresy [3,5,7,10] lat
   Wszystko w jednej linii, inline
6. **Portfele**: jak w Uruchom (checkboxy, warianty, składy)

### Dolny pasek
- "↩ Cofnij zmiany" | "Waliduj" | "💾 Zapisz settings.csv + portfolios.csv"

---

## F. ZAKŁADKA: WYNIKI

### Eksplorator przebiegów (góra)
- Lista po lewej z checkboxami (max 4 zaznaczone, 5. wyszarzony)
- Każdy przebieg: timestamp, czas, tax_mode, drift, portfele
- FAIL: czerwony tag, wyszarzony checkbox
- Podgląd po prawej (kliknięcie):
  - Pełne parametry: okres, kapitał, wyceny, podatek, rebalans, portfele
  - "Zmienione vs poprzedni": lista różnic
  - Przyciski: 📂 Folder, 📄 run.log, 🗑 Usuń

### Tryb jednego przebiegu (1 checkbox)

**Najlepszy portfel:**
- Dropdown kryterium: CAGR / MaxDD / Recovery / StDev / Wartość
- Zmiana → inny portfel na szczycie

**Ranking portfeli:**
- Sortowanie kliknięciem nagłówka (↓/↕)
- Presety kolumn: Kompakt (5), Real pełny (9), Nominal (9),
  Real+nominal (14), Drawdown (6), Własny (checkboxy z ~35 kolumn)
- Zielone komórki = najlepsza wartość

**Eksplorator wykresów:**
- Miniaturki po lewej pogrupowane po portfelach (scrollowalne)
- Podgląd po prawej na hover/klik
- Dwuklik → os.startfile(png)
- Tabele summary PNG też jako miniaturki

**run.log:**
- Podgląd końcówki + przycisk "Pełny run.log"

### Tryb porównania (2-4 checkboxy)

**Parametry przebiegów obok siebie** — pełne, każdy w swojej kolumnie

**Żółty pasek różnic:**
- "Zmienione parametry (N): podatek gross→net, drift 15%→20%..."
- GUI NIE interpretuje przyczyn — tylko fakty

**Porównanie per portfel:**
- Każdy portfel osobną sekcją z PEŁNĄ NAZWĄ
- Metryki obok siebie + kolumna różnic
- Portfel tylko w jednym przebiegu → kreski (—)
- Ostrzeżenie: "Zmieniono N parametrów — efekt łączny"

**Wykresy:** per przebieg, NIE nakładane (nieczytelne)

---

## G. ZAKŁADKA: PORTFELE (konstruktor)

### Nagłówek
- ID + opis
- BEZ rebalansu (to jest w Konfiguracji, wspólne dla taska)

### Tryb budowania (radio button)
- ○ Indeksy historyczne — dane indeksowe od 1926 + ETF-y
- ○ Tickery Yahoo — dowolne ETF-y i walory

### Tryb "Indeksy historyczne"
- Katalog klas aktywów (lewy panel):
  Pogrupowany sektorowo: Akcje US, Międzynarodowe, Obligacje, Alternatywne
  Nazwy po ludzku ("Złoto", nie "GOLD_USD")
  Info: SYNTH od kiedy, sugerowane ETF-y
  Dane z `data/in/asset_catalog.csv`
- Skład portfela (prawy panel):
  Tort kołowy (100px, bez % — są w liście)
  Lista: kolor, nazwa, tagi SYNTH/ETF, waga, ×
  Walidacja sumy wag na żywo

### Tryb "Tickery Yahoo"
- Prosta tabela: ticker, opis, waga, status Yahoo, ×
- Pole "Sprawdź + dodaj"
- Tort + skład (ten sam panel)

### Reguły map
- Wszystkie składniki mają SYNTH → obie mapy
- Choć jeden bez SYNTH → tylko HIST
- NIE budujemy częściowego SYNTH

### ETF-y
- Domyślne z asset_catalog.csv
- Chipy alternatyw (kliknięcie wypełnia)
- "Sprawdź na Yahoo" → mini-download 1 dzień
- Status: ✓ od YYYY / ✗

### Auto-start date
- Przy zapisie: start = najwcześniejsza wspólna data tickerów
- User może zmienić na późniejszą
- Wcześniejsza → blokada z komunikatem

---

## H. EKRAN POWITALNY

- Przy pierwszym otwarciu (żaden task nie zaznaczony)
- Autor, koncepcja portfela pasywnego
- Link: https://akademia.atlasetf.pl/10-klasycznych-portfeli-pasywnych/
- "Dalej" → pierwszy task, zakładka Uruchom
- Nie pojawia się ponownie

---

## I. SCHEMAT DZIAŁANIA PROGRAMU

### Co się dzieje krok po kroku

```
USER OTWIERA GUI
│
├── Pierwszy raz?
│   └── TAK → ekran powitalny → "Dalej" → pierwszy task
│       └── Pasek "pierwszy raz" na górze Uruchom
│
├── Klika task w sidebarze
│   └── read_settings() + read_portfolios() + validate_task()
│       └── Wypełnia WSZYSTKIE zakładki danymi tego taska
│
├── Zakładka URUCHOM
│   ├── Widzi parametry + portfele + ostatnie przebiegi
│   ├── Klika "▶ Uruchom"
│   │   ├── HIST ⚠? → auto-pobieranie brakujących tickerów
│   │   │   └── Brak internetu? → "Uruchomić bez HIST?" Tak/Anuluj
│   │   ├── Niezapisane zmiany w Konfiguracji?
│   │   │   └── "Zapisać i uruchomić?" Tak/Nie
│   │   ├── Przycisk → "■ Przerwij", reszta wyszarzona
│   │   ├── Konsola rozszerza się, stdout na żywo
│   │   └── Po zakończeniu:
│   │       ├── OK → nowy przebieg na liście (zielony)
│   │       └── FAIL → przebieg na liście (czerwony, wyszarzony checkbox)
│   ├── Klika "Dry-run" → stdout do konsoli, bez realnych plików
│   ├── Klika "Refresh HIST" → subprocess refresh_quotes.py
│   └── Klika "Waliduj" → validate_task() → aktualizacja statusów
│
├── Zakładka KONFIGURACJA
│   ├── Edytuje pola → konsola przebudowuje komendę na żywo
│   ├── Checkbox drift on/off → pole progu aktywne/wyszarzone
│   ├── Dropdown tax gross/net → waluta+stawka aktywne/wyszarzone
│   ├── Checkbox SYNTH/HIST per portfel → wariant włączony/wyłączony
│   ├── "Pobierz brakujące" przy HIST ⚠ → subprocess refresh_quotes.py
│   ├── "Cofnij zmiany" → reload z dysku
│   ├── "Waliduj" → validate_task() + validate_tax_settings()
│   └── "💾 Zapisz" → walidacja → zapis settings.csv + portfolios.csv
│
├── Zakładka WYNIKI
│   ├── Klika przebieg na liście → podgląd parametrów po prawej
│   ├── Zaznacza 1 checkbox → ranking + najlepszy + wykresy + log
│   │   ├── Klika nagłówek kolumny → sortowanie
│   │   ├── Klika preset → zmiana kolumn
│   │   ├── Zmienia kryterium najlepszego → inny portfel na szczycie
│   │   ├── Najeżdża miniaturkę wykresu → podgląd po prawej
│   │   └── Dwuklik miniaturkę → pełny rozmiar (os.startfile)
│   ├── Zaznacza 2-4 checkboxy → tryb porównania
│   │   ├── Parametry obok siebie
│   │   ├── Żółty pasek różnic
│   │   └── Porównanie per portfel z różnicami
│   └── 5. checkbox wyszarzony (limit 4)
│
├── Zakładka PORTFELE
│   ├── Radio: Indeksy historyczne / Tickery Yahoo
│   ├── Tryb indeksów:
│   │   ├── Katalog sektorowy po lewej → "+ dodaj"
│   │   ├── Tort + skład po prawej → wagi, ×
│   │   ├── Tabela ETF → chipy, "Sprawdź Yahoo"
│   │   └── "💾 Zapisz mapy + portfolios.csv"
│   └── Tryb tickerów:
│       ├── Tabela: ticker, opis, waga → "Sprawdź + dodaj"
│       ├── Tort + skład po prawej
│       └── "💾 Zapisz" → tylko mapa HIST
│
└── "+ Nowy task" (sidebar)
    └── Dialog: nazwa + szablon → Utwórz → zakładka Portfele
```

---

## J. MAPA ZDARZEŃ

| Typ | Ilość | Opis | Blokuje GUI? |
|---|---|---|---|
| GUI | 18 | Sortowanie, show/hide, przebudowa komendy | Nie |
| READ | 5 | validate_task, read_settings, read_csv | Nie (<1s) |
| WRITE | 2 | Zapis settings/portfolios, zapis map | Nie (<1s) |
| ASYNC | 5 | Analiza, dry-run, refresh danych/HIST, Yahoo check | Nie (wątek) |

---

## K. SYNC vs ASYNC

| Natychmiast (<1s) | Wątek w tle |
|---|---|
| read_settings, read_portfolios | analysis.py (1-4 min) |
| validate_task, validate_dates | refresh_quotes.py (5-30s) |
| write CSV | refresh_data.cmd (10-30s) |
| sortowanie, przebudowa komendy | yfinance.download (2-5s) |
| os.startfile | |

---

## L. PLAN IMPLEMENTACJI

| Etap | Co | Commit | Test |
|---|---|---|---|
| 0 | Szkielet: okno + sidebar + zakładki + konsola + statusbar | gui-skeleton | GUI się otwiera, lista tasków działa |
| 1 | Zakładka Uruchom | gui-uruchom | Parametry, Uruchom/Dry-run, przebiegi |
| 2 | Zakładka Konfiguracja | gui-konfiguracja | Edycja settings, portfele, zapis |
| 3 | Zakładka Wyniki | gui-wyniki | Ranking, presety, wykresy, porównanie |
| 4 | Zakładka Portfele | gui-portfele | Konstruktor, katalog, tort, Yahoo |
| 5 | Ekran powitalny + polish | gui-polish | Powitanie, auto-HIST, niezapisane |

Każdy etap: commit → push → CI zielone → test Windows → następny.

---

## M. SCENARIUSZE ZWERYFIKOWANE (5)

### SC.1: Nowy użytkownik
1. Ekran powitalny → "Dalej" → pierwszy task
2. Pasek "pierwszy raz" z instrukcją
3. Klika Uruchom → auto-pobranie HIST → analiza
4. Dialog "Nowy task": nazwa + szablon → Portfele

### SC.2: Nowy portfel Yahoo + gross/net
1. Nowy task → Portfele → Tickery Yahoo
2. Wpisuje XLE, XLV, TLT → sprawdza Yahoo
3. Auto-start na najwcześniejszą wspólną datę
4. Uruchom gross → zmień na net → uruchom net
5. Wyniki → zaznacz oba checkboxy → porównanie

### SC.3: Zmiana drift + wyłączenie portfela
1. Konfiguracja → odznacz portfel → zmień drift
2. Uruchom bez zapisu → "Zapisać i uruchomić?"
3. Wyniki → porównanie drift 15% vs 20%
4. Przebiegi rozróżnialne po parametrach

### SC.4: Awaria analizy
1. Uruchom → traceback w konsoli na czerwono
2. Przebieg na liście z tagiem FAIL
3. Podgląd z tracebackiem, przycisk run.log
4. Checkbox porównania wyszarzony (brak danych)

### SC.5: Szukanie recovery + porównanie
1. Wyniki → sortuj po Recovery
2. Preset Drawdown → daty peak/trough
3. Porównanie gross vs net → wpływ Belki na recovery
4. Wykresy per przebieg (nie nakładane)

---

## N. KLUCZOWE DECYZJE (chronologicznie)

1. Desktop CustomTkinter, nie web
2. Klasyczne kontrolki, zero kafelków
3. Rebalansowanie: 2 checkboxy (drift + auto), nie 4 radio buttony
4. Konsola komendy zawsze widoczna na dole
5. Mała czcionka CRM-style (9px główne, 7-8px konsola)
6. Tort kołowy w konstruktorze portfeli (Canvas.create_arc)
7. Eksplorator wykresów styl Windows (miniaturki + podgląd na hover)
8. Presety kolumn w wynikach (Kompakt/Real/Nominal/Drawdown/Własny)
9. Porównanie przebiegów: checkboxy max 4, per portfel z pełnymi nazwami
10. Auto-pobranie HIST przed analizą (bez pytania)
11. Niezapisane zmiany → pytanie "Zapisać i uruchomić?"
12. FAIL widoczny na liście z czerwonym tagiem, wyszarzony checkbox
13. Portfele: dwa tryby — Indeksy historyczne / Tickery Yahoo
14. Brak SYNTH → pomiń mapę SYNTH (nie budujemy częściowego)
15. Auto-start na najwcześniejszą wspólną datę tickerów
16. Wykresy NIE nakładane między przebiegami
17. "Wyceny" nie "Częstotliwość", "Najgorsze okresy" nie "Okna crash-test"
18. Portfel wyłączony: wyszarzony BEZ skreślenia
19. Ekran powitalny z linkiem do Atlas ETF
20. Dialog nowego taska: nazwa + szablon → zakładka Portfele

---

*Dokument referencyjny. Wszystkie decyzje zaakceptowane przez autora.*

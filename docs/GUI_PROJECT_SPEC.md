# pasywnyportfel GUI — Specyfikacja projektowa

Autor koncepcji: Wojciech Król (lurk@lurk.com.pl)
Projekt GUI: Claude (Anthropic) na zlecenie autora
Data: 2026-06-18
Status: ZAAKCEPTOWANY — gotowy do implementacji

---

## 1. Technologia

- **Desktop** z CustomTkinter (`pip install customtkinter`)
- Plik: `app/bin/gui.py` + launcher `gui.cmd` (dwuklik)
- Portable — zero serwera, zero przeglądarki
- Python 3.13, Windows 11
- Branch: `gui`

## 2. Architektura

GUI importuje moduły bezpośrednio (zero subprocess dla logiki):
- `task_config.list_tasks()` → lista tasków
- `validate_task()` → walidacja
- `read_settings()` / `read_portfolios()` → odczyt konfiguracji
- `tax_label()` → etykieta podatkowa
- `cmd_builders.ledger_cmd()` → budowanie komendy do podglądu

D�ugie operacje → subprocess w wątku:
- `analysis.py` (1-4 min)
- `refresh_quotes.py` (5-30s)
- `refresh_data.cmd` (10-30s)
- `yfinance.download()` (2-5s)

## 3. Standard wizualny

### Kontrolki
- Checkboxy, radio buttony, dropdowny, listy — ŻADNYCH kafelków/kart
- Inspiracja: Turbo Vision (DOS), CRM
- Kompaktowy layout

### Czcionki
- Etykiety i tekst główny: 9px
- Tekst wewnątrz inputów/dropdownów: 9px (taki sam jak etykiety!)
- Nagłówki sekcji: 8px uppercase
- Hinty, ścieżki, tagi: 7-8px
- Konsola komendy: 7-8px mono
- Statusbar: 7-8px
- Sidebar tytuł: 7px uppercase
- Sidebar taski: 9px
- Pola wag w portfelach: 9px

### Layout
- Sidebar: 140-160px
- Padding: 2-6px
- Tort kołowy: 100px, procenty 7px (bez etykiet gdy redundantne z listą)

## 4. Stały panel "Podgląd komendy" (konsola)

- Na dole okna, zawsze widoczny
- Mono 7-8px, ciemne tło, kolorowanie: flagi pomarańczowe, wartości zielone
- Domyślnie 3 linie, scrollowalne, rozwijalne kliknięciem "▼ rozwiń"
- Przed uruchomieniem: podgląd składanej komendy (aktualizowany na żywo)
- Po kliknięciu Uruchom: stdout z subprocess na żywo
- Po zakończeniu: log zostaje, wraca do komendy przy zmianie taska/zakładki
- Przycisk "📋 kopiuj" do schowka

## 5. Statusbar

- Jedna linia na samym dole
- Lewa: health check (FAIL:0 WARN:0 OK:42)
- Prawa: Python 3.13 | 402 testów | gui branch

## 6. Zakładka: Uruchom

### Sidebar (wspólny dla wszystkich zakładek)
- Lista tasków z kropkami OK (zielona) / WARN (żółta)
- Przyciski: "+ Nowy task", "Odśwież dane CPI/FX"

### Parametry taska (siatka klucz-wartość)
- Okres: start → end (lata)
- Kapitał: kwota USD
- Wyceny: monthly/weekly/daily
- Waluty wynikowe: USD / USD + PLN
- Podatek: tag net_PLN 19% / gross
- Rebalans: ☑ Drift 20% ☐ Auto co — mies.
- Biblioteki: SYNTH OK / HIST OK

### Portfele w analizie (lista)
- Pełna nazwa portfela
- Checkbox INCLUDE (lewy)
- Checkboxy SYNTH / HIST per wariant
- Skład po ludzku: Gold 20%, US Stocks 20%...
- ETF-y: GLD, SPY, IJS...
- Ostrzeżenie HIST ⚠ + przycisk "Pobierz brakujące"
- Portfel wyłączony: wyszarzony (opacity 0.5), BEZ skreślenia, tag "wyłączony"
- Warianty SYNTH/HIST: checkbox zaznaczony / odznaczony / wyszarzony (brak mapy)

### Akcje
- ▶ Uruchom (zielony, wyróżniony)
- Dry-run
- Refresh HIST
- Waliduj

### Zachowanie "▶ Uruchom"
- GUI widzi HIST ⚠ → automatycznie pobiera brakujące → potem uruchamia analizę
- Brak internetu → pyta "Uruchomić bez HIST?"
- Przycisk zmienia się na "■ Przerwij", reszta akcji wyszarzona
- Konsola rozszerza się, strumieniuje stdout
- Po zakończeniu: przycisk wraca, nowy przebieg na liście

### Niezapisane zmiany
- User zmienił coś w Konfiguracji i kliknął Uruchom bez zapisu
- GUI pyta: "Masz niezapisane zmiany. Zapisać i uruchomić?"

### Ostatnie przebiegi
- Lista z tagiem OK (zielony) / FAIL (czerwony)
- Timestamp, czas, tax_mode, drift, liczba portfeli
- Link "📂 otwórz" → os.startfile(folder)

## 7. Zakładka: Konfiguracja

### Sekcje (jeden przewijalny ekran)
1. **Okres analizy**: Start, End, Kapitał startowy, Wyceny (dropdown)
2. **Podatek (Belka)**: Tryb (dropdown gross/net), Waluta (dropdown PLN/USD), Stawka (pole)
   - Gdy gross → waluta i stawka wyszarzone
3. **Rebalansowanie**: ☑ Drift [20] % ☐ Auto rebalans co [12] mies.
   - Pole aktywne tylko gdy checkbox zaznaczony
4. **Dane wejściowe**: ścieżki read-only (mono), ✓ przy istniejących
5. **Opcje wyjścia**: ☑ Wykresy ☑ Tabela summary ☑ Najgorsze okresy [3,5,7,10] lat
   - "Najgorsze okresy" inline za checkboxem, nie osobny wiersz
6. **Portfele w analizie**: jak w zakładce Uruchom (checkboxy, warianty, składy)

### Dolny pasek
- "↩ Cofnij zmiany" (reload z dysku)
- "Waliduj" (validate_task)
- "💾 Zapisz settings.csv + portfolios.csv"

## 8. Zakładka: Wyniki

### Eksplorator przebiegów (góra)
- Lista przebiegów po lewej z checkboxami (max 4 zaznaczone jednocześnie)
  - 5. checkbox wyszarzony gdy 4 zaznaczone
  - FAIL przebiegi: czerwony tag, wyszarzony checkbox (brak danych do porównania)
- Podgląd parametrów po prawej (kliknięcie na przebieg):
  - Okres, kapitał, wyceny, podatek, rebalans, lista portfeli
  - Sekcja "Zmienione vs poprzedni" z listą różnic
  - Przyciski: 📂 Folder, 📄 run.log, 🗑 Usuń

### Tryb jednego przebiegu (1 checkbox)

#### Najlepszy portfel
- Dropdown kryterium: Najwyższy CAGR / Najniższy MaxDD / Najkrótszy recovery / Najniższe StDev / Najwyższa wartość
- Zmiana kryterium → zmiana najlepszego portfela + karta metryczna

#### Ranking portfeli
- Sortowanie kliknięciem nagłówka kolumny (↓ aktualny, ↕ klikalne)
- Presety kolumn: Kompakt (5), Real pełny (9), Nominal (9), Real+nominal (14), Drawdown (6), Własny (checkboxy)
- Zielone komórki = najlepsza wartość w kolumnie
- Numeracja # przeliczana po sortowaniu

#### Eksplorator wykresów
- Miniaturki po lewej, pogrupowane po portfelach (scrollowalne)
- Podgląd po prawej na hover/klik
- Dwuklik → os.startfile(png) → pełny rozmiar
- Tabele summary PNG też jako miniaturki

#### run.log
- Podgląd końcówki (3-4 linie)
- Przycisk "Pełny run.log" → Notatnik

### Tryb porównania (2-4 checkboxy)

#### Parametry obu przebiegów obok siebie
- Pełne: okres, kapitał, wyceny, podatek, rebalans, portfele

#### Pasek różnic (żółty)
- "Zmienione parametry (N różnic): podatek gross→net, drift 15%→20%, portfele 3→4"
- GUI NIE interpretuje co spowodowało różnicę — tylko pokazuje fakty

#### Porównanie per portfel
- Każdy portfel osobną sekcją z pełną nazwą
- Metryki obok siebie z kolumną różnic
- Portfel tylko w jednym przebiegu → kreski (—), adnotacja "(tylko w B)"
- Ostrzeżenie na dole: "Zmieniono N parametrów naraz — różnice są efektem łącznym"

#### Wykresy
- Per przebieg, NIE nakładane na siebie (nieczytelne)

## 9. Zakładka: Portfele (konstruktor)

### Nagłówek
- ID + opis
- Bez rebalansu — to jest w Konfiguracji (wspólne dla taska)
- Hint: "Rebalansowanie i podatek → zakładka Konfiguracja"

### Tryb budowania (radio button)
- ○ Indeksy historyczne — dane indeksowe od 1926 + ETF-y
- ○ Tickery Yahoo — dowolne ETF-y i walory, tylko dane rynkowe

### Tryb "Indeksy historyczne"

#### Katalog klas aktywów (lewy panel)
- Pogrupowany sektorowo: Akcje US (4), Akcje międzynarodowe (2), Obligacje US (5), Alternatywne (3)
- Sekcje rozwijalne/zwijalne strzałką
- Każda klasa: nazwa po ludzku ("Złoto", nie "GOLD_USD"), info SYNTH od kiedy, sugerowane ETF-y
- Przycisk "+ dodaj" / znaczek "✓" gdy już w portfelu
- Dane z `data/in/asset_catalog.csv`

#### Skład portfela (prawy panel)
- Wykres kołowy (tort 100px, bez etykiet procentowych — są w liście)
- Lista składników: kolorowy kwadracik, nazwa, tagi SYNTH/ETF, pole wagi, przycisk ×
- Pasek kolorowy i tort aktualizują się na żywo
- Walidacja sumy wag: ✓ 100% / ✗ (czerwone)
- Info "SYNTH od 1926" (najwcześniejsza wspólna data)

#### Podsumowanie map
- "✓ Mapa SYNTH (5/5, od 1926)" / "✓ Mapa HIST (5/5 ETF)"
- Reguła: wszystkie mają SYNTH → obie mapy. Choć jeden bez → tylko HIST.
- NIE budujemy częściowego SYNTH

#### Tabela ETF
- Domyślne ETF-y z asset_catalog.csv
- Chipy alternatyw (kliknięcie wypełnia pole)
- Pole do wpisania własnego tickera
- Status Yahoo: ✓ od YYYY / ✗ błąd
- Przycisk "Sprawdź wszystkie na Yahoo"

### Tryb "Tickery Yahoo"
- Prosta tabela: ticker, opis, waga, status Yahoo, ×
- Pole "Sprawdź + dodaj" na dole
- Tort + skład po prawej (identyczny panel)
- Podsumowanie: "✓ Mapa HIST. Mapa SYNTH — nie dotyczy"

### Auto-start date
- Przy zapisie portfela: GUI ustawia start na najwcześniejszą wspólną datę tickerów
- User może zmienić na późniejszą
- Próba ustawienia wcześniejszej → blokada z komunikatem

### Zapis
- "💾 Zapisz mapy + dodaj do portfolios.csv"
- Tworzy pliki w maps/synth/ i maps/hist/ + wiersz w portfolios.csv

## 10. Ekran powitalny

- Wyświetla się przy pierwszym otwarciu (żaden task nie zaznaczony)
- Autor: Wojciech Król
- Koncepcja portfela pasywnego
- Link: https://akademia.atlasetf.pl/10-klasycznych-portfeli-pasywnych/
- Przycisk "Dalej" → zaznacza pierwszy task, przechodzi na Uruchom
- NIE pojawia się ponownie (zapamiętane)

## 11. Pasek "pierwszy raz"

- Na górze zakładki Uruchom
- "ℹ Pierwszy raz? Kliknij Odśwież dane CPI/FX, potem Refresh HIST"
- Znika po pierwszym udanym przebiegu albo kliknięciu "×"

## 12. Dialog "Nowy task"

- Otwierany z sidebara
- Pole: nazwa taska (walidacja znaków)
- Dropdown: wybór szablonu
- Przycisk: Utwórz
- Po utworzeniu → przejście na zakładkę Portfele

## 13. Mapa zdarzeń

### GUI (czysta logika okna) — 18 zdarzeń
- Kliknięcie zakładki, sortowanie tabeli, zmiana presetu kolumn
- Show/hide pól (tax_mode gross→wyszarza walutę i stawkę)
- Przebudowa komendy w konsoli
- Aktywacja/deaktywacja pól (checkbox drift → pole progu)
- Resize konsoli (rozwiń/zwiń)
- os.startfile() — otwórz folder/plik/wykres

### READ (odczyt z dysku <1s) — 5 zdarzeń
- Kliknięcie taska → read_settings, read_portfolios, validate_task
- Wybór przebiegu → pandas.read_csv(summary)
- "Cofnij zmiany" → reload z dysku

### WRITE (zapis <1s) — 2 zdarzenia
- "Zapisz settings.csv + portfolios.csv"
- "Zapisz mapy + dodaj do portfolios.csv"

### ASYNC (subprocess w tle) — 5 zdarzeń
- analysis.py (1-4 min)
- analysis.py --dry-run (~2s)
- refresh_quotes.py (5-30s)
- refresh_data.cmd (10-30s)
- yfinance.download — sprawdzenie tickera (2-5s)

## 14. Sync vs Async

- <1s → natychmiast w głównym wątku
- >1s → threading.Thread, GUI nie zamraża
- Wątek ASYNC: przycisk Uruchom→Przerwij, reszta akcji wyszarzona
- stdout z subprocess → linia po linii do konsoli
- Po zakończeniu → przywrócenie normalnego stanu

## 15. Zapis/odczyt CSV

### Odczyt
```python
settings = read_settings(root / "analysis_definitions" / task / "settings.csv")
portfolios = read_portfolios(root / "analysis_definitions" / task / "portfolios.csv")
```

### Zapis
- Jeden przycisk pisze oba pliki naraz
- Walidacja przed zapisem (validate_task + validate_tax_settings)
- Błąd krytyczny (start > end, wagi ≠ 100%) → nie zapisuje
- WARN (brak HIST) → zapisuje z ostrzeżeniem

### Cofnij zmiany
- Ponowny read_settings + read_portfolios z dysku

## 16. Plik asset_catalog.csv

```csv
LIB_COL,SECTOR,SECTOR_PL,DESCRIPTION,SUGGESTED_ETF,ETF_DESC,DATA_FROM
US_STOCKS_TR,US_EQUITY,Akcje US,S&P 500 proxy total return,"SPY,VTI,IVV","SPDR S&P500, Vanguard Total, iShares Core",1926
GOLD_USD,ALTERNATIVE,Alternatywne,Złoto spot USD,"GLD,IAU","SPDR Gold, iShares Gold",1833
```

Statyczny plik, GUI go czyta, silnik go nie potrzebuje.

## 17. Plan implementacji

| Etap | Co | Commit |
|---|---|---|
| 0 | Szkielet: okno + sidebar + zakładki + konsola + statusbar | gui-skeleton |
| 1 | Zakładka Uruchom | gui-uruchom |
| 2 | Zakładka Konfiguracja | gui-konfiguracja |
| 3 | Zakładka Wyniki | gui-wyniki |
| 4 | Zakładka Portfele | gui-portfele |
| 5 | Ekran powitalny + polish | gui-polish |

Każdy etap: commit → push → CI zielone → test na Windows → następny.

## 18. Scenariusze zweryfikowane

| SC | Opis | Decyzje |
|---|---|---|
| 1 | Nowy użytkownik | Ekran powitalny → pasek "pierwszy raz" → auto-pobranie HIST → dialog nowego taska (nazwa+szablon→Portfele) |
| 2 | Nowy portfel Yahoo + gross/net | Auto-start wspólna data → checkboxy porównania przebiegów (max 4) |
| 3 | Zmiana drift + wyłączenie portfela | Pytanie o niezapisane zmiany → parametry przy przebiegach → diff |
| 4 | Awaria analizy | FAIL na liście z tracebackiem, wyszarzony checkbox porównania |
| 5 | Szukanie recovery + porównanie | Sortowanie po kolumnie, presety, wykresy per przebieg (nie nakładane) |

---

*Dokument wygenerowany 2026-06-18. Wszystkie decyzje zaakceptowane przez autora projektu.*

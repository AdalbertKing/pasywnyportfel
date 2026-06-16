# Podłączenie do GitHub — krok po kroku

Autor: Wojciech Król, lurk@lurk.com.pl

---

## Wymagania

- Git zainstalowany na Windows (https://git-scm.com/download/win)
- Konto na github.com

Sprawdź czy Git jest zainstalowany:

```cmd
git --version
```

Jeśli nie — pobierz z https://git-scm.com/download/win i zainstaluj
z domyślnymi ustawieniami.

---

## Krok 1 — Utwórz repozytorium na GitHub

1. Zaloguj się na https://github.com
2. Kliknij "+" → "New repository"
3. Nazwa: `pasywnyportfel`
4. Opis: `Narzędzie do analizy portfeli pasywnych`
5. Widoczność: Private (chyba że chcesz publiczne)
6. **NIE zaznaczaj** "Add README" ani "Add .gitignore" (mamy swoje)
7. Kliknij "Create repository"

GitHub pokaże instrukcje — zignoruj je, użyj poniższych.

---

## Krok 2 — Zainicjuj lokalne repo i wyślij na GitHub

Otwórz CMD i wpisz po kolei:

```cmd
cd /d D:\analises\pasywnyportfel

git init

git add .

git commit -m "VER 2.2.5A — initial commit"

git branch -M main

git remote add origin https://github.com/TWOJ_USER/pasywnyportfel.git

git push -u origin main
```

Zamień `TWOJ_USER` na swój login GitHub.

Git zapyta o hasło — od 2021 GitHub wymaga tokena zamiast hasła:
https://github.com/settings/tokens → "Generate new token (classic)"
→ zaznacz "repo" → skopiuj token i wklej zamiast hasła.

Ewentualnie zainstaluj GitHub CLI (`gh auth login`) — łatwiej.

---

## Krok 3 — Sprawdź czy CI działa

1. Otwórz https://github.com/TWOJ_USER/pasywnyportfel
2. Kliknij zakładkę "Actions"
3. Powinieneś zobaczyć workflow "CI" w trakcie lub zakończony
4. Zielony ✅ = wszystkie testy przeszły
5. Czerwony ❌ = kliknij żeby zobaczyć które testy padły

Pierwszy przebieg trwa ~3 minuty (instalacja Python + bibliotek).
Kolejne ~2 minuty (cache).

---

## Codzienna praca z Git

Po każdej zmianie w kodzie:

```cmd
cd /d D:\analises\pasywnyportfel

git add -A
git commit -m "opis co zmieniles"
git push
```

Sprawdzenie statusu:

```cmd
git status
git log --oneline -5
```

Cofnięcie ostatniej zmiany (przed pushem):

```cmd
git reset --soft HEAD~1
```

Cofnięcie konkretnego commita (po pushu):

```cmd
git revert <hash_commita>
git push
```

---

## Praca z branchami (dla GUI)

Przed rozpoczęciem GUI:

```cmd
git checkout -b gui
```

Teraz pracujesz na branchu `gui`. Main jest nietknięty.
Kiedy GUI będzie gotowe:

```cmd
git checkout main
git merge gui
git push
```

---

## Ważne

- **Nigdy nie commituj haseł, tokenów, kluczy API.** `.gitignore` chroni
  przed przypadkowym dodaniem `_python_cmd.txt` i `runtime/`.
- **`analysis_results/` nie trafia do repo** — to są generowane wyniki,
  każdy przebieg tworzy nowe. Wrzucanie ich do Git zapchałoby repo.
- **`HIST_LIBRARY_DAILY.csv` nie trafia do repo** — jest generowana
  przez `refresh_quotes.cmd`. Każdy klon pobiera ją sam.
- Dane seed (SYNTH_LIBRARY, CPI, FX) **trafiają** do repo — testy
  ich potrzebują i są małe (~200 KB łącznie).

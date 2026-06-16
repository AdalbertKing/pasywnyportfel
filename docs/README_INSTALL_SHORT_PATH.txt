pasywnyportfel — FINAL LIGHT

Zalecana instalacja:

1. Rozpakuj ZIP bezpośrednio do krótkiej ścieżki, najlepiej:

   C:\pasywnyportfel\

2. Wejdź do:

   C:\pasywnyportfel\pasywnyportfel\

   albo jeśli ZIP rozpakujesz bez dodatkowego folderu:

   C:\pasywnyportfel\

3. Uruchom:

   1-start_setup.cmd

W katalogu głównym są tylko trzy pliki startowe:

- 1-start_setup.cmd
- 2-start_check.cmd
- 3-start_myanalise.cmd

Nie rozpakowuj do długiej ścieżki typu:

C:\Users\...\Downloads\pasywnyportfel_FINAL_LIGHT\pasywnyportfel\

bo Windows może nadal mieć problem z bardzo długimi ścieżkami wyników.


Uwaga: graficzne tabele summary pokazują teraz także kapitał startowy analizy (`Start capital`), żeby było jasne, od jakiej kwoty liczony jest `END_VALUE` / wynik końcowy.


Uwaga: graficzne tabele summary pokazują teraz zarówno `END_VALUE` / wynik realny, jak i `END_NOM` / wynik nominalny, oraz `Start capital`.


## Wariant analizy_kompletne

Ta paczka ma pełniejszy drugi przebieg inicjalny:

- benchmark_1970_synth_usd_gross: 10 portfeli, długa historia syntetyczna od 1960 r.
- synth_vs_etf_2005_full10: te same 10 portfeli, porównanie SYN vs ETF/HIST od 2005 r.

Drugi przebieg jest cięższy, bo pobiera i liczy więcej map historycznych ETF/proxy.

## Okna crash-testu

Ustawienia okien crash-testu są rozdzielone:

- `benchmark_1970_synth_usd_gross` — długa analiza od 1960 r.; zostają dłuższe okna z konfiguracji, np. `3,5,7,10,15,20`.
- `synth_vs_etf_2005_full10` — analiza od 2005 r.; używa krótszego zestawu `3,5,7,10`, bo okna 15Y i 20Y są tu mniej użyteczne.
- `user_template` — również używa `3,5,7,10`, żeby domyślna analiza użytkownika była krótsza i czytelniejsza.


## Autorstwo

Autor koncepcji i projektu: **Wojciech Król**  
email: **lurk@lurk.com.pl**

Implementacja i wsparcie techniczne: OpenAI ChatGPT

Wersja silnika: `1.0-complete`

Szczegóły są w plikach:

```text
ABOUT.txt
VERSION.txt
```

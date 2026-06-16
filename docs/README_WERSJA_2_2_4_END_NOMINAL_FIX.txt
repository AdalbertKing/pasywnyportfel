Wersja 2.2.4 END_NOMINAL_FIX

Zmiana:
- app/bin/make_summary_table.py: w automatycznej tabeli summary dla długich okresów dodano kolumnę END_NOM jako "End nominal".
- END_NOM jest także oznaczany zielonym tłem jako najlepsza wartość końcowa nominalna, analogicznie do End real.

Uwaga:
- ledger_summary.py już generował kolumnę END_NOM w CSV; poprawka dotyczy domyślnej listy kolumn pokazywanych w PNG przez --columns AUTO.

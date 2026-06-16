# synth_vs_etf_2005_full10

Pełna analiza porównawcza SYN vs ETF/HIST od 2005 r.

Domyślnie liczy te same 10 portfeli co długi benchmark syntetyczny:

- S&P 500
- US 60/40
- Permanent / Harry Browne
- Golden Butterfly
- Couch Potato 50/50
- Talmud US
- US 70/30
- US 50/50
- Small Value Tilt
- Stocks / Long Bonds / Gold

Cel tej analizy:

- porównać syntetyczną historię portfeli z historycznym ETF/proxy na wspólnym okresie,
- zobaczyć rozjazdy SYN vs HIST,
- nie mylić proxy historycznego z portfelem produkcyjnym.

Domyślnie:

- okres: 2005-01-31 do 2026-03-31
- tax_mode: gross
- make_crash: 1
- focus: pusty, czyli crash-test dla wszystkich portfeli

Crash windows: 3,5,7,10. Okna 15Y i 20Y są celowo wyłączone w analizie 2005+.

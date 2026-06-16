ANALIZY KOMPLETNE — ver. 2.0

Pakiet zawiera dwa domyślne duże taski startowe.

1. benchmark_1970_synth_usd_gross

   Długa historia syntetyczna od 1960 r. dla 10 portfeli:
   S&P 500, US 60/40, Permanent / Harry Browne, Golden Butterfly,
   Couch Potato 50/50, Talmud US, US 70/30, US 50/50,
   Small Value Tilt, Stocks / Long Bonds / Gold.

2. synth_vs_etf_2005_full10

   Porównanie SYN + HIST/proxy ETF od 2005 r. dla tych samych 10 portfeli.

Oba taski są wskazane w:

   analysis_definitions\startup_order.csv

Pełny start:

   1-start_setup.cmd

uruchamia właśnie te taski po kolei. Nie uruchamia automatycznie tasków testowych ani roboczych takich jak user_template lub bfly_10y_vs_vuds_2005.

Dodatkowe taski można uruchomić ręcznie:

   run_task.cmd bfly_10y_vs_vuds_2005
   run_task.cmd user_template

## Domyślny syntetyczny benchmark od 1970

Domyślny duży przebieg syntetyczny startuje od `1970-01-31`, czyli z parametrem danych `dbstart_synth=1970-01-01`.

Powód: główna analiza ma obejmować współczesny reżim po końcowej fazie Bretton Woods / dolara powiązanego ze złotem. Okres wcześniejszy nie jest domyślnie uruchamiany, żeby nie mieszać głównego porównania portfeli z wcześniejszym reżimem monetarnym.

Pełny start uruchamia taski z `analysis_definitions\startup_order.csv`:
- `benchmark_1970_synth_usd_gross`
- `synth_vs_etf_2005_full10`

---
Autor: Wojciech Król, lurk@lurk.com.pl

# Methodology notes

- Synthetic data is not expected to match ETF proxy data 1:1.
- ETF historical proxy is not the production IB portfolio.
- Classic proxy and fit proxy have different goals.
- Golden Butterfly classic proxy: SPY / IJS / IEF / TLT / GLD.
- Golden Butterfly fit/diagnostic proxy: VTI / VBR / IEF / TLT / IAU.
- A major source of Butterfly divergence is imperfect ETF representation of synthetic `US_SMALL_VALUE_TR`.
- Long synthetic analysis: USD-real from 1960.
- PLN-real analysis: methodologically no earlier than 1995-01-01, after PLN denomination.
- Default benchmark/proxy comparisons are gross, without Polish Belka tax.

## Domyślny syntetyczny benchmark od 1970

Domyślny duży przebieg syntetyczny startuje od `1970-01-31`, czyli z parametrem danych `dbstart_synth=1970-01-01`.

Powód: główna analiza ma obejmować współczesny reżim po końcowej fazie Bretton Woods / dolara powiązanego ze złotem. Okres wcześniejszy nie jest domyślnie uruchamiany, żeby nie mieszać głównego porównania portfeli z wcześniejszym reżimem monetarnym.

Pełny start uruchamia taski z `analysis_definitions\startup_order.csv`:
- `benchmark_1970_synth_usd_gross`
- `synth_vs_etf_2005_full10`

---
Autor: Wojciech Król, lurk@lurk.com.pl

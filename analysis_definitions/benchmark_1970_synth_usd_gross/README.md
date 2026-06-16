# benchmark_1970_synth_usd_gross

Default long synthetic benchmark.

- synthetic portfolios from 1970+
- USD-real
- gross / no Polish Belka tax
- CPI_US
- S&P 500 B&H
- other portfolios DRIFT20


## Tax

Default is `tax_mode=gross`.

If you want a curiosity/academic net simulation from 1970, use:

```csv
tax_mode,net
tax_base,USD
tax_rate,0.19
```

This is **not** the real Polish Belka tax. It is a USD-denominated tax approximation, useful only as a long-history stress-test.
Do not use `tax_base=PLN` here, because PLN-real/FX methodology is not accepted before 1995.

Default shipped setting: `tax_mode=gross` (no Belka tax). Create a copied definition for net-tax experiments.


## Additional 1970-compatible synthetic portfolios added in 2.2.7

These portfolios use only synthetic components available from 1970 without shortening the benchmark window:

- Couch Potato 50/50 — 50% US stocks / 50% US 10Y bonds.
- Talmud US — 33.34% US stocks / 33.33% US 10Y bonds / 33.33% gold.
- US 70/30 — 70% US stocks / 30% US 10Y bonds.
- US 50/50 — 50% US stocks / 50% US 10Y bonds. This is intentionally equivalent to Couch Potato 50/50, kept as a separate label for comparison with known portfolio names.
- Small Value Tilt — 50% US stocks / 20% US small value / 30% US 10Y bonds.
- Stocks / Long Bonds / Gold — 40% US stocks / 40% US long Treasury bonds / 20% gold.


Uwaga metodologiczna: domyślny syntetyczny benchmark startuje od 1970-01-31, aby nie mieszać głównej analizy z okresem Bretton Woods / dolara powiązanego ze złotem.

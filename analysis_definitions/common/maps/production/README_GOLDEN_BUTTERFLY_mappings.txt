GOLDEN BUTTERFLY — produkcja IB i analiza historyczna

1. mapping_GOLDEN_BUTTERFLY_IB_PRODUCTION.csv
   Portfel produkcyjny do zakupów na Interactive Brokers:
   SXR4 / ZPRV / SXRM albo ISIN IE00B3VWN518 / DTLA / XGDU.
   Uwaga: dla klocka 10Y na IB szukać przede wszystkim po ISIN IE00B3VWN518, bo ticker/listing może się różnić.

2. mapping_GOLDEN_BUTTERFLY_SYNTH_LONG_HISTORY.csv
   Odpowiednik syntetyczny do długiej historii:
   US_STOCKS_TR / US_SMALL_VALUE_TR / US_10Y_BONDS_TR / US_LT_BONDS_TR / GOLD_USD.

3. mapping_GOLDEN_BUTTERFLY_HIST_CLASSIC_PROXY.csv
   Klasyczny ETF proxy do walidacji:
   SPY / IJS / IEF / TLT / GLD.

4. mapping_GOLDEN_BUTTERFLY_HIST_FIT_PROXY.csv
   Diagnostyczny ETF proxy bliższy syntetykom:
   VTI / VBR / IEF / TLT / IAU.

Metodologia:
- Produkcyjny IB nie jest tym samym co proxy historyczne.
- Synthetic 1960+ służy do długiej historii modelowej.
- ETF proxy służy do walidacji na wspólnym okresie.
- W tym składzie NIE ma obligacji korporacyjnych. Są wyłącznie obligacje skarbowe USA:
  7-10Y Treasury oraz 20+Y/long Treasury.

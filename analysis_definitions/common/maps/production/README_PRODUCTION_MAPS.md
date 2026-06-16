# Production maps

Ten folder jest częścią biblioteki wzorców:

```text
analysis_definitions\common\maps\production
```

Znajdują się tu mapy pomocnicze / produkcyjne, np. dla Interactive Brokers.

Nowy model Stage1:

```text
analysis_definitions\common\maps\...     wzorce
analysis_definitions\<task>\maps\...     kopie lokalne używane do liczenia
```

Do konkretnej analizy kopiuj potrzebne mapy do folderu taska albo używaj `create_task.cmd` i edytuj lokalne pliki w `analysis_definitions\<task>\maps`.

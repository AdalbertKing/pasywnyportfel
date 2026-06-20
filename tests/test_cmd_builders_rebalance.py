"""
tests/test_cmd_builders_rebalance.py
Testy dla patcha REBAL_PERIOD w cmd_builders.py (2026-06-19).

UWAGA UCZCIWOŚCI: to NIE JEST odzyskany oryginalny pakiet 402 testów
projektu — ten plik nie istniał w zipie, z którego Claude pracował, i nie
ma do niego dostępu. To NOWY, węższy plik pokrywający wyłącznie funkcje
dotknięte patchem (mode_label, file_mode_token, display_name, detect_modes,
ledger_cmd) — wsteczną zgodność ze starym zachowaniem ORAZ nowy tryb COMBO.
Jeśli oryginalny pakiet się znajdzie, ten plik powinien obok niego współistnieć,
nie go zastępować.

Uruchomienie: pytest tests/test_cmd_builders_rebalance.py -v
(wymaga: pip install pytest; uruchamiać z korzenia repo, app/bin musi być
importowalne — patrz conftest.py obok).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "bin"))
import cmd_builders as cb  # noqa: E402

SETTINGS = {
    "start": "2000-01-01", "end": "2024-12-31", "saldo": "100000",
    "freq": "monthly", "tax_mode": "gross",
}
ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. WSTECZNA ZGODNOŚĆ — mode_label() / file_mode_token() bez REBAL_PERIOD
# ---------------------------------------------------------------------------
class TestBackwardCompatLabels:
    def test_bh_label(self):
        assert cb.mode_label("BH", "0") == "Buy & Hold"

    def test_drift_label_default(self):
        assert cb.mode_label("DRIFT", "20") == "Rebalans po DRIFT20"

    def test_drift_label_custom_pct(self):
        assert cb.mode_label("DRIFT", "15") == "Rebalans po DRIFT15"

    def test_annual_label_via_annual_token(self):
        assert cb.mode_label("ANNUAL", "0") == "Rebalans roczny"

    def test_annual_label_via_12m_token(self):
        assert cb.mode_label("12M", "0") == "Rebalans roczny"

    def test_unknown_token_passthrough(self):
        assert cb.mode_label("FOO", "0") == "FOO"

    def test_drift_with_zero_max_drift_does_not_raise(self):
        # Skrajny przypadek: stary kod nigdy nie gatował po wartości liczbowej.
        assert cb.mode_label("DRIFT", "0") == "Rebalans po DRIFT0"

    def test_file_token_bh(self):
        assert cb.file_mode_token("BH", "0") == "BH"

    def test_file_token_drift(self):
        assert cb.file_mode_token("DRIFT", "20") == "DRIFT20"

    def test_file_token_annual_unchanged_quirk(self):
        # Stary, dziwny ale ŚWIADOMIE niezmieniony token (zawiera spację) —
        # istniejące nazwy plików w analysis_results/ zależą od tego dosłownie.
        assert cb.file_mode_token("ANNUAL", "0") == "Rebalans roczny"


# ---------------------------------------------------------------------------
# 2. WSTECZNA ZGODNOŚĆ — ledger_cmd() argv identyczne jak przed patchem
# ---------------------------------------------------------------------------
class TestBackwardCompatLedgerCmd:
    def _argv(self, rebalance, max_drift, rebal_period=""):
        return cb.ledger_cmd(
            ROOT, SETTINGS, "maps/x.csv", "db/x.csv", "out/x.csv",
            rebalance, max_drift, rebal_period,
        )

    def test_bh_flags(self):
        argv = self._argv("BH", "0")
        assert "--no-rebalance" in argv
        assert "--conditional-rebalance" not in argv
        i = argv.index("--period")
        assert argv[i + 1] == "9999M"
        i = argv.index("--max-drift")
        assert argv[i + 1] == "0"

    def test_drift_flags(self):
        argv = self._argv("DRIFT", "20")
        assert "--conditional-rebalance" in argv
        assert "--no-rebalance" not in argv
        i = argv.index("--period")
        assert argv[i + 1] == "9999M"
        i = argv.index("--max-drift")
        assert argv[i + 1] == "20"

    def test_annual_flags(self):
        argv = self._argv("ANNUAL", "0")
        assert "--conditional-rebalance" not in argv
        assert "--no-rebalance" not in argv
        i = argv.index("--period")
        assert argv[i + 1] == "12M"
        i = argv.index("--max-drift")
        assert argv[i + 1] == "0"

    def test_unknown_rebalance_raises(self):
        with pytest.raises(ValueError, match="Nieznany REBALANCE"):
            self._argv("BANANA", "0")


# ---------------------------------------------------------------------------
# 3. NOWY TRYB COMBO (REBAL_PERIOD + DRIFT naraz)
# ---------------------------------------------------------------------------
class TestComboMode:
    def _argv(self, rebalance, max_drift, rebal_period):
        return cb.ledger_cmd(
            ROOT, SETTINGS, "maps/x.csv", "db/x.csv", "out/x.csv",
            rebalance, max_drift, rebal_period,
        )

    def test_combo_flags_no_conditional_no_norebalance(self):
        # KLUCZOWE: bez tych dwóch flag silnik faktycznie uruchamia OBA
        # mechanizmy naraz (ledger_engine.py:547-554) — to jest serce patcha.
        argv = self._argv("DRIFT", "20", "6M")
        assert "--conditional-rebalance" not in argv
        assert "--no-rebalance" not in argv
        i = argv.index("--period")
        assert argv[i + 1] == "6M"
        i = argv.index("--max-drift")
        assert argv[i + 1] == "20"

    def test_combo_label(self):
        assert cb.mode_label("DRIFT", "20", "6M") == "Rebalans co 6M + DRIFT20"

    def test_combo_file_token(self):
        assert cb.file_mode_token("DRIFT", "20", "6M") == "DRIFT20_PERIOD6M"

    @pytest.mark.parametrize("period", ["1M", "3M", "6M", "12M", "24M"])
    def test_combo_accepts_valid_period_formats(self, period):
        argv = self._argv("DRIFT", "20", period)
        i = argv.index("--period")
        assert argv[i + 1] == period

    def test_standalone_period_without_drift(self):
        # REBAL_PERIOD samo, bez tokenu DRIFT — czysty harmonogram, MAX_DRIFT
        # ignorowany (kind="PERIOD", nie "COMBO").
        argv = self._argv("BH", "0", "3M")
        assert "--no-rebalance" not in argv
        assert "--conditional-rebalance" not in argv
        i = argv.index("--period")
        assert argv[i + 1] == "3M"
        i = argv.index("--max-drift")
        assert argv[i + 1] == "0"

    def test_bh_with_explicit_period_honors_period_not_bh(self):
        # Regresja złapana podczas pisania patcha: REBALANCE=BH NIE MOŻE
        # po cichu zjadać jawnie ustawionego REBAL_PERIOD.
        assert cb.mode_label("BH", "0", "3M") == "Rebalans co 3M"

    def test_malformed_period_raises_clear_error(self):
        with pytest.raises(ValueError, match="Zły format REBAL_PERIOD"):
            self._argv("DRIFT", "20", "6W")  # tygodnie nieobsługiwane przez ledger_engine.py

    def test_malformed_period_without_unit_raises(self):
        with pytest.raises(ValueError, match="Zły format REBAL_PERIOD"):
            self._argv("DRIFT", "20", "6")


# ---------------------------------------------------------------------------
# 4. detect_modes() z mieszanką trybów (w tym COMBO)
# ---------------------------------------------------------------------------
class TestDetectModes:
    def test_single_mode_no_mixed_prefix(self):
        portfolios = [{"REBALANCE": "BH", "MAX_DRIFT": "0", "REBAL_PERIOD": ""}]
        assert cb.detect_modes(portfolios) == "BH"

    def test_mixed_modes_includes_combo(self):
        portfolios = [
            {"REBALANCE": "BH", "MAX_DRIFT": "0", "REBAL_PERIOD": ""},
            {"REBALANCE": "DRIFT", "MAX_DRIFT": "20", "REBAL_PERIOD": "6M"},
        ]
        result = cb.detect_modes(portfolios)
        assert result.startswith("mixed_")
        assert "BH" in result
        assert "DRIFT20+6M" in result

    def test_old_portfolios_without_rebal_period_column(self):
        # Symuluje stary plik portfolios.csv BEZ kolumny REBAL_PERIOD w ogóle
        # (csv.DictReader nie doda klucza, .get() zwróci None -> "").
        portfolios = [{"REBALANCE": "DRIFT", "MAX_DRIFT": "20"}]
        assert cb.detect_modes(portfolios) == "DRIFT20"

#!/usr/bin/env python3
# pasywnyportfel — Autor koncepcji i projektu: Wojciech Król / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""ledger_engine.py — silnik symulacji portfela (blok 4).

Zawiera build_event_dates i simulate_ledger.
"""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil.relativedelta import relativedelta
import re

from ledger_primitives import (
    _last_day_of_month, _normalize_freq, _safe_div,
    _resample_prices_to_freq, _effective_ledger_end, _attach_fx_to_prices,
)
from ledger_io import read_wide_db_csv, read_cpi_csv
from ledger_tax import LossBucket, apply_loss_buckets

# 4 BEGIN
def build_event_dates(
    session_dates: List[dt.date],
    start: dt.date,
    end: dt.date,
    period_months: int,
    settle_md: str,
    final_settle: bool = False,
) -> Tuple[set, set]:
    """
    Rebalans: co period_months od startu (anniversary), cel = koniec miesiąca po dodaniu N miesięcy.
    Settlement: raz w roku na ostatnią sesję <= settle_md (np. 12-31).
    """
    rebals = set()
    if period_months > 0:
        k = 1
        while True:
            target = start + relativedelta(months=period_months * k)
            target = _last_day_of_month(target)
            if target > end:
                break
            # ostatnia sesja <= target
            candidates = [d for d in session_dates if d <= target]
            if not candidates:
                break
            d_reb = candidates[-1]
            if start <= d_reb <= end:
                rebals.add(d_reb)
            k += 1

    m, d = [int(x) for x in settle_md.split("-")]
    settles = set()
    for y in range(start.year, end.year + 1):
        tgt = dt.date(y, m, d)
        if tgt > end and not (final_settle and y == end.year):
            continue
        candidates = [sd for sd in session_dates if sd.year == y and sd <= min(tgt, end)]
        if candidates:
            sd = candidates[-1]
            if start <= sd <= end:
                settles.add(sd)

    return rebals, settles


def simulate_ledger(
    portfolio_csv: str,
    prices_csv: str,
    fx_csv: Optional[str],
    cpi_pl_csv: Optional[str],
    cpi_us_csv: Optional[str],
    start_str: str,
    end_str: Optional[str],
    saldo_usd: float,
    period: str,
    sma_fast: Optional[int],
    sma_slow: Optional[int],
    max_drift: float,
    settle_md: str,
    tax_mode: str,
    tax_base: str,
    tax_rate: float,
    loss_window_years: int,
    loss_bucket_annual_cap: float,
    freq: str = "daily",
    final_settle: bool = False,
    no_rebalance: bool = False,
    conditional_rebalance: bool = False,
) -> pd.DataFrame:
    freq = _normalize_freq(freq)

    # portfolio
    pf = pd.read_csv(portfolio_csv)
    required_cols = {"ISIN", "Ticker", "WEIGHT"}
    if not required_cols.issubset(set(pf.columns)):
        raise ValueError(f"Brak wymaganych kolumn w portfelu. Wymagane: {sorted(required_cols)}")

    pf = pf.dropna(subset=["ISIN", "Ticker", "WEIGHT"]).copy()
    if pf.empty:
        raise ValueError("Portfel jest pusty po walidacji.")
    pf["ISIN"] = pf["ISIN"].astype(str).str.strip()
    pf["Ticker"] = pf["Ticker"].astype(str).str.strip()
    pf["WEIGHT"] = pd.to_numeric(pf["WEIGHT"], errors="coerce")
    pf = pf.dropna(subset=["WEIGHT"])
    pf = pf[(pf["WEIGHT"] > 0)]
    pf = pf[(pf["ISIN"] != "") & (pf["Ticker"] != "")]
    if pf.empty:
        raise ValueError("Portfel jest pusty po walidacji (brak dodatnich wag / brak ISIN/Ticker).")
    pf["WEIGHT"] = pf["WEIGHT"] / pf["WEIGHT"].sum()

    isins = pf["ISIN"].tolist()
    tickers = pf["Ticker"].tolist()
    weights = dict(zip(isins, pf["WEIGHT"].tolist()))

    # max_drift: relatywny dryft wagi względem celu (np. 20 => 0.20)
    if max_drift is None:
        max_drift = 0.0
    max_drift = float(max_drift)
    if max_drift > 1.0:
        max_drift = max_drift / 100.0
    if max_drift < 0.0:
        max_drift = 0.0

    tax_base = (tax_base or "PLN").upper().strip()
    if tax_base not in {"PLN", "USD"}:
        raise ValueError("--tax-base musi mieć wartość PLN albo USD")

    # DBs
    _, prices = read_wide_db_csv(prices_csv)

    fx_enabled = bool(fx_csv)
    cpi_pl_enabled = bool(cpi_pl_csv)
    cpi_us_enabled = bool(cpi_us_csv)

    if tax_mode.lower() == "net" and tax_base == "PLN" and not fx_enabled:
        raise ValueError("--tax-mode net --tax-base PLN wymaga --fx, bo podatek liczony jest w PLN. Dla akademickiego USD-only użyj --tax-base USD.")

    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        raise ValueError(f"Brak tickerów w bazie cen: {missing}")

    prices_prepared = _resample_prices_to_freq(prices, tickers, freq)

    if fx_enabled:
        _, fx = read_wide_db_csv(fx_csv)
        if "USD/PLN" not in fx.columns:
            if "FX.USDPLN" in fx.columns:
                fx = fx.rename(columns={"FX.USDPLN": "USD/PLN"})
            else:
                raise ValueError("Brak kolumny USD/PLN w DB_FX.csv")
        df = _attach_fx_to_prices(prices_prepared, fx, tickers, freq)
    else:
        df = prices_prepared.dropna(subset=tickers).sort_index().copy()
        if df.empty:
            raise ValueError("Brak kompletnych wierszy cen po przygotowaniu DB cen.")
        df["USD/PLN"] = pd.NA

    start_req = dt.date.fromisoformat(start_str)
    today = dt.date.today()
    end_ref = dt.date.fromisoformat(end_str) if end_str else today
    if end_ref > today:
        end_ref = today

    effective_end = _effective_ledger_end(df.index, freq, end_ref)

    # Ogranicz do faktycznego końca pełnego okresu.
    # Dla weekly/monthly odcinamy niepełny bieżący tydzień/miesiąc.
    df = df.loc[:pd.to_datetime(effective_end)]
    if df.empty:
        raise ValueError("Brak sesji do effective_end po przygotowaniu danych cenowych/FX.")

    # start: pierwsza sesja >= start_req (ale SMA może wymusić późniejszy start)
    start_candidates = df.index[df.index.date >= start_req]
    if len(start_candidates) == 0:
        raise ValueError("Brak sesji w zadanym zakresie dat.")

    trade_start = start_candidates[0].date()
    end = df.index.date[-1]

    # SMA jest opcjonalne. Brak --sma-fast/--sma-slow => tryb pasywny bez SMA i bez warm-up.
    # Podanie obu parametrów włącza liczenie SMA. Podanie tylko jednego jest błędem.
    sma_enabled = (sma_fast is not None) or (sma_slow is not None)
    if sma_enabled and (sma_fast is None or sma_slow is None):
        raise ValueError("Aby włączyć SMA, podaj oba parametry: --sma-fast N --sma-slow N. Brak obu oznacza SMA off.")

    sma_fast_df = None
    sma_slow_df = None

    trade_ts = pd.to_datetime(trade_start)
    trade_pos = int(df.index.get_indexer([trade_ts])[0])
    if trade_pos < 0:
        raise ValueError(f"Nie znaleziono sesji startowej {trade_start.isoformat()} w bazie cen po scaleniach.")

    if sma_enabled:
        sma_fast = int(sma_fast)
        sma_slow = int(sma_slow)
        if sma_fast < 1 or sma_slow < 1:
            raise ValueError("--sma-fast i --sma-slow muszą być >= 1")

        # Warm-up liczony w barach danej częstotliwości (--freq).
        # rolling(N).mean().shift(1) -> aby SMA były dostępne w dniu trade_start,
        # potrzebujemy historii przed trade_start. Dodatkowy +1 daje konserwatywny bufor.
        min_warmup_bars = max(sma_fast, sma_slow) + 1
        warmup_bars = max(250, min_warmup_bars) if freq == "daily" else min_warmup_bars

        if trade_pos < warmup_bars:
            have = trade_pos
            need = warmup_bars
            first = df.index[0].date()
            raise ValueError(
                f"Za mało notowań wstecz dla SMA przy --freq={freq}: wymagane ≈{need} barów przed {trade_start.isoformat()} "
                f"(dostępne {have}). Najwcześniejsza sesja w bazie po scaleniach to {first.isoformat()}. "
                "Dla klasycznego portfela pasywnego pomiń --sma-fast/--sma-slow."
            )

        out_start_ts = df.index[trade_pos - warmup_bars]
        out_start = out_start_ts.date()

        # dane wyjściowe: pełny zakres out_start..end,
        # a okres out_start..trade_start-1 służy wyłącznie do liczenia SMA
        # (bez zakupu/rebalansu/wyceny portfela)
        df = df.loc[out_start_ts:pd.to_datetime(end)]

        sma_fast_df = df[tickers].rolling(window=sma_fast, min_periods=sma_fast).mean().shift(1)
        sma_slow_df = df[tickers].rolling(window=sma_slow, min_periods=sma_slow).mean().shift(1)

        # Weryfikacja: na trade_start muszą istnieć SMA dla wszystkich walorów
        trade_ts = pd.to_datetime(trade_start)
        if trade_ts not in df.index:
            raise ValueError(f"Wewnętrzny błąd: brak {trade_start.isoformat()} w przyciętym zakresie danych.")
        ok_fast = sma_fast_df.loc[trade_ts].notna().all()
        ok_slow = sma_slow_df.loc[trade_ts].notna().all()
        if (not ok_fast) or (not ok_slow):
            diag = []
            for t in tickers:
                fv_fast = sma_fast_df[t].first_valid_index()
                fv_slow = sma_slow_df[t].first_valid_index()
                diag.append(
                    f"{t}: SMA{sma_fast} od {fv_fast.date().isoformat() if fv_fast is not None else 'nigdy'}, "
                    f"SMA{sma_slow} od {fv_slow.date().isoformat() if fv_slow is not None else 'nigdy'}"
                )
            raise ValueError(
                "Brak wystarczających danych do wyliczenia SMA na dzień startu "
                f"{trade_start.isoformat()} (SMA{sma_fast}/SMA{sma_slow}).\n" + "\n".join(diag)
            )
    else:
        out_start_ts = trade_ts
        out_start = trade_start
        df = df.loc[out_start_ts:pd.to_datetime(end)]

    # start pętli outputowej
    start = out_start
    sim_start = trade_start

    # CPI opcjonalne:
    # - brak --cpi-us => brak kolumn USD real / CPI_US, ale nominalny USD działa,
    # - brak --cpi-pl => brak PLN real / CPI_PL,
    # - brak --fx => brak PLN nominal/real; ledger nie jest przycinany przez DB_FX.
    cpi_pl = read_cpi_csv(cpi_pl_csv) if cpi_pl_enabled else None
    cpi_us = read_cpi_csv(cpi_us_csv) if cpi_us_enabled else None

    def attach_cpi(sess_ts: pd.Timestamp, cpi_tbl: Optional[pd.DataFrame]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Attach monthly CPI to a daily/weekly/monthly session date.

        Correct policy:
          - CPI value dated YYYY-MM-01 applies to all sessions in that month,
          - do NOT forward-fill a previous month into a later month with missing CPI,
          - missing CPI month => real value is unavailable for that session.

        This avoids the silent error "inflation = 0 after last CPI".
        """
        if cpi_tbl is None:
            return None, None, None
        month_key = dt.date(sess_ts.year, sess_ts.month, 1)
        idx = pd.to_datetime(month_key)
        if idx not in cpi_tbl.index:
            return None, None, None
        row = cpi_tbl.loc[idx]
        if pd.isna(row["cpi"]):
            return None, None, None
        return float(row["cpi"]), float(row["infl_mom"]) if pd.notna(row["infl_mom"]) else None, float(row["infl_yoy"]) if pd.notna(row["infl_yoy"]) else None

    # period
    m = re.match(r"^(\d+)\s*M$", period.strip().upper())
    if not m:
        raise ValueError("Zły format --period, wymagane np. 12M, 3M, 1M")
    period_months = int(m.group(1))
    if period_months <= 0:
        raise ValueError("--period musi być > 0")

    session_dates = list(df.index.date)
    session_dates_trade = [d for d in session_dates if d >= sim_start]
    rebals, settles = build_event_dates(session_dates_trade, sim_start, end, period_months, settle_md, final_settle=final_settle)
    if no_rebalance:
        rebals = set()
        max_drift = 0.0
    if conditional_rebalance:
        # Tryb Atlas-like: --period oznacza częstotliwość screeningu,
        # ale nie generuje bezwarunkowego rebalansu. Rebalans następuje
        # wyłącznie po przekroczeniu relatywnego dryftu --max-drift.
        rebals = set()
        if max_drift <= 0.0:
            raise ValueError("--conditional-rebalance wymaga --max-drift > 0, np. --max-drift 20")

    # holdings + tax cost basis per unit.
    # tax_base=PLN: koszt podatkowy w PLN/jednostkę.
    # tax_base=USD: akademicki koszt podatkowy w USD/jednostkę.
    units: Dict[str, float] = {isin: 0.0 for isin in isins}
    cost_pln_per_unit: Dict[str, float] = {isin: 0.0 for isin in isins}
    invested = False
    start_capital_usd = float(saldo_usd)

    gains_ytd = 0.0
    losses_ytd = 0.0
    buckets: List[LossBucket] = []

    # CPI bases (month of start; schodkowo)
    cpi_pl0, _, _ = attach_cpi(pd.to_datetime(sim_start), cpi_pl)
    cpi_us0, _, _ = attach_cpi(pd.to_datetime(sim_start), cpi_us)

    out_rows: List[Dict[str, object]] = []

    def portfolio_total_usd(date: dt.date) -> float:
        ts = pd.to_datetime(date)
        pxs = df.loc[ts, tickers]
        return sum(units[isin] * float(pxs[ticker]) for isin, ticker in zip(isins, tickers))

    def is_drift_breached(date: dt.date) -> bool:
        """Czy dowolny walor odjechał od wagi docelowej o >= max_drift (relatywnie do celu)."""
        if max_drift <= 0.0:
            return False
        ts = pd.to_datetime(date)
        pxs = df.loc[ts, tickers]
        cur_val_usd = {isin: units[isin] * float(pxs[ticker]) for isin, ticker in zip(isins, tickers)}
        total = sum(cur_val_usd.values())
        if total <= 0:
            return False
        eps = 1e-12
        for isin in isins:
            wt = float(weights.get(isin, 0.0) or 0.0)
            if wt <= 0:
                continue
            wc = cur_val_usd[isin] / total
            rel = abs(wc - wt) / wt
            if rel + eps >= max_drift:
                return True
        return False

    def do_rebalance(date: dt.date) -> Dict[str, Optional[float]]:
        nonlocal gains_ytd, losses_ytd
        ts = pd.to_datetime(date)
        fxv = float(df.loc[ts, "USD/PLN"]) if fx_enabled else None
        pxs = df.loc[ts, tickers]

        cur_val_usd = {isin: units[isin] * float(pxs[ticker]) for isin, ticker in zip(isins, tickers)}
        total = sum(cur_val_usd.values())
        targets = {isin: total * weights[isin] for isin in isins}
        deltas = {isin: targets[isin] - cur_val_usd[isin] for isin in isins}

        trd: Dict[str, Optional[float]] = {}

        # SELL first
        for isin, ticker in zip(isins, tickers):
            dv = deltas[isin]
            if dv >= 0:
                continue
            sell_usd = -dv
            price = float(pxs[ticker])
            if price <= 0:
                continue
            sell_units = sell_usd / price
            sell_units = min(sell_units, units[isin])
            if sell_units <= 0:
                continue

            # P&L vs average tax cost in selected tax base.
            # tax_base=PLN: realny model polskiej Belki, wymaga FX.
            # tax_base=USD: akademicki model podatku liczony bezpośrednio w USD.
            if tax_mode.lower() == "net":
                if tax_base == "PLN":
                    sell_tax = sell_units * price * fxv
                else:
                    sell_tax = sell_units * price
                basis_tax = sell_units * cost_pln_per_unit[isin]
                pnl_tax = sell_tax - basis_tax
                if pnl_tax >= 0:
                    gains_ytd += pnl_tax
                else:
                    losses_ytd += (-pnl_tax)

            units[isin] -= sell_units
            if units[isin] <= 1e-15:
                units[isin] = 0.0
                cost_pln_per_unit[isin] = 0.0

            prev = trd.get(isin, 0.0) or 0.0
            trd[isin] = prev - sell_usd

        # BUY
        for isin, ticker in zip(isins, tickers):
            dv = deltas[isin]
            if dv <= 0:
                continue
            buy_usd = dv
            price = float(pxs[ticker])
            if price <= 0:
                continue
            buy_units = buy_usd / price
            if buy_units <= 0:
                continue

            old_u = units[isin]
            new_u = old_u + buy_units
            if tax_mode.lower() == "net":
                if tax_base == "PLN":
                    buy_tax = buy_units * price * fxv
                else:
                    buy_tax = buy_units * price
                old_cost_total = old_u * cost_pln_per_unit[isin]
                new_cost_total = old_cost_total + buy_tax
                cost_pln_per_unit[isin] = _safe_div(new_cost_total, new_u)
            units[isin] = new_u

            prev = trd.get(isin, 0.0) or 0.0
            trd[isin] = prev + buy_usd

        for isin in isins:
            if isin not in trd:
                trd[isin] = None
        return trd

    def snapshot_row(
        date: dt.date,
        event: str,
        total_pre_usd: Optional[float],
        total_post_usd: Optional[float],
        belka_pln: Optional[float],
        belka_usd: Optional[float],
        trd_usd: Dict[str, Optional[float]],
    calc_only: bool = False,
    ):
        ts = pd.to_datetime(date)
        fxv = float(df.loc[ts, "USD/PLN"]) if fx_enabled else None

        cpl, iplm, iply = attach_cpi(ts, cpi_pl)
        cus, iusm, iusy = attach_cpi(ts, cpi_us)

        usd_real = None
        pln_real = None
        if total_post_usd is not None:
            if cus is not None and cpi_us0 is not None and cpi_us0 != 0:
                usd_real = total_post_usd / (cus / cpi_us0)
            if fx_enabled and fxv is not None and cpl is not None and cpi_pl0 is not None and cpi_pl0 != 0:
                pln_real = (total_post_usd * fxv) / (cpl / cpi_pl0)
        row: Dict[str, object] = {
            "DATE": date.isoformat(),
            "EVENT": event,
            "IS_SESSION": True,
            "FREQ": freq,
            "FX_USDPLN": fxv,

            "CPI_PL": cpl,
            "INF_PL_MOM": iplm,
            "INF_PL_YOY": iply,

            "CPI_US": cus,
            "INF_US_MOM": iusm,
            "INF_US_YOY": iusy,

            "TOTAL_USD_PRE": total_pre_usd,
            "TOTAL_USD_POST": total_post_usd,
            "TOTAL_PLN_POST": (total_post_usd * fxv) if (fx_enabled and fxv is not None and total_post_usd is not None) else None,

            "TOTAL_USD_POST_REAL": usd_real,
            "TOTAL_PLN_POST_REAL": pln_real,

            "BELKA_USD": belka_usd,
            "BELKA_PLN": belka_pln,
        }

        for isin, ticker in zip(isins, tickers):
            px = float(df.loc[ts, ticker])
            if calc_only:
                row[f"UNITS_{isin}"] = None
                row[f"VAL_USD_{isin}"] = None
                row[f"TRD_USD_{isin}"] = None
            else:
                u = units[isin]
                row[f"UNITS_{isin}"] = u
                row[f"VAL_USD_{isin}"] = u * px
                row[f"TRD_USD_{isin}"] = trd_usd.get(isin, None)
            if sma_enabled:
                v_fast = sma_fast_df.loc[ts, ticker]
                row[f"SMA{sma_fast}_{isin}"] = float(v_fast) if pd.notna(v_fast) else None
                v_slow = sma_slow_df.loc[ts, ticker]
                row[f"SMA{sma_slow}_{isin}"] = float(v_slow) if pd.notna(v_slow) else None
            row[f"EMERGENCY_STATE_{isin}"] = 0

        out_rows.append(row)

    # iterate sessions
    for date in session_dates:
        if date < start or date > end:
            continue

        # Okres przed sim_start występuje tylko przy włączonym SMA.
        if sma_enabled and date < sim_start:
            snapshot_row(date, "CALCULATING SMA", None, None, None, None, {}, calc_only=True)
            continue

        # Start inwestowania: pierwsza sesja >= sim_start
        if not invested:
            ts0 = pd.to_datetime(date)
            fx0 = float(df.loc[ts0, "USD/PLN"]) if fx_enabled else None
            total_pre0 = float(start_capital_usd)

            trd0: Dict[str, Optional[float]] = {}
            for isin, ticker in zip(isins, tickers):
                w = float(weights[isin])
                px = float(df.loc[ts0, ticker])
                if px <= 0:
                    raise ValueError(f"Niepoprawna cena startowa {ticker}={px} w dniu {date.isoformat()}")
                alloc_usd = total_pre0 * w
                units[isin] = alloc_usd / px
                if tax_mode.lower() == "net":
                    if tax_base == "PLN":
                        cost_pln_per_unit[isin] = px * fx0
                    else:
                        cost_pln_per_unit[isin] = px
                else:
                    cost_pln_per_unit[isin] = 0.0
                trd0[isin] = alloc_usd

            invested = True
            total_post0 = portfolio_total_usd(date)
            snapshot_row(date, "INIT", total_pre0, total_post0, None, None, trd0)
            continue

        is_settle = date in settles
        is_sched_rebal = (date in rebals) and (not is_settle) and (not no_rebalance) and (not conditional_rebalance)
        if conditional_rebalance:
            # Miesięczny screening + rebalans tylko gdy przekroczony relatywny dryft.
            # Nie blokujemy dryftu na dacie SETTLE_YE, żeby nie zgubić sygnału
            # przypadkowo wypadającego na koniec roku.
            is_drift_rebal = (not no_rebalance) and (max_drift > 0.0) and is_drift_breached(date)
        else:
            is_drift_rebal = (not is_settle) and (not is_sched_rebal) and (not no_rebalance) and (max_drift > 0.0) and is_drift_breached(date)
        is_rebal = is_sched_rebal or is_drift_rebal

        if not is_settle and not is_rebal:
            total_post = portfolio_total_usd(date)
            snapshot_row(date, "NONE", None, total_post, None, None, {})
            continue

        if is_settle and is_drift_rebal:
            event = "SETTLE_YE_REBAL_DRIFT"
        elif is_settle:
            event = "SETTLE_YE"
        elif is_drift_rebal:
            event = "REBAL_DRIFT"
        else:
            event = "REBAL"

        total_pre = portfolio_total_usd(date)
        if no_rebalance:
            trd = {isin: None for isin in isins}
        elif conditional_rebalance:
            # W trybie warunkowym koniec roku NIE oznacza rebalansu.
            trd = do_rebalance(date) if is_rebal else {isin: None for isin in isins}
        else:
            # Zachowanie historyczne: daty SETTLE_YE wywołują też rebalans.
            trd = do_rebalance(date)

        belka_pln = None
        belka_usd = None

        if is_settle:
            year = date.year
            net = gains_ytd - losses_ytd

            if tax_mode.lower() == "net":
                if net <= 1e-9:
                    loss_amt = -net if net < 0 else 0.0
                    if loss_amt > 1e-9:
                        buckets.append(LossBucket(year=year, original=loss_amt, remaining=loss_amt, used_this_year={}))
                    tax_amt = 0.0
                else:
                    _, taxable = apply_loss_buckets(year, net, buckets, loss_window_years, loss_bucket_annual_cap)
                    tax_amt = tax_rate * taxable

                if tax_amt > 1e-9:
                    ts = pd.to_datetime(date)
                    if tax_base == "PLN":
                        if not fx_enabled:
                            raise ValueError("Wewnętrzny błąd: tax-base PLN wymaga FX.")
                        fxv = float(df.loc[ts, "USD/PLN"])
                        tax_pln = tax_amt
                        tax_usd = tax_pln / fxv
                    else:
                        tax_usd = tax_amt
                        if fx_enabled:
                            fxv = float(df.loc[ts, "USD/PLN"])
                            tax_pln = tax_usd * fxv
                        else:
                            tax_pln = None

                    total_after_rebal = portfolio_total_usd(date)
                    scale = tax_usd / total_after_rebal if total_after_rebal > 0 else 0.0
                    scale = min(max(scale, 0.0), 0.999999)

                    for isin in isins:
                        units[isin] *= (1.0 - scale)

                    belka_pln = float(tax_pln) if tax_pln is not None else None
                    belka_usd = float(tax_usd)

            gains_ytd = 0.0
            losses_ytd = 0.0

        total_post = portfolio_total_usd(date)
        snapshot_row(date, event, total_pre, total_post, belka_pln, belka_usd, trd)

    out = pd.DataFrame(out_rows)

    base_cols = [
        "DATE","EVENT","IS_SESSION","FREQ","FX_USDPLN",
        "CPI_PL","INF_PL_MOM","INF_PL_YOY",
        "CPI_US","INF_US_MOM","INF_US_YOY",
        "TOTAL_USD_PRE","TOTAL_USD_POST","TOTAL_PLN_POST",
        "TOTAL_USD_POST_REAL","TOTAL_PLN_POST_REAL",
        "BELKA_USD","BELKA_PLN",
    ]
    dyn_cols = []
    for isin in isins:
        dyn_cols += [f"UNITS_{isin}", f"VAL_USD_{isin}", f"TRD_USD_{isin}"]
        if sma_enabled:
            dyn_cols += [f"SMA{sma_fast}_{isin}", f"SMA{sma_slow}_{isin}"]
        dyn_cols += [f"EMERGENCY_STATE_{isin}"]
    out = out[base_cols + dyn_cols]
    return out
# 4 END

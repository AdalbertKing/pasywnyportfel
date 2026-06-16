#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.0-complete
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
# build_db_freq.py 2.3.2 – budowa bazy notowań ETF na podstawie mappingu:
# ISIN,Ticker,NAME,ASSET,Currency,COST
#
# Wyjście (DB_*.csv):
# ASSET, ...
# TICKER, ...
# ISIN, ...
# COST, ...
# NAME, ...
# <daty>, ceny...

import argparse
import csv
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build unified ETF price database from mapping CSV"
    )
    parser.add_argument(
        "--mapping",
        required=True,
        help="CSV z kolumnami: ISIN,Ticker,NAME,ASSET,Currency,COST",
    )
    parser.add_argument(
        "--out-etf",
        required=True,
        help="Plik wynikowy CSV (np. DB_Tasty.csv)",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Data startu YYYY-MM-DD (np. 2005-01-01)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Data końca (domyślnie dziś)",
    )
    parser.add_argument(
        "--freq",
        default="daily",
        choices=["daily", "weekly", "monthly", "D", "W", "M"],
        help="Częstotliwość wyjściowej bazy: daily/D, weekly/W, monthly/M (domyślnie daily).",
    )
    parser.add_argument(
        "--library",
        default=None,
        help="Lokalna biblioteka dziennych notowań HIST_LIBRARY_DAILY.csv. Jeśli podana, skrypt nie pobiera Yahoo.",
    )
    parser.add_argument(
        "--start-tolerance-days",
        type=int,
        default=7,
        help="Akceptuj pierwszą sesję do N dni po --start, np. gdy --start wypada w weekend/święto. Domyślnie 7.",
    )
    return parser.parse_args()


def normalize_freq(freq: str) -> str:
    f = (freq or "daily").strip().lower()
    aliases = {
        "d": "daily",
        "daily": "daily",
        "w": "weekly",
        "weekly": "weekly",
        "m": "monthly",
        "monthly": "monthly",
    }
    if f not in aliases:
        raise ValueError(f"Nieprawidłowe --freq={freq}; użyj daily/weekly/monthly albo D/W/M.")
    return aliases[f]


def resample_prices(prices: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Zwraca ceny w zadanej częstotliwości, zachowując rzeczywistą datę ostatniej
    dostępnej obserwacji w okresie.

    daily   -> bez zmian
    weekly  -> ostatnia dostępna sesja tygodnia kończącego się w piątek
    monthly -> ostatnia dostępna sesja miesiąca
    """
    freq = normalize_freq(freq)
    prices = prices.sort_index()

    if freq == "daily":
        return prices

    if freq == "weekly":
        out = prices.groupby(prices.index.to_period("W-FRI")).tail(1)
    elif freq == "monthly":
        out = prices.groupby(prices.index.to_period("M")).tail(1)
    else:
        raise ValueError(f"Nieobsługiwane freq={freq}")

    out = out.dropna(how="all").sort_index()
    return out


def load_mapping(path: str) -> List[Dict[str, Any]]:
    """
    Wczytuje mapping_* CSV w sposób odporny na:
      - separator ',' lub ';'
      - wielkość liter w nagłówkach (Ticker vs TICKER, Currency vs CURRENCY)
      - podstawowe aliasy: YFTicker/Symbol dla tickera, CCY dla waluty
    Wymagane logicznie pola: ISIN, TICKER, ASSET, CURRENCY, COST.
    """
    # sniff delimiter
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        sample = f.read(4096)
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=";,").delimiter
    except Exception:
        delim = ","

    df = pd.read_csv(path, sep=delim, dtype=str).fillna("")
    cols_lc = {str(c).strip().lower(): c for c in df.columns}

    def col(*names: str) -> Optional[str]:
        for n in names:
            c = cols_lc.get(n.lower())
            if c:
                return c
        return None

    c_isin = col("isin")
    c_ticker = col("yfticker", "ticker", "symbol")
    c_asset = col("asset")
    c_ccy = col("currency", "ccy")
    c_cost = col("cost")

    missing = []
    if c_isin is None: missing.append("ISIN")
    if c_ticker is None: missing.append("Ticker/YFTicker")
    if c_asset is None: missing.append("ASSET")
    if c_ccy is None: missing.append("Currency/CCY")
    if c_cost is None: missing.append("COST")
    if missing:
        raise ValueError(f"Brak kolumn w mappingu: {', '.join(missing)}; dostępne: {list(df.columns)}")

    instruments: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        ticker = str(row[c_ticker]).strip()
        if not ticker:
            continue
        asset = str(row[c_asset]).strip()
        if not asset:
            raise ValueError(f"Brak ASSET dla tickera={ticker}")

        cost_raw = str(row[c_cost]).strip().replace(",", ".")
        try:
            cost = float(cost_raw) if cost_raw != "" else 0.0
        except Exception:
            raise ValueError(f"Nieprawidłowy COST dla tickera={ticker}: {row[c_cost]}")

        inst = {
            "ISIN": str(row[c_isin]).strip(),
            "Ticker": ticker,
            "ASSET": asset,
            "NAME": str(row.get(cols_lc.get('name',''))).strip() if cols_lc.get('name') else str(row.get('NAME','')).strip(),
            "Currency": str(row[c_ccy]).strip().upper() or "USD",
            "COST": cost,
        }
        instruments.append(inst)

    if not instruments:
        raise ValueError("Mapping nie zawiera żadnych instrumentów.")

    return instruments


def _extract_adj_close(data: pd.DataFrame, tickers_unique: List[str]) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame) and "Adj Close" in data.columns:
        prices = data["Adj Close"]
    else:
        prices = data
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(name=tickers_unique[0])
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()
    prices = prices.sort_index()
    prices.index = pd.to_datetime(prices.index)
    return prices


def _download_yf_once(tickers_unique: List[str], start: str, end: Optional[str]) -> pd.DataFrame:
    try:
        import yfinance as yf
    except Exception as e:
        raise RuntimeError("Brak modułu yfinance. Uruchom: pip install -r requirements.txt") from e

    data = yf.download(
        tickers_unique,
        start=start,
        end=end,
        auto_adjust=False,
        progress=True,
        threads=False,
    )
    return _extract_adj_close(data, tickers_unique)


def download_prices(
    instruments: List[Dict[str, Any]],
    start: str,
    end: Optional[str],
) -> pd.DataFrame:
    tickers_unique = list(dict.fromkeys(inst["Ticker"] for inst in instruments))

    errors: List[str] = []

    # 1) Batch download with retries. Yahoo/yfinance sometimes fails with transient
    # SSL/curl resets even for valid tickers such as SPY.
    for attempt in range(1, 5):
        try:
            prices = _download_yf_once(tickers_unique, start, end)
            if not prices.empty and len(prices.columns) > 0:
                missing_cols = [t for t in tickers_unique if t not in prices.columns or prices[t].dropna().empty]
                if not missing_cols:
                    return prices
                errors.append(f"batch attempt {attempt}: missing/empty columns {missing_cols}")
            else:
                errors.append(f"batch attempt {attempt}: empty dataframe")
        except Exception as e:
            errors.append(f"batch attempt {attempt}: {type(e).__name__}: {e}")
        time.sleep(min(2 * attempt, 8))

    # 2) Per-ticker fallback. Slower, but much more robust for small mapping files.
    series = {}
    for ticker in tickers_unique:
        ticker_errors = []
        for attempt in range(1, 5):
            try:
                px = _download_yf_once([ticker], start, end)
                if ticker in px.columns:
                    s = px[ticker].dropna()
                elif len(px.columns) == 1:
                    s = px.iloc[:, 0].dropna()
                    s.name = ticker
                else:
                    s = pd.Series(dtype=float, name=ticker)

                if not s.empty:
                    series[ticker] = s.rename(ticker)
                    break
                ticker_errors.append(f"attempt {attempt}: empty")
            except Exception as e:
                ticker_errors.append(f"attempt {attempt}: {type(e).__name__}: {e}")
            time.sleep(min(2 * attempt, 8))

        if ticker not in series:
            errors.append(f"{ticker}: " + " | ".join(ticker_errors))

    if series:
        prices = pd.concat(series.values(), axis=1).sort_index()
        missing = [t for t in tickers_unique if t not in prices.columns or prices[t].dropna().empty]
        if not missing:
            return prices
        errors.append(f"per-ticker fallback incomplete; missing={missing}")

    details = "\n  - " + "\n  - ".join(errors[-20:]) if errors else ""
    raise RuntimeError(
        "Nie udało się pobrać kompletu danych cenowych z yfinance/Yahoo.\n"
        "To zwykle oznacza chwilowy problem sieci/Yahoo/SSL, a nie błąd mappingu.\n"
        f"Tickery: {tickers_unique}\n"
        f"Zakres: {start}..{end or 'today'}\n"
        "Spróbuj ponownie za chwilę. Jeżeli problem wraca, sprawdź dostęp do query1.finance.yahoo.com "
        "albo dostarcz lokalną bazę DB dla ETF historycznych.\n"
        f"Szczegóły prób:{details}"
    )



def read_hist_library(path: str) -> pd.DataFrame:
    lib = pd.read_csv(path)
    if "DATE" not in lib.columns:
        raise ValueError(f"Biblioteka HIST {path} musi mieć kolumnę DATE.")
    lib["DATE"] = pd.to_datetime(lib["DATE"], errors="coerce")
    lib = lib.dropna(subset=["DATE"]).set_index("DATE").sort_index()
    lib = lib[~lib.index.duplicated(keep="last")]
    for c in lib.columns:
        lib[c] = pd.to_numeric(lib[c], errors="coerce")
    return lib


def prices_from_library(instruments: List[Dict[str, Any]], library_path: str, start: str, end: Optional[str], start_tolerance_days: int = 7) -> pd.DataFrame:
    lib = read_hist_library(library_path)
    tickers_unique = list(dict.fromkeys(inst["Ticker"] for inst in instruments))
    missing = [t for t in tickers_unique if t not in lib.columns]
    if missing:
        raise RuntimeError(
            "BRAK NOTOWAŃ W HIST_LIBRARY_DAILY: " + ", ".join(missing) + "\\n"
            "Uruchom: refresh_quotes.cmd <nazwa_taska> albo refresh_quotes.cmd --startup"
        )

    px = lib[tickers_unique].copy()
    start_ts = pd.to_datetime(start)
    px = px[px.index >= start_ts]
    if end:
        px = px[px.index <= pd.to_datetime(end)]
    if px.empty:
        raise RuntimeError(
            f"Biblioteka HIST nie ma danych po zastosowaniu zakresu {start}..{end or 'today'}."
        )

    # Keep rows with at least one price before resampling; completeness is checked after resample.
    px = px.dropna(how="all").sort_index()
    bad = []
    for t in tickers_unique:
        s = px[t].dropna()
        if s.empty:
            bad.append(f"{t}: brak danych w zakresie")
        else:
            delta_days = (s.index.min().normalize() - start_ts.normalize()).days
            if delta_days > start_tolerance_days:
                bad.append(f"{t}: pierwsza cena {s.index.min().date()} > start {start} o {delta_days} dni")
    if bad:
        raise RuntimeError(
            "Biblioteka HIST nie pokrywa wymaganego zakresu.\\n  - "
            + "\\n  - ".join(bad)
            + "\\nUruchom: refresh_quotes.cmd <nazwa_taska>"
        )
    return px


def write_output(
    out_path: str,
    instruments: List[Dict[str, Any]],
    prices: pd.DataFrame,
) -> None:
    series_by_ticker: Dict[str, pd.Series] = {t: prices[t] for t in prices.columns}
    dates = prices.index

    assets_row = ["ASSET"] + [inst["ASSET"] for inst in instruments]
    ticker_row = ["TICKER"] + [inst["Ticker"] for inst in instruments]
    isin_row = ["ISIN"] + [inst["ISIN"] for inst in instruments]
    cost_row = ["COST"] + [f"{inst['COST']:.6f}" for inst in instruments]
    name_row = ["NAME"] + [inst["NAME"] for inst in instruments]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(assets_row)
        writer.writerow(ticker_row)
        writer.writerow(isin_row)
        writer.writerow(cost_row)
        writer.writerow(name_row)

        for dt in dates:
            date_str = dt.strftime("%Y-%m-%d")
            row = [date_str]
            for inst in instruments:
                t = inst["Ticker"]
                s = series_by_ticker.get(t)
                if s is None:
                    row.append("")
                    continue
                val = s.get(dt)
                if pd.isna(val):
                    row.append("")
                else:
                    row.append(f"{float(val):.8f}")
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    try:
        datetime.strptime(args.start, "%Y-%m-%d")
    except ValueError:
        raise SystemExit("Błędny format --start, użyj YYYY-MM-DD (np. 2005-01-01).")

    freq = normalize_freq(args.freq)
    instruments = load_mapping(args.mapping)
    if args.library:
        prices = prices_from_library(instruments, args.library, start=args.start, end=args.end, start_tolerance_days=args.start_tolerance_days)
    else:
        prices = download_prices(instruments, start=args.start, end=args.end)
    prices = resample_prices(prices, freq=freq)
    if prices.empty:
        raise SystemExit(f"Brak danych po resamplingu --freq={freq}.")
    # After resampling, require complete rows for all mapped tickers.
    tickers_unique = list(dict.fromkeys(inst["Ticker"] for inst in instruments))
    prices = prices[tickers_unique].dropna(how="any")
    if prices.empty:
        raise SystemExit(f"Brak kompletnego wspólnego zakresu danych dla mappingu po --freq={freq}. Uruchom refresh_quotes.cmd dla tego taska albo sprawdź daty/tickery.")
    write_output(args.out_etf, instruments, prices)


if __name__ == "__main__":
    main()

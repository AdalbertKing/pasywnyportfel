#!/usr/bin/env python3
# pasywnyportfel
# Autor koncepcji i projektu: Wojciech Król
# email: lurk@lurk.com.pl
# Implementacja i wsparcie techniczne: OpenAI ChatGPT
# Wersja silnika: 1.1-flash-cpi
# Charakter: narzędzie analityczne; nie stanowi rekomendacji inwestycyjnej.
import argparse
import csv
import re
import sys
import urllib.request
from html import unescape
from pathlib import Path
from datetime import datetime

DEFAULT_PAGE = "https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku/"
DEFAULT_CSV = "https://stat.gov.pl/download/gfx/portalinformacyjny/pl/defaultstronaopisowa/4741/1/1/miesiecznewskaznikicentowarowiuslugkonsumpcyjnychod1982roku_5.csv"
MONTHS = {str(i): i for i in range(1, 13)}
PL_MONTHS = {
    "styczen": 1, "styczeń": 1,
    "luty": 2,
    "marzec": 3,
    "kwiecien": 4, "kwiecień": 4,
    "maj": 5,
    "czerwiec": 6,
    "lipiec": 7,
    "sierpien": 8, "sierpień": 8,
    "wrzesien": 9, "wrzesień": 9,
    "pazdziernik": 10, "październik": 10,
    "listopad": 11,
    "grudzien": 12, "grudzień": 12,
}

def norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()
    repl = str.maketrans("ąćęłńóśźż", "acelnoszz")
    s = s.translate(repl)
    s = re.sub(r"\s+", " ", s)
    return s

def fetch_bytes(url: str) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        import requests
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"WARN: requests download failed for GUS CPI source, fallback to urllib: {e}", file=sys.stderr)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def decode_bytes(b: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")

def resolve_csv_text(input_path_or_url: str | None, raw_out: str | None) -> str:
    src = input_path_or_url or DEFAULT_CSV
    if re.match(r"^https?://", src, re.I):
        b = fetch_bytes(src)
        txt = decode_bytes(b)
    else:
        b = Path(src).read_bytes()
        txt = decode_bytes(b)
    if raw_out:
        Path(raw_out).write_text(txt, encoding="utf-8")
    # If someone passed the GUS HTML page, find a CSV link.
    if "<html" in txt[:2000].lower() or "<!doctype" in txt[:2000].lower():
        links = re.findall(r'href=["\']([^"\']+\.csv[^"\']*)["\']', txt, flags=re.I)
        if not links:
            links = re.findall(r'(https?://[^\s"\']+\.csv[^\s"\']*)', txt, flags=re.I)
        if not links:
            raise RuntimeError("Podano HTML, ale nie znalazłem linku CSV na stronie GUS.")
        href = unescape(links[0])
        if href.startswith("/"):
            href = "https://stat.gov.pl" + href
        elif not href.lower().startswith("http"):
            href = DEFAULT_PAGE.rstrip("/") + "/" + href
        txt = decode_bytes(fetch_bytes(href))
    return txt

def parse_decimal(s: str):
    s = str(s).strip().replace("\xa0", "").replace(" ", "")
    if not s or s in (".", "-", "–"):
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def parse_month(s: str):
    s0 = str(s).strip()
    ns = norm(s0)
    if ns in MONTHS:
        return MONTHS[ns]
    if ns in PL_MONTHS:
        return PL_MONTHS[ns]
    m = re.search(r"\b(1[0-2]|0?[1-9])\b", ns)
    if m:
        return int(m.group(1))
    return None

def parse_year(s: str):
    m = re.search(r"(19\d{2}|20\d{2})", str(s))
    return int(m.group(1)) if m else None

def read_rows(text: str):
    sample = text[:5000]
    delim = ";" if sample.count(";") >= sample.count(",") else ","
    return list(csv.reader(text.splitlines(), delimiter=delim))

def extract_dec_prev(rows):
    out = []
    for row in rows:
        if len(row) < 5:
            continue
        nrow = [norm(x) for x in row]
        joined = " | ".join(nrow)
        if "grudzien poprzedniego roku" not in joined:
            continue
        # avoid headers without year/month/value
        years = [(i, parse_year(x)) for i, x in enumerate(row)]
        years = [(i, y) for i, y in years if y is not None]
        if not years:
            continue
        # In GUS long CSV usually: ..., presentation, year, month, value, ...
        # Choose first year-like cell, month after it, first decimal value after month.
        for yi, y in years:
            if yi + 1 >= len(row):
                continue
            mo = parse_month(row[yi + 1])
            if mo is None:
                # sometimes month can be later
                for mi in range(yi + 1, min(len(row), yi + 4)):
                    mo = parse_month(row[mi])
                    if mo is not None:
                        break
            else:
                mi = yi + 1
            if mo is None:
                continue
            val = None
            for vi in range(mi + 1, min(len(row), mi + 6)):
                val = parse_decimal(row[vi])
                if val is not None:
                    break
            if val is None:
                continue
            out.append((y, mo, val, row))
            break
    if not out:
        # diagnostic dump of presentation-like strings
        candidates = []
        for row in rows[:2000]:
            for cell in row:
                nc = norm(cell)
                if "poprzed" in nc or "analogicz" in nc or "grud" in nc:
                    candidates.append(cell.strip())
        uniq = []
        for c in candidates:
            if c and c not in uniq:
                uniq.append(c)
        msg = "Nie znalazłem wierszy 'Grudzień poprzedniego roku = 100'."
        if uniq:
            msg += " Kandydaci w pliku: " + " || ".join(uniq[:20])
        raise RuntimeError(msg)
    # deduplicate by (year, month), keep last occurrence
    d = {}
    for y, m, v, row in out:
        d[(y, m)] = v
    return d

def build_index(month_values, start_date):
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    # Continuous index. We set Dec before first available year = 100 and chain years.
    min_year = min(y for y, m in month_values)
    max_year = max(y for y, m in month_values)
    dec_prev = 100.0
    rows = []
    last_dec_index = None
    for y in range(min_year, max_year + 1):
        # if missing months in year, calculate available months; next year chaining needs Dec
        for m in range(1, 13):
            if (y, m) not in month_values:
                continue
            cpi = dec_prev * month_values[(y, m)] / 100.0
            dt = datetime(y, m, 1).date()
            if dt >= start:
                rows.append([dt.isoformat(), cpi])
            if m == 12:
                last_dec_index = cpi
        if last_dec_index is not None:
            dec_prev = last_dec_index
        else:
            # no December in this year: keep chaining base, but this should only happen for last incomplete year
            pass
    # add mom/yoy after filtering
    import pandas as pd
    df = pd.DataFrame(rows, columns=["date", "cpi"])
    df["cpi"] = pd.to_numeric(df["cpi"])
    df["infl_mom"] = df["cpi"].pct_change()
    df["infl_yoy"] = df["cpi"].pct_change(12)
    return df

def normalize_rate(x):
    """Accept 0.006 or 0.6 or 3.2 style rates. Returns decimal fraction."""
    v = parse_decimal(x)
    if v is None:
        return None
    # 0.6 means 0.6%; 3.2 means 3.2%.
    # 0.006 already means 0.6%.
    if abs(v) > 0.20:
        return v / 100.0
    return v

def apply_flash_estimates(df, flash_file: str | None):
    """
    Append provisional monthly CPI rows, e.g. GUS quick estimates.

    Expected CSV:
      date,infl_mom,infl_yoy,status,source,comment

    Priority:
      - if date already exists in final GUS data, do not override it,
      - use infl_mom when previous month CPI exists,
      - otherwise use infl_yoy when same month previous year CPI exists.
    """
    if not flash_file:
        return df
    path = Path(flash_file)
    if not path.exists():
        return df

    import pandas as pd
    out = df.copy()
    if out.empty:
        return out

    # Preserve optional metadata columns.
    for col in ["status", "source", "comment"]:
        if col not in out.columns:
            out[col] = "FINAL" if col == "status" else ("GUS_FINAL" if col == "source" else "")

    flash = pd.read_csv(path)
    if "date" not in flash.columns:
        raise ValueError(f"Flash CPI file {flash_file} must contain column: date")
    flash["date"] = pd.to_datetime(flash["date"]).dt.date
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out = out.sort_values("date").reset_index(drop=True)

    rows_to_add = []
    existing_dates = set(out["date"])
    cpi_by_date = {r["date"]: float(r["cpi"]) for _, r in out.iterrows() if pd.notna(r["cpi"])}

    for _, r in flash.sort_values("date").iterrows():
        d = r["date"]
        if d in existing_dates:
            continue

        mom = normalize_rate(r.get("infl_mom", None))
        yoy = normalize_rate(r.get("infl_yoy", None))
        cpi_val = None

        prev_month = (pd.Timestamp(d) - pd.DateOffset(months=1)).date().replace(day=1)
        prev_year = (pd.Timestamp(d) - pd.DateOffset(years=1)).date().replace(day=1)

        if mom is not None and prev_month in cpi_by_date:
            cpi_val = cpi_by_date[prev_month] * (1.0 + mom)
        elif yoy is not None and prev_year in cpi_by_date:
            cpi_val = cpi_by_date[prev_year] * (1.0 + yoy)

        if cpi_val is None:
            print(f"WARN: pomijam flash CPI {d}: brak poprzedniego miesiąca/roku do wyliczenia indeksu", file=sys.stderr)
            continue

        row = {
            "date": d,
            "cpi": cpi_val,
            "infl_mom": mom,
            "infl_yoy": yoy,
            "status": str(r.get("status", "PROVISIONAL")).strip() or "PROVISIONAL",
            "source": str(r.get("source", "GUS_FLASH")).strip() or "GUS_FLASH",
            "comment": str(r.get("comment", "")).strip(),
        }
        rows_to_add.append(row)
        existing_dates.add(d)
        cpi_by_date[d] = cpi_val

    if rows_to_add:
        out = pd.concat([out, pd.DataFrame(rows_to_add)], ignore_index=True).sort_values("date").reset_index(drop=True)
        out["cpi"] = pd.to_numeric(out["cpi"], errors="coerce")
        out["infl_mom"] = pd.to_numeric(out.get("infl_mom"), errors="coerce")
        out["infl_yoy"] = pd.to_numeric(out.get("infl_yoy"), errors="coerce")
        # Fill missing derived metrics, but keep explicit flash metrics when present.
        calc_mom = out["cpi"].pct_change()
        calc_yoy = out["cpi"].pct_change(12)
        out["infl_mom"] = out["infl_mom"].where(out["infl_mom"].notna(), calc_mom)
        out["infl_yoy"] = out["infl_yoy"].where(out["infl_yoy"].notna(), calc_yoy)

    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def main():
    ap = argparse.ArgumentParser(description="Build CPI_PLN from official GUS monthly CPI CSV (Dec previous year = 100).")
    ap.add_argument("--input", help="Local GUS CSV/HTML path or URL. Default: official GUS CSV URL.")
    ap.add_argument("--start", default="1995-01-01")
    ap.add_argument("--out", default="CPI_PLN_GUS.csv")
    ap.add_argument("--raw-out", default=None)
    ap.add_argument("--flash-file", default=None, help="Opcjonalny CSV z szybkimi szacunkami CPI_PLN: date,infl_mom,infl_yoy,status,source,comment.")
    args = ap.parse_args()
    txt = resolve_csv_text(args.input, args.raw_out)
    rows = read_rows(txt)
    month_values = extract_dec_prev(rows)
    df = build_index(month_values, args.start)
    df["status"] = "FINAL"
    df["source"] = "GUS_FINAL"
    df["comment"] = ""
    df = apply_flash_estimates(df, args.flash_file)
    df.to_csv(args.out, index=False)
    print(f"OK: zapisano {args.out}; rows={len(df)}; range={df['date'].iloc[0]}..{df['date'].iloc[-1]}")
    print(df.tail(12).to_string(index=False))

if __name__ == "__main__":
    main()

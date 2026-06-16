#!/usr/bin/env python3
# pasywnyportfel — Autor koncepcji i projektu: Wojciech Król / lurk@lurk.com.pl
# -*- coding: utf-8 -*-
"""ledger_tax.py — model opodatkowania strat (blok 3)."""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil.relativedelta import relativedelta
import re

@dataclass
class LossBucket:
    year: int
    original: float
    remaining: float
    used_this_year: Dict[int, float]

def apply_loss_buckets(
    year: int,
    positive_net: float,
    buckets: List[LossBucket],
    window_years: int,
    annual_cap_frac: float
) -> Tuple[float, float]:
    """
    Zwraca (deducted, taxable_after).
    Reguła: koszyk straty żyje window_years lat; w danym roku odliczenie z koszyka <= annual_cap_frac * original.
    """
    buckets[:] = [b for b in buckets if year <= b.year + window_years and b.remaining > 1e-9]
    taxable = positive_net
    deducted = 0.0
    buckets.sort(key=lambda b: b.year)  # FIFO

    for b in buckets:
        if taxable <= 1e-9:
            break
        if year <= b.year:
            continue
        cap = annual_cap_frac * b.original
        used = b.used_this_year.get(year, 0.0)
        room = max(0.0, cap - used)
        take = min(b.remaining, room, taxable)
        if take > 0:
            b.remaining -= take
            b.used_this_year[year] = used + take
            taxable -= take
            deducted += take

    buckets[:] = [b for b in buckets if b.remaining > 1e-9 and year <= b.year + window_years]
    return deducted, max(0.0, taxable)
# 3 END

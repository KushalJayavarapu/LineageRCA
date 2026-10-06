"""SYNTHETIC data generator. Everything here is invented; the same seed always gives the same tables.

Each day uses its own random stream, so changing one day never changes another day.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pyarrow as pa

from core.config import PipelineConfig
from core.rng import make_rng

START_DATE = date(2026, 1, 1)           # day 1 (a fixed calendar, not the wall clock)
BASE_RATES = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}


def date_for_day(day: int) -> str:
    """Day 1 -> '2026-01-01', day 11 -> '2026-01-11'."""
    return (START_DATE + timedelta(days=day - 1)).isoformat()


class DataGenerator:
    def __init__(self, cfg: PipelineConfig, seed: int) -> None:
        self.cfg = cfg
        self.seed = seed

    def customers(self) -> pa.Table:
        """raw_customers: ids like C0001, each with a region and a segment."""
        rng = make_rng(self.seed, "customers")
        n = self.cfg.n_customers
        return pa.table({
            "customer_id": [f"C{i:04d}" for i in range(1, n + 1)],
            "region": rng.choice(self.cfg.regions, size=n).tolist(),
            "segment": rng.choice(self.cfg.segments, size=n).tolist(),
        })

    def orders(self, day: int) -> pa.Table:
        """raw_orders for one day. `amount` is a STRING at the source (like '123.45'), as in many real feeds."""
        rng = make_rng(self.seed, f"orders{day}")
        n = self.cfg.orders_per_day
        amounts = np.round(rng.lognormal(mean=3.5, sigma=0.6, size=n), 2)
        amounts[rng.random(n) < 0.01] = 0.0                       # about 1% zero amounts (the cleaner drops them)
        status = rng.choice(["completed", "cancelled", "test"], size=n, p=[0.85, 0.12, 0.03])
        customer_ids = [f"C{i:04d}" for i in rng.integers(1, self.cfg.n_customers + 1, size=n)]
        return pa.table({
            "order_id": [f"O{day:02d}{i:05d}" for i in range(n)],
            "customer_id": customer_ids,
            "product": rng.choice(self.cfg.products, size=n).tolist(),
            "amount": [f"{a:.2f}" for a in amounts],
            "quantity": rng.integers(1, 6, size=n).astype("int64"),
            "status": status.tolist(),
            "currency": rng.choice(self.cfg.currencies, size=n, p=[0.7, 0.2, 0.1]).tolist(),
            "order_date": [date_for_day(day)] * n,
        })

    def fx_rates(self, day: int) -> pa.Table:
        """raw_fx_rates for one day: each currency moves a little (about 0.3%) around its base rate."""
        rng = make_rng(self.seed, f"fx{day}")
        rates = [round(BASE_RATES[c] * (1 + float(rng.normal(0, 0.003))), 5) if c != "USD" else 1.0
                 for c in self.cfg.currencies]
        return pa.table({"currency": list(self.cfg.currencies), "rate_to_usd": rates,
                         "rate_date": [date_for_day(day)] * len(rates)})

"""Data-quality monitor: plain, explainable checks of one day against the median of the previous days.

Four metrics (all on tables the pipeline produces):
  cleaned_orders.row_count        relative deviation from the median of the previous days
  daily_revenue_agg.revenue_usd   relative deviation
  cleaned_orders.amount_null_rate absolute increase
  cleaned_orders.region_null_rate absolute increase
The replay harness reuses day_metrics() and Monitor.deviation() so it judges a replay with EXACTLY the monitor's thresholds.
"""
from __future__ import annotations

from datetime import date
from statistics import median

import pyarrow as pa

from adapters.delta_store import DeltaStore
from adapters.duck import query
from core.config import MonitorConfig
from core.models import Anomaly
from tasks.datagen import START_DATE

Metrics = dict[str, dict[int, float]]            # metric name -> {day number -> value}

# metric name -> (table it lives in, "rel" = relative change, "abs" = absolute increase)
METRICS: dict[str, tuple[str, str]] = {
    "row_count": ("cleaned_orders", "rel"),
    "revenue_usd": ("daily_revenue_agg", "rel"),
    "amount_null_rate": ("cleaned_orders", "abs"),
    "region_null_rate": ("cleaned_orders", "abs"),
}
MIN_HISTORY_DAYS = 3                             # fewer previous days than this: no baseline, no check


def _day_number(order_date: str) -> int:
    return (date.fromisoformat(order_date) - START_DATE).days + 1


def cleaned_metrics(cleaned: pa.Table) -> Metrics:
    """The three metrics that live in cleaned_orders, for every day present."""
    rows = query("SELECT order_date, COUNT(*) AS n, AVG(CASE WHEN amount IS NULL THEN 1.0 ELSE 0.0 END) AS an, "
                 "AVG(CASE WHEN region IS NULL THEN 1.0 ELSE 0.0 END) AS rn FROM cleaned_orders GROUP BY order_date",
                 cleaned_orders=cleaned).to_pylist()
    return {
        "row_count": {_day_number(r["order_date"]): float(r["n"]) for r in rows},
        "amount_null_rate": {_day_number(r["order_date"]): float(r["an"]) for r in rows},
        "region_null_rate": {_day_number(r["order_date"]): float(r["rn"]) for r in rows},
    }


def revenue_metrics(agg: pa.Table) -> Metrics:
    """The revenue metric that lives in daily_revenue_agg, for every day present."""
    rows = query("SELECT order_date, COALESCE(SUM(revenue_usd), 0) AS r FROM daily_revenue_agg GROUP BY order_date",
                 daily_revenue_agg=agg).to_pylist()
    return {"revenue_usd": {_day_number(r["order_date"]): float(r["r"]) for r in rows}}


def day_metrics(cleaned: pa.Table, agg: pa.Table) -> Metrics:
    """All four metrics for every day present in the two tables."""
    return {**cleaned_metrics(cleaned), **revenue_metrics(agg)}


def metric_from_table(name: str, table: pa.Table, day: int) -> float:
    """One metric of one day, computed from ONE table (used by replay on a replayed table)."""
    metrics = revenue_metrics(table) if METRICS[name][0] == "daily_revenue_agg" else cleaned_metrics(table)
    return metrics[name].get(day, 0.0)


class Monitor:
    def __init__(self, cfg: MonitorConfig) -> None:
        self.cfg = cfg

    def expected(self, metrics: Metrics, name: str, day: int) -> float | None:
        """Median of the previous `baseline_days` days, or None if there is too little history."""
        prev = [metrics[name][d] for d in range(day - self.cfg.baseline_days, day) if d in metrics[name]]
        return median(prev) if len(prev) >= MIN_HISTORY_DAYS else None

    def deviation(self, metrics: Metrics, name: str, day: int) -> float | None:
        """Signed deviation of `day` from its baseline: relative for 'rel' metrics, absolute for null rates."""
        exp = self.expected(metrics, name, day)
        if exp is None:
            return None
        obs = metrics[name].get(day, 0.0)           # a missing day counts as 0 rows / 0 revenue
        return (obs - exp) / exp if METRICS[name][1] == "rel" and exp else obs - exp

    def is_alarm(self, name: str, dev: float) -> bool:
        if METRICS[name][1] == "rel":
            return abs(dev) > self.cfg.rel_threshold
        return dev > self.cfg.null_rate_threshold

    def evaluate(self, metrics: Metrics, day: int, logical_time: int) -> list[Anomaly]:
        """Anomalies for one day (empty list = silent). All anomalies of the day share one incident id."""
        out = []
        for name, (table, _) in METRICS.items():
            dev = self.deviation(metrics, name, day)
            if dev is not None and self.is_alarm(name, dev):
                out.append(Anomaly(incident_id=f"inc_d{day:02d}", table=table, metric=name,
                                   observed=metrics[name].get(day, 0.0), expected=self.expected(metrics, name, day) or 0.0,
                                   deviation=dev, logical_time=logical_time, day=day))
        return out

    def check_store(self, store: DeltaStore, day: int) -> list[Anomaly]:
        """Check `day` on the latest version of the tables in a Delta store."""
        metrics = day_metrics(store.read("cleaned_orders"), store.read("daily_revenue_agg"))
        return self.evaluate(metrics, day, store.clock.now)


def primary_anomaly(anomalies: list[Anomaly]) -> Anomaly | None:
    """The anomaly the investigation starts from: the one on the most downstream table (daily_revenue_agg first).

    Its metric is the one replay must clear. The anomalous table itself is also a suspect if it has its own change
    commit (a table can be corrupted by its own stage, as in s2), see agents/shortlist.py.
    """
    for table in ("daily_revenue_agg", "cleaned_orders"):
        for a in anomalies:
            if a.table == table:
                return a
    return None

"""The synthetic pipeline: raw tables -> cleaned_orders -> daily_revenue_agg, every commit a Delta snapshot.

Derived tables are partitioned by day: a run replaces only that day's rows, so older days stay as they were.
A day is done in separate steps so that a scenario can slip change commits (faults, decoys) in between:
    load_day(d)   append that day's raw data                     (normal_load commits)
    run_clean(d)  re-materialise day d of cleaned_orders from the raw tables
    run_aggregate(d)  re-materialise day d of daily_revenue_agg from cleaned_orders
Each run_* call records WHICH snapshot of every input it read and WHICH code version it used (a RunRecord).
"""
from __future__ import annotations

import pyarrow as pa

from adapters.delta_store import DeltaStore
from adapters.duck import query
from core.models import RunRecord
from tasks import stages
from tasks.datagen import DataGenerator, date_for_day

RAW_TABLES = ("raw_orders", "raw_customers", "raw_fx_rates")
HEALTHY_CODE = {"clean": "clean_v1", "aggregate": "aggregate_v1"}


class Pipeline:
    def __init__(self, store: DeltaStore, gen: DataGenerator) -> None:
        self.store = store
        self.gen = gen
        self.runs: list[RunRecord] = []

    # ---- loading raw data -------------------------------------------------------------------------------------
    def load_day(self, day: int) -> None:
        """Append one day of raw orders and FX rates (customers are loaded once, on day 1)."""
        if day == 1:
            self.store.write("raw_customers", self.gen.customers(), "overwrite", "normal_load")
        self.store.write("raw_orders", self.gen.orders(day), "append", "normal_load")
        self.store.write("raw_fx_rates", self.gen.fx_rates(day), "append", "normal_load")

    # ---- the two derived stages -------------------------------------------------------------------------------
    def run_clean(self, day: int, code_version: str = HEALTHY_CODE["clean"],
                  change_type: str = "normal_load") -> RunRecord:
        inputs = {t: self.store.latest_version(t) for t in RAW_TABLES}
        tables = {t: self.store.read(t, v) for t, v in inputs.items()}
        out = stages.clean(tables["raw_orders"], tables["raw_customers"], tables["raw_fx_rates"], day, code_version)
        return self._commit("clean", "cleaned_orders", out, inputs, code_version, day, change_type, _day_rows(out, day))

    def run_aggregate(self, day: int, code_version: str = HEALTHY_CODE["aggregate"],
                      change_type: str = "normal_load") -> RunRecord:
        inputs = {"cleaned_orders": self.store.latest_version("cleaned_orders")}
        out = stages.aggregate(self.store.read("cleaned_orders", inputs["cleaned_orders"]), day, code_version)
        return self._commit("aggregate", "daily_revenue_agg", out, inputs, code_version, day, change_type,
                            _day_revenue(out, day))

    def run_day(self, day: int) -> None:
        """A whole healthy day: load, clean, aggregate."""
        self.load_day(day)
        self.run_clean(day)
        self.run_aggregate(day)

    def _commit(self, transform_id: str, output: str, data: pa.Table, inputs: dict[str, int], code_version: str,
                day: int, change_type: str, metric: float) -> RunRecord:
        snap = self.store.write(output, data, "overwrite", change_type, metric_value=metric,
                                replace_where=f"order_date = '{date_for_day(day)}'")
        record = RunRecord(run_id=f"run_{len(self.runs) + 1:04d}", transform_id=transform_id,
                           code_version=code_version, inputs=inputs, output_table=output,
                           output_snapshot_id=snap.snapshot_id, logical_time=snap.committed_at, day=day)
        self.runs.append(record)
        return record


def _day_rows(cleaned: pa.Table, day: int) -> float:
    """metric_value for cleaned_orders snapshots: number of rows for that day."""
    res = query(f"SELECT COUNT(*) AS n FROM t WHERE order_date = '{date_for_day(day)}'", t=cleaned)
    return float(res["n"][0].as_py())


def _day_revenue(agg: pa.Table, day: int) -> float:
    """metric_value for daily_revenue_agg snapshots: total revenue_usd for that day."""
    res = query(f"SELECT COALESCE(SUM(revenue_usd), 0) AS r FROM t WHERE order_date = '{date_for_day(day)}'", t=agg)
    return float(res["r"][0].as_py())

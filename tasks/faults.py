"""Fault and decoy injectors (test-only). Each one is a CHANGE COMMIT to a table, recorded with its own change_type.

The dropped-filter fault is a code change: it is injected by re-running the clean step with the code version
clean_v2_no_filter (see Pipeline.run_clean), so it has no function here.
"""
from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc

from adapters.delta_store import DeltaStore
from core.models import SnapshotRecord
from core.rng import make_rng
from tasks.datagen import date_for_day


def bad_join_key(store: DeltaStore, seed: int, fraction: float) -> SnapshotRecord:
    """s1: a random share of customer ids loses its case ('C0042' -> 'c0042'), so orders no longer find their customer."""
    customers = store.read("raw_customers")
    hit = make_rng(seed, "fault_bad_join_key").random(customers.num_rows) < fraction
    ids = [cid.lower() if h else cid for cid, h in zip(customers["customer_id"].to_pylist(), hit, strict=True)]
    broken = customers.set_column(customers.column_names.index("customer_id"), "customer_id", pa.array(ids))
    return store.write("raw_customers", broken, "overwrite", "bad_join_key")


def type_coercion(store: DeltaStore, seed: int, day: int, fraction: float) -> SnapshotRecord:
    """s3: a share of that day's amounts switches to a decimal comma ('12.34' -> '12,34'); the cast then gives NULL."""
    orders = store.read("raw_orders")
    day_rows = orders.filter(pc.equal(orders["order_date"], date_for_day(day)))
    hit = make_rng(seed, "fault_type_coercion").random(day_rows.num_rows) < fraction
    amounts = [a.replace(".", ",") if h else a for a, h in zip(day_rows["amount"].to_pylist(), hit, strict=True)]
    changed = day_rows.set_column(day_rows.column_names.index("amount"), "amount", pa.array(amounts))
    return store.write("raw_orders", changed, "overwrite", "type_coercion",
                       replace_where=f"order_date = '{date_for_day(day)}'")


def benign_fx_refresh(store: DeltaStore, day: int, pct: float) -> SnapshotRecord:
    """The decoy: that day's FX rates are refreshed and move by about `pct` (harmless, within normal variation)."""
    rates = store.read("raw_fx_rates")
    day_rows = rates.filter(pc.equal(rates["rate_date"], date_for_day(day)))
    new_rates = [r if c == "USD" else round(r * (1 + pct), 5)
                 for c, r in zip(day_rows["currency"].to_pylist(), day_rows["rate_to_usd"].to_pylist(), strict=True)]
    changed = day_rows.set_column(day_rows.column_names.index("rate_to_usd"), "rate_to_usd", pa.array(new_rates))
    return store.write("raw_fx_rates", changed, "overwrite", "benign_refresh",
                       replace_where=f"rate_date = '{date_for_day(day)}'")

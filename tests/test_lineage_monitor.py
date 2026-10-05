import json

import pyarrow.compute as pc

from adapters.lineage_store import LineageStore
from core.config import load_settings
from drift.monitor import Monitor, day_metrics, primary_anomaly
from tests.helpers import build


def lineage_for(store, pipe):
    lin = LineageStore(store.snapshots)
    lin.add_runs(pipe.runs)
    return lin


def test_upstream_of_is_transitive_and_closest_first(tmp_path):
    store, pipe = build(tmp_path, 42, days=2)
    lin = lineage_for(store, pipe)
    assert lin.upstream_of("daily_revenue_agg") == ["cleaned_orders", "raw_customers", "raw_fx_rates", "raw_orders"]
    assert lin.distances_upstream("daily_revenue_agg")["raw_orders"] == 2
    assert lin.upstream_of("raw_orders") == []


def test_path_stages_lists_derived_tables_between_suspect_and_target(tmp_path):
    store, pipe = build(tmp_path, 42, days=2)
    lin = lineage_for(store, pipe)
    assert lin.path_stages("raw_customers", "daily_revenue_agg") == ["cleaned_orders", "daily_revenue_agg"]
    assert lin.path_stages("cleaned_orders", "daily_revenue_agg") == ["daily_revenue_agg"]


def test_runs_record_inputs_and_changes_since_uses_logical_time(tmp_path):
    store, pipe = build(tmp_path, 42, days=3)
    lin = lineage_for(store, pipe)
    last_clean = lin.last_run_of("cleaned_orders")
    assert lin.inputs_of_run(last_clean.run_id) == {"raw_orders": 2, "raw_customers": 0, "raw_fx_rates": 2}
    assert [s.snapshot_id for s in lin.changes_since("raw_orders", 0)] == [0, 1, 2]
    assert lin.changes_since("raw_orders", store.clock.now) == []


def test_edges_and_events_export(tmp_path):
    store, pipe = build(tmp_path, 42, days=1)
    lin = lineage_for(store, pipe)
    pairs = {(e.upstream_table, e.downstream_table) for e in lin.edges()}
    assert pairs == {("raw_orders", "cleaned_orders"), ("raw_customers", "cleaned_orders"),
                     ("raw_fx_rates", "cleaned_orders"), ("cleaned_orders", "daily_revenue_agg")}
    assert all(e.source == "synthetic" for e in lin.edges())
    path = tmp_path / "events.jsonl"
    lin.save(path)
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(events) == 2 and events[0]["job"]["codeVersion"] == "clean_v1"


def test_monitor_is_silent_on_healthy_days(tmp_path):
    store, _ = build(tmp_path, 42, days=10, orders_per_day=500)
    mon = Monitor(load_settings().monitor)
    metrics = day_metrics(store.read("cleaned_orders"), store.read("daily_revenue_agg"))
    for day in range(1, 11):
        assert mon.evaluate(metrics, day, 0) == [], f"false alarm on healthy day {day}"
    assert mon.deviation(metrics, "row_count", 2) is None      # too little history: no check


def test_monitor_fires_on_a_hand_made_fault(tmp_path):
    store, pipe = build(tmp_path, 42, days=10, orders_per_day=500)
    pipe.load_day(11)
    pipe.run_clean(11)
    pipe.run_aggregate(11)
    mon = Monitor(load_settings().monitor)
    assert mon.check_store(store, 11) == []                    # a healthy day 11 stays silent
    # hand-made fault: drop 40% of the customers so the join loses orders, then recompute downstream
    customers = store.read("raw_customers")
    keep = pc.less(pc.utf8_slice_codeunits(customers["customer_id"], 1, 5), "0240")
    store.write("raw_customers", customers.filter(keep), "overwrite", "hand_made_fault")
    pipe.run_clean(11)
    pipe.run_aggregate(11)
    anomalies = mon.check_store(store, 11)
    tables = {(a.table, a.metric) for a in anomalies}
    assert ("daily_revenue_agg", "revenue_usd") in tables and ("cleaned_orders", "row_count") in tables
    top = primary_anomaly(anomalies)
    assert top.table == "daily_revenue_agg" and top.deviation < -0.15 and top.expected > top.observed

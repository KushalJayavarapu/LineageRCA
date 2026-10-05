import pyarrow.compute as pc
import pytest

from core.hashing import table_hash
from tasks import stages
from tests.helpers import build

ALL_TABLES = ["raw_orders", "raw_customers", "raw_fx_rates", "cleaned_orders", "daily_revenue_agg"]


def test_same_seed_gives_identical_hashes_and_other_seed_differs(tmp_path):
    a, _ = build(tmp_path, 42, name="a")
    b, _ = build(tmp_path, 42, name="b")
    c, _ = build(tmp_path, 7, name="c")
    for t in ALL_TABLES:
        assert table_hash(a.read(t)) == table_hash(b.read(t)), t
    assert table_hash(a.read("raw_orders")) != table_hash(c.read("raw_orders"))


def test_every_day_adds_a_snapshot_and_old_days_stay_readable(tmp_path):
    store, _ = build(tmp_path, 42, days=3)
    assert [h.snapshot_id for h in store.history("raw_orders")] == [0, 1, 2]
    assert store.read("raw_orders", 0).num_rows == 300 and store.read("raw_orders").num_rows == 900


def test_stages_are_pure_and_filters_work(tmp_path):
    store, _ = build(tmp_path, 42, days=2)
    raw = [store.read(t) for t in ("raw_orders", "raw_customers", "raw_fx_rates")]
    before = [table_hash(t) for t in raw]
    one, two = stages.clean(*raw, day=2), stages.clean(*raw, day=2)
    assert table_hash(one) == table_hash(two)                       # same inputs -> same output
    assert [table_hash(t) for t in raw] == before                    # inputs untouched
    assert set(one["status"].to_pylist()) == {"completed"}
    unfiltered = stages.clean(*raw, day=2, code_version="clean_v2_no_filter")
    assert unfiltered.num_rows > one.num_rows                        # s2's dropped filter lets extra rows in
    assert table_hash(stages.aggregate(one, 2)) == table_hash(stages.aggregate(one, 2))


def test_run_records_pin_input_snapshots_and_code_version(tmp_path):
    store, pipe = build(tmp_path, 42, days=2)
    clean_run = [r for r in pipe.runs if r.transform_id == "clean"][-1]
    assert clean_run.inputs == {"raw_orders": 1, "raw_customers": 0, "raw_fx_rates": 1}
    assert clean_run.code_version == "clean_v1" and clean_run.day == 2
    agg_run = pipe.runs[-1]
    assert agg_run.inputs == {"cleaned_orders": store.latest_version("cleaned_orders")}


def test_daily_revenue_is_stable_across_healthy_days(tmp_path):
    store, _ = build(tmp_path, 42, days=5)
    revenue = [s.metric_value for s in store.history("daily_revenue_agg")]
    assert min(revenue) > 0 and max(revenue) / min(revenue) < 1.15


def test_nondeterministic_aggregate_version_really_differs(tmp_path):
    store, _ = build(tmp_path, 42, days=1)
    cleaned = store.read("cleaned_orders")
    runs = {table_hash(stages.aggregate(cleaned, 1, "aggregate_v2_sample")) for _ in range(3)}
    assert len(runs) > 1


def test_unknown_code_version_is_rejected(tmp_path):
    store, _ = build(tmp_path, 42, days=1)
    with pytest.raises(KeyError):
        stages.aggregate(store.read("cleaned_orders"), 1, "nope")


def _day_rows(table, order_date):
    return table.filter(pc.equal(table["order_date"], order_date))


def test_rerunning_a_day_replaces_only_that_day(tmp_path):
    store, pipe = build(tmp_path, 42, days=3)
    day1_before = table_hash(_day_rows(store.read("cleaned_orders"), "2026-01-01"))
    pipe.run_clean(3, code_version="clean_v2_no_filter", change_type="dropped_filter")
    cleaned = store.read("cleaned_orders")
    assert table_hash(_day_rows(cleaned, "2026-01-01")) == day1_before            # other days untouched
    assert "cancelled" in set(_day_rows(cleaned, "2026-01-03")["status"].to_pylist())
    assert "cancelled" not in set(_day_rows(cleaned, "2026-01-02")["status"].to_pylist())

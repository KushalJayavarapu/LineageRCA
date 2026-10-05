import dataclasses
import json

from core.hashing import table_hash
from tasks.scenarios import IncidentContext, build_scenario

TABLES = ["raw_orders", "raw_customers", "raw_fx_rates", "cleaned_orders", "daily_revenue_agg"]


def changes(run):
    """(table, change_type) of every non-normal commit, oldest first."""
    return [(s.table_name, s.change_type) for s in run.context.store.snapshots if s.change_type != "normal_load"]


def test_all_six_scenarios_exist_with_ground_truth(runs):
    assert list(runs) == ["s1_bad_join_key", "s2_dropped_filter", "s3_type_coercion_latest", "s4_control_no_fault",
                          "s5_two_causes", "s6_nondeterministic_transform"]
    assert runs["s1_bad_join_key"].truth.true_causes == ["raw_customers"]
    assert runs["s4_control_no_fault"].truth.true_causes == []
    assert runs["s5_two_causes"].truth.boundary and runs["s6_nondeterministic_transform"].truth.boundary


def test_s1_fault_then_decoy_after_and_revenue_alarm(runs):
    run = runs["s1_bad_join_key"]
    assert changes(run) == [("raw_customers", "bad_join_key"), ("raw_fx_rates", "benign_refresh")]   # decoy is MORE recent
    assert run.context.anomaly.table == "daily_revenue_agg" and run.context.anomaly.deviation < -0.15


def test_s2_code_fault_is_a_change_commit_on_cleaned_orders_with_decoy_after(runs):
    run = runs["s2_dropped_filter"]
    assert changes(run) == [("cleaned_orders", "dropped_filter"), ("raw_fx_rates", "benign_refresh")]
    assert run.context.anomalies and run.context.anomaly.deviation > 0.15       # extra rows flow in
    last_clean = run.context.lineage.last_run_of("cleaned_orders")
    assert last_clean.code_version == "clean_v2_no_filter"                      # the anomalous run used the bad code


def test_s3_fault_is_the_latest_change_and_nulls_appear(runs):
    run = runs["s3_type_coercion_latest"]
    assert changes(run) == [("raw_fx_rates", "benign_refresh"), ("raw_orders", "type_coercion")]
    assert {a.metric for a in run.context.anomalies} >= {"amount_null_rate", "revenue_usd"}


def test_s4_control_is_silent(runs):
    run = runs["s4_control_no_fault"]
    assert run.context.anomalies == [] and run.context.anomaly is None
    assert changes(run) == [("raw_fx_rates", "benign_refresh")]


def test_s5_and_s6_are_built_with_their_special_setup(runs):
    s5, s6 = runs["s5_two_causes"], runs["s6_nondeterministic_transform"]
    assert [t for t, _ in changes(s5)] == ["raw_customers", "cleaned_orders", "raw_fx_rates"]
    assert s6.context.lineage.last_run_of("daily_revenue_agg").code_version == "aggregate_v2_sample"


def test_incident_context_holds_no_ground_truth(runs):
    names = {f.name for f in dataclasses.fields(IncidentContext)}
    assert not any("truth" in n or "cause" in n or "decoy" in n for n in names)


def test_same_seed_gives_identical_tables_and_logs_have_no_wall_clock(settings):
    a = build_scenario("s1_bad_join_key", 7, settings, log_dir=settings.results_dir / "x")
    b = build_scenario("s1_bad_join_key", 7, settings, log_dir=settings.results_dir / "y")
    for t in TABLES:
        assert table_hash(a.context.store.read(t)) == table_hash(b.context.store.read(t)), t
    log = (settings.results_dir / "x" / "s1_bad_join_key_seed7.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in log.splitlines()]
    assert [e["event"] for e in events][:1] == ["healthy_history_done"] and all(e["source"] == "synthetic" for e in events)
    assert "time" not in log.replace("logical_time", "").replace("healthy_until", "")

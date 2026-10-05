import pytest

from agents.parameter_replay import (
    ParamTest,
    choose_blame,
    code_config,
    parameter_replay,
)
from agents.replay import decide_verdict
from drift.monitor import Monitor


def run_b3(run, settings):
    return parameter_replay(run.context, settings.replay)


def test_code_config_reads_the_code_versions_of_the_healthy_and_the_anomalous_run(runs):
    ctx = runs["s2_dropped_filter"].context
    assert code_config(ctx.lineage, ctx.healthy_until) == {"clean": "clean_v1", "aggregate": "aggregate_v1"}
    assert code_config(ctx.lineage) == {"clean": "clean_v2_no_filter", "aggregate": "aggregate_v1"}


def test_s2_code_fault_is_found_by_reverting_the_code_version(runs, settings):
    out = run_b3(runs["s2_dropped_filter"], settings)
    assert out.differing == {"clean": ("clean_v1", "clean_v2_no_filter")}
    assert [t.verdict for t in out.tests] == ["CONFIRMED"] and out.blamed == "cleaned_orders" and out.n_executions == 1


@pytest.mark.parametrize("sid", ["s1_bad_join_key", "s3_type_coercion_latest"])
def test_data_faults_are_outside_the_parameter_search_space_so_b3_abstains(runs, settings, sid):
    out = run_b3(runs[sid], settings)
    assert out.differing == {} and out.tests == [] and out.blamed is None and out.n_executions == 0


def test_b3_never_reads_an_older_snapshot_and_never_uses_the_shortlist(runs, settings, monkeypatch):
    ctx = runs["s2_dropped_filter"].context
    pinned = ctx.lineage.last_run_of("cleaned_orders").inputs
    calls, original = [], ctx.store.read

    def spy(table, version=None):
        calls.append((table, version))
        return original(table, version)

    monkeypatch.setattr(ctx.store, "read", spy)
    parameter_replay(ctx, settings.replay)
    raw_reads = {c for c in calls if c[0] in pinned}
    assert raw_reads == set(pinned.items())                    # only the snapshots the anomalous run read: no time travel back


def test_b3_uses_the_same_decision_rule_as_replay(runs, settings):
    """B3 differs from replay only in WHAT it varies: its verdicts come from the same decide_verdict."""
    out = run_b3(runs["s2_dropped_filter"], settings)
    ctx = runs["s2_dropped_filter"].context
    verdict, _ = decide_verdict(ctx.anomaly.deviation, [out.tests[0].deviation_after] * settings.replay.replay_repeats,
                                ctx.anomaly.metric, Monitor(settings.monitor), settings.replay)
    assert verdict == out.tests[0].verdict


def test_boundary_scenarios_run_and_return_a_valid_outcome(runs, settings):
    """s5 and s6: whatever B3 does is reported, not asserted."""
    for sid in ("s5_two_causes", "s6_nondeterministic_transform"):
        out = run_b3(runs[sid], settings)
        assert out.blamed in {None, "cleaned_orders", "daily_revenue_agg"} and len(out.differing) == 1


def test_choose_blame_prefers_confirmed_then_smaller_subsets_then_partial():
    def t(reverted, verdict, dev):
        return ParamTest(reverted, verdict, dev, "", 0.0)
    both = t(("aggregate", "clean"), "CONFIRMED", 0.01)
    assert choose_blame([t(("aggregate",), "DENIED", -0.3), t(("clean",), "DENIED", -0.2), both]) == "cleaned_orders"
    assert choose_blame([t(("aggregate",), "CONFIRMED", 0.02), t(("clean",), "CONFIRMED", 0.01), both]) == "cleaned_orders"
    assert choose_blame([t(("aggregate",), "PARTIAL", -0.2), t(("clean",), "DENIED", -0.3)]) == "daily_revenue_agg"
    assert choose_blame([t(("clean",), "DENIED", -0.3), t(("clean",), "INCONCLUSIVE", -0.1)]) is None
    assert choose_blame([]) is None

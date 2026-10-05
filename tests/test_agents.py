import copy

import pytest

from agents.baselines import blame_distance, blame_recency, rank_distance, rank_recency
from agents.replay import decide_verdict, replay_all, rerun_once, top_suspect
from agents.shortlist import Suspect, shortlist
from core.models import ReplayVerdict, SnapshotRecord
from drift.monitor import Monitor


def investigate(run, settings):
    ctx = run.context
    suspects = shortlist(ctx, settings.replay)
    verdicts = {v.suspect_table: v for v in replay_all(ctx, suspects, settings.replay)}
    return suspects, verdicts


def snap(table, committed_at, change_type="x", snapshot_id=5):
    return SnapshotRecord(snapshot_id=snapshot_id, table_name=table, committed_at=committed_at,
                          change_type=change_type, row_count=1)


def suspect(table, committed_at, distance):
    s = snap(table, committed_at)
    return Suspect(table, s, s, s.snapshot_id - 1, distance)


def verdict(table, kind, before, after):
    return ReplayVerdict(incident_id="i", suspect_table=table, suspect_snapshot_id=0, replay_runs=3,
                         anomaly_cleared=kind == "CONFIRMED", verdict=kind, compute_seconds=0.0,
                         deviation_before=before, deviation_after=after, explanation="")


# ---- verdict rules on made-up numbers -------------------------------------------------------------------------------
@pytest.fixture()
def rules(settings):
    return Monitor(settings.monitor), settings.replay


def test_verdict_rules(rules):
    mon, cfg = rules
    assert decide_verdict(-0.26, [-0.01, -0.01, -0.01], "revenue_usd", mon, cfg)[0] == "CONFIRMED"
    assert decide_verdict(-0.26, [-0.25, -0.25, -0.26], "revenue_usd", mon, cfg)[0] == "DENIED"
    assert decide_verdict(-0.40, [-0.18, -0.18, -0.18], "revenue_usd", mon, cfg)[0] == "PARTIAL"
    assert decide_verdict(-0.26, [-0.01, -0.10, -0.05], "revenue_usd", mon, cfg)[0] == "INCONCLUSIVE"
    assert "threshold" in decide_verdict(-0.26, [-0.01] * 3, "revenue_usd", mon, cfg)[1]


def test_top_suspect_prefers_confirmed_then_largest_reduction():
    vs = [verdict("a", "DENIED", -0.3, -0.3), verdict("b", "PARTIAL", -0.4, -0.2), verdict("c", "CONFIRMED", -0.3, -0.01)]
    assert top_suspect(vs) == "c"
    assert top_suspect(vs[:2]) == "b"
    assert top_suspect([verdict("a", "DENIED", -0.3, -0.3), verdict("d", "INCONCLUSIVE", -0.3, -0.1)]) is None


# ---- baselines ------------------------------------------------------------------------------------------------------
def test_b1_blames_the_most_recent_change():
    sus = [suspect("raw_customers", 10, 2), suspect("raw_fx_rates", 12, 2), suspect("cleaned_orders", 11, 1)]
    assert blame_recency(sus) == "raw_fx_rates"
    assert [s.table for s in rank_recency(sus)] == ["raw_fx_rates", "cleaned_orders", "raw_customers"]
    assert blame_recency([]) is None


def test_b2_blames_the_closest_table_and_breaks_ties_by_recency():
    sus = [suspect("raw_customers", 10, 2), suspect("raw_fx_rates", 12, 2), suspect("cleaned_orders", 9, 1)]
    assert blame_distance(sus) == "cleaned_orders"
    assert blame_distance(sus[:2]) == "raw_fx_rates"                      # same distance: the more recent change
    assert rank_distance(sus)[0].table == "cleaned_orders"


# ---- the investigators on the real scenarios (seed 42) ---------------------------------------------------------------
def test_s1_replay_confirms_cause_denies_more_recent_decoy_and_b1_is_fooled(runs, settings):
    suspects, v = investigate(runs["s1_bad_join_key"], settings)
    assert {s.table for s in suspects} == {"raw_customers", "raw_fx_rates"}
    assert v["raw_customers"].verdict == "CONFIRMED" and v["raw_fx_rates"].verdict == "DENIED"
    assert top_suspect(list(v.values())) == "raw_customers"
    assert blame_recency(suspects) == "raw_fx_rates"                      # the lineage-recency baseline blames the decoy


def test_s2_code_fault_replay_confirms_cleaned_orders_and_denies_decoy(runs, settings):
    suspects, v = investigate(runs["s2_dropped_filter"], settings)
    assert {s.table for s in suspects} == {"cleaned_orders", "raw_fx_rates"}     # raw_orders has no change: not a suspect
    assert v["cleaned_orders"].verdict == "CONFIRMED" and v["raw_fx_rates"].verdict == "DENIED"
    assert blame_recency(suspects) == "raw_fx_rates"
    # B2 is NOT fooled here (cleaned_orders is closer to the anomaly): reported as it is, not hidden
    assert blame_distance(suspects) == "cleaned_orders"


def test_s3_fault_is_latest_so_replay_and_both_baselines_agree(runs, settings):
    suspects, v = investigate(runs["s3_type_coercion_latest"], settings)
    assert v["raw_orders"].verdict == "CONFIRMED" and v["raw_fx_rates"].verdict == "DENIED"
    assert top_suspect(list(v.values())) == blame_recency(suspects) == blame_distance(suspects) == "raw_orders"


def test_s4_control_starts_no_investigation(runs, settings):
    suspects, verdicts = investigate(runs["s4_control_no_fault"], settings)
    assert suspects == [] and verdicts == {}


def test_boundary_scenarios_run_and_give_valid_verdicts(runs, settings):
    """s5 and s6: no outcome is asserted on purpose, whatever happens is reported in build_logs.md."""
    for sid in ("s5_two_causes", "s6_nondeterministic_transform"):
        suspects, v = investigate(runs[sid], settings)
        assert suspects and all(x.verdict in {"CONFIRMED", "DENIED", "PARTIAL", "INCONCLUSIVE"} for x in v.values())
        assert all(x.explanation and x.suspect_snapshot_id >= 0 for x in v.values())


# ---- design guarantees ------------------------------------------------------------------------------------------------
def test_replay_pins_every_other_input_and_never_reads_the_latest_version(runs, settings, monkeypatch):
    ctx = runs["s1_bad_join_key"].context
    decoy = {s.table: s for s in shortlist(ctx, settings.replay)}["raw_fx_rates"]
    calls, original = [], ctx.store.read

    def spy(table, version=None):
        calls.append((table, version))
        return original(table, version)

    monkeypatch.setattr(ctx.store, "read", spy)
    rerun_once(ctx, decoy)
    pinned = ctx.lineage.last_run_of("cleaned_orders").inputs
    assert ("raw_fx_rates", decoy.pre_change_snapshot_id) in calls            # the suspect: BEFORE its change
    assert ("raw_customers", pinned["raw_customers"]) in calls                # pinned to what the anomalous run read
    assert ("raw_orders", pinned["raw_orders"]) in calls
    assert all(version is not None for _, version in calls)                   # nothing is read "as of now"
    assert pinned["raw_customers"] != 0                                       # the pinned customers are the BAD version


def test_investigators_work_when_ground_truth_is_deleted(runs, settings):
    run = copy.copy(runs["s1_bad_join_key"])
    del run.truth
    _, v = investigate(run, settings)
    assert v["raw_customers"].verdict == "CONFIRMED"

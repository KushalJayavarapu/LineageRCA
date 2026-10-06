import json

from agents.replay import replay_all
from agents.shortlist import shortlist
from core.models import ReplayVerdict
from metrics.scoring import (
    DEMO_SEED,
    IncidentResult,
    group_of,
    score_incident,
    top1_correct,
)
from metrics.summary import summarize, summarize_group, write_summary_csv
from runners.console import render_summary
from runners.run_all import run_many, save_results
from runners.run_scenario import run_scenario


def make_result(**kw) -> IncidentResult:
    base = {
        "scenario_id": "s1", "seed": 1, "group": "heldout_main", "boundary": False, "true_causes": ["a"],
        "decoy_tables": ["d"], "expect_alarm": True, "alarm_raised": True, "anomaly_table": "t", "anomaly_metric": "m",
        "anomaly_deviation": -0.3, "healthy_day_false_alarms": 0, "suspects": ["a", "d"], "verdicts": [],
        "replay_top1": "a", "b1_blame": "d", "b2_blame": "a", "replay_correct": True, "b1_correct": False,
        "b2_correct": True, "n_replays": 6, "replay_seconds": 1.0, "config_hash": "x",
    }
    return IncidentResult(**{**base, **kw})


def verdict(table, kind):
    return ReplayVerdict(incident_id="i", suspect_table=table, suspect_snapshot_id=0, replay_runs=3,
                         anomaly_cleared=kind == "CONFIRMED", verdict=kind, compute_seconds=0.0, deviation_before=-0.3,
                         deviation_after=0.0, explanation="")


def test_groups_keep_demo_seed_and_held_out_seeds_apart():
    assert group_of(DEMO_SEED, False) == "seed42_main" and group_of(DEMO_SEED, True) == "seed42_boundary"
    assert group_of(3, False) == "heldout_main" and group_of(3, True) == "heldout_boundary"


def test_top1_rules_including_control_and_abstaining():
    assert top1_correct("a", ["a", "b"]) and not top1_correct("d", ["a"])
    assert not top1_correct(None, ["a"])                  # a method that blames nobody is wrong when there is a cause
    assert top1_correct(None, []) and not top1_correct("a", [])


def test_summary_counts_precision_false_confirms_and_control_alarms():
    good = make_result(verdicts=[verdict("a", "CONFIRMED"), verdict("d", "DENIED")])
    bad = make_result(verdicts=[verdict("a", "CONFIRMED"), verdict("d", "CONFIRMED")], replay_correct=False)
    missed = make_result(alarm_raised=False, suspects=[], verdicts=[])
    control = make_result(true_causes=[], alarm_raised=True, suspects=[], verdicts=[])
    row = summarize_group("heldout_main", [good, bad, missed, control])
    assert (row["faulty"], row["detected"], row["investigated"]) == (3, 2, 2)
    assert row["top1_replay_n"] == 1 and row["top1_b1_n"] == 0 and row["top1_b2_n"] == 2
    assert (row["false_confirms"], row["non_cause_suspects"]) == (1, 2)
    assert row["replay_precision"] == 2 / 3 and row["replay_recall"] == 1.0
    assert row["control_false_alarms"] == 1 and row["control_incidents"] == 1


def test_summarize_never_pools_groups_and_csv_is_written(tmp_path):
    rows = summarize([make_result(), make_result(seed=42, group="seed42_main")])
    assert [r["group"] for r in rows] == ["seed42_main", "heldout_main"]
    write_summary_csv(rows, tmp_path / "summary.csv")
    text = (tmp_path / "summary.csv").read_text(encoding="utf-8")
    assert "source" in text.splitlines()[0] and "synthetic" in text
    assert "SYNTHETIC" in render_summary(rows).title


def test_score_incident_labels_ground_truth_and_counts_replays(runs, settings):
    run = runs["s1_bad_join_key"]
    suspects = shortlist(run.context, settings.replay)
    result = score_incident(run.truth, run.context, suspects, replay_all(run.context, suspects, settings.replay),
                            settings.replay.replay_repeats, 42, "abc")
    assert result.group == "seed42_main" and result.replay_correct and not result.b1_correct
    assert result.n_replays == 2 * settings.replay.replay_repeats and result.healthy_day_false_alarms == 0
    assert {v.ground_truth_cause for v in result.verdicts} == {"raw_customers"} and result.source == "synthetic"


def test_run_scenario_and_run_many_write_results(settings, tmp_path):
    small = settings.model_copy(update={"pipeline": settings.pipeline.model_copy(update={"orders_per_day": 300}),
                                        "results_dir": tmp_path / "results"})
    outcome = run_scenario("s4_control_no_fault", 7, small)
    assert outcome.result.verdicts == [] and outcome.result.replay_correct       # control: nobody blamed = right
    results = run_many(small, [7], ["s1_bad_join_key", "s4_control_no_fault"])
    assert [r.scenario_id for r in results] == ["s1_bad_join_key", "s4_control_no_fault"]
    assert not (small.warehouse_dir / "s1_bad_join_key_seed7").exists()          # cleaned up after scoring
    save_results(small, results)
    rows = [json.loads(line) for line in (small.results_dir / "incidents.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and all(r["source"] == "synthetic" and r["config_hash"] for r in rows)
    assert (small.results_dir / "summary.csv").is_file()

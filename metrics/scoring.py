"""Scoring of ONE incident. This is the only module that reads the ground truth.

IncidentResult is one row of results/incidents.jsonl: what the monitor did, what each method blamed, and whether it was right.
"""
from __future__ import annotations

from pydantic import BaseModel

from agents.baselines import blame_distance, blame_recency
from agents.replay import top_suspect
from agents.shortlist import Suspect
from core.models import ReplayVerdict
from drift.monitor import day_metrics
from tasks.scenarios import GroundTruth, IncidentContext

HELDOUT_SEEDS = (1, 2, 3, 4, 5)       # reported separately from the demo seed 42
DEMO_SEED = 42


class IncidentResult(BaseModel):
    scenario_id: str
    seed: int
    group: str                         # seed42_main, seed42_boundary, heldout_main or heldout_boundary
    boundary: bool
    true_causes: list[str]
    decoy_tables: list[str]
    expect_alarm: bool
    alarm_raised: bool
    anomaly_table: str | None
    anomaly_metric: str | None
    anomaly_deviation: float | None
    healthy_day_false_alarms: int      # monitor alarms on healthy days 4..10 of this run
    suspects: list[str]
    verdicts: list[ReplayVerdict]
    replay_top1: str | None
    b1_blame: str | None
    b2_blame: str | None
    replay_correct: bool
    b1_correct: bool
    b2_correct: bool
    n_replays: int                     # suspects x repeats
    replay_seconds: float
    config_hash: str
    source: str = "synthetic"


def group_of(seed: int, boundary: bool) -> str:
    return f"{'seed42' if seed == DEMO_SEED else 'heldout'}_{'boundary' if boundary else 'main'}"


def top1_correct(blamed: str | None, true_causes: list[str]) -> bool:
    """A method is right if it blames a true cause. With no fault (control) the right answer is to blame nobody."""
    return blamed is None if not true_causes else blamed in true_causes


def count_healthy_false_alarms(context: IncidentContext) -> int:
    """Alarms the monitor raises on the healthy days 4..(incident day - 1). The history is never touched by faults."""
    metrics = day_metrics(context.store.read("cleaned_orders"), context.store.read("daily_revenue_agg"))
    return sum(len(context.monitor.evaluate(metrics, d, 0)) for d in range(4, context.day))


def score_incident(truth: GroundTruth, context: IncidentContext, suspects: list[Suspect],
                   verdicts: list[ReplayVerdict], repeats: int, seed: int, cfg_hash: str) -> IncidentResult:
    labelled = [v.model_copy(update={"ground_truth_cause": ",".join(truth.true_causes) or "none"}) for v in verdicts]
    replay, b1, b2 = top_suspect(verdicts), blame_recency(suspects), blame_distance(suspects)
    anomaly = context.anomaly
    return IncidentResult(
        scenario_id=truth.scenario_id, seed=seed, group=group_of(seed, truth.boundary), boundary=truth.boundary,
        true_causes=truth.true_causes, decoy_tables=truth.decoy_tables, expect_alarm=truth.expect_alarm,
        alarm_raised=anomaly is not None, anomaly_table=anomaly.table if anomaly else None,
        anomaly_metric=anomaly.metric if anomaly else None, anomaly_deviation=anomaly.deviation if anomaly else None,
        healthy_day_false_alarms=count_healthy_false_alarms(context), suspects=[s.table for s in suspects],
        verdicts=labelled, replay_top1=replay, b1_blame=b1, b2_blame=b2,
        replay_correct=top1_correct(replay, truth.true_causes), b1_correct=top1_correct(b1, truth.true_causes),
        b2_correct=top1_correct(b2, truth.true_causes), n_replays=len(suspects) * repeats,
        replay_seconds=sum(v.compute_seconds for v in verdicts), config_hash=cfg_hash)

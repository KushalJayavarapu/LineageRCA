"""The replay harness (our contribution): a COUNTERFACTUAL test of each suspect.

For a suspect S: read S at its pre-change snapshot, read EVERY other input at the snapshot the anomalous run used,
re-run the stages on the path from S to the anomalous table with the SAME code versions the anomalous run used, and
check whether the metric that alarmed is back inside the monitor's threshold. Repeat a few times to expose randomness.
It never reads ground truth.

Verdicts:  CONFIRMED  the anomaly is gone                       DENIED        the anomaly stays (barely reduced)
           PARTIAL    not gone, but reduced by a good share      INCONCLUSIVE  the repeats disagree (not deterministic)
CONFIRMED means "undoing THIS table's change clears the metric". It does not prove that no other table is also guilty.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from statistics import mean

import pyarrow as pa

from agents.shortlist import Suspect
from core.config import ReplayConfig
from core.models import ReplayVerdict, Verdict
from drift.monitor import Monitor, day_metrics, metric_from_table
from tasks import stages
from tasks.scenarios import IncidentContext

# transform_id -> how to run that stage from a dict of its input tables
STAGE_RUNNERS: dict[str, Callable[[dict[str, pa.Table], int, str], pa.Table]] = {
    "clean": lambda t, day, cv: stages.clean(t["raw_orders"], t["raw_customers"], t["raw_fx_rates"], day, cv),
    "aggregate": lambda t, day, cv: stages.aggregate(t["cleaned_orders"], day, cv),
}


def rerun_once(context: IncidentContext, suspect: Suspect) -> pa.Table:
    """One replay: returns the replayed version of the anomalous table (only day D's rows are recomputed)."""
    store, lineage, day, target = context.store, context.lineage, context.day, context.anomaly.table
    tables = {suspect.table: store.read(suspect.table, suspect.pre_change_snapshot_id)}   # the suspect, BEFORE its change
    for stage_table in lineage.path_stages(suspect.table, target):
        run = lineage.last_run_of(stage_table)                                             # the anomalous run of this stage
        inputs = {name: tables[name] if name in tables else store.read(name, snap)         # everything else is PINNED
                  for name, snap in run.inputs.items()}
        tables[stage_table] = STAGE_RUNNERS[run.transform_id](inputs, day, run.code_version)   # same code as that run
    return tables[target]


def decide_verdict(before: float, afters: list[float], metric: str, monitor: Monitor,
                   cfg: ReplayConfig) -> tuple[Verdict, str]:
    """Turn the deviations (before the replay, and after each repeat) into a verdict plus the reason in words."""
    spread = max(afters) - min(afters)
    after = mean(afters)
    reduction = (abs(before) - abs(after)) / abs(before) if before else 0.0
    facts = (f"{metric} deviation {before:+.3f} before, {after:+.3f} after replay "
             f"(mean of {len(afters)} runs, spread {spread:.3f})")
    if spread > cfg.instability_tolerance:
        return "INCONCLUSIVE", f"{facts}: the repeats differ by more than {cfg.instability_tolerance}, so replay cannot be trusted"
    if not monitor.is_alarm(metric, after):
        return "CONFIRMED", f"{facts}: back inside the monitor threshold, so the anomaly is gone"
    if reduction >= cfg.partial_min_reduction:
        return "PARTIAL", f"{facts}: still alarming but reduced by {reduction:.0%} (at least {cfg.partial_min_reduction:.0%})"
    return "DENIED", f"{facts}: still alarming, reduced by only {reduction:.0%}"


def measure(context: IncidentContext, produce: Callable[[], pa.Table], cfg: ReplayConfig) -> tuple[list[float], float]:
    """Run `produce` (one re-execution that returns the anomalous table) `replay_repeats` times and return, for each run,
    the deviation of the alarming metric against the monitor's baseline, plus the seconds spent. Shared by replay and by
    the parameter-replay baseline so both are judged in exactly the same way."""
    anomaly, monitor = context.anomaly, context.monitor
    baseline = day_metrics(context.store.read("cleaned_orders"), context.store.read("daily_revenue_agg"))
    started = time.perf_counter()
    afters = []
    for _ in range(cfg.replay_repeats):
        value = metric_from_table(anomaly.metric, produce(), context.day)
        baseline[anomaly.metric][context.day] = value            # swap day D's value; the history days stay as they were
        afters.append(monitor.deviation(baseline, anomaly.metric, context.day))
    return afters, time.perf_counter() - started                 # seconds are reported only; they never influence a verdict


def replay_suspect(context: IncidentContext, suspect: Suspect, cfg: ReplayConfig) -> ReplayVerdict:
    anomaly, monitor = context.anomaly, context.monitor
    afters, seconds = measure(context, lambda: rerun_once(context, suspect), cfg)
    verdict, why = decide_verdict(anomaly.deviation, afters, anomaly.metric, monitor, cfg)
    return ReplayVerdict(
        incident_id=anomaly.incident_id, suspect_table=suspect.table, suspect_snapshot_id=suspect.pre_change_snapshot_id,
        replay_runs=cfg.replay_repeats, anomaly_cleared=verdict == "CONFIRMED", verdict=verdict,
        compute_seconds=seconds, deviation_before=anomaly.deviation, deviation_after=mean(afters),
        explanation=f"{suspect.table} at snapshot {suspect.pre_change_snapshot_id}: {why}")


def replay_all(context: IncidentContext, suspects: list[Suspect], cfg: ReplayConfig) -> list[ReplayVerdict]:
    return [replay_suspect(context, s, cfg) for s in suspects]


def top_suspect(verdicts: list[ReplayVerdict]) -> str | None:
    """The single table replay blames: CONFIRMED first, then PARTIAL; within a group the biggest deviation reduction wins
    (ties: smallest remaining deviation, then table name). None if replay found nothing (all DENIED or INCONCLUSIVE)."""
    rank = {"CONFIRMED": 0, "PARTIAL": 1}
    pool = [v for v in verdicts if v.verdict in rank]
    if not pool:
        return None
    best = min(pool, key=lambda v: (rank[v.verdict], -(abs(v.deviation_before) - abs(v.deviation_after)),
                                    abs(v.deviation_after), v.suspect_table))
    return best.suspect_table

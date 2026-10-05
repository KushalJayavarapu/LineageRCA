"""Builds one SYNTHETIC incident end to end and hands back two SEPARATE things:

  IncidentContext  what an investigator may see: the Delta store, the lineage, the anomaly. No ground truth.
  GroundTruth      the injected cause(s) and decoys. Only metrics/ reads it, to score verdicts.

Timeline of every scenario:  days 1-10 healthy -> day 11 load -> healthy day-11 run -> change commits (faults, decoy)
-> the pipeline re-runs day 11 with the deployed code (the ANOMALOUS run) -> the monitor checks day 11.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from adapters.delta_store import DeltaStore
from adapters.lineage_store import LineageStore
from core.config import ScenarioSpec, Settings
from core.models import Anomaly
from drift.monitor import Monitor, primary_anomaly
from run_logging.jsonl import RunLog
from tasks import faults
from tasks.datagen import DataGenerator
from tasks.pipeline import Pipeline


@dataclass
class IncidentContext:
    scenario_id: str
    seed: int
    day: int
    store: DeltaStore
    lineage: LineageStore
    monitor: Monitor
    anomalies: list[Anomaly]
    anomaly: Anomaly | None       # the anomaly the investigation starts from (None = monitor silent)
    healthy_until: int            # logical time of the last healthy run; suspects must have changed after it


@dataclass
class GroundTruth:
    scenario_id: str
    true_causes: list[str]
    decoy_tables: list[str]
    expect_alarm: bool
    boundary: bool


@dataclass
class ScenarioRun:
    context: IncidentContext
    truth: GroundTruth


def build_scenario(scenario_id: str, seed: int, settings: Settings, log_dir: Path | None = None) -> ScenarioRun:
    spec: ScenarioSpec = settings.scenarios.scenarios[scenario_id]
    sc, day = settings.scenarios, settings.scenarios.incident_day
    log = RunLog(None if log_dir is None else log_dir / f"{scenario_id}_seed{seed}.jsonl")

    store = DeltaStore(settings.warehouse_dir / f"{scenario_id}_seed{seed}", settings.warehouse_dir)
    store.reset()
    pipe = Pipeline(store, DataGenerator(settings.pipeline, seed))
    for d in range(1, day):                                    # healthy history
        pipe.run_day(d)
    pipe.load_day(day)                                         # incident day: load, then one HEALTHY run
    pipe.run_clean(day)
    pipe.run_aggregate(day)
    healthy_until = store.clock.now
    log.event("healthy_history_done", day=day, healthy_until=healthy_until)

    for step in spec.steps:                                    # change commits: faults and the decoy
        if step == "bad_join_key":
            snap = faults.bad_join_key(store, seed, sc.bad_join_key_fraction)
        elif step == "type_coercion":
            snap = faults.type_coercion(store, seed, day, sc.type_coercion_fraction)
        elif step == "decoy":
            snap = faults.benign_fx_refresh(store, day, sc.decoy_pct)
        elif step == "dropped_filter":                         # a code fault: re-run clean with the filter removed
            run = pipe.run_clean(day, "clean_v2_no_filter", change_type="dropped_filter")
            snap = next(s for s in store.snapshots if s.table_name == run.output_table
                        and s.snapshot_id == run.output_snapshot_id)
        else:
            raise ValueError(f"unknown scenario step: {step}")
        log.event("change_commit", step=step, table=snap.table_name, snapshot_id=snap.snapshot_id,
                  change_type=snap.change_type, committed_at=snap.committed_at)

    clean_run = pipe.run_clean(day, spec.deployed_clean)        # the anomalous run, with the deployed code
    agg_run = pipe.run_aggregate(day, spec.deployed_aggregate)
    log.event("anomalous_run", clean_inputs=clean_run.inputs, clean_code=clean_run.code_version,
              aggregate_inputs=agg_run.inputs, aggregate_code=agg_run.code_version)

    lineage = LineageStore(store.snapshots)
    lineage.add_runs(pipe.runs)
    monitor = Monitor(settings.monitor)
    anomalies = monitor.check_store(store, day)
    for a in anomalies:
        log.event("anomaly", **a.model_dump())
    if not anomalies:
        log.event("monitor_silent", day=day)

    context = IncidentContext(scenario_id, seed, day, store, lineage, monitor, anomalies,
                              primary_anomaly(anomalies), healthy_until)
    truth = GroundTruth(scenario_id, list(spec.true_causes), list(spec.decoy_tables), spec.expect_alarm, spec.boundary)
    return ScenarioRun(context, truth)

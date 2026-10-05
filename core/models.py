"""Plain data records. They mirror the three tables in the proposal; fields marked (extension) are ours."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Verdict = Literal["CONFIRMED", "DENIED", "PARTIAL", "INCONCLUSIVE"]


class SnapshotRecord(BaseModel):
    """One row per table snapshot (= one Delta version)."""

    snapshot_id: int            # Delta version number
    table_name: str
    committed_at: int           # LOGICAL clock tick, never the wall clock
    change_type: str            # normal_load, benign_refresh, or the name of an injected fault
    row_count: int
    metric_value: float | None = None
    source: str = "synthetic"


class LineageEdge(BaseModel):
    """One row per lineage edge emitted by a pipeline run."""

    upstream_table: str
    downstream_table: str
    transform_id: str
    run_id: str
    lineage_source: str = "hand_built_json"
    upstream_snapshot_id: int   # (extension) which version of the upstream table this run read
    source: str = "synthetic"


class RunRecord(BaseModel):
    """(extension) One pipeline run: what it read and wrote. Replay needs this to pin inputs and code."""

    run_id: str
    transform_id: str
    code_version: str           # (extension) which version of the stage code ran
    inputs: dict[str, int]      # table -> snapshot id that was read
    output_table: str
    output_snapshot_id: int
    logical_time: int
    day: int


class Anomaly(BaseModel):
    """What the monitor reports when a metric leaves its normal range."""

    incident_id: str
    table: str
    metric: str
    observed: float
    expected: float
    deviation: float            # relative (or absolute for null rates)
    logical_time: int
    day: int


class ReplayVerdict(BaseModel):
    """One row per replay verdict. ground_truth_cause is filled by metrics/ for scoring only."""

    incident_id: str
    suspect_table: str
    suspect_snapshot_id: int    # the PRE-change snapshot used for the replay
    replay_runs: int
    anomaly_cleared: bool
    verdict: Verdict
    ground_truth_cause: str | None = None
    compute_seconds: float
    deviation_before: float     # (extension)
    deviation_after: float      # (extension)
    explanation: str            # (extension) WHY, with numbers
    source: str = "synthetic"

"""Step 1 of every investigator: shortlist the suspects.

A suspect is a table that (a) feeds the anomalous table, or IS the anomalous table, and (b) had a CHANGE commit
(anything except a normal daily load) after the last healthy run, within the last `shortlist_window_commits` commits.
Ground truth is never used here.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.config import ReplayConfig
from core.models import SnapshotRecord
from tasks.scenarios import IncidentContext


@dataclass
class Suspect:
    table: str
    first_change: SnapshotRecord      # earliest change commit in the window
    last_change: SnapshotRecord       # latest change commit in the window (what the recency baseline looks at)
    pre_change_snapshot_id: int       # the version just BEFORE the first change commit: the "healthy" snapshot
    distance: int                     # graph distance to the anomalous table (0 = it is the anomalous table)


def shortlist(context: IncidentContext, cfg: ReplayConfig) -> list[Suspect]:
    """Suspects for the incident, in table-name order. Empty if the monitor raised no anomaly."""
    anomaly = context.anomaly
    if anomaly is None:
        return []
    lineage = context.lineage
    distance = {anomaly.table: 0, **lineage.distances_upstream(anomaly.table)}
    window_start = max(context.healthy_until, anomaly.logical_time - cfg.shortlist_window_commits)
    suspects = []
    for table in sorted(distance):
        changes = [s for s in lineage.changes_since(table, window_start) if s.change_type != "normal_load"]
        if changes and changes[0].snapshot_id > 0:
            suspects.append(Suspect(table, changes[0], changes[-1], changes[0].snapshot_id - 1, distance[table]))
    return suspects

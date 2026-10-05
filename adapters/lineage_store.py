"""Lineage store: who feeds whom, and which snapshot of each input every run read.

Hand-built JSON lineage in OpenLineage-style events (the proposal allows this instead of Marquez).
It is built from the RunRecords of the pipeline plus the snapshot records of the Delta store.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.models import LineageEdge, RunRecord, SnapshotRecord


class LineageStore:
    def __init__(self, snapshots: list[SnapshotRecord]) -> None:
        self.snapshots = snapshots              # live list owned by the DeltaStore (same objects, no copy)
        self.runs: dict[str, RunRecord] = {}

    def add_runs(self, runs: list[RunRecord]) -> None:
        for run in runs:
            self.runs[run.run_id] = run

    # ---- the graph --------------------------------------------------------------------------------------------
    def graph(self) -> dict[str, set[str]]:
        """downstream table -> set of tables that feed it directly."""
        feeds: dict[str, set[str]] = {}
        for run in self.runs.values():
            feeds.setdefault(run.output_table, set()).update(run.inputs)
        return feeds

    def distances_upstream(self, table: str) -> dict[str, int]:
        """Every table that (transitively) feeds `table`, with its graph distance (1 = direct input)."""
        feeds, dist, frontier, step = self.graph(), {}, [table], 0
        while frontier:
            step += 1
            nxt = []
            for node in frontier:
                for up in sorted(feeds.get(node, ())):
                    if up not in dist:
                        dist[up] = step
                        nxt.append(up)
            frontier = nxt
        return dist

    def upstream_of(self, table: str) -> list[str]:
        """Transitive upstream tables, closest first (ties in alphabetical order)."""
        dist = self.distances_upstream(table)
        return sorted(dist, key=lambda t: (dist[t], t))

    def path_stages(self, suspect: str, target: str) -> list[str]:
        """Tables to re-materialise when `suspect` is replayed: the derived tables on the way from suspect to target, in order."""
        feeds = self.graph()

        def walk(node: str) -> list[list[str]]:   # all paths from `suspect` up to `node` (as lists of tables)
            if node == suspect:
                return [[suspect]]
            return [p + [node] for up in sorted(feeds.get(node, ())) for p in walk(up)]

        paths = walk(target)
        if not paths:
            return []
        longest = max(paths, key=len)
        return longest[1:]                         # drop the suspect itself

    # ---- queries used by the investigators --------------------------------------------------------------------
    def changes_since(self, table: str, logical_time: int) -> list[SnapshotRecord]:
        """Snapshots of `table` committed strictly after `logical_time` (oldest first)."""
        return [s for s in self.snapshots if s.table_name == table and s.committed_at > logical_time]

    def inputs_of_run(self, run_id: str) -> dict[str, int]:
        """Which snapshot of each input table this run read."""
        return dict(self.runs[run_id].inputs)

    def last_run_of(self, table: str) -> RunRecord | None:
        """The most recent run that wrote `table`."""
        candidates = [r for r in self.runs.values() if r.output_table == table]
        return max(candidates, key=lambda r: r.logical_time, default=None)

    # ---- export (proposal table 2: one row per lineage edge) --------------------------------------------------
    def edges(self) -> list[LineageEdge]:
        return [LineageEdge(upstream_table=up, downstream_table=r.output_table, transform_id=r.transform_id,
                            run_id=r.run_id, upstream_snapshot_id=snap)
                for r in sorted(self.runs.values(), key=lambda r: r.run_id) for up, snap in sorted(r.inputs.items())]

    def events(self) -> list[dict]:
        """OpenLineage-style COMPLETE events, one per run (logical time, never wall-clock)."""
        return [{"eventType": "COMPLETE", "logicalTime": r.logical_time, "run": {"runId": r.run_id},
                 "job": {"name": r.transform_id, "codeVersion": r.code_version},
                 "inputs": [{"name": t, "snapshotId": v} for t, v in sorted(r.inputs.items())],
                 "outputs": [{"name": r.output_table, "snapshotId": r.output_snapshot_id}], "source": "synthetic"}
                for r in sorted(self.runs.values(), key=lambda r: r.run_id)]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(e, sort_keys=True) for e in self.events()) + "\n", encoding="utf-8")

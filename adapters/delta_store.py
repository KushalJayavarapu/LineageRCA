"""Delta snapshot store: write tables, read any old version (time travel), list the history.

Every commit is one Delta version (= one snapshot). We also keep our own LOGICAL commit time per snapshot, because
Delta's real commit times are wall-clock and would differ between runs.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from core.clock import LogicalClock
from core.config import check_warehouse_dir
from core.models import SnapshotRecord


class DeltaStore:
    """A folder of Delta tables plus a list of SnapshotRecords describing every commit."""

    def __init__(self, root: Path, warehouse_dir: Path, clock: LogicalClock | None = None) -> None:
        self.root = Path(root)
        self.warehouse_dir = check_warehouse_dir(Path(warehouse_dir))
        self.clock = clock or LogicalClock()
        self.snapshots: list[SnapshotRecord] = []

    def reset(self) -> None:
        """Delete and recreate this store's folder. Only allowed strictly INSIDE the warehouse directory."""
        root, wh = self.root.resolve(), self.warehouse_dir.resolve()
        if wh not in root.parents:
            raise ValueError(f"refusing to delete {root}: not inside the warehouse {wh}")
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        self.snapshots = []

    def _path(self, table: str) -> str:
        return str(self.root / table)  # Windows-safe: a plain string path

    def write(self, table: str, data: pa.Table, mode: str, change_type: str,
              metric_value: float | None = None, replace_where: str | None = None) -> SnapshotRecord:
        """Commit `data` as a new version. mode is 'overwrite' or 'append'. Returns the snapshot record.

        replace_where (a SQL condition such as "order_date = '2026-01-11'") replaces ONLY the matching rows, so one
        day can be re-materialised without touching the other days.
        """
        if replace_where and DeltaTable.is_deltatable(self._path(table)):
            write_deltalake(self._path(table), data, mode="overwrite", predicate=replace_where)
        else:
            write_deltalake(self._path(table), data, mode=mode)
        version = self.latest_version(table)
        row_count = self.read(table, version).num_rows
        record = SnapshotRecord(snapshot_id=version, table_name=table, committed_at=self.clock.tick(),
                                change_type=change_type, row_count=row_count, metric_value=metric_value)
        self.snapshots.append(record)
        return record

    def read(self, table: str, version: int | None = None) -> pa.Table:
        """Read the table as of `version` (time travel), or the latest version if None."""
        dt = DeltaTable(self._path(table)) if version is None else DeltaTable(self._path(table), version=version)
        return dt.to_pyarrow_table()

    def latest_version(self, table: str) -> int:
        return DeltaTable(self._path(table)).version()

    def history(self, table: str) -> list[SnapshotRecord]:
        """All snapshots of one table, oldest first."""
        return [s for s in self.snapshots if s.table_name == table]

import pyarrow as pa
import pytest

from adapters.delta_store import DeltaStore
from adapters.duck import query
from core.hashing import table_hash


@pytest.fixture()
def store(tmp_path):
    wh = tmp_path / "lineagerca_warehouse"
    s = DeltaStore(wh / "t", wh)
    s.reset()
    return s


def test_time_travel_returns_exactly_the_rows_of_that_version(store):
    v0 = store.write("t", pa.table({"k": [1, 2, 3]}), "overwrite", "normal_load")
    v1 = store.write("t", pa.table({"k": [4, 5]}), "append", "normal_load")
    v2 = store.write("t", pa.table({"k": [9]}), "overwrite", "some_fault")
    assert [v0.snapshot_id, v1.snapshot_id, v2.snapshot_id] == [0, 1, 2]
    assert sorted(store.read("t", 0)["k"].to_pylist()) == [1, 2, 3]
    assert sorted(store.read("t", 1)["k"].to_pylist()) == [1, 2, 3, 4, 5]
    assert store.read("t")["k"].to_pylist() == [9]


def test_old_version_hash_is_stable_after_later_commits(store):
    store.write("t", pa.table({"k": [1, 2]}), "overwrite", "normal_load")
    before = table_hash(store.read("t", 0))
    store.write("t", pa.table({"k": [7]}), "overwrite", "fault")
    assert table_hash(store.read("t", 0)) == before


def test_history_uses_logical_clock_and_records_change_type(store):
    store.write("t", pa.table({"k": [1]}), "overwrite", "normal_load")
    store.write("t", pa.table({"k": [2]}), "overwrite", "benign_refresh")
    hist = store.history("t")
    assert [h.committed_at for h in hist] == [1, 2]
    assert [h.change_type for h in hist] == ["normal_load", "benign_refresh"]
    assert hist[1].row_count == 1 and hist[0].source == "synthetic"


def test_duckdb_query_over_old_snapshot(store):
    store.write("t", pa.table({"v": [10.0, 20.0]}), "overwrite", "normal_load")
    store.write("t", pa.table({"v": [10.0, 20.0, 30.0]}), "overwrite", "normal_load")
    old = store.read("t", 0)
    assert query("select sum(v) as s from old", old=old)["s"][0].as_py() == 30.0


def test_reset_refuses_folders_outside_the_warehouse(tmp_path):
    wh = tmp_path / "lineagerca_warehouse"
    outside = DeltaStore(tmp_path / "other", wh)
    with pytest.raises(ValueError):
        outside.reset()

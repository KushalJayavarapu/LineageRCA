import pyarrow as pa
import pytest

from core.clock import LogicalClock
from core.config import check_warehouse_dir, load_settings
from core.hashing import table_hash
from core.rng import make_rng


def test_clock_is_logical_and_starts_at_zero():
    clock = LogicalClock()
    assert clock.now == 0
    assert [clock.tick(), clock.tick()] == [1, 2]


def test_rng_same_seed_same_numbers_and_streams_differ():
    assert make_rng(42, "a").random() == make_rng(42, "a").random()
    assert make_rng(42, "a").random() != make_rng(42, "b").random()
    assert make_rng(42).random() != make_rng(1).random()


def test_hash_ignores_row_order_but_sees_changes():
    a = pa.table({"k": [1, 2, 3], "v": ["x", "y", "z"]})
    b = pa.table({"k": [3, 1, 2], "v": ["z", "x", "y"]})
    c = pa.table({"k": [1, 2, 3], "v": ["x", "y", "Q"]})
    assert table_hash(a) == table_hash(b)
    assert table_hash(a) != table_hash(c)


def test_settings_load_and_warehouse_name_rule(tmp_path):
    s = load_settings()
    assert s.pipeline.healthy_days == 10 and s.monitor.rel_threshold == 0.15 and s.replay.replay_repeats == 3
    assert s.warehouse_dir.name.endswith("lineagerca_warehouse")
    with pytest.raises(ValueError):
        check_warehouse_dir(tmp_path / "somewhere_else")

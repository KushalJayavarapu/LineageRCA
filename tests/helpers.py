"""Shared test helper: build a small healthy pipeline in a temp warehouse."""
from adapters.delta_store import DeltaStore
from core.config import load_settings
from tasks.datagen import DataGenerator
from tasks.pipeline import Pipeline


def build(tmp_path, seed: int, days: int = 4, name: str = "a", orders_per_day: int = 300):
    s = load_settings()
    cfg = s.pipeline.model_copy(update={"orders_per_day": orders_per_day})   # small and fast for tests
    wh = tmp_path / "lineagerca_warehouse"
    store = DeltaStore(wh / name, wh)
    store.reset()
    pipe = Pipeline(store, DataGenerator(cfg, seed))
    for day in range(1, days + 1):
        pipe.run_day(day)
    return store, pipe

import pytest

from core.config import load_settings
from tasks.scenarios import build_scenario


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    wh = tmp_path_factory.mktemp("wh") / "lineagerca_warehouse"
    return load_settings().model_copy(update={"warehouse_dir": wh, "results_dir": wh.parent / "results"})


@pytest.fixture(scope="session")
def runs(settings):
    """Every scenario at the demo seed, built once per test session (about 4-5 s each at the configured size)."""
    return {sid: build_scenario(sid, 42, settings, log_dir=settings.results_dir / "runs")
            for sid in settings.scenarios.scenarios}

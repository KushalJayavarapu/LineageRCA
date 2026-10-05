"""Loads the YAML configs in configs/ and applies the .env overrides. All tunables live in those files."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
WAREHOUSE_SUFFIX = "lineagerca_warehouse"  # safety rule: we only ever delete folders under such a directory


class PipelineConfig(BaseModel):
    orders_per_day: int
    healthy_days: int
    n_customers: int
    regions: list[str]
    segments: list[str]
    currencies: list[str]
    products: list[str]


class MonitorConfig(BaseModel):
    rel_threshold: float
    null_rate_threshold: float
    baseline_days: int


class ReplayConfig(BaseModel):
    replay_repeats: int
    partial_min_reduction: float
    instability_tolerance: float
    shortlist_window_commits: int


class ScenarioSpec(BaseModel):
    description: str
    steps: list[str]
    true_causes: list[str]
    decoy_tables: list[str]
    expect_alarm: bool
    deployed_clean: str = "clean_v1"
    deployed_aggregate: str = "aggregate_v1"
    boundary: bool = False


class ScenarioConfig(BaseModel):
    incident_day: int
    decoy_pct: float
    bad_join_key_fraction: float
    type_coercion_fraction: float
    scenarios: dict[str, ScenarioSpec]


class Settings(BaseModel):
    pipeline: PipelineConfig
    monitor: MonitorConfig
    replay: ReplayConfig
    scenarios: ScenarioConfig
    warehouse_dir: Path
    output_dir: Path
    results_dir: Path


def _read_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))


def _override(data: dict, key: str, env_name: str, cast: type) -> None:
    """If the env var is set, it wins over the YAML value."""
    if os.environ.get(env_name):
        data[key] = cast(os.environ[env_name])


def check_warehouse_dir(path: Path) -> Path:
    """Refuse any warehouse folder whose name does not end with 'lineagerca_warehouse'."""
    if not path.name.endswith(WAREHOUSE_SUFFIX):
        raise ValueError(f"WAREHOUSE_DIR must end with '{WAREHOUSE_SUFFIX}', got: {path}")
    return path


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    pipeline, monitor, replay = _read_yaml("pipeline.yaml"), _read_yaml("monitor.yaml"), _read_yaml("replay.yaml")
    _override(pipeline, "orders_per_day", "ORDERS_PER_DAY", int)
    _override(pipeline, "healthy_days", "HEALTHY_DAYS", int)
    _override(monitor, "rel_threshold", "MONITOR_REL_THRESHOLD", float)
    _override(replay, "replay_repeats", "REPLAY_REPEATS", int)
    _override(replay, "partial_min_reduction", "PARTIAL_MIN_REDUCTION", float)
    _override(replay, "instability_tolerance", "INSTABILITY_TOLERANCE", float)
    raw = os.environ.get("WAREHOUSE_DIR") or str(Path.home() / WAREHOUSE_SUFFIX)
    warehouse = check_warehouse_dir(Path(os.path.expandvars(raw)))
    return Settings(
        pipeline=PipelineConfig(**pipeline),
        monitor=MonitorConfig(**monitor),
        replay=ReplayConfig(**replay),
        scenarios=ScenarioConfig(**_read_yaml("scenarios.yaml")),
        warehouse_dir=warehouse,
        output_dir=ROOT / os.environ.get("OUTPUT_DIR", "outputs"),
        results_dir=ROOT / os.environ.get("RESULTS_DIR", "results"),
    )

"""Run ONE scenario with ONE seed: build the incident, investigate it with replay and the baselines, score it.

    python -m runners.run_scenario --scenario s1_bad_join_key --seed 42
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from agents.replay import replay_all
from agents.shortlist import shortlist
from core.config import Settings, config_hash, load_settings
from metrics.scoring import IncidentResult, score_incident
from tasks.scenarios import ScenarioRun, build_scenario


@dataclass
class Outcome:
    result: IncidentResult
    run: ScenarioRun                 # kept so the report can draw the lineage and the snapshots


def run_scenario(scenario_id: str, seed: int, settings: Settings, log_dir: Path | None = None) -> Outcome:
    run = build_scenario(scenario_id, seed, settings, log_dir)
    suspects = shortlist(run.context, settings.replay)               # empty when the monitor stayed silent
    verdicts = replay_all(run.context, suspects, settings.replay)
    result = score_incident(run.truth, run.context, suspects, verdicts, settings.replay.replay_repeats, seed, config_hash())
    return Outcome(result, run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one SYNTHETIC LineageRCA scenario.")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    settings = load_settings()
    result = run_scenario(args.scenario, args.seed, settings, settings.results_dir / "runs").result
    from rich.console import Console  # the CLI may print; library code may not
    out = Console()
    out.print(f"[bold]{result.scenario_id}[/bold] seed {result.seed}  (SYNTHETIC data, real time-travel replay)")
    out.print(f"anomaly: {result.anomaly_table} / {result.anomaly_metric} deviation {result.anomaly_deviation}")
    for v in result.verdicts:
        out.print(f"  {v.suspect_table:15s} {v.verdict:12s} {v.explanation}")
    out.print(f"replay top-1: {result.replay_top1} | B1 recency: {result.b1_blame} | B2 distance: {result.b2_blame}")
    out.print(f"truth (scoring only): {result.true_causes or 'none'}  -> correct: replay {result.replay_correct}, "
              f"B1 {result.b1_correct}, B2 {result.b2_correct}")


if __name__ == "__main__":
    main()

"""Run every scenario for the demo seed 42 and the held-out seeds 1-5, then write results/ and print the summary.

    python -m runners.run_all                 # seed 42 + held-out seeds 1-5 (about 3 minutes)
    python -m runners.run_all --seeds 42      # demo seed only
Thresholds live in configs/ and are never changed here. Each result stores a hash of those files.
"""
from __future__ import annotations

import argparse

from core.config import Settings, load_settings
from metrics.scoring import DEMO_SEED, HELDOUT_SEEDS, IncidentResult
from metrics.summary import summarize, write_summary_csv
from runners.console import render_summary
from runners.run_scenario import run_scenario


def run_many(settings: Settings, seeds: list[int], scenario_ids: list[str] | None = None,
             cleanup: bool = True) -> list[IncidentResult]:
    """Every scenario for every seed. Delta folders are deleted after scoring (they are rebuilt from the seed)."""
    results = []
    for seed in seeds:
        for scenario_id in scenario_ids or list(settings.scenarios.scenarios):
            outcome = run_scenario(scenario_id, seed, settings)
            results.append(outcome.result)
            if cleanup:
                outcome.run.context.store.remove()
    return results


def save_results(settings: Settings, results: list[IncidentResult]) -> None:
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    lines = [r.model_dump_json() for r in results]
    (settings.results_dir / "incidents.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_summary_csv(summarize(results), settings.results_dir / "summary.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all SYNTHETIC LineageRCA scenarios.")
    parser.add_argument("--seeds", type=int, nargs="*", default=[DEMO_SEED, *HELDOUT_SEEDS])
    args = parser.parse_args()
    settings = load_settings()
    results = run_many(settings, args.seeds)
    save_results(settings, results)
    from rich.console import Console
    Console().print(render_summary(summarize(results)))


if __name__ == "__main__":
    main()

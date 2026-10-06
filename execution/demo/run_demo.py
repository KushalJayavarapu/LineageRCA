"""One-command demo (offline):   python demo/run_demo.py

Runs the six SYNTHETIC scenarios for the demo seed 42 live, then writes to outputs/:
  demo_report.html, lineage_<scenario>.png, metric_<scenario>.png, snapshots.csv, lineage_edges.csv, replay_verdicts.csv
The held-out seeds 1-5 take about 3 minutes, so they are read from results/incidents.jsonl (made by `python -m runners.run_all`).
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:                      # lets `python demo/run_demo.py` find core/, tasks/, ...
    sys.path.insert(0, str(ROOT))

from core.config import Settings, config_hash, load_settings
from demo.figures import lineage_figure, metric_figure
from demo.report import render_report
from metrics.scoring import DEMO_SEED, IncidentResult
from metrics.summary import summarize
from runners.console import render_summary
from runners.run_scenario import Outcome, run_scenario

TIME_LIMIT_SECONDS = 120


def load_heldout(settings: Settings) -> tuple[list[IncidentResult] | None, str]:
    """Held-out results from results/incidents.jsonl, plus a note if they are missing or were made with other configs."""
    path = settings.results_dir / "incidents.jsonl"
    if not path.is_file():
        return None, "Held-out results not found. Run `python -m runners.run_all` (about 3 minutes) to create results/incidents.jsonl."
    rows = [IncidentResult.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    heldout = [r for r in rows if r.seed != DEMO_SEED]
    if not heldout:
        return None, "results/incidents.jsonl has no held-out seeds. Run `python -m runners.run_all`."
    stale = {r.config_hash for r in heldout} - {config_hash()}
    note = "WARNING: these held-out results were made with different config files than the current ones." if stale else ""
    return heldout, note


def write_csvs(outcomes: list[Outcome], out_dir: Path, seed: int) -> None:
    """The three tables of the proposal, for all demo scenarios, each row tagged source=synthetic."""
    def dump(name: str, rows: list[dict]) -> None:
        with (out_dir / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    tag = lambda o: {"scenario_id": o.result.scenario_id, "seed": seed}
    dump("snapshots.csv", [{**tag(o), **s.model_dump()} for o in outcomes for s in o.run.context.store.snapshots])
    dump("lineage_edges.csv", [{**tag(o), **e.model_dump()} for o in outcomes for e in o.run.context.lineage.edges()])
    dump("replay_verdicts.csv", [{**tag(o), **v.model_dump()} for o in outcomes for v in o.result.verdicts]
         or [{**tag(o), "source": "synthetic"} for o in outcomes[:1]])


def run_demo(settings: Settings, out_dir: Path | None = None, seed: int = DEMO_SEED) -> float:
    """Build everything; returns the elapsed seconds (for the 120 s check, never used for any decision)."""
    started = time.perf_counter()
    out_dir = out_dir or settings.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    outcomes = [run_scenario(sid, seed, settings, settings.results_dir / "runs") for sid in settings.scenarios.scenarios]
    for o in outcomes:
        name = o.result.scenario_id
        lineage_figure(o, out_dir / f"lineage_{name}.png")
        metric_figure(o, out_dir / f"metric_{name}.png", settings.monitor.rel_threshold, settings.monitor.null_rate_threshold)
    write_csvs(outcomes, out_dir, seed)
    heldout, note = load_heldout(settings)
    descriptions = {sid: spec.description for sid, spec in settings.scenarios.scenarios.items()}
    html = render_report(outcomes, descriptions, out_dir, heldout, note, config_hash(), seed, settings)
    (out_dir / "demo_report.html").write_text(html, encoding="utf-8")

    from rich.console import Console  # the demo may print; library code may not
    console = Console()
    console.print(f"[bold]LineageRCA demo - SYNTHETIC data, real time-travel replay (seed {seed})[/bold]")
    console.print(render_summary(summarize([o.result for o in outcomes] + (heldout or []))))
    if note:
        console.print(f"[yellow]{note}[/yellow]")
    for o in outcomes:
        o.run.context.store.remove()                # the Delta tables are rebuilt from the seed on every run
    elapsed = time.perf_counter() - started
    console.print(f"Report: {out_dir / 'demo_report.html'}")
    console.print(f"Finished in {elapsed:.1f} s (limit {TIME_LIMIT_SECONDS} s).")
    return elapsed


if __name__ == "__main__":
    run_demo(load_settings())

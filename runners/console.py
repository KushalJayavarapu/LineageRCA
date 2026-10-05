"""Console rendering (rich) of the summary rows. Used by run_all and by the demo."""
from __future__ import annotations

from rich.table import Table


def _frac(num: int, den: int) -> str:
    return f"{num}/{den}" if den else "n/a"


def _num(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_summary(rows: list[dict]) -> Table:
    table = Table(title="LineageRCA results (SYNTHETIC data, real time-travel replay) - groups are never pooled")
    for col in ("group", "detected", "top-1 replay", "top-1 B1 recency", "top-1 B2 distance", "false confirms",
                "ctrl false alarms", "replays/incident", "replay s/incident"):
        table.add_column(col)
    for r in rows:
        table.add_row(
            r["group"], _frac(r["detected"], r["faulty"]), _frac(r["top1_replay_n"], r["investigated"]),
            _frac(r["top1_b1_n"], r["investigated"]), _frac(r["top1_b2_n"], r["investigated"]),
            _frac(r["false_confirms"], r["non_cause_suspects"]), _frac(r["control_false_alarms"], r["control_incidents"]),
            _num(r["mean_replays"], 1), _num(r["mean_replay_seconds"], 2))
    return table

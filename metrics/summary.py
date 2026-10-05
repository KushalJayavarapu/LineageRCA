"""Turns a list of IncidentResults into one summary row per group.

Groups are reported SEPARATELY and never pooled: seed42_main, seed42_boundary, heldout_main, heldout_boundary.
Top-1 accuracy is counted over DETECTED faulty incidents (the investigators only start when the monitor alarms);
the detection rate is reported next to it, so a missed detection is visible and not hidden inside the accuracy.
"""
from __future__ import annotations

import csv
from pathlib import Path

from metrics.scoring import IncidentResult

GROUP_ORDER = ["seed42_main", "seed42_boundary", "heldout_main", "heldout_boundary"]


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def summarize_group(group: str, results: list[IncidentResult]) -> dict:
    faulty = [r for r in results if r.true_causes]
    controls = [r for r in results if not r.true_causes]
    investigated = [r for r in faulty if r.alarm_raised]
    tp = fp = fn = non_cause = b1_tp = b1_fp = b2_tp = b2_fp = true_total = 0
    verdict_counts = {"CONFIRMED": 0, "DENIED": 0, "PARTIAL": 0, "INCONCLUSIVE": 0}
    for r in investigated:
        confirmed = {v.suspect_table for v in r.verdicts if v.verdict == "CONFIRMED"}
        true = set(r.true_causes)
        tp, fp, fn = tp + len(confirmed & true), fp + len(confirmed - true), fn + len(true - confirmed)
        non_cause += len([v for v in r.verdicts if v.suspect_table not in true])
        true_total += len(true)
        b1_tp, b1_fp = b1_tp + r.b1_correct, b1_fp + (not r.b1_correct)
        b2_tp, b2_fp = b2_tp + r.b2_correct, b2_fp + (not r.b2_correct)
        for v in r.verdicts:
            verdict_counts[v.verdict] += 1
    return {
        "group": group, "incidents": len(results), "faulty": len(faulty), "detected": len(investigated),
        "detection_rate": _ratio(len(investigated), len(faulty)),
        "top1_replay": _ratio(sum(r.replay_correct for r in investigated), len(investigated)),
        "top1_b1_recency": _ratio(sum(r.b1_correct for r in investigated), len(investigated)),
        "top1_b2_distance": _ratio(sum(r.b2_correct for r in investigated), len(investigated)),
        "top1_replay_n": sum(r.replay_correct for r in investigated), "top1_b1_n": sum(r.b1_correct for r in investigated),
        "top1_b2_n": sum(r.b2_correct for r in investigated), "investigated": len(investigated),
        "replay_precision": _ratio(tp, tp + fp), "replay_recall": _ratio(tp, true_total),
        "b1_precision": _ratio(b1_tp, b1_tp + b1_fp), "b2_precision": _ratio(b2_tp, b2_tp + b2_fp),
        "false_confirms": fp, "non_cause_suspects": non_cause, "false_confirm_rate": _ratio(fp, non_cause),
        "control_incidents": len(controls), "control_false_alarms": sum(r.alarm_raised for r in controls),
        "healthy_day_false_alarms": sum(r.healthy_day_false_alarms for r in results),
        "mean_replays": _ratio(sum(r.n_replays for r in investigated), len(investigated)),
        "mean_replay_seconds": _ratio(sum(r.replay_seconds for r in investigated), len(investigated)),
        "verdicts": verdict_counts,
    }


def summarize(results: list[IncidentResult]) -> list[dict]:
    """One row per group that has results, in a fixed order."""
    return [summarize_group(g, [r for r in results if r.group == g]) for g in GROUP_ORDER
            if any(r.group == g for r in results)]


def write_summary_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = [{**{k: v for k, v in row.items() if k != "verdicts"},
             **{f"verdict_{k}": n for k, n in row["verdicts"].items()}, "source": "synthetic"} for row in rows]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)

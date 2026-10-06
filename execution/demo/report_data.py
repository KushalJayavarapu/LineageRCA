"""Page data for the HTML report. It only READS what the run produced (IncidentResult, the monitor's Anomaly, the snapshot list);
it never computes a verdict, a metric or a score. Every number is formatted here, once, so the browser never rounds anything.
Each number is stored as {"v": exact value, "s": the text shown on the page}."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from core.config import MonitorConfig
from demo.findings import LIMITATIONS, build_findings
from drift.monitor import METRICS, day_metrics
from metrics.scoring import IncidentResult
from metrics.summary import summarize, summarize_group
from runners.run_scenario import Outcome

# Emphasis (a coral bar) goes on what is awkward FOR THE METHOD, never on a baseline failing: replay failing or abstaining, a monitor miss,
# masking, run-to-run randomness, a tie with the baselines, or a baseline being right. The finding text itself is never changed.
WARNING_WORDS = ("did NOT", "NOT alarm", "missed", "does not mean", "different numbers", "fair-comparison", "(right)",
                 "INCONCLUSIVE", "PARTIAL")


def num(v: float) -> dict:
    """A deviation as shown on the page (3 decimals, always signed) next to its exact value."""
    return {"v": v, "s": f"{v:+.3f}"}


def metric_text(metric: str, v: float) -> str:
    if metric == "row_count":
        return f"{v:.0f}"
    if metric == "revenue_usd":
        return f"{v:,.2f}"
    return f"{v:.4f}"                                   # null rates


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _methods(r: IncidentResult) -> list[dict]:
    rows = [("Replay (our method)", r.replay_top1, r.replay_correct), ("B1 lineage recency", r.b1_blame, r.b1_correct),
            ("B2 lineage distance", r.b2_blame, r.b2_correct), ("B3 parameter replay (BugDoc-style)", r.b3_blame, r.b3_correct)]
    return [{"name": n, "blame": b or "nobody", "correct": ok} for n, b, ok in rows]


def scenario_view(outcome: Outcome, description: str, out_dir: Path, monitor_cfg: MonitorConfig) -> dict:
    r, ctx = outcome.result, outcome.run.context
    monitor, silent = None, []
    if ctx.anomaly is not None:
        a = ctx.anomaly
        thr = monitor_cfg.rel_threshold if METRICS[a.metric][1] == "rel" else monitor_cfg.null_rate_threshold
        monitor = {"table": a.table, "metric": a.metric, "observed": metric_text(a.metric, a.observed),
                   "expected": metric_text(a.metric, a.expected), "deviation": num(a.deviation),
                   "threshold": {"v": thr, "s": f"{thr}"}}
    else:                                               # control: show what the monitor saw instead (same values as the PNG)
        metrics = day_metrics(ctx.store.read("cleaned_orders"), ctx.store.read("daily_revenue_agg"))
        silent = [{"metric": m, "table": METRICS[m][0], "dev": num(ctx.monitor.deviation(metrics, m, ctx.day))} for m in METRICS]
    changes = [{"table": s.table_name, "snapshot_id": s.snapshot_id, "change_type": s.change_type, "committed_at": s.committed_at}
               for s in ctx.store.snapshots if s.change_type != "normal_load"]
    last_change = {c["table"]: c["change_type"] for c in changes}
    methods = _methods(r)
    return {
        "id": r.scenario_id, "short": r.scenario_id.split("_")[0], "title": r.scenario_id.split("_", 1)[1].replace("_", " "),
        "description": description, "boundary": r.boundary, "truth": r.true_causes, "decoys": r.decoy_tables,
        "alarm": r.alarm_raised, "monitor": monitor, "silent": silent, "changes": changes,
        "suspects": [{"table": t, "change_type": last_change.get(t, "")} for t in r.suspects],
        "verdicts": [{"table": v.suspect_table, "snapshot": v.suspect_snapshot_id, "runs": v.replay_runs, "verdict": v.verdict,
                      "before": num(v.deviation_before), "after": num(v.deviation_after), "seconds": f"{v.compute_seconds:.2f}",
                      "explanation": v.explanation} for v in r.verdicts],
        "methods": methods, "b3_notes": r.b3_notes, "replay_seconds": f"{r.replay_seconds:.2f}",
        "all_agree": bool(r.true_causes) and r.alarm_raised and all(m["correct"] for m in methods[:3]),
        "monitor_text": ("silent, no investigation" if not r.alarm_raised else
                         f"alarm on {r.anomaly_table} / {r.anomaly_metric} ({r.anomaly_deviation:+.3f})"),
        "images": {"lineage": _b64(out_dir / f"lineage_{r.scenario_id}.png"), "metric": _b64(out_dir / f"metric_{r.scenario_id}.png")},
    }


JS_KEYS = ("id", "short", "title", "description", "boundary", "truth", "decoys", "alarm", "monitor", "silent", "suspects",
           "verdicts", "methods", "changes")


def replay_json(scenarios: list[dict], seed: int, rel_threshold: float) -> str:
    """The JSON block the replay panel reads. '</' is escaped so it can sit inside a <script> tag."""
    data = {"seed": seed, "rel_threshold": {"v": rel_threshold, "s": f"{rel_threshold}"}, "scenarios": [{k: sc[k] for k in JS_KEYS} for sc in scenarios]}
    return json.dumps(data, ensure_ascii=True).replace("</", "<\\/")


def heldout_by_scenario(heldout: list[IncidentResult]) -> list[dict]:
    rows = []
    for sid in sorted({r.scenario_id for r in heldout}):
        rs = [r for r in heldout if r.scenario_id == sid]
        det = [r for r in rs if r.alarm_raised]
        rows.append({"id": sid, "boundary": rs[0].boundary, "control": not rs[0].true_causes, "runs": len(rs),
                     "alarms": len(det), "replay": sum(r.replay_correct for r in det), "b1": sum(r.b1_correct for r in det),
                     "b2": sum(r.b2_correct for r in det), "b3": sum(r.b3_correct for r in det), "n": len(det)})
    return rows


def page_context(outcomes: list[Outcome], descriptions: dict[str, str], out_dir: Path, heldout: list[IncidentResult] | None,
                 note: str, cfg_hash: str, seed: int, monitor_cfg: MonitorConfig) -> dict:
    demo = [o.result for o in outcomes]
    scenarios = [scenario_view(o, descriptions[o.result.scenario_id], out_dir, monitor_cfg) for o in outcomes]
    findings = build_findings(demo, heldout)
    return {
        "seed": seed, "cfg_hash": cfg_hash, "demo": demo, "scenarios": scenarios,
        "glance": [summarize_group(g, [r for r in demo if r.group == g]) for g in ("seed42_main", "seed42_boundary")
                   if any(r.group == g for r in demo)],
        "findings": [{"text": f, "warn": any(w in f for w in WARNING_WORDS)} for f in findings],
        "heldout_rows": summarize(heldout) if heldout else [], "heldout_scen": heldout_by_scenario(heldout) if heldout else [],
        "heldout_note": note, "limitations": LIMITATIONS, "replay_json": replay_json(scenarios, seed, monitor_cfg.rel_threshold),
    }

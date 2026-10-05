"""PNG figures for the report. Every title says SYNTHETIC. Colours are colour-blind safe and every node also carries a text label."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")                      # draw to files, no window
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from drift.monitor import METRICS, day_metrics
from runners.run_scenario import Outcome

COLORS = {"CONFIRMED": "#D55E00", "DENIED": "#56B4E9", "PARTIAL": "#E69F00", "INCONCLUSIVE": "#CC79A7", "none": "#E5E5E5"}
POS = {"raw_orders": (0.0, 2.0), "raw_customers": (0.0, 1.0), "raw_fx_rates": (0.0, 0.0),
       "cleaned_orders": (1.6, 1.0), "daily_revenue_agg": (3.2, 1.0)}
EDGES = [("raw_orders", "cleaned_orders"), ("raw_customers", "cleaned_orders"), ("raw_fx_rates", "cleaned_orders"),
         ("cleaned_orders", "daily_revenue_agg")]


def lineage_figure(outcome: Outcome, path: Path) -> None:
    """The lineage graph. Colour = replay verdict of that table; thick outline = the anomalous table; star = true cause."""
    r = outcome.result
    verdict = {v.suspect_table: v.verdict for v in r.verdicts}
    fig, ax = plt.subplots(figsize=(8.4, 3.9))
    for up, down in EDGES:
        ax.annotate("", xy=(POS[down][0] - 0.55, POS[down][1]), xytext=(POS[up][0] + 0.55, POS[up][1]),
                    arrowprops={"arrowstyle": "-|>", "color": "#555555", "lw": 1.2})
    for name, (x, y) in POS.items():
        kind = verdict.get(name, "none")
        anomalous = name == r.anomaly_table
        ax.add_patch(FancyBboxPatch((x - 0.55, y - 0.28), 1.1, 0.56, boxstyle="round,pad=0.02",
                                    fc=COLORS[kind], ec="black" if anomalous else "#777777", lw=3 if anomalous else 1))
        star = "  ★" if name in r.true_causes else ""
        ax.text(x, y + 0.08, name + star, ha="center", va="center", fontsize=8.5, weight="bold")
        ax.text(x, y - 0.14, kind if kind != "none" else "not a suspect", ha="center", va="center", fontsize=7.5)
    ax.set_xlim(-0.8, 3.9)
    ax.set_ylim(-0.6, 2.5)
    ax.axis("off")
    ax.set_title(f"{r.scenario_id} (seed {r.seed}) - SYNTHETIC data, real time-travel replay", fontsize=10)
    caption = (f"replay blames: {r.replay_top1}   |   B1 recency: {r.b1_blame}   |   B2 distance: {r.b2_blame}   |   "
               f"truth (scoring only, ★): {', '.join(r.true_causes) or 'none'}")
    fig.text(0.5, 0.03, caption, ha="center", fontsize=7.5)
    fig.text(0.5, 0.0, "thick outline = anomalous table the monitor flagged", ha="center", fontsize=7, color="#555555")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def metric_figure(outcome: Outcome, path: Path, rel_threshold: float, null_threshold: float) -> None:
    """Deviation of the alarming metric in the anomalous run and after each replay, against the monitor threshold band.

    For the control (no alarm) it shows the four day-11 deviations instead, all expected inside the band.
    """
    r, ctx = outcome.result, outcome.run.context
    if r.alarm_raised:
        labels = ["anomalous run"] + [f"replay: {v.suspect_table}\n({v.verdict})" for v in r.verdicts]
        values = [r.anomaly_deviation] + [v.deviation_after for v in r.verdicts]
        colors = ["#888888"] + [COLORS[v.verdict] for v in r.verdicts]
        threshold = rel_threshold if METRICS[r.anomaly_metric][1] == "rel" else null_threshold
        title = f"{r.scenario_id}: {r.anomaly_metric} deviation vs baseline"
    else:
        metrics = day_metrics(ctx.store.read("cleaned_orders"), ctx.store.read("daily_revenue_agg"))
        labels = list(METRICS)
        values = [ctx.monitor.deviation(metrics, m, ctx.day) for m in METRICS]
        colors = ["#56B4E9"] * len(values)
        threshold = rel_threshold
        title = f"{r.scenario_id}: day-{ctx.day} deviations, the monitor stays silent"
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    ax.axhspan(-threshold, threshold, color="#009E73", alpha=0.15, label=f"inside the monitor threshold (±{threshold})")
    ax.axhline(0, color="#444444", lw=0.8)
    bars = ax.bar(range(len(values)), values, color=colors, edgecolor="#333333")
    for bar, value in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:+.3f}", ha="center",
                va="bottom" if value >= 0 else "top", fontsize=8)
    ax.set_xticks(range(len(values)), labels, fontsize=8)
    ax.set_ylabel("deviation from the 7-day median")
    ax.set_title(f"{title} - SYNTHETIC", fontsize=10)
    low, high = min([*values, -threshold]), max([*values, threshold])
    pad = 0.18 * (high - low)
    ax.set_ylim(low - pad, high + pad)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), fontsize=7.5, frameon=False)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)

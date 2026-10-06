"""B3 baseline, BugDoc-style PARAMETER replay: vary pipeline parameters, not table snapshots.

This is NOT BugDoc itself (we use none of its code); it is the same idea, restricted to the parameters our pipeline has:
the code version of each stage. Steps:
  1. Compare the parameters of the last HEALTHY run of each stage with those of the ANOMALOUS run.
  2. For every non-empty subset of the parameters that differ, put the healthy values back, re-execute day D with ALL inputs
     pinned to what the anomalous run read, and check whether the alarming metric clears.
  3. The smallest subset that clears it is the "minimal root cause"; we blame the output table of its stage.
The decision rule, thresholds and repeats are the SAME as in replay (decide_verdict, measure), so only the thing being varied differs.
It does not use the lineage shortlist and never reads an older snapshot. So a fault in DATA (a table's contents) is outside its
search space by construction: if no parameter differs, or reverting them does not help, it abstains. That is the point of the
baseline: it shows whether the snapshot substrate matters.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from statistics import mean

import pyarrow as pa

from adapters.lineage_store import LineageStore
from agents.replay import STAGE_RUNNERS, decide_verdict, measure
from core.config import ReplayConfig
from core.models import Verdict
from tasks.scenarios import IncidentContext

STAGE_TABLE = {"clean": "cleaned_orders", "aggregate": "daily_revenue_agg"}   # stage -> table it produces (what we blame)


@dataclass
class ParamTest:
    reverted: tuple[str, ...]          # stages whose code version was put back to the healthy value
    verdict: Verdict
    deviation_after: float
    explanation: str
    seconds: float


@dataclass
class ParamOutcome:
    differing: dict[str, tuple[str, str]]   # stage -> (healthy code version, anomalous code version)
    tests: list[ParamTest]
    blamed: str | None                      # a table name, or None = abstained
    seconds: float

    @property
    def n_executions(self) -> int:
        return len(self.tests)


def code_config(lineage: LineageStore, up_to: int | None = None) -> dict[str, str]:
    """Code version of each stage in its latest run (up to logical time `up_to`, or overall if None)."""
    config = {}
    for stage in STAGE_TABLE:
        runs = [r for r in lineage.runs.values() if r.transform_id == stage and (up_to is None or r.logical_time <= up_to)]
        if runs:
            config[stage] = max(runs, key=lambda r: r.logical_time).code_version
    return config


def _execute(context: IncidentContext, code: dict[str, str]) -> pa.Table:
    """Re-run day D from the raw tables as the anomalous run read them, with the given code versions."""
    store, lineage, day = context.store, context.lineage, context.day
    clean_run = lineage.last_run_of("cleaned_orders")
    raw = {name: store.read(name, snap) for name, snap in clean_run.inputs.items()}     # pinned, never an older snapshot
    cleaned = STAGE_RUNNERS["clean"](raw, day, code["clean"])
    if context.anomaly.table == "cleaned_orders":
        return cleaned
    return STAGE_RUNNERS["aggregate"]({"cleaned_orders": cleaned}, day, code["aggregate"])


def choose_blame(tests: list[ParamTest]) -> str | None:
    """CONFIRMED subsets beat PARTIAL ones. Within a group the smallest subset wins, then the smallest remaining deviation
    (which is also the biggest reduction, since 'before' is the same for every test). None = abstain (nothing helped enough)."""
    for kind in ("CONFIRMED", "PARTIAL"):
        pool = [t for t in tests if t.verdict == kind]
        if not pool:
            continue
        best = min(pool, key=lambda t: (len(t.reverted), abs(t.deviation_after), t.reverted))
        singles = [t for t in tests if len(t.reverted) == 1 and t.reverted[0] in best.reverted]
        # a subset of several stages blames the stage whose own single revert helped most
        main = min(singles, key=lambda t: (abs(t.deviation_after), t.reverted)).reverted[0] if len(best.reverted) > 1 and singles             else best.reverted[0]
        return STAGE_TABLE[main]
    return None


def parameter_replay(context: IncidentContext, cfg: ReplayConfig) -> ParamOutcome:
    """Run the BugDoc-style search for one incident (needs an anomaly; otherwise nothing starts)."""
    anomaly, lineage = context.anomaly, context.lineage
    good, bad = code_config(lineage, context.healthy_until), code_config(lineage)
    differing = {s: (good[s], bad[s]) for s in STAGE_TABLE if s in good and good[s] != bad[s]}
    tests: list[ParamTest] = []
    for size in range(1, len(differing) + 1):
        for subset in combinations(sorted(differing), size):
            code = {**bad, **{s: differing[s][0] for s in subset}}               # healthy values back for this subset only
            afters, seconds = measure(context, lambda code=code: _execute(context, code), cfg)
            verdict, why = decide_verdict(anomaly.deviation, afters, anomaly.metric, context.monitor, cfg)
            tests.append(ParamTest(subset, verdict, mean(afters), f"revert {', '.join(subset)}: {why}", seconds))
    return ParamOutcome(differing, tests, choose_blame(tests), sum(t.seconds for t in tests))

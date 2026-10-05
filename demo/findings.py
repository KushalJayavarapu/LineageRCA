"""Plain-language findings, generated from the run itself. Every number comes from the results; nothing is typed in by hand.

The wording is deliberately honest: cases where the baselines tie replay, or where replay fails, get their own sentence.
"""
from __future__ import annotations

from metrics.scoring import IncidentResult
from metrics.summary import summarize

LIMITATIONS = [
    (
        'All data and all faults are SYNTHETIC and written by us. The results show that the mechanism works for pure, '
        'deterministic batch transforms on a five-table toy pipeline; they are not evidence about real production '
        'pipelines.'
    ),
    (
        'The evaluation is partly circular: we wrote the faults, the decoy placement and the method. Fixed thresholds, '
        'held-out seeds and the boundary scenarios reduce this but do not remove it. Held-out seeds change the random '
        'data, not the types of fault.'
    ),
    (
        'Replay is only a clean counterfactual for pure, deterministic, batch transforms. Non-deterministic, '
        'incremental or side-effecting transforms are out of scope (scenario s6 shows what happens when this is '
        'violated).'
    ),
    (
        "A CONFIRMED verdict means that undoing THIS table's change clears the metric. It does not prove that no other "
        'table is also guilty, and rolling back a downstream table can hide an upstream cause.'
    ),
    (
        'One DAG, five tables and six scenarios are far too few for statistical claims. With so few tables a lineage- '
        'distance rule is hard to fool.'
    ),
    (
        'Replay itself is not new (BugDoc, Newt, aaiclick). The narrow claim here is native lakehouse time travel as '
        'the replay mechanism, guided by lineage shortlisting, aimed at data-quality root causes.'
    ),
    (
        'Replay cannot undo a code fault that was never versioned: it relies on knowing which code version each run '
        'used.'
    ),
    (
        'Compute cost here is a fraction of a second per incident because the tables are tiny; it says nothing about '
        'full-scale cost.'
    ),
]


def _scenario_sentence(r: IncidentResult) -> str:
    truth = ", ".join(r.true_causes) or "none"
    if not r.true_causes:
        verb = "raised an alarm" if r.alarm_raised else "stayed silent, so no investigation started"
        return f"{r.scenario_id} (control, no fault): the monitor {verb}."
    if not r.alarm_raised:
        return f"{r.scenario_id}: the monitor did NOT alarm, so nobody investigated (true cause: {truth})."
    verdicts = ", ".join(f"{v.suspect_table} {v.verdict}" for v in r.verdicts)
    base = f"{r.scenario_id}: replay verdicts: {verdicts}. Replay blames {r.replay_top1 or 'nobody'}; truth: {truth}."
    if r.replay_correct and r.b1_correct and r.b2_correct:
        return base + " Both lineage baselines named the same table, so replay does not win here; this is the fair-comparison case."
    parts = []
    parts.append(f"lineage-recency blamed {r.b1_blame or 'nobody'} ({'right' if r.b1_correct else 'wrong'})")
    parts.append(f"lineage-distance blamed {r.b2_blame or 'nobody'} ({'right' if r.b2_correct else 'wrong'})")
    prefix = "" if r.replay_correct else " Replay did NOT name a true cause here."
    joined = "; ".join(parts)
    return base + prefix + " " + joined[0].upper() + joined[1:] + "."


def _masking_sentence(results: list[IncidentResult]) -> list[str]:
    out = []
    for r in results:
        if len(r.true_causes) > 1 and r.alarm_raised:
            confirmed = {v.suspect_table for v in r.verdicts if v.verdict == "CONFIRMED"} & set(r.true_causes)
            out.append(f"{r.scenario_id} has {len(r.true_causes)} true causes and replay CONFIRMED {len(confirmed)} of them "
                       f"({', '.join(sorted(confirmed)) or 'none'}). Rolling back a downstream table also removes an upstream "
                       "fault, so a CONFIRMED verdict does not mean the other causes are innocent.")
        if r.scenario_id.startswith("s6") and r.alarm_raised:
            counts = {k: sum(v.verdict == k for v in r.verdicts) for k in ("CONFIRMED", "DENIED", "PARTIAL", "INCONCLUSIVE")}
            out.append(f"{r.scenario_id} (unseeded random sample): verdict counts {counts}. Replay with a random step gives "
                       "different numbers on every run, even with the same seed.")
    return out


def _group_sentence(row: dict) -> str:
    inv = row["investigated"]
    detected = f"{row['detected']} of {row['faulty']} faulty incidents were detected by the monitor"
    return (f"{row['group']}: {detected}; top-1 correct: replay {row['top1_replay_n']}/{inv}, lineage-recency "
            f"{row['top1_b1_n']}/{inv}, lineage-distance {row['top1_b2_n']}/{inv}; false confirms {row['false_confirms']}/"
            f"{row['non_cause_suspects']}; control false alarms {row['control_false_alarms']}/{row['control_incidents']}.")


def build_findings(demo: list[IncidentResult], heldout: list[IncidentResult] | None) -> list[str]:
    """Findings for the report: one per demo scenario, the group results, and a held-out summary if it is available."""
    findings = [_scenario_sentence(r) for r in demo] + _masking_sentence(demo)
    findings += [_group_sentence(row) for row in summarize(demo)]
    if heldout:
        findings += [_group_sentence(row) for row in summarize(heldout)]
        missed = [f"{r.scenario_id} seed {r.seed}" for r in heldout if r.true_causes and not r.alarm_raised]
        if missed:
            findings.append("The monitor missed these held-out incidents (nobody investigated): " + ", ".join(missed) + ".")
    return findings

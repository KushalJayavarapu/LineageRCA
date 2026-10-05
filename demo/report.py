"""Self-contained HTML report: no network, no CDN, images embedded. Everything is labelled SYNTHETIC."""
from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment

from demo.findings import LIMITATIONS, build_findings
from metrics.scoring import IncidentResult
from metrics.summary import summarize
from runners.run_scenario import Outcome

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LineageRCA demo report (SYNTHETIC)</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:1000px;margin:0 auto;padding:16px;color:#1b1b1b;line-height:1.45}
 .banner{background:#7a1f00;color:#fff;padding:12px 16px;border-radius:6px;font-weight:600}
 .box{background:#fff6dd;border:1px solid #e0c36a;border-radius:6px;padding:10px 16px;margin:16px 0}
 table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0 16px} th,td{border:1px solid #ccc;padding:5px 8px;text-align:left}
 th{background:#eee} td.num{text-align:right} .ok{color:#0a6b3d;font-weight:600} .bad{color:#a30000;font-weight:600}
 .card{border:1px solid #ccc;border-radius:8px;padding:12px 16px;margin:18px 0} img{max-width:100%;height:auto}
 .small{font-size:13px;color:#444} .scroll{overflow-x:auto}
</style></head><body>
<div class="banner">SYNTHETIC data, real time-travel replay. Every table, fault and number below comes from our own toy pipeline.</div>
<h1>LineageRCA: counterfactual replay for data-pipeline root cause analysis</h1>
<div class="box"><b>Read this first.</b> When a data-quality alarm fires, replay re-runs the downstream steps with ONE suspect table at its
 earlier Delta snapshot (everything else pinned to what the anomalous run used). If the anomaly disappears the suspect is CONFIRMED,
 if not it is DENIED. The two baselines only look at the lineage graph. The data and the faults are synthetic and written by us,
 so the evaluation is partly circular; see Limitations. Demo seed {{ seed }}; config fingerprint {{ cfg_hash }}.</div>

<h2>1. Summary, demo seed {{ seed }} (one run per scenario)</h2>
<div class="scroll"><table><tr><th>scenario</th><th>true cause (scoring only)</th><th>monitor</th><th>replay blames</th><th>B1 recency</th>
 <th>B2 distance</th><th>B3 param replay</th><th>replay s</th></tr>
{% for r in demo %}<tr><td>{{ r.scenario_id }}{% if r.boundary %} (boundary){% endif %}</td><td>{{ r.true_causes|join(', ') or 'none' }}</td>
 <td>{% if r.alarm_raised %}alarm on {{ r.anomaly_table }}/{{ r.anomaly_metric }} ({{ '%+.3f'|format(r.anomaly_deviation) }}){% else %}silent{% endif %}</td>
 {% for name, ok in [(r.replay_top1, r.replay_correct), (r.b1_blame, r.b1_correct), (r.b2_blame, r.b2_correct), (r.b3_blame, r.b3_correct)] %}
 <td class="{{ 'ok' if ok else 'bad' }}">{{ name or '-' }} {{ 'right' if ok else 'wrong' }}</td>{% endfor %}
 <td class="num">{{ '%.2f'|format(r.replay_seconds) }}</td></tr>{% endfor %}</table></div>
<p class="small">"-" means that method blamed nobody (right for the control, wrong when there is a cause). Scored per incident, not pooled. B3 is a BugDoc-style baseline that varies stage code versions instead of snapshots (see section 5).</p>

<h2>2. Held-out seeds 1-5 (reported separately; read from results/incidents.jsonl)</h2>
{% if heldout_rows %}<div class="scroll"><table><tr><th>group</th><th>detected</th><th>top-1 replay</th><th>top-1 B1 recency</th><th>top-1 B2 distance</th><th>top-1 B3 param replay</th>
 <th>false confirms</th><th>control false alarms</th></tr>
{% for g in heldout_rows %}<tr><td>{{ g.group }}</td><td>{{ g.detected }}/{{ g.faulty }}</td><td>{{ g.top1_replay_n }}/{{ g.investigated }}</td>
 <td>{{ g.top1_b1_n }}/{{ g.investigated }}</td><td>{{ g.top1_b2_n }}/{{ g.investigated }}</td><td>{{ g.top1_b3_n }}/{{ g.investigated }}</td>
 <td>{{ g.false_confirms }}/{{ g.non_cause_suspects }}</td><td>{{ g.control_false_alarms }}/{{ g.control_incidents }}</td></tr>{% endfor %}</table></div>
 {% if heldout_note %}<p class="bad">{{ heldout_note }}</p>{% endif %}
{% else %}<p class="bad">{{ heldout_note }}</p>{% endif %}

<h2>3. Findings (generated from the runs, including where replay fails or the baselines tie)</h2>
<ul>{% for f in findings %}<li>{{ f }}</li>{% endfor %}</ul>

<h2>4. One card per scenario (seed {{ seed }})</h2>
{% for c in cards %}<div class="card"><h3>{{ c.r.scenario_id }}</h3><p>{{ c.description }}</p>
 <p><b>Monitor:</b> {% if c.r.alarm_raised %}{{ c.r.anomaly_table }} / {{ c.r.anomaly_metric }} deviation {{ '%+.3f'|format(c.r.anomaly_deviation) }}{% else %}silent{% endif %}</p>
 <img alt="lineage graph" src="data:image/png;base64,{{ c.lineage }}"><img alt="metric before and after replay" src="data:image/png;base64,{{ c.metric }}">
 {% if c.r.verdicts %}<div class="scroll"><table><tr><th>suspect</th><th>pre-change snapshot</th><th>verdict</th><th>before</th><th>after</th><th>why</th></tr>
 {% for v in c.r.verdicts %}<tr><td>{{ v.suspect_table }}</td><td class="num">{{ v.suspect_snapshot_id }}</td><td>{{ v.verdict }}</td>
 <td class="num">{{ '%+.3f'|format(v.deviation_before) }}</td><td class="num">{{ '%+.3f'|format(v.deviation_after) }}</td><td>{{ v.explanation }}</td></tr>{% endfor %}</table></div>{% endif %}
 {% if c.r.b3_notes %}<p class="small"><b>B3 (parameter replay, BugDoc-style):</b> {{ c.r.b3_notes|join(' | ') }}</p>{% endif %}</div>{% endfor %}

<h2>5. Limitations</h2><ul>{% for l in limitations %}<li>{{ l }}</li>{% endfor %}</ul>
<p class="small">Files next to this report: snapshots.csv, lineage_edges.csv, replay_verdicts.csv (all with source=synthetic), lineage_*.png, metric_*.png.</p>
</body></html>
"""


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def render_report(outcomes: list[Outcome], descriptions: dict[str, str], out_dir: Path, heldout: list[IncidentResult] | None,
                  heldout_note: str, cfg_hash: str, seed: int) -> str:
    """Build the HTML text. The PNG files must already exist in out_dir."""
    demo = [o.result for o in outcomes]
    cards = [{"r": o.result, "description": descriptions[o.result.scenario_id],
              "lineage": _b64(out_dir / f"lineage_{o.result.scenario_id}.png"),
              "metric": _b64(out_dir / f"metric_{o.result.scenario_id}.png")} for o in outcomes]
    return Environment(autoescape=True).from_string(TEMPLATE).render(
        demo=demo, cards=cards, findings=build_findings(demo, heldout), limitations=LIMITATIONS, seed=seed, cfg_hash=cfg_hash,
        heldout_rows=summarize(heldout) if heldout else [], heldout_note=heldout_note)

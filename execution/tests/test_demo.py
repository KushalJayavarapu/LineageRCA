import csv
import json
import re
from pathlib import Path

import pytest

from demo.figures import lineage_figure, metric_figure
from demo.findings import LIMITATIONS, build_findings
from demo.report import render_report
from demo.run_demo import load_heldout, run_demo
from runners.run_scenario import run_scenario


@pytest.fixture(scope="module")
def small(settings, tmp_path_factory):
    """Small pipeline so these tests stay fast; real thresholds. It has its OWN warehouse, because run_demo deletes the
    Delta folders it builds and must never touch the ones the session-wide `runs` fixture uses."""
    wh = tmp_path_factory.mktemp("demo_wh") / "lineagerca_warehouse"
    return settings.model_copy(update={"pipeline": settings.pipeline.model_copy(update={"orders_per_day": 300}),
                                       "warehouse_dir": wh})


def test_figures_are_written_for_an_incident_and_for_the_control(small, tmp_path):
    for sid in ("s1_bad_join_key", "s4_control_no_fault"):
        outcome = run_scenario(sid, 7, small)
        lineage_figure(outcome, tmp_path / f"l_{sid}.png")
        metric_figure(outcome, tmp_path / f"m_{sid}.png", small.monitor.rel_threshold, small.monitor.null_rate_threshold)
        for name in (f"l_{sid}.png", f"m_{sid}.png"):
            assert (tmp_path / name).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        outcome.run.context.store.remove()


def test_findings_come_from_results_and_mention_failures_and_ties(runs, settings):
    from agents.replay import replay_all
    from agents.shortlist import shortlist
    from metrics.scoring import score_incident
    results = []
    for sid in ("s1_bad_join_key", "s3_type_coercion_latest", "s4_control_no_fault", "s5_two_causes"):
        run = runs[sid]
        sus = shortlist(run.context, settings.replay)
        results.append(score_incident(run.truth, run.context, sus, replay_all(run.context, sus, settings.replay),
                                      settings.replay.replay_repeats, 42, "x"))
    text = "\n".join(build_findings(results, None))
    assert "fair-comparison case" in text                       # s3: the baselines tie replay and we say so
    assert "Lineage-recency blamed raw_fx_rates (wrong)" in text  # s1: the baseline is fooled by the decoy
    assert "control, no fault" in text and "stayed silent" in text
    assert "CONFIRMED 2 of them" in text and "does not mean the other causes are innocent" in text   # s5 masking


def _build_report(small, tmp_path, scenario_ids, seed=7):
    outcomes = [run_scenario(sid, seed, small) for sid in scenario_ids]
    for o in outcomes:
        n = o.result.scenario_id
        lineage_figure(o, tmp_path / f"lineage_{n}.png")
        metric_figure(o, tmp_path / f"metric_{n}.png", small.monitor.rel_threshold, small.monitor.null_rate_threshold)
    desc = {o.result.scenario_id: "d" for o in outcomes}
    html = render_report(outcomes, desc, tmp_path, None, "Held-out results not found.", "abc123", seed, small)
    for o in outcomes:
        o.run.context.store.remove()
    return outcomes, html


def test_report_keeps_the_honesty_content_and_is_offline(small, tmp_path):
    ids = ("s1_bad_join_key", "s3_type_coercion_latest", "s4_control_no_fault", "s5_two_causes", "s6_nondeterministic_transform")
    outcomes, html = _build_report(small, tmp_path, ids)
    assert "SYNTHETIC DATA - real Delta time-travel replay - not a production pipeline" in html     # the always-visible banner
    assert "Read this first" in html and 'id="limitations"' in html and "Limitations" in html
    assert all(lim[:30] in html for lim in LIMITATIONS)
    assert "CascadeGuard" not in html and "Attest" not in html                                      # no words from the style reference
    assert "http://" not in html and "https://" not in html                                         # no external requests, no CDN
    assert "@import" not in html and "url(" not in html.split("</style>")[0]                       # no fonts or images loaded by CSS
    assert html.count("data:image/png;base64,") == 2 * len(outcomes) and "Held-out results not found." in html
    assert "prefers-reduced-motion" in html and "aria-pressed" in html and "aria-valuetext" in html
    # awkward results must be visible: any PARTIAL or INCONCLUSIVE verdict the boundary scenarios produced is on the page
    produced = {v.verdict for o in outcomes if o.result.boundary for v in o.result.verdicts} & {"PARTIAL", "INCONCLUSIVE"}
    for word in produced:
        assert f'class="tag v-{word}"' in html
    if not produced:                                  # s6 is random: this run produced neither, so the page must show what it did produce
        assert 'class="tag v-CONFIRMED"' in html and 'class="tag v-DENIED"' in html


def test_replay_data_matches_the_results_exactly_and_nothing_autoplays(small, tmp_path):
    outcomes, html = _build_report(small, tmp_path, ("s1_bad_join_key", "s4_control_no_fault"))
    data = json.loads(re.search(r'<script type="application/json" id="replay-data">(.*?)</script>', html, re.DOTALL).group(1))
    for o, sc in zip(outcomes, data["scenarios"], strict=True):
        r = o.result
        assert sc["id"] == r.scenario_id and sc["alarm"] == r.alarm_raised and sc["truth"] == r.true_causes
        assert [(v["table"], v["verdict"], v["before"]["v"], v["after"]["v"]) for v in sc["verdicts"]] ==             [(v.suspect_table, v.verdict, v.deviation_before, v.deviation_after) for v in r.verdicts]      # exact values, no rounding
        assert [m["blame"] for m in sc["methods"]] == [x or "nobody" for x in (r.replay_top1, r.b1_blame, r.b2_blame, r.b3_blame)]
    shown = [v["after"]["s"] for sc in data["scenarios"] for v in sc["verdicts"]]
    assert shown and all(s in html for s in shown)                                                       # the text on the page
    js = (Path(__file__).resolve().parents[1] / "demo" / "report.js").read_text(encoding="utf-8")
    assert js.count("start()") == 2                    # only the definition and the click handler: play never starts by itself


def test_emphasis_goes_on_what_is_awkward_for_the_method(small, tmp_path):
    _, html = _build_report(small, tmp_path, ("s1_bad_join_key", "s3_type_coercion_latest"))
    items = re.findall(r'<li class="(warn)?">(.*?)</li>', html, re.DOTALL)
    s1 = next(css for css, text in items if text.startswith("s1_bad_join_key"))
    s3 = next(css for css, text in items if text.startswith("s3_type_coercion_latest"))
    assert s1 == "" and s3 == "warn"                  # a baseline failing is not a warning; a tie with the baselines is


@pytest.mark.slow
def test_run_demo_end_to_end_writes_every_output(small, tmp_path):
    small = small.model_copy(update={"results_dir": tmp_path / "no_results"})        # no held-out cache: a notice is shown
    out = tmp_path / "outputs"
    elapsed = run_demo(small, out)
    assert elapsed < 120
    names = {p.name for p in out.iterdir()}
    assert {"demo_report.html", "snapshots.csv", "lineage_edges.csv", "replay_verdicts.csv"} <= names
    assert len([n for n in names if n.startswith("lineage_s")]) == 6 and len([n for n in names if n.startswith("metric_s")]) == 6
    for name in ("snapshots.csv", "lineage_edges.csv", "replay_verdicts.csv"):
        rows = list(csv.DictReader((out / name).open(encoding="utf-8")))
        assert rows and all(r["source"] == "synthetic" for r in rows)
    assert load_heldout(small)[0] is None


def test_load_heldout_reads_the_cache_and_flags_results_made_with_other_configs(small, tmp_path):
    from core.config import config_hash
    from runners.run_all import run_many, save_results
    results = run_many(small, [7], ["s1_bad_join_key", "s4_control_no_fault"])
    cfg = small.model_copy(update={"results_dir": tmp_path / "res"})
    save_results(cfg, results)
    heldout, note = load_heldout(cfg)
    assert [r.seed for r in heldout] == [7, 7] and note == ""
    path = cfg.results_dir / "incidents.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace(config_hash(), "000000000000"), encoding="utf-8")
    assert "different config" in load_heldout(cfg)[1]
    missed = [results[0].model_copy(update={"alarm_raised": False, "verdicts": [], "suspects": []})]
    text = "\n".join(build_findings(results, missed))
    assert "missed these held-out incidents" in text and "s1_bad_join_key seed 7" in text and "heldout_main" in text

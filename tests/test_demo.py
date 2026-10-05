import csv

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


def test_report_is_self_contained_and_labelled_synthetic(small, tmp_path):
    outcomes = [run_scenario(sid, 7, small) for sid in ("s1_bad_join_key", "s4_control_no_fault")]
    for o in outcomes:
        n = o.result.scenario_id
        lineage_figure(o, tmp_path / f"lineage_{n}.png")
        metric_figure(o, tmp_path / f"metric_{n}.png", 0.15, 0.05)
    desc = {o.result.scenario_id: "d" for o in outcomes}
    html = render_report(outcomes, desc, tmp_path, None, "Held-out results not found.", "abc123", 7)
    assert "SYNTHETIC data, real time-travel replay" in html and "Read this first" in html and "Limitations" in html
    assert "http://" not in html and "https://" not in html and "<script" not in html        # offline, no CDN
    assert html.count("data:image/png;base64,") == 4 and "Held-out results not found." in html
    assert all(lim[:30] in html for lim in LIMITATIONS)
    for o in outcomes:
        o.run.context.store.remove()


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

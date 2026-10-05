# DEMO_SCRIPT.md - 3-minute talk track for LineageRCA

Every number below comes from a real run: `results/incidents.jsonl` and `results/summary.csv` (36 incidents: demo seed 42 plus
held-out seeds 1-5, config fingerprint `d47f36ff9e6b`, latest full grid including the BugDoc-style baseline) and the demo run (`python demo/run_demo.py`, about 31 s). Say "SYNTHETIC" out
loud at least twice. If a number on screen differs from this script (scenario s6 varies between runs), trust the screen and say why.

## Before you start (not part of the 3 minutes)
- Terminal in the `execution` folder, venv active, `outputs/demo_report.html` already generated once as a backup.
- Run `python demo/run_demo.py` live at minute 0:45; it takes about half a minute, so talk while it runs.

## 0:00 - 0:30  The problem (one speaker, no screen)
"A dashboard number suddenly looks wrong. Today an engineer opens the lineage graph, sees which upstream tables changed recently,
and guesses the most recent one. That is a guess based on 'these things happened near each other'. It is not proof.
Our idea: test the guess. Lakehouse tables like Delta keep every old version as a snapshot. So we roll the suspect table back to
how it looked before the change, re-run the downstream steps, and see whether the problem goes away. That is a counterfactual:
what would the output have been if this table had not changed?"

## 0:30 - 0:45  What is real and what is synthetic
"Everything you will see runs on a toy pipeline with SYNTHETIC data and faults that we inject ourselves, so we know the true cause.
The time travel and the re-execution are real: Delta Lake tables, DuckDB queries, on a laptop, no Spark, no cloud."
*(Show the lineage picture: three raw tables feed `cleaned_orders`, which feeds `daily_revenue_agg`.)*

## 0:45 - 1:30  Live run, then scenario s1 (the main story)
Type: `python demo/run_demo.py` and keep talking.
"We run six scenarios. In s1 the customer table loses the case of 30% of its ids, so the join drops orders. Afterwards a harmless
FX-rate refresh happens, so the most recent change is NOT the cause. The monitor sees daily revenue 26% below its normal level
(deviation -0.261 against a 0.15 threshold). Two suspects are shortlisted: `raw_customers` and `raw_fx_rates`.
The lineage-recency baseline blames the most recent change, the FX refresh: wrong. Replay rolls each suspect back and re-runs:
with customers rolled back the deviation falls to -0.004, so CONFIRMED; with the FX table rolled back it stays at -0.263, so DENIED."
*(Open `outputs/demo_report.html`, scroll to the s1 card: the lineage picture colours `raw_customers` as CONFIRMED and `raw_fx_rates` as DENIED.)*

## 1:30 - 2:00  Fair comparison and the control
"We also built scenarios where we do NOT win by construction. In s3 the fault is the most recent change, so replay and both
baselines all name `raw_orders`. In s4 there is no fault at all and the monitor stays silent: no investigation, no false alarm.
In s2 a code fault removes a filter; the distance baseline is right there because the culprit table is closest to the anomaly."
*(Show the summary table at the top of the report.)*

## 2:00 - 2:35  Numbers, held-out seeds, and what failed
"On held-out seeds 1 to 5, in the four main scenarios, replay named the true cause in 15 of 15 detected incidents, the recency
baseline in 5 of 15, the distance baseline in 10 of 15, with 0 false confirmations and 0 false alarms on the controls.
A BugDoc-style baseline that varies pipeline parameters instead of snapshots got 5 of 15: it only finds the code fault in s2 and
abstains on data faults, never blaming a wrong table. That is the point: what you vary matters.
We caution: we wrote the faults and the method, so this is partly circular; it shows the mechanism works, not real-world accuracy.
And we report where it breaks. With two causes at once, replay found only one of the two in every detected held-out case, 4 of 8
true-cause slots, because rolling back a downstream table hides the upstream fault. With a random, non-deterministic
step, replay sometimes says INCONCLUSIVE and abstains, and the same seed gives different numbers on different runs."

## 2:35 - 3:00  Close
"Replay in general is not new: BugDoc, Newt and aaiclick exist. Our narrow claim is native lakehouse time travel as the replay
mechanism, guided by lineage shortlisting, aimed at data-quality root causes, with a proper evaluation. Next semester: more
scenarios, Iceberg, and mild non-determinism. Thank you."

## If something goes wrong
- Demo too slow or errors: open the pre-generated `outputs/demo_report.html`; say "this is the report from an earlier run of the same command".
- Report numbers differ for s6: "s6 contains an unseeded random step on purpose, so it differs between runs."
- Asked for a number you do not have: say "we did not measure that" (see `docs/VIVA_NOTES.md`).

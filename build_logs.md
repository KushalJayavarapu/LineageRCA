# build_logs.md — LineageRCA build log

Claude Code: append a new entry after EVERY milestone and at the end of every session (newest at the bottom).
Paste real commands and real output summaries. Never write a number that did not come from a run.

## Entry template

```text
### Entry N — <date> — <milestone, e.g. M2 Pipeline + data generator>
What I did:
Commands run (exact) and result (real output, trimmed):
Problems and how I fixed them:
Decisions (and why):
Honest notes (anything that did not behave as expected):
Next:
Git checkpoint printed: yes/no
```

---

### Entry 0 — scaffold created (before any coding)
- Folder layout, CLAUDE.md, ARCHITECTURE.md, PROGRESS.md, env files, requirements and the kickoff prompt were created from
  the LineageRCA proposal PDF in `../docs/`. No code has been written yet.
- Verified outside the project (scratch test): `deltalake` can write two Delta versions of a table and read version 0 back
  with `DeltaTable(path, version=0)`, and DuckDB can query the result. So the demo needs no Spark, Java or Docker.
- Next: M0 (environment check).

### Entry 1 — 2026-10-05 — M0 Environment ready
What I did: read CLAUDE.md, ARCHITECTURE.md, PROGRESS.md, build_logs.md and the proposal PDF (text extracted read-only with pypdf;
the Read tool could not render the PDF). Reported installed tools, created the venv, installed requirements, ran check_env.
Commands run (exact) and result (real output, trimmed):
- `python --version` -> Python 3.14.6 (global; not used). `py -0` -> 3.14, 3.13, 3.12 present.
- `.venv312` did not exist. `py -3.12 -m venv .venv312` -> Python 3.12.10. `.\.venv312\Scripts\python.exe -m pip install -U pip` -> pip 26.2.1.
- `.\.venv312\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt` -> OK (deltalake 1.6.6, duckdb 1.5.6,
  pyarrow 25.0.1, pandas 3.0.6, numpy 2.5.3, pydantic 2.13.5, matplotlib 3.11.2, rich 15.0.0, pytest 9.1.1, ruff 0.16.10).
- `git --version` -> 2.54.0.windows.1. `git rev-parse --is-inside-work-tree` -> not a git repo yet.
- Optional tools present but NOT used by the demo: Java openjdk 21.0.12.1, Docker 29.6.2.
- `.env` already existed (not printed). WAREHOUSE_DIR=%USERPROFILE%\lineagerca_warehouse -> C:\Users\Kushal\lineagerca_warehouse (outside OneDrive, name OK).
- `.\.venv312\Scripts\python.exe scripts/check_env.py` -> "Summary: 23 OK, 4 WARN, 0 FAIL; READY". Delta time-travel smoke test:
  "version 0 has 3 rows, latest has 4, DuckDB sum on old = 60.0".
Problems and how I fixed them: Activate.ps1 not used (called the venv python directly). The "ruff (dev tool)" WARN is only because
.venv312\Scripts is not on PATH when the venv python is called directly; ruff 0.16.10 is installed in the venv (run it as `.\.venv312\Scripts\ruff.exe`).
Other WARNs: pyiceberg, openlineage-python (stretch, not installed), no git repo yet.
Decisions (and why), design challenges to ARCHITECTURE.md found in Step 0:
1. Replay must pin the STAGE CODE VERSION used by the anomalous run, not only the input snapshots. Otherwise, in s2 (code fault: filter
   removed from `clean`), replaying the decoy re-runs the healthy current `clean` and falsely CONFIRMS the decoy. Run records get a `code_version` field (extension).
2. s2: the denied suspect is the decoy raw_fx_rates (raw_orders has no change commit in s2, so it is not shortlisted); fixes the table in ARCHITECTURE section 7.
3. Suspects come only from change commits (change_type != normal_load) after the day-D load; the pre-change snapshot is the version just before that commit.
4. run_demo runs seed 42 live; held-out seeds 1-5 are produced by runners/run_all and cached in results/.
Honest notes: replay cannot undo a fault in code that was never versioned; to be stated in the report.
Next: M1 (core + Delta store).
Git checkpoint printed: yes

### Entry 2 — 2026-10-05 — M1 Core + Delta store
What I did: core/{models,config,clock,rng,hashing}.py, configs/{pipeline,monitor,replay}.yaml, adapters/{delta_store,duck}.py,
tests/test_core.py, tests/test_delta_store.py. DeltaStore writes (append/overwrite), reads any version, keeps a logical-clock
SnapshotRecord per commit, and only deletes folders strictly inside a WAREHOUSE_DIR whose name ends with lineagerca_warehouse.
Commands run (exact) and result (real output, trimmed):
- `.\.venv312\Scripts\python.exe -m pytest` -> "9 passed in 1.05s"
- `.\.venv312\Scripts\ruff.exe check .` -> first run: 1 error (DTZ001 naive datetime in core/clock.py); fixed with tzinfo=utc; then "All checks passed!"
Problems and how I fixed them: a bash heredoc containing all files failed to parse (nothing written), so I created the files with the Write tool.
Also: DuckDB result is fetched with `.to_arrow_table()` (the older `fetch_arrow_table` name is avoided).
Decisions (and why): RunRecord (with code_version, the Step-0 fix) lives in core/models.py already. Thresholds (0.15, 0.05, 7 days,
3 repeats, 0.5, 0.02) were written into configs/ now, before any scenario exists, so they cannot be tuned to results.
Honest notes: none yet; no scenario data exists.
Next: M2 (data generator + pipeline, 10 healthy days).
Git checkpoint printed: yes

### Entry 3 — 2026-10-05 — M2 Pipeline + data generator
What I did: tasks/datagen.py (seeded SYNTHETIC customers / orders / FX rates, one random stream per day), tasks/stages.py (clean and
aggregate as pure DuckDB SQL with named code versions: clean_v1, clean_v2_no_filter (s2), aggregate_v1, aggregate_v2_sample (s6, unseeded
on purpose)), tasks/pipeline.py (load_day / run_clean / run_aggregate / run_day; every run returns a RunRecord with input snapshot ids and
code_version), tests/test_pipeline.py. adapters/duck.py now sets PRAGMA threads=1 so float sums are reproducible.
Commands run (exact) and result (real output, trimmed):
- `.\.venv312\Scripts\python.exe -m pytest` -> "16 passed in 8.51s"; `ruff check .` -> "All checks passed!"
- Scratch run of the real-size pipeline (seed 42, 2000 orders/day, 10 days; script in the temp folder, not in the repo):
  "seconds for 10 healthy days: 3.59"; raw_orders 20000 rows (versions 0..9); raw_customers 400; raw_fx_rates 30; cleaned_orders 16910;
  daily_revenue_agg 40 rows; daily revenue_usd per day [69293, 69826, 71548, 69927, 69820, 69420, 70096, 70899, 68825, 69853];
  cleaned rows per day [1667, 1674, 1707, 1703, 1684, 1702, 1687, 1700, 1682, 1704]. Healthy day-to-day variation is under 4%, far below the 0.15 threshold.
Problems and how I fixed them: none besides one edit with wrong indentation that I redid.
Decisions (and why):
- Orders with an unparseable amount are KEPT with amount=NULL (the amount > 0 filter only drops amounts that parse and are <= 0), so
  scenario s3 shows up as a null-rate rise and a revenue drop rather than rows silently vanishing.
- Stages are split (load_day / run_clean / run_aggregate) so that M4 can insert fault commits between the day-D load and the anomalous run.
  A scenario will do: load day 11, a healthy run (so the pre-change snapshot holds healthy day-11 data), change commits, then the anomalous run.
- cleaned_orders snapshot metric_value = rows of the latest day; daily_revenue_agg metric_value = revenue of the latest day.
Honest notes: the data is SYNTHETIC; nothing about real pipelines follows from these numbers.
Next: M3 (lineage store + monitor).
Git checkpoint printed: yes

### Entry 4 — 2026-10-05 — M3 Lineage store + monitor (and a redesign of the M2 stages)
What I did: adapters/lineage_store.py (graph, upstream_of, distances_upstream, path_stages, changes_since, inputs_of_run, last_run_of,
edges(), OpenLineage-style events(), save()), drift/monitor.py (day_metrics, Monitor.deviation/evaluate/check_store, primary_anomaly),
tests/helpers.py, tests/test_lineage_monitor.py.
Problems and how I fixed them (IMPORTANT, a design flaw of my own M2 code): the hand-made-fault test found NO anomaly. Cause: run_clean
recomputed the whole history from the raw tables, so a fault in raw_customers also rewrote days 1-10 and the baseline moved with the
fault (debug print: day 10 had 266 rows, day 11 had 243, and the monitor saw a 9% change). Fix: the stages now process ONE day (a partition)
and each commit replaces only that day's rows (DeltaStore.write(replace_where=...), Delta overwrite with a predicate). History stays
healthy; replay will also only need to recompute day D. Two further small bugs in the same edit (a double WHERE in the sampled aggregate
SQL; `==` on Arrow columns in a test) were found by the tests and fixed.
Commands run (exact) and result (real output, trimmed):
- `.\.venv312\Scripts\python.exe -m pytest` -> "23 passed in 17.21s"; `.\.venv312\Scripts\ruff.exe check .` -> "All checks passed!"
- Re-run of the full-size scratch check after the redesign (seed 42, 2000 orders/day): "seconds for 10 healthy days: 3.82"; table hashes
  identical to the pre-redesign run (raw_orders edce7d5021a6, cleaned_orders ae5e0772b7e7, daily_revenue_agg 4573f68cce12), so the
  same data is produced; "alarms on healthy days 1-10: 0"; max |relative deviation| on days 4-10: revenue 0.0158, row_count 0.0173
  (threshold 0.15).
Decisions (and why): see ARCHITECTURE.md section 14 (daily partitions, pinned code version, s2 suspects, suspect definition, incident
starts at the most downstream anomalous table, unparseable amounts kept as NULL). The monitor needs at least 3 previous days; with fewer it
does not check (days 1-3 are never judged).
Honest notes: s2 will be close to the threshold. Removing the cancelled/test filter adds about 15% of orders, which should move revenue by
about 17-18% (my estimate from the generator's status mix, NOT yet measured); it will be measured in M4 and reported as it comes out,
without changing sizes to make it comfortable.
Next: M4 (fault injectors and scenarios s1-s6).
Git checkpoint printed: yes

### Entry 5 — 2026-10-05 — M4 Faults + scenarios s1-s6
What I did: configs/scenarios.yaml (six scenarios with steps, deployed code versions, ground truth; fault sizes fixed BEFORE running:
decoy 1%, bad_join_key 30% of customers, type_coercion 40% of day-11 amounts), tasks/faults.py (bad_join_key, type_coercion,
benign_fx_refresh), tasks/scenarios.py (build_scenario returns IncidentContext = what investigators may see, and GroundTruth =
scoring only, kept separate), run_logging/jsonl.py (JSONL log, logical times only, written to results/runs/, git-ignored),
ScenarioSpec/ScenarioConfig in core/config.py, tests/test_scenarios.py. The dropped-filter fault is a code change: the clean step is
re-run with code version clean_v2_no_filter and that commit on cleaned_orders is the change commit.
Commands run (exact) and result (real output, trimmed):
- Exploratory run of all six scenarios, seed 42, default size (2000 orders/day), about 4.1-4.9 s per scenario. Monitor results for day 11
  (deviation vs the median of the previous 7 days; alarm if |relative| > 0.15, or null-rate increase > 0.05):
  s1: row_count -0.2565, revenue_usd -0.2607 -> alarms on both; investigation starts on daily_revenue_agg.
  s2: row_count +0.1653 (ALARM), revenue_usd +0.1458 (NO alarm, 0.0042 under the threshold) -> investigation starts on cleaned_orders.
  s3: amount_null_rate +0.4291, revenue_usd -0.4204, row_count +0.0118 -> alarms on null rate and revenue.
  s4: row_count +0.0094, revenue_usd -0.0039, null rates 0 -> monitor SILENT (as required).
  s5: row_count -0.1435 (no alarm), revenue_usd -0.1516 (ALARM, 0.0016 over the threshold) -> investigation starts on daily_revenue_agg.
  s6: row_count -0.2565, revenue_usd -0.3304 -> alarms on both (random 90% sample adds a bias and noise on top of the s1 fault).
- `.\.venv312\Scripts\python.exe -m pytest` -> "31 passed in 51.36s"; `.\.venv312\Scripts\ruff.exe check .` -> "All checks passed!"
Problems and how I fixed them: none in code. Findings below.
Decisions (and why):
- My Step-0/M3 estimate that s2 would move revenue by about 17-18% was WRONG (measured +14.58%; the fault adds cancelled/test orders but
  the zero-amount filter and order mix reduce the effect). I did NOT change any magnitude or the threshold. The monitor still alarms
  through the row-count check, so the incident is detected, but the investigation then starts on cleaned_orders, which is the true cause table
  itself. Consequence for M5: the suspect set must include the anomalous table when it has its own change commit, and replay must clear the
  metric that alarmed (row_count here). Written into ARCHITECTURE.md section 14.
- s5 only just alarms (-0.1516 vs 0.15). Reported as is; it is a boundary scenario.
Honest notes: detection of s2 and s5 depends on thresholds sitting a few thousandths away from the measured deviations. With another seed
they may not alarm; the held-out seeds (M6) will show how often. A related effect to look for in M5: rolling back a downstream suspect table
(cleaned_orders) to its pre-change snapshot also removes the effect of an upstream fault that was applied before it (s5), so a CONFIRMED
verdict means "rolling THIS table back clears the metric", not "only this table is guilty".
Next: M5 (shortlist, replay harness, baselines).
Git checkpoint printed: yes

### Entry 6 — 2026-10-05 — M5 Investigators (shortlist, replay, baselines)
What I did: agents/shortlist.py, agents/replay.py (rerun_once with pinned inputs and pinned code versions, decide_verdict,
replay_suspect with 3 repeats, replay_all, top_suspect), agents/baselines.py (B1 recency, B2 distance), drift/monitor.py split into
cleaned_metrics / revenue_metrics / metric_from_table so replay uses exactly the monitor's metrics and thresholds, tests/conftest.py
(session-scoped scenario fixtures), tests/test_agents.py. Baselines documented in ARCHITECTURE.md section 15.
Commands run (exact) and result (real output, trimmed):
- Exploratory run on all six scenarios, seed 42 (before writing the assertions):
  s1: suspects raw_customers, raw_fx_rates. raw_customers CONFIRMED (-0.261 -> -0.004); raw_fx_rates DENIED (-0.261 -> -0.263).
      replay top-1 raw_customers (correct); B1 raw_fx_rates (wrong, the decoy); B2 raw_fx_rates (wrong, tie on distance, decoy more recent).
  s2: incident starts on cleaned_orders (row_count). cleaned_orders CONFIRMED (+0.165 -> +0.009); raw_fx_rates DENIED (+0.165 -> +0.165).
      replay correct; B1 wrong (decoy); B2 CORRECT (cleaned_orders is closer than the decoy). So B2 is not fooled in s2.
  s3: raw_orders CONFIRMED (-0.420 -> -0.004); raw_fx_rates DENIED. Replay, B1 and B2 all pick raw_orders (fair comparison holds).
  s4: monitor silent, no suspects, no investigation.
  s5: cleaned_orders CONFIRMED (-0.152 -> -0.007); raw_customers CONFIRMED (-0.152 -> +0.146); raw_fx_rates DENIED. NOT PARTIAL as predicted.
  s6: raw_customers CONFIRMED (-0.337 -> -0.102, spread 0.007); raw_fx_rates DENIED (spread 0.013). NOT INCONCLUSIVE as predicted.
  Each replay of 3 repeats took about 0.07-0.18 s (reported only; it never influences a verdict).
- `.\.venv312\Scripts\python.exe -m pytest` -> "42 passed in 55.20s"; `.\.venv312\Scripts\ruff.exe check .` -> "All checks passed!"
Problems and how I fixed them: none in the logic. ruff flagged an import order (auto-fixed) and one RUF015 style nit in a test (fixed by hand).
Decisions (and why): replay judges the metric that alarmed (revenue_usd or row_count) against the monitor threshold, so an incident
and its replay are measured the same way. Replay recomputes only day D (partitions), keeping the baseline days from the live store.
HONEST NOTES (kept as they are; nothing was tuned):
1. s5 did NOT show PARTIAL. cleaned_orders was CONFIRMED because rolling back that table also drops the effect of the upstream customer
   fault applied before it (rollback of a downstream table masks upstream causes). raw_customers was CONFIRMED only because, after undoing
   it, the remaining dropped-filter fault leaves revenue at +0.146, which is 0.004 INSIDE the 0.15 threshold: the two faults roughly cancel
   in the revenue metric. The verdict says "no alarm", not "healthy". This is a limit of judging by threshold; with a different
   fault mix it would be PARTIAL or DENIED.
2. s6 did NOT show INCONCLUSIVE. The unseeded 90% sample is a fairly mild noise source here: the spread of the 3 repeats was 0.007 and
   0.013, under instability_tolerance 0.02 (fixed before any scenario ran). Replay's verdict happened to be right, but the replayed
   deviation is -0.102 because the sample bias (about -10%) remains: the repeat check did not detect the non-determinism at all.
   Also, s6 is not reproducible run to run: the anomalous run itself uses unseeded randomness, so its deviation was -0.323 in one build
   and -0.337 in the next (same seed). That is the point of the scenario but it means s6 numbers differ between runs.
3. A CONFIRMED verdict means "undoing THIS table's change clears the metric", not "this is the only guilty table" (see s5).
4. In s2 B2 (distance) is not fooled: the true cause is the table closest to the anomaly. B1 (recency) is fooled in s1 and s2. This
   weakens any claim that replay beats lineage-only: with this tiny DAG, B2 already ties replay in s2 and s3.
Next: M6 (metrics + runners, demo seed 42 and held-out seeds 1-5).
Git checkpoint printed: yes

### Entry 7 — 2026-10-05 — M6 Metrics + runners (seed 42 and held-out seeds 1-5)
What I did: metrics/scoring.py (IncidentResult, scoring against ground truth, healthy-day false-alarm count), metrics/summary.py (one row per
group, groups never pooled), runners/run_scenario.py (CLI: `python -m runners.run_scenario --scenario s1_bad_join_key --seed 42`),
runners/run_all.py, runners/console.py (rich table), config_hash() in core/config.py, DeltaStore.remove(), tests/test_metrics_runners.py.
Held-out discipline: no file in configs/ was edited after M4 (config hash stored in every result: d47f36ff9e6b; the held-out seeds 1-5
were run exactly once, here, and I changed nothing afterwards).
Commands run (exact) and result (real output, trimmed):
- `.\.venv312\Scripts\python.exe -m runners.run_all` -> 36 incidents (6 scenarios x seeds 42,1,2,3,4,5) in 2 min 55 s. Wrote results/incidents.jsonl
  and results/summary.csv. Summary (top-1 = counted over DETECTED faulty incidents; "n/m" = n correct of m):
  group             detected  replay  B1 recency  B2 distance  false confirms  replays/incident  replay s/incident
  seed42_main (s1-s4)   3/3     3/3      1/3         2/3           0/3              6.0              0.31      (control s4: 0/1 false alarms)
  seed42_boundary (s5,s6) 2/2   2/2      0/2         1/2           0/2              7.5              0.41
  heldout_main (s1-s4, seeds 1-5) 15/15  15/15  5/15  10/15        0/15              6.0              0.33      (control s4: 0/5 false alarms)
  heldout_boundary (s5,s6, seeds 1-5) 9/10 7/9  0/9   4/9          0/9              7.3              0.39
  Replay suspect-level precision 1.00 / recall 1.00 in both main groups; heldout_boundary precision 1.00, recall 0.538.
  Verdict counts heldout_main: CONFIRMED 15, DENIED 15. heldout_boundary: CONFIRMED 7, DENIED 13, PARTIAL 0, INCONCLUSIVE 2.
  Monitor: 0 false alarms on healthy days 4-10 across all 36 incidents; control s4 silent on all 6 seeds.
- `pytest -q` -> "48 passed in 69.10s"; `ruff check .` -> "All checks passed!"
Honest notes (nothing was tuned; the numbers are what they are):
1. Main scenarios: replay 15/15 on held-out vs B1 5/15 and B2 10/15. B1 fails in s1 and s2 (decoy more recent); B2 fails in s1 only (tie on
   distance, decoy more recent). s3 is the fair case where all three agree. The comparison is circular: we wrote the faults, the decoy
   placement and the method, and held-out seeds only change the random data, not the fault types. It shows the mechanism works on this
   tiny DAG, not general accuracy.
2. Boundary s5 (two causes): one of five held-out seeds was NOT detected by the monitor (seed 1; its deviation stayed under 0.15). Where detected,
   replay always blames cleaned_orders (a true cause, so scored correct) and CONFIRMS it, because rolling back that table also removes the
   upstream customer fault. raw_customers was CONFIRMED only at seed 42 (where its leftover deviation +0.146 sat just under the threshold) and
   DENIED in seeds 2-5 (leftover +0.176 to +0.190). So replay finds ONE of the two causes: recall 0.538 over the 13 true-cause slots is the
   honest number. The expected PARTIAL never happened (0 PARTIAL verdicts in all 36 incidents): the two faults push revenue in OPPOSITE
   directions, so removing one leaves a deviation of the other sign that is as large as the original.
3. Boundary s6 (non-deterministic aggregate): INCONCLUSIVE does occur now (2 held-out incidents, on raw_customers in seeds 1 and 4, so replay
   abstained there; and once on the decoy at seed 42), but in the other cases the repeats agreed within 0.02 and replay was right with a
   leftover -0.065 to -0.108 sampling bias. Replay top-1 on s6 held-out: 3 of 5 correct (2 abstentions). s6 is not reproducible between
   runs: at seed 42 the first build (M5 exploration) gave raw_customers CONFIRMED / decoy DENIED, this grid gave decoy INCONCLUSIVE.
4. B2 ties or beats B1 everywhere; its only blind spot in our scenarios is the tie in s1/s6. A real DAG with more tables at equal
   distance would hurt it more; ours has four.
5. Replay compute is tiny (about 0.33 s per incident, 6 replays) because the tables are tiny. The proposal's 30 minutes per incident is a
   full-scale estimate; do not compare the two.
Next: M7 (HTML report, PNG figures, CSV tables, demo/run_demo.py under 120 s).
Git checkpoint printed: yes

### Entry 8 — 2026-10-05 — M7 Report + one-command demo
What I did: demo/figures.py (lineage_<scenario>.png coloured by verdict; metric_<scenario>.png deviation before/after replay with the monitor
threshold band; the s4 control shows its four day-11 deviations), demo/findings.py (findings generated from the results, plus 8 fixed
limitations), demo/report.py (self-contained HTML, jinja2, images embedded, no network), demo/run_demo.py (seed 42 live, held-out read
from results/incidents.jsonl with a warning if missing or made with different configs), tests/test_demo.py.
Commands run (exact) and result (real output, trimmed):
- `.\.venv312\Scripts\python.exe demo/run_demo.py` -> "Finished in 31.6 s (limit 120 s)" (second run 31.4 s); offline. outputs/ holds demo_report.html
  (about 495 KB, 0 external URLs), 6 lineage_*.png, 6 metric_*.png, snapshots.csv, lineage_edges.csv, replay_verdicts.csv (all with source=synthetic),
  and the console prints the summary table with the four groups kept apart.
- `.\.venv312\Scripts\python.exe -m pytest` -> "52 passed in 106.49s"; `.\.venv312\Scripts\ruff.exe check .` -> "All checks passed!"
Problems and how I fixed them:
- Metric figure: legend covered a bar label and the y-axis clipped a bar; fixed (padding, legend below), checked by looking at the PNG.
- ruff ISC004 on the limitations list; wrapped each string in parentheses.
- Test isolation bug: test_demo's run_demo built and then deleted seed-42 Delta folders in the SAME warehouse folder as the session-wide
  `runs` fixture, which made a later test fail with TableNotFoundError. The demo tests now use their own warehouse folder.
- A wording bug in the findings ("capitalize()" would lowercase table names; "blames None"): fixed.
Decisions (and why): the demo does not run the held-out seeds (about 3 minutes, over the 120 s budget); it shows the cached results of
`python -m runners.run_all` and says clearly if they are missing or stale. Per-incident compute time is reported only.
Honest notes: s6 is not reproducible between runs even with the same seed (its anomalous run is unseeded on purpose). In the
M6 grid, seed-42 s6 gave raw_customers CONFIRMED (replay top-1 correct, boundary group 2/2); in the two demo runs of this session the
raw_customers replay was INCONCLUSIVE at least once (replay abstained, boundary group 1/2). So the seed42_boundary row printed by the
demo can differ from the seed42 rows stored in results/incidents.jsonl. This is by design and is stated in the report findings.
Next: M8 (quality gate: pytest, ruff, README quick start from a clean clone, held-out reported separately).
Git checkpoint printed: yes

### Entry 9 — 2026-10-05 — M8 Quality gate
What I did: ran every gate, found and closed small gaps, updated README, simulated a clean clone.
Commands run (exact) and result (real output, trimmed):
- `.\.venv312\Scripts\python.exe scripts/check_env.py` -> "Summary: 26 OK, 3 WARN, 0 FAIL; READY" (WARN: pyiceberg and openlineage-python are stretch
  only and not installed; ruff WARN is only because .venv312\Scripts is not on PATH when the venv python is called directly).
- `.\.venv312\Scripts\ruff.exe check .` -> "All checks passed!"
- `.\.venv312\Scripts\python.exe -m pytest` -> 53 tests collected, all passed (the final run prints dots only because pytest.ini already has -q).
- Coverage run (pytest --cov, before adding the last test): TOTAL 96% of 966 statements; every source module is exercised. Not covered: the two
  CLI main() functions (checked by hand instead), a few branches. I then added a test for the held-out loading path (stale-config warning,
  held-out findings sentence).
- Static scans: largest source file is 118 lines (scripts/check_env.py, provided at scaffold time, is 217); no print( in core, adapters,
  agents, drift, metrics, tasks, run_logging; `git check-ignore -v` confirms .env, .venv312/, outputs/* and results/runs/ are ignored and
  results/incidents.jsonl is tracked.
- README: added `ruff check .`, the single-scenario command, `python -m runners.run_all`, and a "What you get" section (no numbers in it).
- Clean-clone simulation: copied the sources to the scratchpad WITHOUT .env, .venv312, outputs/, logs/, results/runs, ran `copy .env.example .env`
  and then, with the existing .venv312 interpreter (the rules forbid installing packages anywhere else, so `pip install` itself was NOT re-run;
  it was verified in M0): check_env -> READY; `ruff check .` -> clean; `pytest -q` -> all passed; `python demo/run_demo.py` -> "Finished in 30.4 s
  (limit 120 s)", all 16 output files written, held-out table read from the tracked results/incidents.jsonl.
Problems and how I fixed them: in the copy check_env showed 1 FAIL ("`.venv312` is git-ignored") because the copy had no .venv312 folder and git
cannot match a directory-only pattern against a path that does not exist; creating the empty folder gave "26 OK, 3 WARN, 0 FAIL". It is a simulation
artifact (the README creates the venv first), not a .gitignore defect. The copy also contained the user's .git folder (harmless, in scratch only).
Decisions (and why): held-out seeds are reported separately in the console table, the HTML report and results/summary.csv (groups never pooled).
Honest notes: `pip install -r requirements*.txt` from a truly fresh machine was not re-run in this session beyond M0; the README steps after it were.
Next: M9 (docs/DEMO_SCRIPT.md and docs/VIVA_NOTES.md, real numbers only).
Git checkpoint printed: yes

### Entry 10 — 2026-10-05 — M9 Talk material
What I did: wrote docs/DEMO_SCRIPT.md (3-minute talk track with timings, what to show, fallbacks) and docs/VIVA_NOTES.md (60-second explanation,
suggested split of files among four students, results table, 18 likely questions with honest answers, "do not claim" list, limitations, how to reproduce).
Commands run (exact) and result (real output, trimmed):
- Re-read results/incidents.jsonl (36 incidents, one config hash d47f36ff9e6b) and computed the per-scenario held-out counts that the viva notes quote:
  held-out detected / replay / B1 / B2 correct: s1 5/5, 5, 0, 0; s2 5/5, 5, 0, 5; s3 5/5, 5, 5, 5; s4 0 alarms in 5; s5 4/5 detected, 4, 0, 4; s6 5/5 detected, 3, 0, 0.
- Re-checked the s1 numbers quoted in the script against results/incidents.jsonl: deviation -0.261; raw_customers CONFIRMED (-0.004); raw_fx_rates DENIED (-0.263).
Problems and how I fixed them: none.
Decisions (and why): the script quotes only numbers present in results/ or build_logs.md and tells the speaker to trust the screen for s6, which varies
between runs. Q14 (snapshot retention limits how far back replay can go) is a design caveat, not a measured result, and is labelled that way; no number given.
Honest notes: not measured and therefore not quoted: sensitivity to thresholds, full-scale compute cost, behaviour on a larger DAG, several faults on one table.
Next: all demo-critical milestones M0-M9 are done. Stretch items (Iceberg, Marquez, BugDoc-style baseline) are NOT started; ask the user first.
Git checkpoint printed: yes

### Entry 11 — 2026-10-05 — S3 (stretch, requested by the user): BugDoc-style parameter-replay baseline (B3)
What I did: agents/parameter_replay.py (code_config, parameter_replay, choose_blame), a small refactor of agents/replay.py (the shared `measure()`
routine, so replay and B3 are judged in exactly the same way), B3 fields in metrics/scoring.py (b3_blame, b3_correct, b3_executions, b3_seconds,
b3_notes), B3 columns in metrics/summary.py, runners/console.py and the HTML report, B3 sentences and one extra limitation in demo/findings.py,
tests/test_parameter_replay.py (8 tests), ARCHITECTURE.md section 15, docs/DEMO_SCRIPT.md and docs/VIVA_NOTES.md (numbers updated).
Design (written before running it on any held-out seed; B3 has no tunables): B3 is NOT BugDoc, only the idea restricted to the parameters this
pipeline has (stage code versions). It compares the code versions of the last healthy run with the anomalous run, reverts each subset of the
differing ones (smallest first), re-executes day D with all inputs pinned to what the anomalous run read, and uses replay's own decision rule,
thresholds and repeats. It does not use the shortlist, the lineage graph or any older snapshot (a test spies on every store read to prove it).
Commands run (exact) and result (real output, trimmed):
- Seed 42 development run first: s1 and s3 -> no parameter differs, B3 abstains; s2 -> reverting clean_v2_no_filter to clean_v1 gives +0.165 -> +0.009,
  CONFIRMED, blames cleaned_orders; s5 -> reverting the code makes it WORSE (-0.152 -> -0.261, the two faults partly cancel), abstains;
  s6 -> reverting the sampled aggregate leaves the data fault (-0.326 -> -0.261), abstains; s4 -> no alarm, nothing starts.
- `.\.venv312\Scripts\python.exe -m pytest` -> 61 passed in 114.49 s; ruff clean.
- `.\.venv312\Scripts\python.exe -m runners.run_all` (second full grid, with B3; 2 min 57 s, config hash still d47f36ff9e6b). Top-1 over detected incidents:
  seed42_main: replay 3/3, B1 1/3, B2 2/3, B3 1/3.  heldout_main: replay 15/15, B1 5/15, B2 10/15, B3 5/15 (B3 blamed 5, abstained 10, never wrong).
  seed42_boundary: replay 2/2, B1 0/2, B2 1/2, B3 0/2.  heldout_boundary: replay 9/9, B1 0/9, B2 4/9, B3 0/9 (detected 9/10).
  B3 wrong blames in all 36 incidents: 0. Controls silent 6/6. Healthy-day false alarms 0. B3 cost: 0 or 1 parameter tests, about 0.1 s.
- Reproducibility check between the first full grid (M6) and this one: replay top-1, B1, B2 and all verdicts were IDENTICAL for 32 of 36 incidents; the 4
  that differ are exactly s6 at seeds 42, 1, 2 and 4 (unseeded random step). First grid: s6 held-out replay 3/5 (INCONCLUSIVE on raw_customers at seeds 1
  and 4, replay abstained), boundary group 7/9 and replay recall 0.538 (7/13). Second grid: s6 5/5 (INCONCLUSIVE on the decoy raw_fx_rates at seeds 1 and 2),
  boundary group 9/9 and recall 0.692 (9/13). s5 is stable: replay finds 4 of 8 true-cause slots in both grids (always cleaned_orders, never raw_customers).
Decisions (and why): the docs now quote the second grid and say explicitly that s6 changes between runs; the Entry 7 numbers for s6 are superseded, not wrong
for that run. B3 abstains instead of guessing when nothing clears the anomaly, as a BugDoc-style search would report "no root cause found".
Honest notes: (1) B3 failing on data faults is by construction of its search space, not evidence about BugDoc. Real BugDoc could treat input datasets as
parameters; we did not build that variant because it would need alternative dataset versions, i.e. snapshots. (2) B3 matches replay only on s2, where the
fault is a versioned code change; that is the one scenario type we authored for it. (3) The held-out seeds 1-5 were already seen for the other methods;
B3 was run on them once, after being implemented, with nothing tuned. (4) The first grid's numbers for replay on s6 and the boundary group are no longer the
latest; both runs are reported in docs/VIVA_NOTES.md.
Next: nothing demo-critical is open. Remaining stretch items (Iceberg adapter S1, Marquez S2, TPC-H DAG plan S4) are not started; ask the user first.
Git checkpoint printed: yes

### Entry 12 — 2026-10-05 — S4 (stretch, chosen by the user): Semester 5-8 plan
What I did: wrote docs/SEM5_PLAN.md (plan only; no code, no installs, no downloads, no new results). It lists the weak spots our own runs exposed
(narrow alarms in s2 and s5, rollback masking in s5, weak noise detection in s6, small DAG, held-out seeds not types, no sensitivity or full-scale cost),
nine work packages (WP-A to WP-I) mapped onto the proposal's semesters, the stretch backlog with decisions, risks and the rules that stay in force.
Commands run (exact) and result: none besides writing the file; no tests were affected (docs only).
Decisions (and why): all times and sizes in the plan are marked as estimates. The TPC-H data generation through DuckDB's tpch extension needs a download, so the
plan says to ask before doing it. The plan quotes only facts already in this repo or in the proposal; TPC-H's eight table names are general knowledge, not a result.
Honest notes: nothing in the plan has been tried; WP-C (multi-cause replay) may not fix s5, and a bigger DAG may show no advantage over the distance rule.
Next: nothing demo-critical is open. S1 (Iceberg) and S2 (Marquez) remain, each needs the user's go-ahead (and an install or image download).
Git checkpoint printed: yes

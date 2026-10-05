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

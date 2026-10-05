# ARCHITECTURE.md — LineageRCA (what to build)

Source of truth for the idea: `../docs/LineageRCA — Counterfactual Replay for Data-Pipeline Root Cause Analysis.pdf`.
This file turns it into a build spec for the Review-1 demo. Where this file adds something the proposal does not
contain, it is marked **(extension)** so we can explain it honestly in the viva.

## 1. What the demo shows (one paragraph)

A synthetic mini pipeline runs for 10 healthy days, then on day 11 a fault is injected into ONE upstream table, plus a
harmless recent change to another table (a "decoy"). The data-quality monitor flags the daily revenue table. The
lineage graph gives a list of suspects. Baselines pick a culprit from the graph alone. The replay harness re-runs the
downstream steps for each suspect with that table at its pre-change snapshot and returns CONFIRMED or DENIED. The report
shows who was right, using the injected fault as ground truth. Everything is labelled SYNTHETIC.

## 2. Pipeline of the system (5 stages, matches the proposal diagram)

```
Fault injector (test only)
        |
 1. Pipeline + snapshots   -> tasks/, adapters/delta_store.py   (Delta tables, every commit readable)
 2. Lineage capture        -> adapters/lineage_store.py          (who feeds whom, which snapshots each run read)
 3. Data-quality monitor   -> drift/monitor.py                   (flags the anomaly, starts the investigation)
 4. Replay harness (NEW)   -> agents/replay.py (+ agents/baselines.py for comparison)
 5. Verdict report         -> metrics/, demo/report.py           (CONFIRMED / DENIED per suspect, compute cost)
```

## 3. The synthetic pipeline (tasks/pipeline.py, tasks/datagen.py)

Delta tables on local disk (`WAREHOUSE_DIR`, outside OneDrive). Source tables (raw) and derived tables:

| Table | Kind | Columns (suggested) |
| --- | --- | --- |
| `raw_orders` | source, append per day | order_id, customer_id, product, amount (decimal as string at source), quantity, status, currency, order_date |
| `raw_customers` | source | customer_id (like `C0001`), region, segment |
| `raw_fx_rates` | source, refreshed daily | currency, rate_to_usd, rate_date |
| `cleaned_orders` | derived | orders without `cancelled`/test status and amount > 0, `amount` cast to number, joined to customers (inner join on customer_id) and converted to USD with fx rates |
| `daily_revenue_agg` | derived | one row per order_date and region: revenue_usd, order_count |

Lineage graph (edges upstream -> downstream):
`raw_orders -> cleaned_orders`, `raw_customers -> cleaned_orders`, `raw_fx_rates -> cleaned_orders`, `cleaned_orders -> daily_revenue_agg`.
So an anomaly in `daily_revenue_agg` has 4 upstream suspects (the proposal expects about 5 per incident; 4 is fine for a toy DAG).

Stages are PURE functions of their input tables: `cleaned_orders = clean(raw_orders, raw_customers, raw_fx_rates)` and
`daily_revenue_agg = aggregate(cleaned_orders)`, implemented as DuckDB SQL over Arrow tables read from Delta.
No wall-clock time, no random numbers, no external calls (except scenario s6, see section 7). This is a scoping decision, stated openly.

Data size: about 2,000 orders per day, 10 healthy days then the incident day (about 22,000 rows total). Small on purpose,
the demo must run in under 2 minutes. Sizes live in `configs/pipeline.yaml`.

### Snapshots, logical time and "like for like" (the key design decision)
- Tables are cumulative (each day appends). Every commit creates a Delta version (snapshot). We keep our OWN logical
  commit timestamps (a simulated clock that moves 1 minute per commit) in the snapshot table, because Delta's real commit
  times are wall-clock and would not be reproducible.
- Day D (the incident day) has a normal load commit, then **change commits** may rewrite parts of day D's data in an
  upstream table (a fault, or a benign decoy). Therefore the snapshot just before a fault commit contains the SAME day-D
  data in healthy form, which is what makes a fair counterfactual possible.
- The anomalous pipeline run (run D) reads specific snapshot ids of its inputs. They are recorded as lineage
  (**extension**: `input_snapshots` on the run record, needed to pin inputs during replay).

## 4. Lineage capture (adapters/lineage_store.py)

Hand-built JSON lineage in OpenLineage-style events (the proposal allows this fallback; Marquez/Docker is a stretch only).
One event per pipeline run: run_id, stage (transform_id), input tables with snapshot ids, output table with snapshot id, logical time.
The store answers: `upstream_of(table)` (transitive), `changes_since(table, logical_time)`, `inputs_of_run(run_id)`.

## 5. Data-quality monitor (drift/monitor.py)

Deterministic checks on the latest day versus the median of the previous 7 days (all taken from the same output table):
- row count of `cleaned_orders` for the day (relative deviation),
- revenue_usd per day in `daily_revenue_agg` (relative deviation),
- null rate of `amount` and `region` in `cleaned_orders` (absolute increase).
Default alarm threshold: relative deviation > 0.15 (`configs/monitor.yaml`). Output: `Anomaly(incident_id, table, metric, observed, expected, deviation)`.
The monitor must stay SILENT on the healthy days and on scenario s4. Count monitor false alarms as a metric.

## 6. The investigators (agents/)

All investigators receive the same `Anomaly` and the same lineage store, and return a ranked list of suspect tables with a verdict or score.

1. **Shortlist (shared first step)**: walk upstream from the anomalous table; keep tables with at least one change commit after
   the last healthy run and before the anomaly (within `shortlist_window_commits`). Typically 1-4 suspects.
2. **Replay harness (`agents/replay.py`, our contribution)** for each suspect S:
   - build a replay plan: the stages on the path from S to the anomalous table, in order;
   - read S at its pre-change snapshot; read EVERY other input at the snapshot the anomalous run used (pinned);
   - re-execute the stages with the CURRENT stage code; compute the same monitor metric for day D; repeat `replay_repeats` = 3 times;
   - decide with the same thresholds as the monitor:
     - **CONFIRMED**: replayed metric is back within threshold (anomaly cleared);
     - **DENIED**: replayed metric is still anomalous (deviation reduced by less than `partial_min_reduction`);
     - **PARTIAL (extension)**: not cleared but deviation reduced by at least `partial_min_reduction` (0.5): a contributing cause;
     - **INCONCLUSIVE (extension)**: the 3 repeats disagree by more than `instability_tolerance` (the transform is not deterministic, so replay is not trustworthy).
   - record compute seconds and number of replays.
3. **Baseline B1 `lineage_recency`**: rank shortlisted suspects by most recent change commit; blame the top one. Represents "the most
   recently changed upstream table is the likely cause" (the lineage-correlation pattern in the proposal).
4. **Baseline B2 `lineage_distance`**: rank by graph distance to the anomalous table (closest first), ties broken by recency.
5. **(Stretch) B3 `parameter_replay`** BugDoc-style: vary pipeline parameters instead of snapshots. Not for Review 1.

Replay never reads the ground truth. Ground truth is used only by `metrics/` to score verdicts.

## 7. Fault scenarios with ground truth (tasks/, configs/scenarios.yaml)

Each scenario: a healthy history (days 1-10), day-11 load, then change commits. `decoy` = a benign refresh of `raw_fx_rates`
(rates move by about 1%, within normal variation), placed AFTER or BEFORE the real fault.

| Id | Name | What goes wrong | True cause table | Decoy | What a correct system does |
| --- | --- | --- | --- | --- | --- |
| s1 | `bad_join_key` | `raw_customers.customer_id` loses its prefix/case so the join drops about 30% of orders | `raw_customers` | after (most recent) | replay CONFIRMS `raw_customers`, DENIES the decoy; B1 blames the decoy |
| s2 | `dropped_filter` | the `cancelled`/test-order filter is removed from the `cleaned_orders` step, so extra rows flow in | `cleaned_orders` | after | replay CONFIRMS `cleaned_orders`, DENIES `raw_orders`; B1 blames the decoy |
| s3 | `type_coercion_latest` | `raw_orders.amount` switches format (e.g. `1,234.50` strings), cast silently gives nulls/zeros | `raw_orders` | before (fault is the most recent change) | replay CONFIRMS `raw_orders`; B1 and B2 also succeed (fair comparison, shows replay does not "win" by construction) |
| s4 | `control_no_fault` | only the benign decoy; metrics stay in range | none | before | monitor stays silent, no investigation |
| s5 | `two_causes` | s1 and s2 faults together | `raw_customers` AND `cleaned_orders` | after | each replay alone only reduces the deviation: expected PARTIAL for both (boundary test, report what happens) |
| s6 | `nondeterministic_transform` | a downstream step uses a random 90% sample (unseeded), plus a real fault as in s1 | `raw_customers` | after | replay repeats disagree: expected INCONCLUSIVE. This is the known breaking point (research question 2); show it, do not hide it |

Fault magnitudes and the monitor threshold are fixed in config BEFORE running held-out seeds. s5 and s6 are the "boundary"
scenarios and are reported separately from s1-s4.

## 8. Data model (pydantic; mirrors the three tables in the proposal, plus marked extensions)

- **SnapshotRecord**: snapshot_id (Delta version), table_name, committed_at (logical), change_type (normal_load / fault name / benign_refresh), row_count, metric_value.
- **LineageEdge**: upstream_table, downstream_table, transform_id, run_id, lineage_source, **(extension)** upstream_snapshot_id used by the run.
- **ReplayVerdict**: incident_id, suspect_table, suspect_snapshot_id (pre-change), replay_runs, anomaly_cleared, verdict, ground_truth_cause (scoring only), compute_seconds, **(extension)** deviation_before, deviation_after, explanation.
- **Anomaly**: incident_id, table, metric, observed, expected, deviation, logical_time.

## 9. Outputs (demo/run_demo.py writes these into `outputs/`)

- `demo_report.html` (self-contained, offline, no CDN): banner "SYNTHETIC data, real time-travel replay"; a "Read this first" box;
  1 summary table (seed 42: top-1 correct for replay / B1 / B2, false confirms, compute seconds), 2 held-out seeds table (separate), 3 findings
  in plain language (generated from the run, including cases where replay failed or baselines tied), 4 one card per scenario
  (lineage graph with suspects coloured by verdict, metric before / after replay), 5 limitations.
- `lineage_<scenario>.png` (graph with verdicts), `metric_<scenario>.png` (observed vs expected vs replayed).
- CSV: `snapshots.csv`, `lineage_edges.csv`, `replay_verdicts.csv`, all with `source=synthetic`.
- Console: a `rich` summary table.

## 10. Metrics (metrics/)

- **Top-1 root-cause accuracy** per method (replay: the single CONFIRMED suspect, or the one with the largest deviation reduction; B1/B2: their blamed table).
- **Suspect-level precision / recall** of replay (CONFIRMED vs the true cause set), and of the baselines' blame.
- **False-confirm rate**: CONFIRMED verdicts on non-causes (must be reported even if it is 0).
- **Compute cost**: replays and seconds per incident (the proposal estimates about 30 minutes per incident at full scale; ours is a toy).
- **Monitor**: detection on faulty scenarios, false alarms on healthy days and s4.
- Held-out: seeds 1-5 for s1-s6; the demo seed 42 is reported separately.

## 11. Testing (tests/)

- Time travel: reading a table at version k returns exactly the rows committed up to k.
- Determinism: same seed gives identical content hashes for every table; stages are pure.
- Monitor: silent on healthy days, fires on each injected fault, with deviation numbers.
- Replay: pinned inputs are used (test with a fake lineage); CONFIRMED on a clean single fault, DENIED on a decoy.
- Baselines: B1 blames the most recent change; B2 blames the closest table.
- Scenarios: ground truth recorded and never read by the investigators (test that investigators work when ground truth is deleted).
- End to end: `run_demo.py` produces all outputs (mark `slow`).

## 12. Stretch (only after the demo milestones, and ask first)

- S1 Iceberg adapter (`pyiceberg` with a local SQL catalog), same tests as the Delta store.
- S2 Real OpenLineage events and Marquez (needs Docker, ask first).
- S3 BugDoc-style parameter-replay baseline (B3).
- S4 Semi-realistic DAG from TPC-H data and mild non-determinism study (Semester 7 in the plan).

## 13. Known limitations (must appear in the report)

- Synthetic data and authored faults: results show the MECHANISM works under pure deterministic transforms, not real-world accuracy.
- Evaluation is partly circular (we wrote the faults and the method); mitigated by fixed thresholds, held-out seeds and boundary scenarios.
- Replay is not a clean counterfactual for non-deterministic, incremental or side-effecting transforms.
- One DAG, five tables, six scenarios: too small for statistical claims.
- Novelty is narrow: replay itself exists (BugDoc, Newt, aaiclick); our claim is lakehouse time travel plus lineage shortlisting plus evaluation.
- Real-company pipelines are out of scope (no access).

## 14. Design changes made during the build (added 2026-10-05, honest record)

- **Daily partitions.** Derived tables are partitioned by day: a stage run replaces only that day's rows (Delta overwrite with a
  predicate). A first version recomputed the whole history, so a fault in `raw_customers` corrupted days 1-10 as well and the
  monitor's baseline moved with it. That was found by a failing test, not by design.
- **Pinned code version.** Each run record stores `code_version`; replay re-runs stages with the code version the anomalous run used.
  Without it, replaying a decoy in s2 would re-run the healthy code and falsely CONFIRM the decoy.
- **s2 suspects.** `raw_orders` has no change commit in s2, so it is not shortlisted; the denied suspect is the decoy `raw_fx_rates`.
- **Suspects** come only from change commits (`change_type != normal_load`) after the day-D load; the pre-change snapshot is the
  version just before that commit.
- **Incident start.** The investigation starts from the most downstream anomalous table (`daily_revenue_agg` first) and replay
  must clear the metric that alarmed. The anomalous table itself is a suspect when it has its own change commit: in s2 only the
  `cleaned_orders` row-count check alarms (revenue is +0.1458, just under 0.15), so the incident starts ON `cleaned_orders`, which
  is also the true cause. Rolling a suspect table back to its pre-change snapshot is then the replay (no stage re-run if the suspect
  is the anomalous table).
- **Unparseable amounts** are kept with `amount = NULL` (visible in the null rate) instead of being dropped.

## 15. Exactly what each investigator does (as implemented in agents/)

- **Shortlist (shared by all three):** suspects = the anomalous table itself plus every table upstream of it that has at least one
  change commit (`change_type != normal_load`) after the last healthy run and within `shortlist_window_commits` commits of the anomaly.
  Pre-change snapshot = the version just before that table's FIRST change commit in the window.
- **Replay:** reads the suspect at its pre-change snapshot; re-runs only the stages on the path from the suspect to the anomalous table;
  every other input is read at the snapshot the anomalous run used and every stage uses the code version that run used; repeats
  `replay_repeats` times; judges the metric that alarmed with the monitor's own threshold. Verdict order: INCONCLUSIVE if the repeats
  differ by more than `instability_tolerance`; else CONFIRMED if the metric is back inside the threshold; else PARTIAL if the deviation
  fell by at least `partial_min_reduction`; else DENIED. Replay's single blame (`top_suspect`): CONFIRMED before PARTIAL, then the biggest
  deviation reduction, then the smallest remaining deviation, then table name; no blame if everything is DENIED or INCONCLUSIVE.
- **B1 lineage_recency:** among the shortlisted suspects, blame the one with the most recent change commit (ties: table name).
- **B2 lineage_distance:** blame the suspect closest to the anomalous table in the lineage graph (distance 0 = the anomalous table
  itself); ties go to the most recent change, then table name.
- Both baselines see exactly the same shortlist as replay, use no re-execution, and never see ground truth. They are the strongest
  simple lineage-only rules we can defend; a baseline that looked at the size of each table's change would need data access and is out of scope.

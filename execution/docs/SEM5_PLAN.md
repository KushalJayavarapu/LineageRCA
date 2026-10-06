# SEM5_PLAN.md - what comes after the demo (plan only, nothing here is built or measured yet)

This is a plan. Every time or size below is an ESTIMATE, not a measurement. The only measured numbers in this repo are in
`results/` and `build_logs.md`. The proposal in `../docs/` gives the semester split; this file adds what OUR demo taught us.

## 1. Where we stand (facts from the demo)
- Built and working: Delta snapshot store, synthetic 5-table pipeline, lineage store, monitor, six scenarios (s1-s6), replay harness,
  three baselines (lineage recency, lineage distance, BugDoc-style parameter replay), metrics, report, one-command demo.
- Weak spots we found ourselves (each one drives a work package below):
  1. s2 and s5 alarm only narrowly (revenue +0.1458 and -0.1516 against a 0.15 threshold at seed 42); one held-out s5 incident was missed.
  2. Replay finds only one of two causes when a downstream table is rolled back (s5): rollback masks upstream causes.
  3. Our repeat check catches only strong noise (s6); the sampling bias stayed hidden when the repeats agreed.
  4. The DAG has only four upstream tables, so a lineage-distance rule is hard to fool; we cannot say how replay compares on a bigger DAG.
  5. Held-out seeds change the data, not the fault TYPES; the proposal asks to hold out types.
  6. No threshold sensitivity analysis, no full-scale compute measurement, no snapshot-retention study.

## 2. Plan by semester (aligned with the proposal)

### Semester 5 (this one): finish and defend the demo
- Done: M0-M9 and the BugDoc-style baseline. Remaining: rehearse `docs/DEMO_SCRIPT.md`, each student reads their files (`docs/VIVA_NOTES.md` section 2).
- Optional if time allows: WP-A below (sensitivity) because it is cheap and answers the most likely viva question.

### Semester 6: the full scenario suite and proper evaluation (proposal: 20 scenarios, baselines, precision/recall)
- **WP-A threshold and fault-size sensitivity.** Sweep the monitor threshold and the fault magnitudes over a grid, report detection rate and replay
  accuracy per cell. Fixes weak spot 1 and 6. Rule stays: thresholds for the headline results are chosen BEFORE the held-out run.
- **WP-B grow to about 20 scenarios** across fault TYPES (bad join key, dropped filter, type coercion, duplicated rows, late data, schema rename,
  unit change, ...), and HOLD OUT whole types, not only seeds (weak spot 5). Tune nothing on the held-out types.
- **WP-C multi-cause replay.** Add replay of suspect PAIRS and an "undo only this table's own change" variant to separate causes that rollback
  merges (weak spot 2). Report whether it fixes s5 or just trades one failure for another.
- **WP-D statistics.** More seeds per scenario (the proposal's compute estimate is about 10 hours for 20 scenarios at full scale; ours is far
  smaller), confidence intervals, and a clear statement of which differences are not significant.
- **WP-E baseline B3 extension.** A variant where input dataset VERSIONS are also parameters, to show how much of replay's advantage is the snapshot substrate.

### Semester 7: realism and the breaking point (proposal: mild non-determinism, incremental steps, TPC-H DAG)
- **WP-F semi-realistic DAG from TPC-H.** TPC-H has 8 tables (region, nation, supplier, customer, part, partsupp, orders, lineitem). Build a
  multi-stage pipeline from a subset (for example revenue per nation and per customer segment, joins across 4-6 tables) with the same fault injectors.
  Goal: test weak spot 4. Note: DuckDB can generate TPC-H data through its `tpch` extension, which has to be downloaded the first time, so ASK before
  doing it; pick a small scale factor and measure the size before committing to it.
- **WP-G non-determinism study.** Make the noise level a parameter (for example sample fraction 99%, 95%, 90%, 50%; seeded vs unseeded; timestamps in
  output) and measure where the repeat check starts to flag INCONCLUSIVE and where replay's verdict flips. Includes a second check, for example comparing
  repeats to the original anomalous run, to expose the hidden sampling bias (weak spot 3).
- **WP-H incremental steps.** One incremental or stateful transform, to see how far "pure batch" can be relaxed. Expect replay to break; the value is a
  clear statement of where.
- **WP-I snapshot retention and cost.** Study how far back replay can go when old files are cleaned up, and measure real compute at a larger scale
  (we measured only toy sizes).

### Semester 8: write-up
- Workshop or student-conference paper (the proposal expects workshop level, not top tier). Claim stays narrow: native lakehouse time travel as the replay
  substrate, guided by lineage shortlisting, aimed at data-quality root causes, with an honest evaluation including where it fails.

## 3. Stretch items from the demo backlog (not started, ask before each)
| Item | What | Needs | Decision |
| --- | --- | --- | --- |
| S1 | Iceberg adapter with the same store tests | `pip install pyiceberg` into `.venv312` | ask first |
| S2 | Real OpenLineage events and Marquez | Docker images (size to be checked) | ask first |
| S3 | BugDoc-style baseline | nothing | DONE (restricted version, see ARCHITECTURE.md section 15) |
| S4 | This plan | nothing | DONE |

## 4. Risks and how we handle them
| Risk | Handling |
| --- | --- |
| Evaluation stays circular (we write faults and method) | hold out fault types (WP-B), report limits in every document, never tune on held-out data |
| Bigger DAG shows replay no better than the distance rule | report it; that is a valid result |
| Replay breaks on non-determinism earlier than expected | that is research question 2; WP-G measures where, not whether |
| Time travel needs old snapshots | WP-I; state the retention assumption explicitly |
| Four students, uneven load | keep the file split from `docs/VIVA_NOTES.md` section 2; each work package has one owner and a test |
| Scope creep | work packages are ordered; nothing starts before the previous one has tests and a build-log entry |

## 5. Rules that stay in force
Everything labelled SYNTHETIC; fixed seeds; logical clock inside data and metadata; thresholds fixed before held-out runs; no number in a document unless
it came from a run we executed and logged; baselines implemented in good faith; no LLM or ML in the core method; the git repository is changed only by the team.

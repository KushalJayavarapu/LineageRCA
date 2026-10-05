# VIVA_NOTES.md - LineageRCA: likely questions, honest answers, limits

Numbers quoted here come from `results/incidents.jsonl` and `results/summary.csv` (36 incidents, config fingerprint `d47f36ff9e6b`) and
from `build_logs.md`. If a number is not in those files, we did not measure it and we say so.

## 1. The 60-second explanation
When a data-quality monitor fires, we shortlist upstream tables that changed shortly before (using the lineage graph), then for each
suspect we re-run the downstream steps with that one table read at its snapshot from BEFORE the change (Delta time travel), every
other input pinned to what the anomalous run used, and the same code version. If the alarming metric returns inside the monitor's
threshold the suspect is CONFIRMED, if not DENIED (PARTIAL and INCONCLUSIVE are our extensions). Two baselines use only the lineage
graph: most recent change, and closest table. All data and faults are SYNTHETIC; the time travel and re-execution are real.

## 2. Who explains what (suggested split, four students)
| Student | Files they should be able to walk through |
| --- | --- |
| A: data and pipeline | `tasks/datagen.py`, `tasks/stages.py`, `tasks/pipeline.py`, `core/rng.py`, `core/clock.py`, `core/hashing.py` |
| B: storage, lineage, monitor | `adapters/delta_store.py`, `adapters/duck.py`, `adapters/lineage_store.py`, `drift/monitor.py`, `core/models.py` |
| C: investigators | `agents/shortlist.py`, `agents/replay.py`, `agents/baselines.py` |
| D: scenarios, metrics, report | `tasks/faults.py`, `tasks/scenarios.py`, `configs/*.yaml`, `metrics/*`, `runners/*`, `demo/*` |

## 3. Results we can quote (all SYNTHETIC)
| Group (never pooled) | Monitor detected | Top-1 replay | Top-1 B1 recency | Top-1 B2 distance | False confirms |
| --- | --- | --- | --- | --- | --- |
| seed 42, s1-s4 | 3/3 | 3/3 | 1/3 | 2/3 | 0/3 |
| held-out seeds 1-5, s1-s4 | 15/15 | 15/15 | 5/15 | 10/15 | 0/15 |
| held-out seeds 1-5, s5-s6 (boundary) | 9/10 | 7/9 | 0/9 | 4/9 | 0/9 |
- Top-1 is counted over DETECTED faulty incidents; detection is shown beside it so a missed alarm is not hidden.
- Controls (s4): the monitor stayed silent in all 6 runs. Healthy days: 0 false alarms in all 36 incidents.
- Per scenario, held-out (replay / B1 / B2 correct out of detected): s1 5/0/0 of 5; s2 5/0/5 of 5; s3 5/5/5 of 5; s5 4/0/4 of 4 (seed 1 was not
  detected); s6 3/0/0 of 5.
- Boundary group replay recall: 7 of 13 true-cause slots, precision 1.00 (so replay never CONFIRMED a non-cause in our runs).
- Compute: about 6 replays and about 0.33 s per main-scenario incident. Tiny because the tables are tiny. The proposal's "about 30 minutes
  per incident" is its own full-scale estimate (5 suspects x 3 replays x about 2 minutes); we did NOT measure anything like it.

## 4. Likely questions and honest answers

**Q1. Is replay new?** No. BugDoc (varies pipeline parameters), Newt (lineage-based replay for Hadoop), aaiclick (re-runs a pipeline) exist.
Our narrow claim: native lakehouse snapshots as the replay mechanism, guided by lineage shortlisting, for data-quality root causes, evaluated
against lineage-only baselines. "Open as far as we found" is not "proven empty"; Google Scholar was not searched.

**Q2. Why synthetic data?** We have no access to a real pipeline, and we needed faults with a known true cause to score anything. The consequence
is that results show the mechanism works under pure deterministic transforms, not real-world accuracy.

**Q3. Isn't your evaluation circular?** Partly, yes. We wrote the faults, the decoy placement and the method. Mitigations: thresholds and fault sizes
fixed in `configs/` before the held-out seeds were run (config fingerprint stored in every result), held-out seeds reported apart from seed 42,
boundary scenarios reported apart from the main ones, baselines implemented in good faith. Held-out seeds change the random data, not the types of
fault, so they do not remove the circularity.

**Q4. Replay got 15/15 and B1 only 5/15. Does replay beat lineage?** On this toy DAG, against a recency rule, yes; against the distance rule the gap is
smaller (10/15), and in s3 (the fault is the latest change) all methods tie by design. With only four tables a distance rule is hard to fool; a bigger
DAG would hurt it more, but we have not measured that. Do not claim more than "replay was never fooled by a more recent harmless change".

**Q5. What exactly does CONFIRMED mean?** Undoing THIS table's change brings the alarming metric back inside the monitor's threshold. It does not
prove no other table is also guilty (see s5).

**Q6. Why do you pin the code version?** Scenario s2 is a code fault (the filter removed from the clean step). If replay re-ran the CURRENT healthy
code for the decoy table, the filter would come back and the anomaly would clear, so the decoy would be wrongly CONFIRMED. So every run record stores
`code_version` and replay uses the version the anomalous run used. Consequence: replay cannot isolate a code fault that was never versioned.

**Q7. Why daily partitions?** My first version recomputed the whole history on every run. A failing test showed that a fault then also rewrote days 1-10,
so the monitor's baseline moved with the fault and nothing alarmed. Now each run replaces only that day's rows. (Logged in `build_logs.md` Entry 4.)

**Q8. s2: the monitor nearly missed it. Why?** Revenue moved +0.1458 against the 0.15 threshold, so only the row-count check alarmed (+0.1653). Our own
early estimate (17-18%) was wrong. We did not change sizes or thresholds. The incident therefore started on `cleaned_orders`, which is the cause itself;
that is why the suspect set includes the anomalous table when it has its own change commit.

**Q9. s5 (two causes): what happened?** On seed 42 and held-out seeds where it was detected, replay always CONFIRMED `cleaned_orders` (a true cause)
because rolling that table back also removes the upstream customer fault applied before it. `raw_customers` was CONFIRMED only at seed 42, where its
leftover deviation (+0.146) was 0.004 inside the 0.15 threshold; it was DENIED in seeds 2-5. We expected PARTIAL verdicts; there were 0 in all 36 incidents,
because the two faults push revenue in opposite directions. One of five held-out seeds was not detected by the monitor at all.

**Q10. s6 (non-deterministic step): what happened?** Replay sometimes returned INCONCLUSIVE (it abstained twice on the held-out seeds), but often the
repeats agreed within the 0.02 tolerance and replay was right while still carrying a sampling bias of about 6-11% in the replayed deviation. So our
repeat check detects strong noise only. s6 is also not reproducible between runs, even with the same seed, because its anomalous run is unseeded on purpose.

**Q11. Why 3 repeats and these thresholds?** 3 repeats comes from the proposal. Thresholds (0.15 relative, 0.05 null-rate, 0.5 partial, 0.02 instability)
are simple, round values written into `configs/` before running scenarios. They were not tuned. We did not run a sensitivity analysis, so we cannot say
how results change with them.

**Q12. Why no machine learning or LLM?** To keep the monitor, shortlist and replay deterministic and explainable. An LLM could rank suspects later; it is not
needed for the claim.

**Q13. Why Delta and DuckDB, not Spark or Iceberg?** They run on a laptop with `pip install`, no Java, no Docker, no network. Iceberg is a planned stretch.
Time travel exists in both.

**Q14. What about real systems: retention and cost?** Time travel works only while old snapshots are kept; cleaning up old files limits how far back replay
can go. A real replay re-runs real transforms on big tables and costs real compute; we only measured a toy (about 0.33 s per incident).

**Q15. Which transforms can replay handle?** Pure, deterministic, batch transforms. Not streaming, incremental, side-effecting or random ones (s6 shows the
last case).

**Q16. How do you know the baselines are not strawmen?** Each is the best simple lineage-only rule we can defend, with the same shortlist as replay; both
are documented in `ARCHITECTURE.md` section 15. B2 actually beats B1 everywhere and ties replay in s2 and s3. The proposal also wants a BugDoc-style
parameter-replay baseline; we did not build it (planned stretch S3).

**Q17. What is in the lineage store?** Hand-built OpenLineage-style JSON events: one per run with input and output snapshot ids, the transform id and the code
version. No Marquez or Docker.

**Q18. What happens with several faults on the same table?** The shortlist uses the version just before the FIRST change commit in the window as the
"healthy" snapshot, so replay undoes all changes of that table. We tested only single changes per table per scenario.

## 5. Do NOT claim
- That the results generalise to real pipelines, or give a "percent accuracy" for real use.
- That replay is a new idea, or that no one has used snapshots for this ("open as far as we found").
- That CONFIRMED proves the other tables are innocent.
- Any compute cost for full scale; we measured only the toy.
- That s5 shows PARTIAL or that s6 always shows INCONCLUSIVE; neither is what happened.

## 6. Known limitations (also in the report)
Synthetic data and authored faults; partly circular evaluation; one DAG with five tables and six scenarios (no statistical claims); replay is a clean
counterfactual only for pure, deterministic, batch transforms; downstream rollback can mask upstream causes; code faults need versioned code; detection of
s2 and s5 sits close to the threshold; no sensitivity analysis; no BugDoc-style baseline yet; held-out seeds do not vary the fault types.

## 7. How to reproduce
`python demo/run_demo.py` (about 31 s) for seed 42; `python -m runners.run_all` (about 3 minutes) for seeds 42 and 1-5, which rewrites
`results/incidents.jsonl` and `results/summary.csv`; `python -m runners.run_scenario --scenario s1_bad_join_key --seed 42` for one scenario.
Expect s6 to differ between runs; everything else is deterministic from the seed.

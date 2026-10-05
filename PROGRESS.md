# PROGRESS.md — LineageRCA build tracker

Claude Code: update this file at the end of every milestone (tick the box, add the date and one line). Order matters.
Everything marked **[DEMO]** must be done before anything marked **[STRETCH]**.

Last updated: 2026-10-05 (M5 done)

## Current status
- M0-M5 done. Next: M6.
- This is the BACKUP idea. The main idea (CascadeGuard) lives in a separate folder.

## Demo-critical milestones

- [x] **M0 [DEMO] Environment ready** — venv `.venv312`, `pip install -r requirements*.txt`, `python scripts/check_env.py` green (includes a Delta time-travel smoke test). (~20 min) — done 2026-10-05: 23 OK, 0 FAIL, time-travel smoke test passed.
- [x] **M1 [DEMO] Core + Delta store** — `core/models.py`, `core/config.py` (+ `configs/*.yaml`), seeded RNG and logical clock, `adapters/delta_store.py` (write, read at version, history), `adapters/duck.py`. Tests: time travel returns old rows; content hash is stable. — done 2026-10-05: 9 tests pass, ruff clean.
- [x] **M2 [DEMO] Pipeline + data generator** — `tasks/datagen.py`, `tasks/pipeline.py` (clean + aggregate as pure DuckDB SQL), 10 healthy days. Tests: determinism (same seed = same hashes), stages are pure. — done 2026-10-05: 16 tests pass, 10 healthy days in 3.59 s.
- [x] **M3 [DEMO] Lineage + monitor** — `adapters/lineage_store.py` (runs record input/output snapshot ids), `drift/monitor.py`. Tests: silent on healthy days; fires on a hand-made fault. — done 2026-10-05: 23 tests pass, 0 false alarms on 10 healthy days.
- [x] **M4 [DEMO] Faults + scenarios** — `tasks/faults.py`, `tasks/s1..s6` with ground truth in `configs/scenarios.yaml`. Each scenario produces the final Delta tables and a JSONL log in `results/`. — done 2026-10-05: 31 tests pass; s4 silent; s2 and s5 alarm only narrowly (see build_logs Entry 5).
- [x] **M5 [DEMO] Investigators** — `agents/shortlist.py`, `agents/replay.py` (pinned inputs, 3 repeats, CONFIRMED/DENIED/PARTIAL/INCONCLUSIVE), `agents/baselines.py` (B1 recency, B2 distance). Tests as in ARCHITECTURE section 11. — done 2026-10-05: 42 tests pass; s1-s3 behave as specified; s5 and s6 did NOT behave as predicted (see build_logs Entry 6).
- [ ] **M6 [DEMO] Metrics + runners** — `metrics/*`, `runners/run_scenario.py`, `runners/run_all.py` (demo seed 42 plus held-out seeds 1-5 reported separately). Log honestly what s5 and s6 do.
- [ ] **M7 [DEMO] Report + one-command demo** — `outputs/` HTML + PNG + CSV tables, `demo/run_demo.py` (< 120 s, offline).
- [ ] **M8 [DEMO] Quality gate** — `pytest -q` green, `ruff check .` clean, README quick start verified, held-out seeds reported separately.
- [ ] **M9 [DEMO] Talk material** — `docs/DEMO_SCRIPT.md` (3-minute talk track), `docs/VIVA_NOTES.md` (questions, honest answers, limitations). Real numbers only.

## Stretch (only after M0-M9 are done, and ask the user first)

- [ ] **S1 [STRETCH]** Iceberg adapter (`pyiceberg`, local SQL catalog) with the same tests as the Delta store.
- [ ] **S2 [STRETCH]** Real OpenLineage events + Marquez (needs Docker, ask first).
- [ ] **S3 [STRETCH]** BugDoc-style parameter-replay baseline (B3).
- [ ] **S4 [STRETCH]** Semi-realistic DAG (TPC-H derived) and a non-determinism study (plan only, in `docs/SEM5_PLAN.md`).

## Later semesters (for context only, do not build now)
Sem 5: toy pipeline, lineage, monitor, first replay harness, a handful of faults (this demo is the start). Sem 6: full 20-scenario suite,
baselines (lineage-only, BugDoc-style), precision/recall. Sem 7: mild non-determinism, incremental steps, TPC-H DAG, breaking point.
Sem 8: write-up and workshop/student-conference paper.

## Decisions log (short; details go to build_logs.md)
- Backup idea: demo uses Delta Lake via `deltalake` (delta-rs) + DuckDB so it needs no Spark, Java or Docker. Iceberg is a stretch.
- Warehouse folder is outside OneDrive (`WAREHOUSE_DIR`) to avoid sync locks.

# LineageRCA — counterfactual replay for data-pipeline root-cause analysis

Backup capstone idea. When a data-quality alarm fires, we do not just guess the upstream cause from the lineage graph.
We re-run the downstream steps with the suspect table at its earlier snapshot (Delta Lake time travel) and check whether the
problem disappears: CONFIRMED or DENIED.

**Status:** see `PROGRESS.md`. **Everything here runs on SYNTHETIC data** (real time-travel replay, synthetic pipeline and
injected faults with known ground truth). It shows that the mechanism works under pure, deterministic transforms. It is not
evidence about real production pipelines.

## Quick start (Windows PowerShell, from this `execution` folder)

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1          # if blocked: use .\.venv312\Scripts\python.exe directly
python -m pip install -U pip
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env                    # only if .env is missing
python scripts/check_env.py               # must say READY
pytest -q
python demo/run_demo.py                   # the demo; opens/writes outputs\demo_report.html
```

No Spark, no Java, no Docker, no network (after the packages are installed).
The Delta tables are written to `WAREHOUSE_DIR` (see `.env`), outside OneDrive, and are regenerated on every run.

## Where things are

See `CLAUDE.md` (rules and folder map), `ARCHITECTURE.md` (what is built), `PROGRESS.md` (milestones),
`build_logs.md` (what happened), `docs/` (talk track and viva notes). Reference papers are in `../docs/`.

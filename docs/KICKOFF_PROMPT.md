# Kickoff prompt for Claude Code (LineageRCA, the backup idea)

How to use: open a terminal in the `execution` folder, start `claude`, and paste everything inside the block below.
(Claude Code loads `CLAUDE.md` automatically; the prompt also tells it to re-read it.)

```text
You are implementing LineageRCA, our BACKUP capstone idea, as a working demo. Work ONLY inside this folder (the
"execution" folder). The folder layout, rules, specs and tracker already exist; follow them.

STEP 0 - READ FIRST (no coding yet)
Read, in this order: CLAUDE.md (hard rules), ARCHITECTURE.md (what to build), PROGRESS.md (milestones), build_logs.md,
then the proposal PDF in ../docs/ (read-only, never edit anything there).
Reply with a 10-line summary of what you understood, the plan with a rough time estimate per milestone, and any BLOCKING
question (otherwise continue straight to Step 1). Challenge anything in ARCHITECTURE.md that looks wrong or too big, before coding.

STEP 1 - INSTALLATION AND DOWNLOAD CHECKS (milestone M0)
1. Report what is installed, without installing anything yet: `python --version`, `py -0` (Python versions on Windows),
   whether `.venv312` exists, `git --version`, and the OPTIONAL tools `java -version` and `docker --version`
   (the demo needs neither).
2. Create the venv if missing: `py -3.12 -m venv .venv312`. If Python 3.12 is not installed, STOP and ask me which version
   to use. Do not install Python yourself.
3. Activate it (`.\.venv312\Scripts\Activate.ps1`; if PowerShell blocks it, call `.\.venv312\Scripts\python.exe` directly and do
   NOT change the execution policy). Then: `python -m pip install -U pip` and
   `pip install -r requirements.txt -r requirements-dev.txt`.
4. Make sure `.env` exists (copy from `.env.example` only if missing). Never print or commit `.env`. Check that WAREHOUSE_DIR
   points outside OneDrive and its folder name ends with `lineagerca_warehouse`.
5. Run `python scripts/check_env.py`. Fix every FAIL (WARN items such as Java/Docker are optional). The Delta time-travel
   smoke test must pass. Paste the real output into build_logs.md and tick M0 in PROGRESS.md.
6. NEVER install system software (Java, Spark, Docker Desktop, Marquez, WSL) or download anything larger than 50 MB
   without asking me first: tell me the name, source and size. No `curl | sh`, no admin shell, no TLS shortcuts.

STEP 2 - BUILD M1 TO M9, IN ORDER (see PROGRESS.md and ARCHITECTURE.md)
Core + Delta snapshot store -> synthetic pipeline and data generator (10 healthy days) -> lineage store + data-quality monitor ->
fault injectors and scenarios s1-s6 -> investigators (shortlist, replay harness with pinned inputs and 3 repeats, two baselines) ->
metrics and runners (seed 42 plus held-out seeds 1-5) -> report and one-command demo -> tests and quality gate -> talk material.
Acceptance (all must hold):
- `python demo/run_demo.py` runs offline in under 120 seconds and writes to outputs/: an HTML report, PNG figures per scenario and
  CSV tables (snapshots, lineage edges, replay verdicts), and prints a summary table.
- s1 and s2: replay CONFIRMS the true table and DENIES the more-recent decoy; the recency baseline blames the decoy.
  s3: the fault is the latest change, so replay and the baselines agree (keep this scenario, it keeps the comparison fair).
  s4 (control): the monitor stays silent. s5 (two causes) and s6 (non-deterministic transform) report WHATEVER actually happens.
- `pytest -q` passes and `ruff check .` is clean.
Quality rules: everything is labelled SYNTHETIC; fix thresholds in configs BEFORE looking at held-out seeds; never tune anything
just to make replay win; implement the baselines in good faith; no LLM, no ML; small readable files with plain-language comments
(four students must explain them in the viva); a test for every module; fixed seeds (demo seed 42, held-out seeds 1-5 reported
separately); a logical clock, never wall-clock time, inside data and metadata. No number may appear in docs or reports unless it
came from a run you executed. If the replay logic has a conceptual flaw you notice (for example a fault that replay cannot undo),
tell me, do not paper over it.

STEP 3 - GIT (you never touch the repository)
Do NOT run git init/add/commit/push/pull/checkout/reset/merge/stash or any write command, and no `gh` writes. Read-only git
(status, diff, log) is fine. After EVERY milestone and at the end of the session, print a "GIT CHECKPOINT" block with the exact
commands for me to run myself: git status, git add <explicit paths>, git status (to confirm .env and .venv312 are NOT listed),
git commit -m "<conventional message>", git push. Never use `git add .` or `git add -A`. If this folder is not a git repo yet,
print the one-time setup commands once (git init, git branch -M main, git remote add origin <YOUR-REPO-URL>) and continue.

STEP 4 - AFTER EACH MILESTONE
Tick it in PROGRESS.md, append an entry to build_logs.md (what, exact commands, real output summary, problems, decisions, next),
print the Git checkpoint, then give me a summary of at most 6 lines.

STEP 5 - TIME BOX AND CUTTING ORDER
Aim for M0-M7 working in about 5 hours, then quality gate and talk material. If time is short, cut in this order:
(1) the PARTIAL verdict and scenario s5, (2) HTML report polish (keep PNGs, CSVs and the console table), (3) scenario s6.
NEVER cut: the s4 control, s3 (fair comparison), the SYNTHETIC labels, the pinned-input replay with real Delta time travel, the unit
tests, or the honesty notes. If the same error happens 3 times, log it in build_logs.md and ask me instead of looping.
Do not start any STRETCH item (Iceberg, Marquez, BugDoc-style baseline) before M9 is done, and ask me before starting one.

Begin with Step 0 now.
```

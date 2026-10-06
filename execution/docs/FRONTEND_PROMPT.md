# Claude Code prompt: restyle the LineageRCA report (same front end as CascadeGuard)

Paste everything below the line into Claude Code (started inside `LineageRCA\execution`).

---

The LineageRCA demo works. This task is **front end only**: restyle the generated report (`outputs/demo_report.html`) so it uses the
same neo-brutalist front end as our other project (CascadeGuard), with LineageRCA content. Do not change pipeline, monitor, replay,
baseline or metric logic.

## Step 0: read first (do not skip)

1. `CLAUDE.md`, `ARCHITECTURE.md`, `PROGRESS.md`, `build_logs.md`.
2. Design references in `../docs/` (read-only, never edit anything there):
   - `../docs/attest-frontend-reference.md`: the written design spec (cream background, thick borders, hard zero-blur shadows,
     sharp cards, pill buttons, coral highlight word, monospace only for UI chrome, step cards with different badge colours).
   - `../docs/frontend_reference/report.css`, `report.js`, `report_template.html`: a WORKING implementation of that style from our
     CascadeGuard report. Reuse its tokens, components and structure (copy the code into `demo/`, it is ours). Read them, then adapt.
3. The current LineageRCA report code (`demo/`, wherever the template and report builder live).

Then print a short plan: files you will touch, which parts of the reference you reuse, and which parts you replace.

## Rules for using the reference

- Take the STYLE and the component patterns. Do not copy any CascadeGuard text, scenario names, numbers or the words
  "Attest" or "CascadeGuard". Every word on the page must be LineageRCA content.
- Put the reusable pieces in `demo/report.css` and `demo/report.js` (inline both into the final HTML). One shared set of tokens
  (CSS variables), one `.mark` highlight component, one `.tag`, `.btn`, `.card`, step-card style.

## Content for the LineageRCA page

- **Banner (always visible):** "SYNTHETIC DATA - real Delta time-travel replay - not a production pipeline".
- **Header:** "LineageRCA" wordmark plus a black pill badge, e.g. "BACKUP IDEA DEMO".
- **Hero:** eyebrow tag; big headline with ONE coral-highlighted word (for example "prove"); one sentence on what it does (replay the
  downstream steps on the suspect's earlier snapshot, and check whether the anomaly disappears); two buttons: jump to Findings, jump to Scenarios.
- **Old question vs new question** (two cards like the reference): "Which upstream table changed most recently?" (guess) versus
  "If this table had not changed, would the problem still happen?" (test).
- **Replay panel (the main interactive piece):** for the selected scenario s1-s6, an inline SVG lineage graph
  (`raw_orders`, `raw_customers`, `raw_fx_rates` -> `cleaned_orders` -> `daily_revenue_agg`). A play/pause button and a scrubber step through the
  real investigation: anomaly flagged -> suspects shortlisted -> each suspect replayed in turn (show observed vs expected vs replayed metric)
  -> verdict tag per suspect (CONFIRMED green, DENIED coral, PARTIAL yellow, INCONCLUSIVE black). Data comes only from the existing run outputs
  (the CSVs / result files). No new numbers.
- **Method comparison:** one table per scenario: replay vs baseline B1 (recency) vs baseline B2 (distance), with who blamed which table, and
  whether it matched the ground truth. Show s3 (where all methods agree) just as prominently as s1 and s2.
- **How a replay runs:** five step cards matching the five pipeline stages in `ARCHITECTURE.md`, each with a different badge colour.
- **Summary and held-out tables:** responsive, no sideways page scroll (wrap, stack on narrow screens, or scroll inside the card).
  Seed 42 and held-out seeds 1-5 stay in separate tables.
- **Limitations:** a clear bordered card, not hidden. Keep the "Read this first" box.

## Non-negotiable honesty rules

The page must not make the demo look more convincing than it is.

1. Keep every SYNTHETIC label, the "Read this first" box and the Limitations section, restyled but with the same meaning and prominence.
2. Keep all findings text and every number exactly as the run produces it. Do not round, drop, reorder for effect, or invent anything.
3. Show negative or awkward results plainly: wrong verdicts, PARTIAL and INCONCLUSIVE outcomes in s5 and s6, scenarios where the baselines tie or win,
   and any false CONFIRMED. If something in the report looks wrong or misleading, tell me instead of quietly fixing or hiding it.
4. Do not tune thresholds, data sizes, fault sizes or any logic in this task. If the front end needs data the pipeline does not emit, tell me and propose it.

## Technical constraints

- Still produced by `python demo/run_demo.py`. Offline, finishes within the existing time budget, no server, no CDN, no external requests.
- The HTML opens straight from disk. Inline CSS and JS. Fonts: system fallbacks only (`Arial Black`, `Impact`, `ui-monospace`, `Consolas`).
- Keep the PNG figures as a fallback if the JS replay cannot load, or replace them with inline SVG from the same data. Numbers must match the CSVs.
- Responsive at 390 px and 1280 px, no horizontal page scroll, visible focus states, keyboard-operable play/pause and scrubber,
  `prefers-reduced-motion` respected (no auto-play or blinking).
- Keep `pytest -q` and `ruff check .` green. Add a small test that the generated HTML contains the SYNTHETIC label, the Limitations section
  and a PARTIAL or INCONCLUSIVE verdict from s5/s6 if the run produced one.
- No new heavy dependencies. Ask before installing anything.

## Verify before you say it is done

1. Run `python demo/run_demo.py` end to end and report the time.
2. Screenshot the report at 390 px and 1280 px (Playwright only if already installed, or ask me first) into `outputs/screens/` and look at them.
   List any visual problems you found and fixed.
3. Confirm there are no external network requests in the HTML.
4. Diff the numbers on the page against `replay_verdicts.csv` and the metrics output and state that they match.

## Rules that still apply

- **Git:** never run any git write command. Read-only git is fine. At the end print the **GIT CHECKPOINT** block from `CLAUDE.md` with explicit
  paths only (never `git add .` or `-A`) and a conventional message such as `feat(report): neo-brutalist front end for demo report`.
- Update `PROGRESS.md` (add a front-end milestone, for example M7b) and add an entry to `build_logs.md`.
- Order: working restyle first (layout, tokens, components, fixed tables), then the interactive replay, then polish. If time is short, cut polish
  before you cut any honesty content.
- If unsure, ask me ONE question.

When done, report: files changed, what the page now contains, verification results, anything in the report that looks off, and the GIT CHECKPOINT block.

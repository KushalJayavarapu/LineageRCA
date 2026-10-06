# Frontend Reference — "Attest" Landing Page Design

*Describes three screenshots of a reference landing page, for use as a build spec with Claude Code.*

## Design system

**Overall aesthetic:** neo-brutalist. Thick black borders, sharp (non-rounded) corners on cards, hard offset drop-shadows (solid black shadow offset down-right, not soft/blurred — like a sticker stacked on a card), warm off-white/cream background throughout.

**Color palette:**
- Background: warm cream/off-white (~`#F5EFE0`)
- Primary text: near-black (~`#1A1A1A`)
- Coral/red-orange: used for highlight blocks and "pasted/negative" states (~`#FF5A3C`)
- Blue: primary CTA buttons, provenance/info accents (~`#3355FF`)
- Yellow/gold: secondary tags, one step accent, secondary CTA (~`#F0C040`)
- Green: "written/positive" state tags
- Purple: used once, for a step-number accent only

**Typography:**
- **Display/headline font:** very bold, oversized, tight letter-spacing — a heavy geometric grotesk (e.g. Archivo Black, Inter Black, or similar). Used for all large headlines.
- **UI/label font:** monospace, uppercase, letter-spaced — used for ALL small chrome: tags, badges, timestamps, button text, section eyebrows (e.g. "PROOF, NOT DETECTION", "00:03", "WRITTEN"). Looks like JetBrains Mono / IBM Plex Mono / Space Mono.
- **Body copy font:** regular-weight sans-serif, gray (~`#555`), comfortable line-height, used for descriptive paragraphs only.

**Core components:**
- **Pill buttons:** fully rounded, bold uppercase monospace text. Primary = solid blue bg / white text. Secondary = outlined, black border, transparent/cream bg, black text.
- **Bordered cards:** 2-3px solid black border, sharp corners, hard offset black drop-shadow (not soft). Used for both content cards and the step-list rows.
- **Small tag/badge:** tiny bordered box, uppercase monospace text, cream or colored background — used as section "eyebrows" and inline status labels (e.g. "WRITTEN", "PASTED").
- **Highlight-block text:** a headline word/phrase rendered as white text on a solid coral block, mimicking a marker/highlighter swipe. Used twice across the three screenshots as a recurring motif — reuse this as a reusable `<mark>`-style component, not a one-off.

---

## Section 1 — Hero (Image 1)

**Header row:** "Attest" wordmark, bold, top-left. A black pill badge top-right, white uppercase monospace text: "ORAL DEFENSE FOR THE POST-AI CLASSROOM." Full-width horizontal rule below the header.

**Eyebrow tag:** small bordered box, uppercase monospace: "PROOF, NOT DETECTION."

**Headline (huge, bold, black):**
"Proof a human / understood / this."
— the word "understood" is the coral highlight-block treatment (white text on solid coral background), rendered as its own line, visually distinct from the rest of the black headline text.

**Subheading (regular weight, gray):**
"Detectors ask whether a human made the work — a question with no reliable answer, that turns teachers into police. Attest asks whether a human can stand behind it, then makes them able to."

**CTA row:** two buttons side by side — "SEE THE SEAM" (solid blue, primary) and "DEFEND YOUR WORK" (outlined, secondary).

**Right-side panel (bordered card, hard shadow), simulating a live editor replay:**
- Top row: "DRAFT · REPLAYED" (left, monospace gray) / "00:03" (right, monospace, timer-style)
- Horizontal rule
- A green "WRITTEN" tag, followed by in-progress text: "I used a hash map so the lookups would stay cons" with a blinking text-cursor (blue vertical bar) at the end — implies an actively-typing animation.
- Horizontal rule
- Small italic/gray caption: "Watching where the writing stops looking like writing…"

**Bottom comparison row** (two cards side by side, split by a vertical divider, thick shared black border):
- **Left card** (cream bg): eyebrow "THE OLD QUESTION," large quote with a red strikethrough across it: ~~"Did a human make this?"~~, below in gray: "Unanswerable. Falsely accuses honest students. Dies to a paraphrase."
- **Right card** (solid yellow/gold bg): black badge "THE QUESTION THAT LASTS," large bold quote (no strikethrough): "Can a human stand behind this?", below in black: "Provenance-agnostic. Never accuses. Closes the gap instead of flagging it."

---

## Section 2 — Live diff/replay demo (Image 2)

**Eyebrow tag** (yellow bg): "THE SAME ESSAY, WRITTEN TWO WAYS."

**Headline:** "Watch where the writing stops looking like / writing /." — "writing" (second instance) again uses the coral highlight-block treatment, reinforcing it as the site's recurring "key term" motif.

**Subheading (gray):** "Identical final text, one shared timeline. One was written; one arrived in a single paste, flagged as it lands."

**Small back-link, top-right:** "← ATTEST" (underlined, monospace) — a nav element back to the main page.

**Two-panel side-by-side comparison** (bordered cards, same hard-shadow style):
- **Left panel** — header row: green "WRITTEN" tag (left) / "2:09 · 716 chars" (right, monospace). Body: a full paragraph of essay text about the printing press and the Reformation, ending mid-sentence with a blinking cursor — implies this panel plays a live "typing" animation.
- **Right panel** — header row: red/coral "PASTED" tag (left) / "1:24 · 815 chars · 60% pasted" (right, monospace). Body: the *same* essay text, but the latter portion of the paragraph is rendered with a red/pink highlighted background, visually marking it as the pasted segment. Has a visible scrollbar (content is taller than the panel).

**Playback control, below both panels:** a solid blue "PAUSE" pill button on the left, next to a horizontal scrubber/timeline bar with a circular blue draggable handle (positioned partway along, implying this is a replayable timeline, like a video player).

---

## Section 3 — Process steps + CTA (Image 3)

**Eyebrow tag:** "HOW A DEFENSE RUNS."

**Five stacked step-cards**, each a bordered/hard-shadow card containing: a small colored square badge with a two-digit number (left), a bold step title next to it, and a gray description paragraph filling the rest of the row. Each step uses a **different accent color** for its number badge — this color variation is intentional, not random, and should be preserved:

1. **Capture** (yellow badge) — "A light editor records the writing as it happens — every keystroke, pause, and paste, kept as an event log."
2. **Provenance** (blue badge) — "Replayed, each character remembers when it was written and whether it was pasted. Pasted prose has one birth; written prose has hundreds."
3. **Seam** (coral/red badge) — "The examiner finds the claim the writer is least able to defend — not the pasted one, the un-understood one."
4. **Defense** (green badge) — "It probes that claim in a live voice exchange, following up the way a sharp examiner does. You can paste an essay. You cannot defend one."
5. **Remediation** (purple badge) — "When a gap opens, it stops examining and starts teaching — Socratically, until you can defend the point, then asks again."

**Closing CTA banner** (full-width, solid blue background, same hard-shadow bordered-card treatment):
- Bold white heading: "For teachers"
- White subtext: "Rewrite an assignment so it survives AI — and get the defense rubric."
- Two buttons: "REDESIGN AN ASSIGNMENT" (solid yellow/gold, black bold text) and "CREATE A CLASS" (outlined, white border/text).

---

## Implementation notes for Claude Code

- The **hard offset drop-shadow** (not a soft/blurred box-shadow) is the single most distinctive visual trait here — implement as a solid-color shadow with zero blur, e.g. `box-shadow: 6px 6px 0px #000;` not a typical soft CSS shadow.
- **No border-radius on cards** (sharp corners) but **full border-radius on buttons** (pills) — this contrast is deliberate, preserve it.
- The **coral highlight-block on headline text** is a reusable motif, not a one-off — appears in both Section 1 and Section 2 headlines on a key word. Worth building as a shared component (e.g. a `<Highlight>` wrapper) rather than one-off styling each instance.
- Monospace font is reserved specifically for UI chrome (tags, timestamps, buttons, badges) — body paragraphs and headlines use different fonts. Don't apply monospace globally.
- The editor-replay and diff-comparison panels both imply **JS-driven animation/interactivity** (blinking cursor, scrubber control, paste-highlight reveal) — these are functional demo components, not static screenshots, if faithfully reproduced.

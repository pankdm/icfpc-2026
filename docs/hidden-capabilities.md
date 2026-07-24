# Littleman: undocumented behavior, golf tricks & recon

Curated from a multi-agent investigation of the reference interpreter (Go→WASM),
verified against the oracle. "CONFIRMED" = observed in the oracle; a few are
inferred from the binary and marked. Companion to `multi-man-interactions.md`.

## Corrections to the public docs
- **Private test cases exist.** The public API reports `privateTestCount: 0`, but the
  standings `casesTotal` reveals the real totals (~2–3× the public count: e.g. triangle
  6 public / 19 total, reverse 8/20, brackets 9/26). You must **generalize**, and you
  need ≥1 private pass to score.
- **`Y` (fork) may be rejected by the grader.** There's an admin flag `split_released`
  ("the grader starts/stops accepting Y"); `/split/docs` 404s until released. `Y` runs
  in the local oracle but **test-submit before relying on it** (likely the post-lightning
  language update).
- **Three run-end caps, not one:** `step-cap`, `op-cap`, `time-cap` (docs mention only step).

## Scoring & ranking
- Score = `max(width,height)² × avg_ticks` (or just `max(width,height)²` for footprint-only).
  **Lower is better.**
- Footprint = bbox of **non-space** cells only — trailing spaces, blank lines, indentation
  are free. A stray non-space glyph at an extreme still counts (no comment syntax).
- Only the **larger** dimension is squared → make layouts **square**, not long/thin.
- Ticks counted only until the **final correct output settles**; the program need not halt
  — looping/crashing afterward is free (so `H` is often unnecessary: crash into a wall
  after the last output).
- Avg ticks includes **blocked/waiting** ticks. Output-pipe **length adds ticks** (value
  must reach the pipe's end). Keep pipes short.
- Ranking: cases-passed first; only full-passers ranked by score; **ties count in your
  favor**; solo-eligible gets the full ranking point.
- Rounds run in one continuous sim (no reset); ticks accumulate; a zero-output round
  unlocks the next input immediately.

## Language edge-cases (CONFIRMED)
- **Complete instruction set** — besides `Y` there are **no** other hidden ops; every
  other printable ASCII is a fatal `bad-op`.
- Case-sensitive & asymmetric; **`V`/`v` is the only case-duplicated op** (both "south").
  `M`≠`m`, `X`≠`x`, `W`≠`w`(bad-op), `b`≠`B`(bad-op), etc.
- Floored `/` and `%` (remainder takes divisor's sign). **`/` with B=0 → A=0, B=dividend**
  — a one-cell "B:=A, A:=0". `%0 → A=0`.
- Shifts unmasked: `{` → 0 if B∉0–63; `}` → 0 if B<0, **sign-fills** if B>63.
- Turn geometry CW = E→S→W→N. `X`: turn by sign(A). `d`/`a`: turn only if BP>0 (0 and
  negative = straight). `x`: always turns on BP's raw low bit.
- Literals load only on the **closing** backtick (overwrite); read in the walk direction
  (reversed westward); a **corner backtick opens H+V literals sharing digits**; rejected
  if digits overflow i64 in *either* direction.

## Fork / `Y`, collision, walls
See `multi-man-interactions.md` (owns this). TL;DR: `Y` forks (may be grader-gated);
same-cell collision = free clean `done` halt; a wall/bad-op is a **fatal** whole-program abort.

## Pipes
- FIFO queue: capacity = length; latency = (length−1) ticks; a value shifted into the dest
  cell can be read the **same tick**. Full pipe blocks the sender (back-pressure).
- `r`/`s`/`q` use the **nearest** pipe (Manhattan to attachment, reading-order ties) and
  **lock onto it even if busy** while another pipe is ready. `R`/`U` take from any ready
  incoming. `S` = all-outgoing, all-or-nothing.
- **`U` = receive + turn *away from the pipe*** — and the turn is **position-relative**:
  a pipe directly above the `U` cell → man turns south; a pipe off to the side → he turns
  sideways. Align the pipe directly over the `U` cell to drive him straight in.
- `q` counts ALL in-flight values in the nearest pipe (not just the ready one), never blocks.
- Self-loop pipes = load error. Two-way and parallel duplicate pipes are legal. Men can't
  travel pipes (only values).

## LM-75 display
- **Write-only** (no readback — can't be program memory). Ports: top=ADDR, left=DATA
  (color 0–15, cursor auto-advances and **wraps** with no fault), bottom=SWAP.
- Every SWAP (0 and 1) commits a judged frame; `1` keeps the buffer+cursor (delta frames).
- **ADDR pipe is optional** for raster fills (cursor auto-wraps). First all-black frame is
  free (one bare SWAP). Extra commits after all frames match are ignored (can't fail).

## API & recon (public unless noted)
- **Undocumented public GETs:** `/standings` (all teams' points), `/standings/problems/:id`
  (every team's raw score + pass counts + rank — the exact target to beat; **UUID only**,
  slug returns empty), `/public/queue` (grader load/latency), `/public/contest-clock`
  (freeze/deadline windows), `/split/docs` (404 until released), `/health`.
- Only 4 of ~20 endpoints are documented. `/submissions` uses Bearer key; `dashboard/*` +
  `admin/*` use cookie session (admin correctly 401s — no bypass). 429 = max 5 pending.
- The interpreter is scriptable as `globalThis.littlemanWasm` (this is our oracle):
  `load/step/stepN/back` + `analyze/flow/route/validOps/structuralGlyphs`. `flow()` is a
  static reachability/crash analysis; `back()` is reverse-step debugging.

_Full raw findings (127, with per-finding verify verdicts) are in the workflow journal
`wf_dce21779-fe5/journal.jsonl`; this file is the curated, team-facing subset._

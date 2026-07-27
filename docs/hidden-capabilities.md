# Littleman: undocumented behavior, golf tricks & recon

Curated from a multi-agent investigation of the reference interpreter (Go→WASM),
verified against the oracle. "CONFIRMED" = observed in the oracle; a few are
inferred from the binary and marked. Companion to `multi-man-interactions.md`.

## Corrections to the public docs
- **Private test cases exist.** The public API reports `privateTestCount: 0`, but the
  standings `casesTotal` reveals the real totals (~2–3× the public count: e.g. triangle
  6 public / 19 total, reverse 8/20, brackets 9/26). You must **generalize**, and you
  need ≥1 private pass to score.
- **`Y` (fork) is RELEASED — the gate is open.** `/split` and `/split/docs` both return 200
  (checked), and the organizers have published the official *"Y, precisely"* clarification,
  which is now the authority on split semantics — see `multi-man-interactions.md`. The old
  `split_released` caveat no longer applies; `Y` can be relied on.
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
- **Backticks pair per ROOM, per interior row and column** — within one interior row (or
  column) they pair consecutively (0,1),(2,3),… Two literals on the same row in *different*
  rooms never pair across the wall between them (that pairing is what a global row scan gets
  wrong, and it rejects real programs: sort-numbers, subset-sum, sudoku all rely on it).
  Inside one room a non-digit between a pair is a **load error on both axes**, and a backtick
  with no partner on either axis is `unmatched backtick`. An all-space span carries no value:
  crossing either of its backticks is a nop.
- **Literal content is a nop only ALONG the literal's own axis.** A man who crosses a
  horizontal literal *vertically* executes the digit he lands on (`A = digit`) — the literal
  itself only loads on the closing backtick. Same for a vertical literal crossed horizontally.
  A digit cell inside a literal is therefore live traffic, not padding, for perpendicular
  paths. (Both rules verified against the oracle: `scratchpad/lit-probe/`, and pinned as
  difftest fixtures `lit-cross-*`, `lit-two-rooms-same-row`, `lit-junk-in-*`, `lit-unmatched`.)

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
  It is also a **broadcast**: every man in a room can `q` the same pipe on the same tick, all get
  the same depth, and the pipe is not consumed — one token in a signal pipe re-steers a whole crowd
  via `d`/`a`/`x` with no per-man channel (men in one room have no other way to communicate).
- **Pipe contention between men is resolved by ascending entity id**, one winner per tick, for both
  `s` and `r` — see `multi-man-interactions.md` §4b. A crowd of men is a FIFO, never a stack.
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
  (freeze/deadline windows), `/split` + `/split/docs` (the split clarification; now live), `/health`.
- Only 4 of ~20 endpoints are documented. `/submissions` uses Bearer key; `dashboard/*` +
  `admin/*` use cookie session (admin correctly 401s — no bypass). 429 = max 5 pending.
- The interpreter is scriptable as `globalThis.littlemanWasm` (this is our oracle):
  `load/step/stepN/back` + `analyze/flow/route/validOps/structuralGlyphs`. `flow()` is a
  static reachability/crash analysis; `back()` is reverse-step debugging.

_Full raw findings (127, with per-finding verify verdicts) are in the workflow journal
`wf_dce21779-fe5/journal.jsonl`; this file is the curated, team-facing subset._


## `Y` copies do NOT inherit the parent's heading (measured 2026-07-27)

A man heading EAST forks into a copy at `(x, y+1)` heading **SOUTH** and a copy at `(x, y-1)`
heading **NORTH** — perpendicular, away from the `Y`. Assuming they keep the parent's heading
crashes with `wall` (it did, at tick 5, in `scratchpad/rowbranch/probeC.man`). Put a `>`/`<` on
each birth cell to steer them back.

## Parked men wake in CREATION ORDER, not reading order (measured 2026-07-27)

Several men blocked on the same incoming pipe are served **oldest-first by age**, not by
position. A rig with two parked copies and one input value woke the SOUTH (older) copy, and two
values came out `["2","1"]`. Layout cannot influence the choice, so a crowd of parked men is not
an addressable dispatch table. Compounding it: a genuinely parked man is blocked on `r`/`s` and
therefore **cannot execute `q`**, so he cannot see a broadcast either.

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

## Room stacking, pipe gaps, and speculative verdicts (measured on sudoku-validity, 2026-07-26)

All four confirmed against the wasm oracle.

**A room may hold at most one `@`.** `room has multiple '@'s — rooms start with at
most one little man` is a load error. Several men in one room therefore come from
one `@` plus `Y` forks. A serpentine's row 0 is nearly empty — `serp` writes only
`(0,0)='@'` and `(1,0)='v'` — so row 0 can double as the fork row and a multi-loop
room costs just ONE extra row for the fork return lane. `Y` birth in a wall is
fatal, so the fork row can never be the interior's top row.

**A pipe into a room's TOP wall needs exactly 2 gap rows.** 1 gap row is rejected
(`pipe runs into a room wall`): the source cell's backward neighbour must be the
room above's bottom wall, which forces the cell to flow south, which puts the next
cell in the destination's wall — a 1-cell pipe. Measured:

| arrangement | result |
| --- | --- |
| 2 gap rows, straight vertical | LOAD OK |
| 1 gap row, 1 cell | rejected |
| 1 gap row, 2 cells along the gap row | rejected |
| **0 gap, 2-cell L into the destination's SIDE wall** | **LOAD OK** |
| 0 gap, 3-cell L from the source's side wall | LOAD OK |

So zero-gap stacking works only when the pipe enters the destination's **side**
wall (the brackets `stack6` trick), and the destination must overhang the source
by >=1 non-corner column. `pipe()` draws through its last waypoint and would
overwrite the wall, so place the L cells with `put()`.

**Side entry can separate at most two rooms' worth of `r` cells.** Pipes on one
wall share a column, so |dx| is identical for all of them and only |dy| decides —
and co-resident loops span the same rows. Measured on the 3-loop band: with three
pipes on the east wall every `r` in all three loops binds the same pipe; with
west+east, the middle loop's own `r` cells split across both. Three or more
co-resident loops therefore need TOP entry, hence 2 gap rows.

**Branch-free "is it zero": `r M 1 + M 1 / s`** gives 1 for x==0 and 0 for every
nonzero x (verified to 2^54) using floored division, `1/(x+1)`. Sound only while
x >= 0.

**A self-clocking timer is a latency-hiding device, not overhead.** It emits the
common-case verdict *speculatively* without reading anything, so the round period
only has to cover **detection** latency — the time for a dissenting value to
preempt it. Anything that instead *collects* results (an aggregator) puts the full
collection latency on the round's critical path, because the round gate withholds
the next input until the verdict is emitted. Measured: cliff == decide + 1 in
three independent builds (decide 45 -> cliff 46; decide 43 -> cliff 44 twice), so
every tick between the last producer's `s` and the output room's consumption moves
the period 1:1. On sudoku-validity, replacing the 2-row/0-op timer with a
6-lane OR aggregator needs box <= 796 just to break even at period 52, and the
branch-free strips that pay for it also force a wider addresser band.

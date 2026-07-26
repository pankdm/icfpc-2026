# The littleman optimizing compiler: what each pass is worth

Score is `max(width,height)^2 * avg ticks` — AREA x LATENCY on a 2D fabric — so this is
high-level synthesis, not a constant tuner. This is the measured yield of every pass we
built, including the ones that turned out to be worth nothing. **The negatives are the
point**: they say where the remaining score actually is.

## The pipeline

| stage | tool | status |
|---|---|---|
| front end: `.man` -> IR (rooms, pipes, per-man CFG, basic blocks) | `tools/lift.py` | done, oracle-gated (`--verify`) |
| analyses: tick attribution (compute / turn / glide / stall) | `sim/xray.js`, `sim/profile.js` | done |
| pass: dead-code elimination | `tools/dce.py` | done — **no dead code exists** |
| pass: instruction scheduling | `tools/sched.py` | done — **worth 0** |
| pass: strength reduction / peephole | — | cancelled, see below |
| pass: line folding | `tools/fold.py` | done — small wins |
| back end: room floorplanning + pipe re-routing | `tools/place.py` | done — small wins |
| back end: intra-room code re-placement | in progress (`optimizer-walkfold`) | **where the score is** |
| verify: all cases pass AND score strictly lower | `tools/grade_json.js` | done |

## What each pass actually returned

**`dce.py` — 0.** Every champion has zero unreachable instruction cells (memory has two,
and deleting them is score-neutral because they free no row or column). These grids carry
no slack for a local rewrite to reclaim. Proven non-vacuous by injecting a dead column
into `triangle/p2` and watching it come back out.

**`sched.py` — 0.** 135 candidate schedules across six targets, all still correct, none
faster. The reason generalises: a parked man executes nothing, so the only legal move is
issuing a blocking `r`/`s` *later* (gain = `min(slide, wait)`), and **in steady state a
man that stalls is by definition not the bottleneck**. xray's global stall percentage
averages over idle satellite men; on the *critical* man the headroom is 17.6% (sudoku, not
the 63% the global figure suggests) and exactly **0.0%** on matmul and gradebook. tcp and
plotter get monotonically *worse* with slide distance — their sends never wait at all.

**peephole / strength reduction — cancelled, correctly.** Ticks here are cells **walked**,
not instructions executed: a 6-op run rewritten as 4 equivalent ops still walks 6 cells
unless the path is re-laid. So a peephole cannot pay on its own; it only pays through the
same intra-room re-placement listed above. The historical wins that motivated it (brackets
bit-op classify 1.75x, tcp `w & X` gadget 1.49x) were *algorithm* changes hand-designed
together with the layout, not local substitutions.

**`fold.py` — a few percent.** Merges two adjacent grid lines when no glyph would land in
the other line's traversal path. Strictly stronger than `polish.py`'s blank-line deletion,
which every champion had already had. gradebook 120 -> 117 rows.

**`place.py` — a few percent.** Rigid room translation plus pipe re-routing. The one
placement move that cannot change a man's walk, so only pipes can break. tcp 41x41 ->
39x36, gradebook 60x120 -> 61x116.

## The four correctness cliffs (each silent — no error, just a wrong answer)

1. **`r`/`s`/`q` bind to the NEAREST pipe** by Manhattan distance from the *instruction
   cell*, reading-order ties. Moving an op or a pipe one cell can silently rebind it. This
   is not theoretical: it cut `sched.py`'s gradebook slide budget from 136 cells to 56.
2. **Pipe length is BOTH latency and capacity.** gradebook uses a 54-cell pipe as a delay
   line; shortening it to 23 cells passed six of seven public cases and timed out on the
   seventh. `place.py --pipe-len min|exact` exists for exactly this.
3. **A pipe that merely runs ALONGSIDE a room reads as attached to it**, stealing that
   room's `s`/`r`. This is what made gradebook's re-placement fail with pipes at *exactly*
   their original lengths — ruling out both latency and capacity — until the adjacency
   guard was forced on.
4. **A backtick literal reads REVERSED walked westward**, and is parsed on *both* axes, so
   a corner backtick opens overlapping horizontal and vertical literals sharing digits.

## Two process lessons that cost us real score

- **Baseline against `tools/ours.py`, never against whatever `.man` is on your branch.**
  Our live brackets champion (`stack6.man`, 23x23) sat on a branch one worktree did not
  have; work measured against the stale file produced a "win" that was worse than what we
  had already submitted.
- **`tools/submit.py` now archives the exact submitted bytes** under `submitted/<slug>/`.
  Our live tcp build is *gone* — no `.man` blob reachable from any ref matches it, and the
  server exposes no way to read a submitted program back. It was roughly 30% better than
  anything in git. A champion you cannot reproduce is one you cannot improve.

## Where the remaining score is

Not in any local rewrite. gradebook's critical man spends **85.9% of its ticks gliding**,
and the lever is that only `s`/`r`/`q`/`S`/`R`/`U` are column-locked — all twelve of room
0's pipe attachments sit in one row, so the y-term cancels and nearest-pipe is a pure
function of an op's *column*. Every other op is horizontally free. Choosing each code
row's entry/exit column to minimise travel between consecutive pipe ops is a DP over the
CFG: the "v2 walk folding" deferred in `docs/routing-requirements.md`.

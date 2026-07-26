# Floorplan reflow — the LLLM breakthrough (41.9x), and how to repeat it

2026-07-26. `tools/reflow.py` (branch `optimizer-lllm`, commit `7f5d89f`) took
Little Little Little Man from 149x1469 / 9.73e12 to **250x251 / 2.32e11 local**
(box 34.25x, ticks 1.22x). Submitted: server 10,914,705,606,074 →
**261,120,298,700**, 21/21. This file records why it worked and what transfers,
so the next agent does not rediscover it.

## The core insight: pipe bands are Voronoi cells of attachments

Every intra-room pass (dce/sched/peep/walkfold) measured ~zero on champions.
The reason is now understood, and it is *structural*, not bad luck:

- An `r`/`s`/`q` op binds to the **nearest** pipe (Manhattan from the
  instruction cell, reading-order ties). When all attachments sit on one wall,
  the y-term cancels and binding is a pure function of the op's **column**.
- Therefore the columns where an op bound to pipe P may legally sit — P's
  "band" — form **the Voronoi cell of P's attachment among the same-direction
  attachments of that room**.
- **A hot attachment placed mid-wall can never own more than half the room.**
  LLLM's two hot pipes were attached at columns 55/53 *between* cold
  attachments at 22 and 90/92, pinning 27,904 `r`/`s` ops to a 33-column band.
  `fuse` was *correct* to refuse — no in-band increasing assignment existed.
- The fix is a **floorplan move no intra-room pass can express**: re-attach the
  hot pipe at the *outermost* position and pack the cold attachments against
  the opposite end. LLLM's hot band went 33 → 214 columns (6.5x); the dense
  boustrophedon re-emit then folded 1469 rows into 251.

Same shape of ceiling was SUSPECTED for gradebook (`git show 053a6a0`) — but
the gradebook reflow (771M -> 438M server, 2026-07-26) DISPROVED it there:
with 22 branch states and ~30 CFG edges, every logical line is E-heading under
any attachment order, so band-widening cannot enable fusion. **The band move
pays on op-dense, control-sparse grids (LLLM: 14 blocks / 7 edges). On
control-dense grids the waste is op-free CONNECTOR geometry — attack it with
`tools/stairfold.py` (flatten walk staircases), `tools/reroute.py` (A* rip-up
of connectors with an empty-row-cost objective), and `tools/walkfold.py
squash`.** Diagnose first: count blocks vs edges with `tools/blockify3.py`.

## The method (`tools/reflow.py`)

1. **blockify** — recover the program as basic blocks from the executed walk
   (LLLM: 14 blocks, 7 back edges). Wall-ness is geometric: `-` and `|` are
   walls *or* instructions depending on position, so lift from the oracle's
   executed sequence, never from glyph identity.
2. **Layout** — re-emit the walk as a dense boustrophedon, placing each op at
   the next column its pipe binding allows. One rule covers the dense body and
   peripheral zig-zag ops.
3. Back edges are interval-coloured onto a few corridor columns; a merge's
   fall-through predecessor and its back edge share the same `>` cell.
4. Closed sub-networks (rooms + display reachable only through one pipe) are
   **translated verbatim**, not redrawn.
5. `fold` (separate pass): redraw long delay lines as staircases —
   `tools/equiv.py` can certify those (1.693x alone on LLLM).

## Gates that made it safe

- Identical block structure and op sequence after reflow.
- Pipe signature identical **keyed by (src, dst, len)** — `pipecheck` renumbers
  pipes, so an index-keyed diff is pure noise.
- Pipe lengths preserved: length is BOTH latency and capacity. Never shorten a
  pipe that might be a FIFO store (gradebook's 54-cell delay line at 23 cells
  passed 6/7 public and timed out on the 7th — a *silent private-style* fail).
- `emit.py --roundtrip` clean; `difftest` green; grade on the Rust engine and
  spot-check tick-exact agreement with the wasm oracle.
- `equiv.py` cannot certify transforms that change path lengths by design —
  for those the gate is the op-sequence + binding + grade triple, not a proof.

## Traps (each cost real time)

1. A pipe's **last cell must be an arrowhead pointing at the destination
   wall**. Ending a straight run on `|` silently disconnects it — the loader
   reports `dst: -1` and nothing errors until the program hangs.
2. Backtick literals parse on **both axes** and read **reversed westward** —
   literal runs are rigid; never re-head or split one.
3. A pipe running alongside a room's wall reads as attached to that room and
   steals its `s`/`r` bindings (adjacency, not just endpoints).
4. `R`/`U` pick among ready incoming pipes in **reading order** — moving
   attachments must preserve each room's incoming reading-order permutation.
5. The wasm oracle (Go) OOMs on heavy runs (`Go program has already exited`).
   Use the Rust engine: `python3 tools/grade_fast.py <slug> <file> --jobs 4`
   (binary: `interp/target/release/lm`; a prebuilt copy lives in the
   `icfpc-2026-lllm` worktree and the sources are identical — copying the
   binary between worktrees is fine).

## Where this transfers

- Any champion whose box is mostly whitespace with hot pipes attached mid-wall.
  Diagnose with `tools/walkfold.py map` (band report) + `sim/xray.js` (BOX
  DRIVER / CORRIDORS): if the hot pipe's band is a small fraction of the wall,
  reflow applies.
- Generated (stateflow/flowgrid) solutions: the same economics, but fix the
  *generator* instead — snake went 632x364/451B → 312x346/60.6B local (server
  685B → 91.8B) by shrinking `code_x` 380→60 (edge-lane spread), banking both
  RAMs (`split_ram`; scalar 32/4 works, 32/8 fails), and raising the display.
  Grids from builders should be reflowed in the builder, not post-hoc.
- Estimated ~1.2x still on the table for LLLM itself (room0 fill 78%, room2 /
  display stacking) — see the reflow report in `tl-b8w6f` notes.

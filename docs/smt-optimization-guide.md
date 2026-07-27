# SMT-based optimization: inside the box and outside it

`score = max(w,h)^2 * avgTicks`. Only the **binding dimension** is squared, so every geometric
move is worth exactly nothing unless it shrinks `max(w,h)`. This guide is how to use the Z3
tooling to do that, what each solver can and cannot see, and the one missing capability that
currently blocks most of it.

## The two problems, and which tool owns each

| | what moves | tool | when it can help |
|---|---|---|---|
| **OUT of the box** | whole rooms, rigidly, with their men and cells carried along | `tools/place.py` (anneal) / `tools/smtplace.py` (Z3-exact) | the air is BETWEEN rooms |
| **IN the box** | individual ops inside one room | `tools/smtrows.py` + `tools/liftflow.py` | the air is INSIDE a room |

**Diagnose before you solve.** Compute density and `box/area` per champion:

    density = content_cells / (w*h)      low  => intra-room work (smtrows)
    box/area = max(w,h)^2 / (w*h)        >1.1 => inter-room work (place)

Measured 2026-07-27 on the live champions:

| champion | grid | density | box/area | rooms | which stage |
|---|---|---|---|---|---|
| LLM | 356x793 | 6.0% | 2.23 | 26 | **inside** (see below) |
| Snake | 67x67 | 19.7% | 1.00 | 5 | inside |
| Grade Book | 47x64 | 26.2% | 1.36 | 8 | both |
| LLLM | 142x141 | 29.7% | 1.01 | 5 | inside |
| Matrix Multiply | 68x75 | 30.8% | 1.10 | 9 | both |
| Plotter | 48x58 | 35.9% | 1.21 | 7 | outside |
| Subset Sum | 449x386 | 36.1% | 1.16 | **279** | outside |
| sudoku / tcp / memory / brackets / history | — | 55–95% | 1.00 | — | **none, already dense** |

A high `box/area` is NOT sufficient. LLM scores 2.23 yet rigid placement is useless on it,
because **one room is 742 of its 793 rows**. Always check *where* the rows live, not just the
aspect ratio:

    python3 tools/place.py <slug> <man> --budget 400 --top 0 --dry-run -v

That prints the block decomposition, a byte-for-byte round-trip check, and the offsets of every
room. If one offset owns most of the binding dimension, stop — a placer moves rooms, it cannot
reshape one.

## Inside the box: `liftflow` + `smtrows`

`smtrows` asks Z3 for the true optimum of the boustrophedon placement problem. Encoding, per
block: ints `r_i` (row), `c_i` (col); direction is row parity (blocks enter east); same row =>
strictly monotone columns in the row direction; `row+1` => drop-column linkage (east->west
`c' <= c`, west->east `c' >= c`); every port op must sit strictly inside its pipe's Voronoi band.
Phase 1 fixes the port columns and **certifies** how far the greedy layout is from optimal;
phase 2 frees them for the joint optimum.

It used to accept only a `build*.py` exposing `build_flow()` — which just two builders in the
repo do. `tools/liftflow.py` closes that: it recovers the same object straight from a grid, so
smtrows runs on ANY champion.

    python3 tools/liftflow.py <man> --man-index <i>     # inspect the recovered flow
    python3 tools/smtrows.py  <man> [--free-ports] [--timeout MS]

What `liftflow` reports, and how to read it (snake's controller, live 4d96c89f):

    28 blocks, 283 ops, 160 port ops, 6 ports
    coplanar attaches: True      <-- all r/s attach on ONE row
    op rows used now: 48 (room gives 59)
    o3 col 19 band [1,24] used 65x    i1 col 20 band [1,27] used 64x
    o4 col 31 band [26,37] used 5x    i0 col 37 band [30,39] used 4x
    i2 col 43 band [41,45] used 5x    o5 col 46 band [40,45] used 17x

Two things jump out and both are actionable. **`coplanar attaches: True`** means every port
shares one wall row, so the Manhattan y-term cancels and binding degenerates to a pure COLUMN
Voronoi — a self-inflicted constraint, since binding is really full 2D. And the **cold ports
own the east half**: three ports used 4x/5x/5x occupy columns 31..46, which is what forces the
room's width. Clustering cold attachments is the highest-value port move.

## Aim the reflow: shrink the BINDING dimension only

On snake the two dimensions are driven by different structures:

    grid_h = 6  + controller_h      (top band: two 6x4 relays + a 3x3 input)
    grid_w = 20 + controller_w      (driver 11x7 + display stack, east)

so the balance condition is `controller_h = controller_w + 14`. The live champion is 47x61 —
**exactly on that line**, so it is already optimally proportioned and any further gain must come
from DENSITY, not shape. Compute the analogous relation before optimizing anything; shrinking
the non-binding dimension moves the score by zero.

## AIM THE SOLVER AT THE BINDING AXIS — and min-ROWS IS THE WRONG OBJECTIVE

`smtrows` used to shrink the ROW count only. It now takes `--objective`:

    --objective rows    legacy: minimise rows, width only a constraint
    --objective width   (a) minimise WIDTH subject to rows <= --max-rows
    --objective box     (b) minimise max(rows + chrome_h, width + chrome_w)  <- the REAL one

`chrome_*` are derived from the grid (`grid_w - room_outer_w`, likewise h), not hardcoded.
The rows-vs-width curve is computed by an O(n*W) DP (`dp_block_rows_fast`, prefix/suffix
minima over the same automaton; cross-checked against the quadratic DP on 1,511 (block,width)
pairs, 0 mismatches), so the whole Pareto curve is seconds, not minutes. `--curve` prints it.

**MEASURED 2026-07-27 — the legacy objective makes the score WORSE on 3 of the 4 targets:**

| problem | current | min-ROWS | min-WIDTH (a) | joint (b) optimistic | joint GUARANTEED |
|---|---|---|---|---|---|
| Snake | 67²=4,489 | 70²=**4,900** | 67²=4,489 | 67²=4,489 | 67²=4,489 |
| LLLM | 142²=20,164 | 143²=**20,449** | 141²=19,881 | 138²=19,044 | **141²=19,881** |
| Pathfinder | 180²=32,400 | 187²=**34,969** | infeasible | 182²=33,124 | 182²=33,124 |
| LLM | 793²=628,849 | 786²=617,796 | 786²=617,796 | 786²=617,796 | 793²=628,849 |

Read the min-ROWS column: cashing it in costs 9% on snake, 8% on pathfinder, 1.4% on LLLM.
It buys rows with width, and only the squared axis is ever paid for. **LLM is the only
problem where min-rows is even pointed the right way**, and that is exactly the one problem
whose binding axis is HEIGHT.

### GUARANTEED vs OPTIMISTIC — the chrome does not slide for free

Additivity (`grid_w = room_w + chrome_w`) assumes the chrome MOVES when the room shrinks.
The tool now also computes the **rigid floor**: the bbox of every non-room cell, i.e. what
the grid cannot go below if nothing outside the room moves. The two bracket the truth, and
the gap is precisely the work a placer would have to do.

* **LLLM** — non-room content stops at x=101 but reaches y=140. So the room owns the WIDTH
  (narrowing is free and needs no placement) while the HEIGHT is 39 rows of pipe forest
  *below* the room. Guaranteed 141²=19,881 (1.4%); the further drop to 138² needs that
  forest to slide up, which re-lengths every pipe crossing the room's bottom wall.
* **LLM** — the rigid floor is 356x793, i.e. the current grid EXACTLY. The 7 rows min-rows
  finds inside the controller are worth **zero** unless the chrome slides.
* **Pathfinder** — the rigid floor is already 180x180, so the controller room cannot change
  the box at all, whatever the model says.

### Per-target verdicts

* **Snake — NEGATIVE, certified.** The joint objective's V-bottom lands on side 67 at
  width 42 / 59 rows: *exactly the champion*. The curve either side (w=41 → side 71,
  w=43 → 68, w=45 → 70) is strictly worse. Snake is optimally proportioned under this model
  and there is nothing left to take.
* **Pathfinder — NEGATIVE twice over.** The model needs 118 rows where the champion spends
  116, so it loses at every width; and the rigid floor pins the grid at 180x180 anyway.
* **LLM — CONDITIONAL.** 7 rows are available inside the controller, worth 1.8% *if and only
  if* the 51 rows of chrome below it can be moved up. That is a `place.py` + folded-routing
  job, not an `smtrows` job.
* **LLLM — the only guaranteed win, and it is small.** 1.4%. It needs a genuine re-placement:
  no interior column is blank (the boustrophedon turns at x=140), the champion was imported
  rather than generated, so no builder knob exists, and the model's row answer (97) is below
  the champion's block-rows (102) but ABOVE its 95 physical rows — so an emit that fails to
  reproduce the row SHARING comes out ~2 rows taller and makes the box worse.

### Coordinate bug fixed: port bands were absolute, op columns were relative

`liftflow` reports a port's column and Voronoi band in **absolute grid columns** (they come
off the pipe's attach cell), but every placement model here puts ops at columns `1..wmax`
where `wmax` is the interior WIDTH. Those agree only when the room's interior starts at x=1.
Snake, LLLM and LLM all do — **pathfinder does not** (its interior starts at x=59), so its
bands (up to 145) sat entirely outside the 1..87 column range and every block reported
INFEASIBLE. A silent wrong answer, not an error. `smtrows.normalize_ports()` now shifts the
bands at load time; it is idempotent and a no-op for x0 == 1, so earlier results stand.

## smtrows CANNOT BEAT A HAND-FOLDED CHAMPION — it forbids row sharing

Measured, with a Z3 optimality certificate (per block: `rows<=k` SAT and `rows<=k-1` UNSAT):

    snake champion : 48 PHYSICAL op rows (54 block-rows, 6 SHARED between blocks)
    smtrows optimum: 50 rows (41 if `X` is inline)     -> the champion is ALREADY BETTER
    gradebook      : model 49, champion 46 physical    -> same result

The champion wins by parking several small blocks on ONE row. The encoding lays blocks strictly
one under another, so it structurally cannot express that fold. **The "70% blank glide" figure is
therefore misleading**: that air is the boustrophedon's turn-around and drop columns, and Z3
re-creates the same structure rather than removing it.

If you want to keep pulling this thread, the lever is to EXTEND THE MODEL with an
interval-packing layer that allows row sharing between independent blocks — not to run the
existing model harder or longer.

Practical notes: with ports FIXED no constraint couples two blocks, so phase 1 decomposes into
N tiny problems (0.7s) — a monolithic `Optimize()` over 25 blocks did NOT close in 300s. Phase 2
(`--free-ports`) did not close either (UNSAT/timeout at 601s); coordinate descent over port
columns with the exact per-block DP as evaluator reached 46, against a rigorous lower bound of
35, so phase 2 is BRACKETED [35,46], not solved.

## Moving ports is NECESSARY but NOT SUFFICIENT

`place.py` already slides attachments — 25% of the annealer's moves, free unless `--pin-attach`.
Its own move-set docstring says why that matters: *"with the attachment pinned, a room can only
move on the axis its pipes already point along, and whole floorplans are unreachable."*

But **a rigid room cannot be reshaped by moving it or its ports.** Measured:

    LLLM  grid 142x141:  room 0 = 142w x 102h   <-- room 0's own WIDTH is the grid width
    LLM   grid 356x793:  room 0 spans y0..742   <-- room 0's own HEIGHT is 742 of 793 rows

The placer duly finds 142x138 / 142x139 / 142x140 on LLLM — it re-attaches pipes to compact the
HEIGHT — and width 142 never moves, because no rearrangement of a rigid 142-wide block fits in
less than 142 columns.

So when one room owns the binding dimension, the answer is neither room moves nor port moves
alone, but **both together with the ops**: `smtrows --free-ports` frees the port columns and
derives the Voronoi bands INSIDE the model, so ports and the ops bound to them move jointly.
That joint encoding is the only thing that can narrow the room itself — which is exactly why it
exists, and why `liftflow` (which lets it run on a grid at all) was the unlock.

## The missing capability: LENGTH-PRESERVING FOLDED ROUTING

This is why most placement proposals die. `tools/router.py` is A* minimising
`steps + BEND*bends + GROW*bbox_growth` — it finds the SHORTEST path and has no notion of a
length target (`grep min_len|pad|detour|serpent` finds only a scope note: *"v2 (CFG folding) is
NOT here"*). But **pipe length is capacity AND latency, so a re-route may never shorten a pipe.**
When the shortest available route is shorter than the original, the router cannot pad, and
reports `pipe N unroutable`.

Measured consequences:
* `smtplace` on gradebook: UNSAT at a tight budget; at a relaxed budget **all 20 proposals failed
  routing**.
* `place.py` on LLM: 198 tries, 26 valid floorplans, **every one identical to baseline**, all
  failures `pipe N unroutable`.

The fix is standard PCB length-matching, and it is not hard:

1. Route the shortest path with the existing A*.
2. If `len < required`, absorb the slack in an **accordion serpentine** placed in nearby FREE
   cells — each fold adds 2 cells of length for 1 cell of width.
3. Validate with the existing `layout.validate_pipe`.

A folded pipe keeps its length exactly, so capacity and latency are untouched and the result is
`tools/equiv.py`-PROVABLE — it can be accepted with no grading at all. This one addition
unblocks rigid placement on every problem in the table above.

**Ports can already move**: `place.py` takes `--pin-attach` to pin them (so they are free by
default), and the plan JSON carries `attach:[[[sx,sy],[dx,dy]]..]`. Moving a port is what makes
a reflow possible in the first place — but it re-binds every op inside its new radius, silently.

## The four silent cliffs — reuse the checks, never re-implement them

Each produces a wrong answer with NO error. `place.py` already implements all four:

1. **nearest-pipe binding** under BOTH endpoint readings (Manhattan, reading-order ties);
2. **R/U reading-order permutation**;
3. **pipe length floor** — capacity AND latency;
4. **`Program.pipe` silently overwrites a room wall** if a pipe starts on the wall column.

On (3), the rule is not "never resize a ring" — it is *check capacity against the true worst
case*. Snake `push2` changed pipes `[3,5,5,6,8,11,16,31,38] -> [...,11,31,46]` and failed 2
PRIVATE cases (15/17) after a clean 5/5 public oracle pass; `push4` shrank `16->14` and was fine
(17/17). Fuzz the worst case (snake's failing shape is `grow-60`) before submitting.

## Gating: prove it when you can, grade it when you cannot

* `tools/equiv.py before.man after.man` PROVES identical behaviour — same op sequence per man,
  same path length, same pipe structure — without simulating. A move-only transform cannot change
  the tick count, so an equiv-proved move is safe on every case INCLUDING PRIVATE ones, by
  construction, at zero cost. **Caveat: it can only ever accept transforms that preserve path
  length exactly, so it can never accept a line deletion.**
* Otherwise grade: `python3 tools/grade_fast.py <slug> <man> --jobs 8`, which averages over
  PASSING cases only — a partial pass is NOT comparable.
* Snake's server/local ratio is **1.4665** and very stable across four submissions, so
  `local * 1.4665` predicts the server score. Derive the equivalent constant per problem before
  deciding a candidate is worth a submission slot.

## Recommended order

0. **Run `--objective box` FIRST** (`python3 scratchpad/axis_table.py` does all four at once,
   ~2 min). It reports the rigid floor and the joint optimum together, so a negative is
   established before any solver time is spent — and three of the four targets are negatives.
1. Measure density and `box/area`; check whether one room owns the binding dimension.
2. If it does — `liftflow` + `smtrows` (inside). Phase 1 first: it may certify you are already
   optimal, which is a complete answer.
3. If it does not — `place`/`smtplace` (outside), but expect routing failures until folded
   routing exists.
4. Aim at the binding dimension only, using the problem's own `grid_h`/`grid_w` relation.
5. Gate with `equiv` where possible, grade otherwise, fuzz any ring change, and submit —
   submitting never lowers a score.

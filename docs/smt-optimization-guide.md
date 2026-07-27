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
  **(Cashed 2026-07-27 — see PHASE 2 below. It needed no re-placement at all.)**

## PHASE 2 (2026-07-27): the LLLM width win was REAL — and it needed no emitter

`scratchpad/narrow_room.py` + `scratchpad/lllm_narrow141.py` cashed it: **LLLM 142x141 →
141x141, box 20,164 → 19,881, server 6,282,959,332 → 6,181,747,964 at 21/21** (submission
`a9f9882b`). Ticks fell too (285,127.6 → 284,527.8), so the win is 1.61%, not 1.4%.

**Do not re-emit a hand-folded champion to narrow it — SLIDE it.** Deleting one BLANK cell per
row and shifting that row's suffix one column west keeps every op in the same row and the same
order, so the walk is the original minus a few nop glides and the ticks can only fall. Only two
things can break, and both are constraints in a Z3 model rather than hopes:

1. **vertical moves** — `v` at (x,y) hands control to (x,y+1), so rows y and y+1 must agree on
   whether column x slid. Read the links off the static walk's TRANSITIONS, never the states'
   own headings: a branch is entered eastward and leaves vertically, so the branch cell's own
   heading does not reveal the link it creates (this bug produced a walk that died after 383
   of 4,499 ops);
2. **pipe re-binding** — every `s`/`r`/`q` is re-resolved at its destination with
   `liftflow._bind` (the engine's rule verbatim) against its ORIGINAL binding, and pinned if it
   would change pipe.

**The blocking structure, and how it was broken.** With the pipes where they were the model is
UNSAT, with a 3-literal core: LLLM's hot rows are packed solid from column 48 — the o1|o2
Voronoi floor — to column 139, so nothing can slide. The fix is to move the two COLD `s` pipes
and drag the midpoints west: `o0` 18→22 and `o1` 31→29, both re-routed at **EXACTLY** their old
length (pipe 0 is 137 cells because room 4 + pipes 0/8 are the LLLM tape's shift register — a
cell either way changes the machine, not merely its timing). Then all 100 rows slide.

`smtrows --objective box` had said the same thing a different way (width headroom all the way
down to w=130) but attributed the win to re-placement. The champion did not need re-placing.

Pipe-drawing gotcha found here: a pipe's **first and last cell must carry a direction glyph**
(`v^<>`), never a straight `|`/`-`. Emit `|` at the endpoint and the analyser reports `dst = -1`
and the oracle says `pipe runs into wall` — with the grid otherwise perfect.

Gates used, in order: liftflow token sequences byte-identical (23 blocks, 4,499 ops, same
ports); pipe profile identical (9 pipes, same src→dst and same LENGTH, only two attach cells
moved); per-man op sequences identical with only man 0's walk shrinking (7,721 → 7,694 cells);
`grade_fast` 10/10; **oracle** 10/10; and the four extra suites — `lllm-adv` 115/115,
`lllm-fuzz` 200/200, `lllm-stress` 17/17, `lllm-oos` 3/6 (the champion also fails those three).
`tools/equiv.py` correctly REFUSES this transform: deleting blank cells changes the path length,
which is exactly what it is built to reject. This is not a move-only transform.

### Where LLLM stands now, and what the next column costs

141x141 is square, so BOTH axes bind. Two facts for whoever picks this up:

* interior **row 100 is completely blank**, so the height drops to 140 for free — the moment the
  width reaches 140. Deleting a blank interior row shifts the whole pipe forest up rigidly and
  preserves every pipe length exactly, because the deleted row contains no pipe cell.
* the second column is **SAT in the slide model** (`narrow_room.py narrow141.man --cols 1
  --pipe-cols 1:27` → 140x141) but blocked by pipe congestion: `o1` must then attach at column
  27, and pipe 0's 137-cell delay line needs five spacing-2 legs, which can only sit in columns
  18..26 (pipe 8 owns ≤17, room 2 starts at 34) — so a leg always lands adjacent to column 27.
  Four legs cannot hold 137 cells (4x28+3 = 115). Solve that and LLLM is 140x140 = 19,600,
  another 1.4%.

## PHASE 2: the other three targets, re-confirmed NEGATIVE

* **Snake, Pathfinder** — nothing emitted, as Phase 1 certified. Snake's joint optimum IS the
  champion; pathfinder's rigid floor is already 180x180.
* **LLM — `place.py` with the new folded routing still cannot move the box.** 396 tries, 40
  valid floorplans, **every one box 628,849 (356x793)**, room 0 pinned at offset (1,0) in all of
  them. Folded routing raised the valid rate but not the box: room 0 is 318w x 742h of a 356x793
  grid, so no rigid move can touch either axis.
* **But there is a 12% lead on LLM that is not an `smtrows` problem.** Room 0 occupies
  x 0..317, y 0..741; all 25 other rooms sit in rows 744..792. That leaves **38 free columns
  (x 318..355) x 742 rows** of air beside room 0. Move the bottom cluster into that strip and
  the grid becomes ~356x744: box 628,849 → 553,536, **-12.0%**, ticks untouched. The annealer
  will never find it (one coordinated move of 25 rooms and 48 pipes); it needs a hand-written
  `place.py --plan` with `--pipe-len exact`.

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

### RESOLVED, AND IT UNBLOCKED NOTHING — the real blocker is COLUMN-VORONOI BINDING

Folded routing landed (`tools/router.py` §3c, `be429ed`; `place.py` already had its own
`_route_len`/`_pad`). Measured 2026-07-27 on the three named targets: **no problem's box moved.**

| target | baseline | best floorplan found | why it stops |
|---|---|---|---|
| LLLM | 142x141, box 20164 | 142x136 (free), 142x141 (exact) — **box 20164 either way** | room 0 is **142 wide**, and the grid is 142 wide. `max(w,h)^2` is already at its floor; the height the placer buys is worth exactly zero. |
| Grade Book | 47x64, box 4096 | 4096 in free/min/exact | height floor 58+2+4 = 64, see below |
| LLM | 356x793, box 628849 | 628849 | tail is a fixed-length pipe CHAIN, see below |

**Widening `place.py::_pad`'s fold window changed nothing**: gradebook, 798 tries/seed 7, old
window (2..len-4) vs new (1..len-2) gives byte-identical results — exact 2 valid, min 19, free 15,
best box 4096, same failure histograms. The comment in `_pad` that credited the widening with
`2/60 -> 20/60` was wrong and has been corrected.

**Most `pipe N unroutable` failures are NOT length failures.** They persist with `--pipe-len free`,
where there is no length target at all (gradebook free: 74 for pipe 9, 43 for pipe 3, …; LLM tail
lifted 1 row: `pipe 5 unroutable` in free/min/exact alike). They are occupancy and attachment
failures. Length padding was never the binding constraint.

**What actually binds: `r`/`s` resolution.** Both big controllers put EVERY port on ONE wall of
the big room, and each pipe's ops form a narrow COLUMN band spanning nearly the room's full
height — so binding is a pure column Voronoi and the port set cannot leave that wall:

    gradebook room0 39x58, 12 ports all on y=57, 66 ops:
      's'->pipe 1: x[8,8]    y[18,56]      'r'->pipe 7:  x[2,5]   y[1,44]
      's'->pipe 2: x[9,10]   y[14,50]      'r'->pipe 8:  x[7,11]  y[15,55]
      ...                                  ...
    LLM room0 318x742, 12 ports all on y=741, 2362 ops:
      's'->pipe 1: x[119,206] y[1,735]  (1381 ops)   'r'->pipe 10: x[150,203] y[3,735]

The decisive experiment: gradebook's satellites stacked in the right margin is a **47x58, box
3364 (-17.9%)** floorplan, and it **ROUTES COMPLETELY** — `route_all(pipe_len='exact')` returns
`bad=None` with every pipe at its exact original length `[48,2,2,2,2,2,38,2,2,2,2,2]`, the two
long ones padded by the folder. `build()` then rejects it with **`nearest-pipe resolution
changed`**. Every op band spans the full height, so no row-ordering of right-wall ports can
reproduce a column partition. It is not a near miss; it is structurally impossible.

Two geometric floors that follow, both proven rather than searched:

* **Grade Book h=64 is exact.** A 2-cell pipe must be a STRAIGHT 2-cell stub out of the source
  wall (`interp/src/lib.rs`: cells[0] is a pipe start only if `cells[0] - arrow_dir(cells[0])` is
  a room border, so the first step is the wall normal; only the LAST cell may bend). For the five
  satellite->room0 pipes that forces the satellite's top wall to y=60, and four satellites are 4
  tall => 58+2+4 = 64. Side-wall variants that reach y=58 force `left_edge = qx_out+2` and
  `left_edge = qx_in+1` simultaneously, i.e. `qx_in = qx_out+1`, which no satellite's port pair
  satisfies (block 4 needs 9, has 11) and which moving the port would re-bind.
* **LLM's 51-row tail is a pipe chain, not a slab.** room0(y=741) --len 9--> block3 (7x8)
  --len 2--> block24 (15x38). Block 24 cannot go beside room 0 (room 0 owns x 0..317 for all
  y<742) so its top is >= 742 and its bottom >= 779: the absolute rigid floor is ~790 vs 793,
  **1.03x**, not the 1.14x this guide previously implied. Pulling the whole tail up even ONE row
  fails as `pipe 5 unroutable` in free mode (the 18x18 display collides), so the 1.03x is a
  ceiling nobody can reach cheaply.

**Practical rule.** Before running any placer, print the op bands
(`base_resolution` grouped by (op, pipe) with x/y extents). If each pipe's ops are a column band
spanning the room's height, the ports are welded to one wall and rigid placement can only
translate the satellites along that wall — the box will not move, whatever the router can do.
Folded routing is still worth having (it is what let the 3364 floorplan route at exact length at
all, which is how we could prove the blocker is binding); it is just not the lever.

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

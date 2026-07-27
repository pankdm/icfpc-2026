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

1. Measure density and `box/area`; check whether one room owns the binding dimension.
2. If it does — `liftflow` + `smtrows` (inside). Phase 1 first: it may certify you are already
   optimal, which is a complete answer.
3. If it does not — `place`/`smtplace` (outside), but expect routing failures until folded
   routing exists.
4. Aim at the binding dimension only, using the problem's own `grid_h`/`grid_w` relation.
5. Gate with `equiv` where possible, grade otherwise, fuzz any ring change, and submit —
   submitting never lowers a score.

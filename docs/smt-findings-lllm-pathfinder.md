# SMT on the LLLM and Pathfinder champions (measured 2026-07-27)

Companion to `docs/smt-optimization-guide.md`. Everything here was measured against the
**live** downloaded submissions — LLLM `dae1e98e` (142x125) and pathfinder `637a8296`
(151x174) — not against in-git variants.

## 0. The pipe-endpoint bug had a SECOND casualty: the LLLM champion

The `border_cell_of_pipe_end` / `pipe_flow_dir` defect fixed on main (found via the snake
champion) also made `grade_fast.py` reject the **LLLM champion** on all 10 cases with
`display pipe bad side`, while the wasm oracle ran it **10/10**. Every fast loop —
smtplace, autotune, any search — was therefore blind to that champion, which is why the
sweeps below had to be re-run after the fix.

The LLLM instance, for the record: pipe 5 arrives westward along row 124 and turns north at
`^` (64,124) into the display's bottom wall (SWAP). `prev -> end` gives `(-1,0)` and border
`(63,124)`, a blank cell; the arrowhead's own direction gives `(0,-1)` and border
`(64,123)`. With the fix, Rust matches the oracle exactly on that file (10/10, avgTicks
285104.6, score 5,748,849,154) and `sim/difftest.js` is 61/61.

A sweep of every `.man` in the repo found no *other* file whose load status changed, so
snake and LLLM appear to be the only two casualties — but note both were found by accident,
one per investigation. `trace_pipe` guarantees the end cell is an arrow pointing into the
room, so the arrowhead is always authoritative.

## 1. LLLM: rigid placement is provably dead

    smtplace little-little-little-man live-125x142.man --gap 2 --extra 8
    -> UNSAT in 0.0s

Not a timeout — a certificate. Room 0 **is** the binding dimension: 142x102, and
`max(w,h) >= w >= 142` = baseline for any rigid placement. Room 0 is 81.6% of envelope
area, well above the guide's ~70% "smtplace has nothing to work with" threshold.

Intra-box geometry is exhausted too:

| pass | result |
|---|---|
| `roomfit` | "no room has a free margin" — nothing to do |
| `fold` | 1 row fold, **0 column folds** |
| `polish` | 1 pipe-row; cuts h 125->124, **score unchanged** (width binds) |

There are no blank columns anywhere in the grid, and every interior column of room 0 has
>= 2 occupied cells.

## 2. `smtrows` cannot run on EITHER champion — and an objective flag will not fix it

`smtrows` minimises ROWS, so it only pays where HEIGHT binds. That makes it the wrong
tool for LLLM (width binds) — but the deeper problem is that its model puts **one block
per row**, and both champions have blocks wider than the room:

| | ops | as-built op rows | room interior | max block | verdict |
|---|---|---|---|---|---|
| LLLM | 4499 | 95 | 140x100 | 1650 ops | infeasible |
| pathfinder | 984 | 117 | 59x163 | 62 ops | `block B0 has no legal placement at wmax=59` |

So the missing capability is **blocks that wrap across rows**, and only then an
axis-selectable objective. Two further cautions before building it:

* For a **fixed** width the greedy is already at/near optimal — as-built 117 rows beats
  greedy's 121 (the hand-fold wins). A column objective alone would therefore report the
  current width as optimal. A useful column mode must sweep width and **re-derive the port
  columns**, because the Voronoi bands move with the ports.
* `coplanar attaches: True` on both: every port shares one wall row, so the Manhattan
  y-term cancels and binding degenerates to a pure column Voronoi — a self-inflicted
  constraint, per the guide.

## 3. What a reflow is worth (bounds, not guesses)

**Band-implied row floor.** Ops bound to a port must sit inside its band, one op per cell,
so any port group confined to a `W`-column window needs `>= uses/W` rows:

| | tightest group | ops | window | row floor | as-built | slack |
|---|---|---|---|---|---|---|
| LLLM | o2+i4 | 3438 | cols 40..140 (101) | 35 | 95 | 2.7x |
| pathfinder | o37+i41 | 433 | cols 81..99 (19) | 23 | 117 | **5.1x** |

**Ideal-packing box ceiling** (controller packed to 100% density, other structures held
constant — LLLM grid = controller + 2 cols + 25 rows; pathfinder = + 92 cols + 11 rows):

| | now | ideal | ceiling |
|---|---|---|---|
| LLLM | 142x125, box 20164, controller 32% dense | 81x82, box 6724 | **3.00x** |
| pathfinder | 151x174, box 30276, controller 10% dense | width-capped at 151, box 22801 | **1.33x** |

Pathfinder's is width-capped because 92 of its 151 columns are rooms *beside* the
controller. The encouraging part: capturing the **entire** 1.33x needs the controller's
interior to go 163 -> 140 rows — only 23 rows — and **46 of its 163 rows already carry no
ops**. This is packing, not algorithm.

## 4. The live pathfinder is a different architecture from the bitplane model

`pathfinder_bitplane_floorplan.json` describes the **in-progress bitplane** design
(149x16 controller + 16 lanes of 9x120 + 19x7 counter). The **live** 151x174 build is not
that machine: it is 23 rooms / 43 pipes with **one 61x165 room owning 165 of its 174
rows**. Numbers from one do not transfer to the other.

For the live build: `max(w,h) >= 165` (the tall room), so rigid packing alone is worth at
most 174 -> 165, box 30276 -> 27225 = **1.11x**, with zero tick change. Round-trip is OK
and the baseline grades 7/7 (13,706,745,351 on Rust), so it is a legitimate smtplace target.

**But Z3 cannot solve it.** Two runs, both `unknown` with 0 sat / 0 unsat:

| run | settings | result |
|---|---|---|
| 1 | `--gap 1 --extra 12 --timeout 120` | solver timeout at 120s |
| 2 | + `--min-m 165` (the true floor), `--timeout 480` | solver timeout at 480s |

So 24 blocks / 43 pipes is already past this encoding's reach at an 8-minute budget — the
pathfinder win in `0b55bfe` came from a *sparser* instance, not a bigger budget. Note also
that the printed lower bound is **area-only** (`M >= 132`) and ignores the trivial
`M >= max(block_w, block_h) = 165`; adding that as a hard constraint (not just a printed
hint) is the cheapest available improvement to the encoding, since it removes 33 hopeless
values of M from the search.

## 5. The bitplane floor is 144, and 149 is only the controller's own width

Solved with `smt_layout.py` on the committed spec:

| spec | result |
|---|---|
| controller 149 wide (as modelled) | 149x143, box 22201 |
| controller narrowed to 144 | **144x143, box 20736** |
| controller 125 wide, counter tucked beside it | 144x144, box 20736 |
| cap 143x143, controller only 100 wide | **UNSAT — floor proved** |

So **box >= 20736 for this architecture**, set by the 16 lanes (16 x 9 = 144 columns;
stacking them instead makes H >= 240, strictly worse). The 149 in the current envelope is
purely the controller's own width — narrowing it by 5 columns captures 22201 -> 20736
(1.07x), and nothing narrows it further. Against the live 30276 the whole bitplane
geometry prize is **1.46x**.

`smt_layout` used to crash on UNSAT (z3 exits nonzero because the trailing `(get-value)`
has no model, and `solve()` checked the exit code before the verdict). Since UNSAT is the
*informative* answer when proving a floor, it now raises `Unsat` and exits **3**, so a
caller can distinguish "proved impossible" from "tool broke".

## 6. Why LLM is 15x off: it is ALL box, and we are already faster than the leader

Server-side split (`submissions.py --match`): ours is **356x793, box 628,849, avgTicks
4,541,013** = 2.856T, HEIGHT-bound with **+437 columns of slack**. Board best 190.41B.
Decomposing 190.41B against the 50M tick cap:

| leader side | box | implied avgTicks | vs our ticks |
|---|---|---|---|
| <=56 | <=3136 | >50M | **ruled out by the cap** |
| 64x64 | 4,096 | 46.5M | 10.2x MORE |
| 80x80 | 6,400 | 29.8M | 6.6x MORE |
| 100x100 | 10,000 | 19.0M | 4.2x MORE |
| 142x142 | 20,164 | 9.4M | 2.1x MORE |

In **every** feasible split the leader spends MORE ticks than we do. We are not slow; we
are enormous. The whole 15x is box, and box is squared while ticks are linear.

Cause: the controller **unrolls the CFG** — 742 of 793 rows in one room, one op-row per
block (194 blocks + 98 `br` x 3 rows ~ 490-row structural floor). A 64-100 side grid
cannot hold an unrolled CFG, so the leaders must keep the program as **data** and
interpret it in a loop: ~10x the ticks, ~150x the box.

The tell: **our avgTicks is 9% of the 50M cap.** We hoard tick headroom and pay for it
quadratically. The trade is `score_ratio = k/s^2` (k = tick multiplier, s = side shrink),
so spending ticks to shrink the side is almost always profitable from where we sit.

Ceiling for layout work: CLAUDE.md's measured no-band-conflict ideal is 321x552 =
304,704 (2.78x), squaring 356x793 gives ~2x, and the CFG floor 490-507 rows gives
2.4-2.8x — these **overlap rather than compound**. So SMT/placement reaches at most
~2.8x of the 15x; the remaining ~5.4x is architectural. Do not spend floorplanner time
on LLM expecting more.

The same test applied to LLLM (`decompose.py`): board best 926.76M is consistent with
58x58 (3364) x 275,493 ticks or 59x59 x 266,234 — i.e. ticks within 13% of our 311,593,
with a **6x smaller box**. Our 4499-op controller cannot fit in a 56x56 interior, so the
LLLM leader is also looping where we unroll. Its 6.8x gap is ~6x box, ~1.1x ticks, and
section 3's ideal-packing ceiling (3.0x, box 6724 = 82x82) still lands ABOVE the leader's
3364 — packing alone cannot get there either.

## 7. Where LLM's box actually goes — and the exact 1.14x tuck

Block decomposition of the live 356x793 (`live-2b320f4f`, 27 blocks / 48 pipes):

* **r0 = 318x742** at x 0..317, y 0..741 — the controller, **742 of the 793 rows**, and it
  has **0 fully blank interior rows** (so `roomfit`/`polish`/`fold` have nothing: every row
  carries content, one op-row per CFG block).
* **bottom band y 742..792** (51 rows): 26 rooms + an 18x18 display spanning x 51..355 —
  a whole I/O complex (two symmetric groups of 6x10 + 7x8 + eight 4x6 + 8x4, plus two
  15x38 rooms and a 3x3), **3551 content cells**.
* **right margin x 318..355, y 0..741: completely empty — 0 cells**, i.e. 38 x 742 =
  **28,196 free cells**.

Since `max(w,h) >= 742` (r0's own height), the rigid-placement ceiling is exactly
742^2 = 550,564 vs 628,849 = **1.14x**, reached by emptying the 51-row band into the
margin. The band fits ~8x over by area and its widest block is the 18-wide display, well
under 38 — so this is *not* an area or aspect problem.

**What makes it hard is cliff #1, not the packing.** The controller's ports are coplanar on
its BOTTOM wall. Re-attaching the satellites on r0's *right* wall would re-resolve
nearest-pipe binding for every one of its ~4000 port ops — silently. The move must
therefore keep each pipe's attachment cell on the bottom wall at the same x, leave the
room downward, run east below y=741, and only then turn north into the margin. That costs
~2 extra rows (box ~= 744^2 = 553,536, still 1.14x) and needs **length-preserving** routes,
i.e. the folded router from `be429ed`.

Do not expect `smtplace` to find this: it timed out (`unknown`) on pathfinder's 24 blocks
at 480s, and LLM has 27. This is a `place.py --plan` job with a hand-written plan, gated by
`equiv.py` (a move-only transform cannot change the tick count, so it is provable without
grading — which matters because LLM's 28 cases OOM the wasm oracle and Rust is the only
grader).

And keep it in proportion: 1.14x on a problem that is **15x** off the lead, where the whole
remaining prize is 0.17 pts. Section 6 is the reason — LLM's gap is architectural.

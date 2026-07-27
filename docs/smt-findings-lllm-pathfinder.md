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

## 8. Matmul and the newer pathfinder: both certified at their floor

**matmul `b53230d6`, 42x42 box 1764, 75.0% dense, box/area 1.00, 9 rooms / 12 pipes.**
This is the well-conditioned case — small enough that Z3 answers in seconds instead of
timing out — and the answer is unambiguous:

| M | Z3 | place.py |
|---|---|---|
| 39 (box 1521, **1.16x**) | SAT, 4 models | all 4 `pipe 9/10 unroutable` |
| 40 | SAT, 4 models | all 4 `pipe 3/8/9 unroutable` |
| 41 | SAT, 4 models | all 4 `pipe 2/5/8 unroutable` |
| >=42 | **UNSAT** | — |

So the ROOMS fit in 39x39; the 12 PIPES do not. 12/12 routing failures, then an
optimality certificate at 42. `tools/peep.py` then freed **77 cells** (24 register-run
rewrites, each oracle-verified, identical box/ticks/score, 75.0% -> 70.6% density) and the
re-run **still** failed on pipe 9 — so density was not the binding constraint either.
42x42 is optimal under this router. Do not re-run this sweep.

Note `place.py` needs no help from `router.py` here: it has its own `_pad` accordion
serpentine (its comments cite gradebook 20/60 -> 2/60 from widening the fold window), so
these are genuine geometry failures, not the missing-length-target problem.

**pathfinder `0138b404`, 141x173 box 29929, 17.7% dense** — better than `637a8296`
(151x174 / 30276) and 7/7 at 12,141,288,879 on Rust. Height binds. The floor looks like
164 (block 0 is 51x164) but is really **165**, and the 1.11x is unreachable:

* blocks 20/21/22 (7x4, 9x4, 3x3) attach to block 0's **bottom wall** at x82/x98/x101 with
  pipes of just 2/5/4 cells;
* block 0 spans y0..163 across x57..107, so those rooms **cannot be lifted above y164** —
  that space is block 0;
* routing all three along the single remaining row y164 makes them collide. A hand plan
  moving them into the free `x111..132, y130..170` region fails `pipe 42 unroutable`
  (and `pipe 38` even with `--pipe-len free`).

Height 173 is in fact set by **pipes** at y171/y172, not by rooms (max room y = 171). A
local-span search (`--span 8`, 6000 tries) found only **2** legal floorplans, neither
better than baseline; `pipe 41` is the usual casualty. smtplace `--min-m 164` times out as
before. This build is at its rigid-placement optimum.

## 9. matmul `e55c808d` (42x42): the same floor, now with the reason visible

Newer than `b53230d6`: same 42x42 box, 73.4% dense (was 75.0%), rooms tightened (r3 9x8,
r6 15x15), 7/7 Rust at avgTicks 11136.86, **score 19,645,416**. All three passes agree it
is done:

| pass | result |
|---|---|
| `smtplace` | 16 SAT models at M=39/40/41, **all 16 `pipe N unroutable`**, then UNSAT at 42 |
| `peep` (superoptimizer) | 22 rewrites, **59 freed cells**, box/ticks/score IDENTICAL |
| `fold` | **0 row folds, 0 column folds** — on the peeped file too |

**Why 42 is structural, and it is not the rooms.** Rooms reach only y32; rows 33..41 are
pure pipe. Printing the grid shows the reason immediately: rows 36..41 are an **accordion
serpentine** (`^---<` / `>---^` alternating across x7..41) and rows 0..11 are another on
the left. Those are LENGTH-PADDING pipes, and pipe length is capacity AND latency, so their
cell count is load-bearing and cannot be reduced. Rooms total ~655 cells against ~640 cells
of pipe; the box is a near-square packing of rooms plus a FIXED quantity of pipe, which is
why Z3 keeps fitting the rooms into 39x39 and the router keeps failing to thread the pipes.

**Do not submit a peeped matmul.** peep frees cells at *identical* score (its own docs: a
shorter op run does not save ticks — the man walks the same cells and the freed ones become
blanks), the freed cells do not line up into a deletable row/column, and `fold` cannot use
them. It would spend a submission slot for a guaranteed zero.

## 10. Pathfinder: geometry is DONE (proved), and the ticks are 16 idle lanes

**Geometry is closed.** `smtplace` timing out left "can it get smaller?" unanswered, so the
coarse solver was used on the same 24 blocks as rigid rectangles (dims only + pipe
connectivity), which solves in seconds:

| cap | result |
|---|---|
| 141 / 150 / 160 | **UNSAT** — no packing of the 24 rectangles fits |
| 164 / 168 / 173 | timeout |

The tallest component is 164, so `max(w,h) >= 164` regardless. Floor = **164**, box >= 26896,
so rigid placement can never beat 29929 -> 26896 = **1.11x** — and section 8 shows even that
is blocked. Rooms are 61% of the envelope; the rest is the 43 pipes' corridors.

**Against a 9.3x gap, geometry is 1.11x. The other ~8.4x is ticks** — and the profiler
(`lm --profile`, stderr) says exactly where, on the dominant case "around the pillars":

    wall-clock ticks              500,786
    total man-ticks            21,228,018   (~42 men: 22 at t=0, rest via Y)
      stalled (blocked)        10,210,726    48.1%
      executed ops             11,017,292    51.9%

    stall time by column:  x=37  7,971,510  = 78.1% of ALL stalling
    x=37 holds exactly 16 stall cells, y=51..156 -> the sixteen 14x7 LANE rooms
    per-lane stall ~498,219 of 500,786 wall-clock  =  99.5% IDLE
    'r' (receive) = 8,979,443 executions = 42.3% of all man-ticks

**The 16-lane wavefront has effective parallelism ~1.** The workers are not slow, they are
starved: each sits on a blocking `r` for 99.5% of the run, and that single column is 78% of
all stall time. The lever is the FEED (the controller / the 7x112 relay at x50..56), not the
lane bodies and not the floorplan. Ticks are also nearly uniform across cases (291,641 to
500,786, a 1.7x spread), so there is no pathological case to fix — it is a fixed structural
serialization.

Worth noting for the tick budget: `pathfinder-d67da44b` (170x170, box **28900** — smaller
than the champion's 29929) scores **17.69B vs 12.14B** because its ticks are 611,941 vs
405,671. Box is squared and it still loses. Do not trade ticks for box here.

### 10b. The pathfinder tick bottleneck is TRANSFER LATENCY, not compute

Every public case feeds exactly **258 values** per round (a fixed 16x16 grid + 2), which is
also why there are exactly 16 lanes — one per row. Per-round cost:

| case | ticks/round | ticks per cell per round |
|---|---|---|
| running errands | 66,617 | 258 |
| rooms and doors | 70,259 | 272 |
| a cluttered field | 95,306 | 369 |
| there and back again | 97,214 | 377 |
| a straight shot | 97,692 | 379 |
| the long way | 120,784 | 468 |
| around the pillars | 125,196 | 485 |

**The lanes finish their work in ~2,567 ticks; the round takes ~100,000.** So ~97% of every
round happens OUTSIDE the lanes, moving 258 values in and results out at ~390 ticks per
value — against pipes whose length is ~129 (pipe 39 is 129 cells).

That identity (258 values x ~390 ticks ~= 100k ticks/round) is the whole story: the machine
is **latency-bound on serial value transfer**, not compute-bound. A pipe IS a FIFO with
capacity equal to its length, so a 129-cell pipe can hold 129 values in flight. Paying ~390
ticks per value means the design is doing one value per ROUND TRIP (send -> wait -> receive
-> send next) instead of streaming. It also explains `r` = 42.3% of man-ticks and stalls =
48%: everyone is waiting on transfers, and the 16 lanes idle at 99.5% because they are fed
one value at a time.

Priority for a tick round:

1. **Stream, do not round-trip.** Issue sends back-to-back and let the pipes buffer them.
   Ceiling ~= pipe length (~100x); realistically bounded by the lanes' 2,567 ticks of real
   work, so target **10-30x**. Needs no floorplan change, which matters because section 10
   proves the floorplan is closed at 1.11x.
2. **Then shorten the long relays** (pipe 39 = 129; the 7x112 at x50..56 and 30x122 at
   x0..29 are pure transit). This only pays while you are still paying L per value; after
   pipelining, latency amortizes and it stops mattering.
3. **Never trade ticks for box** — `d67da44b` has the smaller box (28900 < 29929) and loses
   17.69B vs 12.14B.

NOT a lever, though it looks like one: the 3-7 "rounds" are INPUT rounds supplied by the
test case, not internal iterations, so there is no fixed iteration count to early-exit.

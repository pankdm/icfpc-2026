# Matmul rewrite: the CAROUSEL machine

Replaces the 4-ring stationary-C streaming machine (`build_opt5.py`, live
`61x61 x 61,830 = 230,073,151`, rank 32/74). Algorithm and choreography validated
7/7 on the public cases by `solutions/matmul/model_carousel.py`.

## Target

| | box | avg ticks | score | rank |
|---|---|---|---|---|
| live today | 3,721 | 49,864 | 230,073,151 | 32 |
| **P=1 carousel** | ~2,025 | 10,580 | **21,424,500** | ~9 |
| **P=3 carousel** | ~2,025 | 4,264 | **8,634,021** | ~2 |
| P=3, box 1,296 | 1,296 | 4,264 | 5,525,774 | 1 |
| board best (fixstars) | — | — | 8,320,307 | 1 |

## Algorithm — stationary-C, streamed a

```
for i in 0..N-1:                 # one output row
    for k in 0..M-1:
        a = A_queue.pop()        # consumed once, never returned
        for j in 0..K-1:         # K MACs
            b = b_ring.pop();  c = c_ring.pop()
            c_ring.push(c + a*b);  b_ring.push(b)
    emit c_ring (K values); refill with K zeros
```

`B` is stored row-major, which **is exactly input order** — no permutation is needed
at seeding. Each output row cycles the whole b-ring once.

### A must be buffered — this is forced, not a choice

Input order is `N,M,K`, then **all of A**, then **all of B**. `B` must be resident
before the first MAC, and `A` arrives first, so `A` cannot be streamed. Both cost a
ring. (An earlier version of this design claimed A could stream; it cannot.)

| ring | values | cells | behaviour |
|---|---|---|---|
| A-queue | N*M <= 256 | 257 | drains once, never re-enqueued |
| b-ring | M*K <= 256 | 257 | cycles once per output row |
| c-ring | K <= 16 | 17 | cycles once per k-step |
| a-holder | 1 | 2 | re-enqueued by each worker |
| | | **533** | vs **880** pipe cells today |

## The lap — 10 ops, two registers, one MAC

The whole point is that `c += a*b` fits in A and B alone, because `*` leaves B intact:

| # | op | A | B | note |
|---|---|---|---|---|
| 1 | `r` | b | – | nearest = b-ring in |
| 2 | `s` | b | – | re-enqueue b |
| 3 | `M` | b | b | |
| 4 | `r` | a | b | nearest = a-holder in |
| 5 | `s` | a | b | re-enqueue a for the next worker |
| 6 | `*` | a*b | b | **B survives `*`** |
| 7 | `M` | a*b | a*b | |
| 8 | `r` | c | a*b | nearest = c-ring in |
| 9 | `+` | c+a*b | a*b | |
| 10 | `s` | c+a*b | | to c-ring return |

10 op cells + 4 corners = a **14-cell loop**. `BP` stays free for the controller's
`b`/`m`/`d` counters.

**Layout constraint (the main geometric risk):** cells 1,2,4,5,8,10 must each be
nearest to a *different* pipe endpoint — six endpoints around a 14-cell loop.
This is what `tools/router.py` and the nearest-pipe placement machinery exist for,
but it is the part most likely to need several attempts.

## Where `Y` earns its place

`Y` is **not** useful for broadcasting a value here — `S` (atomic send to every
outgoing pipe) already does that in one op, and the lap needs no broadcast at all.

`Y` is useful for exactly one thing, and it is the whole tick win:

> **P workers in ONE room cost ~zero extra area.** Rooms cost area; men are free.
> Spawn P men into the same 14-cell lap, spaced `14/P` apart, and throughput becomes
> one MAC per `14/P` ticks with the box unchanged.

A single `Y` at startup doubles the worker population, and both copies inherit A, B
and BP exactly, so they are identical workers by construction. Two `Y`s give 4, etc.
This is why score scales as ~1/P here while it would be score-*neutral* in a design
where each lane needed its own room and pipes.

## The two hazards — both are real

**1. Carousel collision is FATAL and SILENT.** "A mover entering a blocked or
otherwise stationary man's cell" kills *both men, without an error*. Workers are
`14/P` cells apart, so at P=7 (spacing 2) a single stall tick from any ring merges
two workers and the program silently emits wrong answers. This is the dominant
correctness risk and it is why the build plan starts at P=1.

**2. Ring transit stalls dominate the small cases.** A pipe passes values at 1
cell/tick, so a re-enqueued value needs ~L ticks to come back, where L is the
*physical* ring length — sized for 16x16x16 and identical for every case. A 2x2x2
case drains its 4-value b-ring long before the first value returns:

| case | compute | stall | total |
|---|---|---|---|
| 2x2 warm up | 37 | **507** | 560 |
| identity 4x4x4 | 299 | **729** | 1,079 |
| skinny 16x2x16 | 2,389 | **1,723** | 4,435 |
| 16x16x16 | 19,115 | 0 | 19,886 |

Stalls are a *fixed* cost that parallelism does not reduce, which is why P past ~3
gives diminishing returns (P=3 -> 4,264 avg; P=7 -> only 2,770). Note that at P>1
these stalls are also collision risk, not just lost ticks.

The principled cure is **men-as-storage**: a circulating crowd of V men has a cycle
time proportional to V (the data), not to the physical track length, so it adapts to
the case size automatically. That is the genuinely "dense" design — and it is also
where `Y` would spawn the storage crowd. It is strictly harder to build and should
not be attempted first.

## Build plan

1. **P=1, pipe rings.** No collision hazard (a lone worker may block freely — parked
   men are free), trivial control. ~10.7-16.8x -> score ~13.7M-21.4M, rank ~9.
   This alone beats every incremental option on the board.
2. **Fold the box.** 533 ring cells at ~50% packing plus a 14-cell lap room and two
   3x3 I/O rooms is ~1,300-2,000 cells. Square it; only `max(w,h)` is squared.
3. **P=2, then P=3.** Add one `Y` at a time and re-verify on the Rust engine after
   each. Stop as soon as spacing stops covering the worst measured stall run.
4. *(stretch)* men-as-storage for B, to remove the small-case stall floor.

A controller man is needed alongside the workers: it pops the A-queue every K MACs
into the a-holder, and at row end drains the c-ring to output and pushes K zeros.
At P>1 the row-end drain is a barrier, and a barrier means blocked workers — so
step 3 must solve the drain without stalling the lap.

---

# Improving the design (measured 2026-07-26)

**The 16x16x16 case is 78% of the average**, and at any useful P it is essentially
pure compute (4096 MACs; I/O is 771 ticks, 9%). So one number sets the score:

> **ticks per MAC = lap_cells / P = the spacing between workers.**

Everything below is an attack on that number, and `score ~ box x ticks_per_MAC`.

| ticks/MAC | 16^3 ticks | avg | box 2,025 | box 1,296 | box 900 |
|---|---|---|---|---|---|
| 14 (as designed) | 58,115 | 10,454 | 21,169,929 | 13,548,754 | 9,408,857 |
| 10 | 41,731 | 7,525 | 15,237,257 | 9,751,845 | 6,772,114 |
| 8 | 33,539 | 6,060 | 12,270,921 | 7,853,390 | 5,453,743 |
| 4 | 17,155 | 3,130 | 6,338,829 | 4,056,850 | 2,817,257 |
| **2 (floor)** | **8,963** | **1,684** | **3,409,232** | **2,181,909** | **1,515,214** |

Board best is 8,320,307, so the design has **2.4x-5.5x of headroom below the leader**
if it reaches the floor.

## The four improvements, in priority order

**1. Hoist the a-fetch out of the inner loop. lap 14 -> 10, ~28% off everything.**
`a` is constant for K consecutive MACs, so `r a` / `s a` do not belong in the lap.
Wrap the j-loop in a k-loop that fetches `a` once, counting K down in `BP` with
`b`/`m`/`d`. Cheapest, safest win available; do this first.

**2. Put the accumulators in MEN, not a c-ring. lap 10 -> 8, and -17 pipe cells.**
K men circulate a short track, each holding `c_j` in register **B**, and each doing
only `r` `+` `M` (3 ops) at a tap cell. This deletes the c-ring outright: no c pipe,
no c transit, no c stall, and two fewer ops in the worker lap. This is the place where
"dense storage" genuinely pays — accumulators live in registers, not cells.

**3. Raise P with `Y`.** Linear in P, and free in area. This is the whole reason the
carousel exists.

**4. Tiered b-rings {17, 65, 257}, selected at seed time by M*K.** Worth only ~15%
in ticks directly — but that is not its job. Its job is to **guarantee no stall**, and
no-stall is what makes small spacing survivable (see below). Costs +82 pipe cells.

## Why ticks/MAC cannot go below ~2

Workers sit `lap/P` cells apart and *a mover entering a blocked man's cell kills both,
silently*. Spacing 1 means any hiccup at all is fatal, so **spacing 2 is the hard
floor** — and it is only safe if no ring ever runs dry, which is exactly what
improvement 4 buys. Note the trap: shortening the lap (1 and 2) *reduces* spacing at
fixed P, so improvements 1+2 must be paid for with tiering before P is raised.

Stalls are not merely slow here; at low spacing they are silent wrong answers.

## Revised build order

1. lap 14, P=1 — correctness first, no collision risk at all.
2. Improvement 1 (a-hoist) -> lap 10, still P=1. ~15.2M at box 2,025.
3. Improvement 4 (tiering) -> stalls provably zero. No score change; it is the
   safety interlock for step 5.
4. Improvement 2 (accumulators in men) -> lap 8.
5. Raise P to 4 (spacing 2) with `Y`, re-grading on the Rust engine after each step.

## Ideas considered and rejected

- **Strassen.** One level on 16x16 saves 12.5% of MACs for a large control-flow cost.
  MAC count is otherwise irreducible at N*M*K.
- **Two carousels sharing a b-ring** (ring routed room1 -> room2 -> room1) could reach
  ticks/MAC ~1, but doubles the ring area, and score ~ box x ticks/MAC makes it roughly
  neutral. Only worth it if the box turns out to be room-bound rather than ring-bound.
- **Overlapping seed with compute.** B is complete at ~tick 515 and the first row needs
  all of B within its first 256 MACs, so the overlap saves ~515 ticks (6%) for real
  complexity. Not now.
- **Men-as-storage for the b-ring.** A crowd of V men on a T-cell track still has cycle
  time T, not V, so it does *not* fix the small-case stall — tiering does. Men only pay
  where the value lives in a register permanently (the accumulators, improvement 2).

---

# Probe results (2026-07-26) — two of these change the design

Measured with `scratchpad/mm_probe.py` on the Rust engine.

**1. `s` preserves A, and `*` preserves B.** CONFIRMED (`r M r * W s s` on input
`3 5` emits `3 3`, settle 9). The 10-op lap is sound as written.

**2. A pipe may NOT connect a room to itself** — `loaderror: "pipe self-loop"`.
Every ring therefore costs a **relay room plus two pipes**, not one pipe. This is
why the old design is built from "CTRL<->relay" rings. Minimum relay is a 5x4 room
running a 6-cell shuttle loop:

```
+---+
|@rv|
|^s<|
+---+
```

Budget accordingly: 4 rings (A-queue, b-ring, c-ring, a-holder) = 4 relay rooms
(~20 cells each) + 8 pipes. Several rings can share ONE relay room if each gets its
own `r`/`s` cell, since nearest-pipe binding is per-cell — worth doing to save area.

**3. Holding `a` in B collapses the lap from 10 ops to 4.** This falls out of result
1. If the multiplier man keeps `a` in **B** permanently, then per MAC:

| op | A | B |
|---|---|---|
| `r` | b | a |
| `s` | b | a | re-enqueue b |
| `*` | a*b | **a** | B survives, so `a` is still there next lap |
| `s` | a*b | a | send the product to an accumulator man |

**4 ops + 2 corners = a 6-cell lap**, and `a` only needs refreshing once per k-step
(a branch out of the loop counted in `BP`). This *requires* improvement 2
(accumulators in men), because the product must leave the lap for someone else to
add — but it means improvements 1 and 2 are not independent: doing 2 gives 1 for free
and goes further than either.

Revised ceiling: lap 6 at P=3 is ticks/MAC = 2, the collision floor, i.e. the
1,684-avg / ~3.4M row of the table above becomes reachable at P=3 rather than needing
P=4 on an 8-cell lap.

---

# Resolved control flow (2026-07-26) — no counter rings needed

The open question after `seedA` was how to drive three nested loops with only ONE
`BP`. Resolved: **markers in the rings**, not counters, with one hard constraint
discovered while working it through.

## The ordering constraint that decides everything

A marker can only live in the ring that the lap pops **first**. If the lap pops `b`
then `c`, and the k-step boundary is signalled in the c-ring, then by the time the
boundary is seen a `b` has already been popped — and pushing it back sends it to the
ring's TAIL, corrupting FIFO order. Every marker scheme must respect this.

The lap must pop `b` first (it re-pushes `b` immediately, before `*` clobbers it), so
**the markers go in the b-ring.**

## Ring inventory

| ring | contents | notes |
|---|---|---|
| A-ring | N*M raw a-values | consumed once; drains, never re-pushed |
| b-ring | M*K raw b-values + one ROWMARK | cycles once per output row |
| c-ring | K accumulators | pops K per k-step, so it self-aligns |
| a-holder | the live `a` | re-read every MAC (registers cannot hold it) |
| K-ring | K | re-read to reset `BP` at each k-step |

Five relay rooms. **No i-counter, k-counter, N or M ring** — the ROWMARK drives the
row boundary and the program simply ends when the A-ring runs dry (the man blocks
forever, which is free: output has already settled).

## Loop structure

```
k-step:  reload BP = K        (r K-ring, s K-ring back, b)
         pop b
         if b is ROWMARK:     push it back (it belongs at the tail), emit the row,
                              then fall through to fetch the next a
         else:                fetch a from A-ring into the a-holder
         run the j-loop:      the 10-op lap, x K, counted down in BP with m/d
```

The marker test costs ~6 ops but runs **once per k-step (256x), not per MAC (4096x)**,
so it is ~1,500 ticks total — noise against the 16^3 case.

## Why accumulators keep an OFFSET

Store `c + 1e6`. Addition preserves the offset (`(c+OFF) + a*b = c' + OFF`), so the
lap needs no correction, but every c stays positive and a negative marker is
distinguishable with a single `X`. |c| <= 16*99*99 = 156,816 << 1e6, so it is safe.
Subtract the offset only at emit time.

## Remaining work, in order

1. `seedB` — seed A-ring and b-ring (needs an M-ring and K-ring to recompute M*K
   after N*M has consumed the registers), push the ROWMARK, init the c-ring with K
   zeros.
2. `mac` — one k-step: the 10-op lap x K under `BP`, then emit the c-ring. This is
   the core risk and should be built against a hand-fed input before the seeder is
   wired to it.
3. Join them, add the ROWMARK branch and the row emit.
4. Fold the box, then raise P with `Y` (see the improvements section above).

Pipe-column plan that makes nearest-binding unambiguous for the lap (walk east along
the top row, west along the bottom):
```
top wall (segments y=ctrl_top-1):   bIn  bOut  aIn  aOut     ascending columns
bottom wall:                        cOut ....  cIn           cIn east of cOut
input on the LEFT wall, output on the RIGHT
```
so the eastward walk meets `r b, s b, ..., r a, s a` in order and the westward return
meets `r c, ..., s c` in order.

---

# Session ledger 2026-07-26/27 (carousel BUILT and working — read before touching it)

`solutions/matmul/build_carousel_full.py` -> `matmul-carousel.man`: the composed
P=1 machine. **7/7 on the wasm oracle, tick-exact with the Rust engine**
(16^3 = 87,633 both). 52x62, box 3,844 x avg 17,637 = **67.8M** (not submitted:
a teammate's independent build is live at 45.0M, 63x63 x 11.3k).

Profile (lm --profile): the 16-cell lap is EXACTLY stall-free — every lap cell
fires once per MAC, rb = 4096-256. 16^3 = 65.5k lap + 14.4k prologue walks
(~56/k-step: TOP row + real path + riser round trip) + 7.7k seed/emit.

## Hazards burned into this build (violating any of these deadlocks or corrupts)

1. Backticks pair per COLUMN too: two horizontal literals must not share
   backtick columns (`100` row 4 vs `150` row 9 originally did -> loaderror).
2. The marker path must not consume BP before the emit loop runs (BP=K is
   loaded at TOP and spent exactly once).
3. c-ring standing inventory (=K) must fit on the PUSH side (cf+relay+cr).
   The pop side can't help: sc blocks -> relay blocks -> circular wait.
   cf and cr are straight parallel columns (4/5) into the far-south relay.
4. Multi-feed relays serve values in READING ORDER of the pipe END cells:
   cf2's end must read before cf's, or the first products overtake the last
   seed zeros for K>=7 (double-added slots + trailing zeros symptom).
5. Never run a pipe body alongside a room wall (1-cell gap minimum except the
   attach cell itself) — spurious attachment silently breaks delivery.
6. bf2 (marker re-push) must be LONGER than bf minus ~62 ticks (the lap-exit ->
   marker-s path length), else the ROWMARK overtakes the current row's last
   re-pushes at the relay. Currently ~100 vs threshold ~64.

## Dead ends measured/analyzed this session (do not redo without a new idea)

- **Accumulator-men (lap 6-10)**: an acc-man holds c_j in B; there is NO
  register left to detect a flush token (X is 3-way on signed products), and
  push-every-MAC makes the emitter pop N*M*K values (~30k ticks). Needs a new
  flush mechanism (e.g. a second tap pipe + geometry) before it is viable.
- **P=2 worker split**: at row boundaries workers park on dry rings and the
  trailing worker WALKS INTO the parked one (silent death). Staggered parks at
  ra/rc survive only if the b-ring is also metered, which makes the controller
  the bottleneck (2 ops/MAC > workers' rate). Needs a real barrier design.
- **P=2 on the unified man**: impossible — two men on one prologue+lap track
  serialize k-steps (the holder swap mid-laps corrupts a).
- b-relay shuttle forwards 1 value/8 ticks -> P>=2 runs the b-ring at/over
  its throughput limit; any hiccup collapses worker spacing (death).
- Tiered small b-ring (latency 440 -> ~40 for M*K<=~35) is worth only ~1.3k
  avg (-2M-ish) for +2-3 box rows and a seeder branch. Marginal.

## Where the remaining juice is (in order)

1. Prologue trim 56 -> ~40/k-step (~-4.5k on 16^3, ~-0.7k avg): column jenga
   on TOP/real rows; the K-reload (r Kr, s Kf, b) and the `100` literal set
   the width. Safe but only ~-5M.
2. The flush mechanism for acc-men (see above) — THE structural win:
   lap 10 at P=1 = ~11.5k avg, and it removes the holder ring entirely.
3. A real P=2 barrier (gate ring with pre-loaded GO tokens?) on top of 2.

## Endgame measurements (2026-07-27 07:00–10:15Z) — do not repeat these

**P2-CC was killed on arithmetic, not on a bug.** The design paces the whole machine
from the controller's steady loop `[r s W s(Ha) W m d]` = 10 cells = **10 ticks/MAC
regardless of P**; the workers are never the bottleneck, so the second man buys nothing.
The live machine already runs ~13.7 ticks/MAC, so a *finished* P2-CC is a 1.37x tick win,
and at its unfolded 44x49 footprint (2401) it would score ~19.7M against a live 28.1M —
not worth the remaining debug. `build_p2.py` is committed at the seeder stage; the
control flow (token spawn, A-ring markers, absorb, stall-stagger) is fully resolved in
the P2-CC section above if anyone wants it later.

**Public ticks are ~23% optimistic on this problem.** Submitting the 44x46 reflow
returned `20/20, 29,410,178`. That is 2116 x **13,899** — but the same file grades
**11,256** avg on the 7 public cases. The 13 private cases are tick-heavier, and the
inflation factor is the same 13,898 the live 44x45 build shows. So: **compare matmul
builds by BOX only** (box is exact locally); a local avg-ticks win of <23% is noise.

**Matrix Multiply is now a pure density game and it is near its floor.** Decomposing the
44x46 champion (`tools/place.py` Plan) gives:

| component | cells |
|---|---|
| 9 rooms (16x16 worker + 16x10 + 12x10 + 10x9 + 10x10 + …) | 800 |
| 12 pipes — **pipe0 = 254 (A-store), pipe10 = 244 (B-store)** | 745 |
| **total** | **1545** → sqrt = 39.3 |

so ~40x40 = 1600 is the topology's absolute floor and 42x42 is the realistic one. The two
250-cell serpentines are **capacity-bound** (A needs N*M ≤ 256 resident before B arrives;
B needs M*K ≤ 256 resident to be reused for each of the N rows) — they can be *reshaped*
but never shortened. The leader's 8,320,307 factors uniquely to **1024 box x 8,125 ticks**,
i.e. 1024 cells total — *fewer cells than we have*. Their lead is a structurally smaller
machine, not a tighter pack of ours. The one idea that would close it: values are in
[-99,99], so **two of them pack into one i64 cell** (`a*200+b`, unpacked by a single `/`
which leaves the remainder in B) — that halves both stores, 498 -> ~250 cells, total
~1300 -> 36x36. That is a machine redesign, not a fold.

**Both automated packers converge at 2116 and stop.** `tools/incremental_pack.py`
(rigid-room moves + shears, exact pipe lengths) ran to v9 making only mass-centering
moves. `tools/place.py` (annealer) with `--pipe-len exact` finds ~1 valid neighbour per
thousand proposals; with `--pipe-len free --tighten` it finds routings needing only
**509** pipe cells but never a smaller box. Forcing the issue by hand fails on the
serpentines specifically: base offsets + `--tighten` → `pipe 0 unroutable`; shifting the
worker room and its relay up one row (the move that would kill row 45) → `pipe 7
unroutable`. The router will not synthesise a 254-cell snake, and that is the blocker.

Only rows 0 and 45 need to disappear to reach 44x44 = 1936 (the rooms already fit in
42x44). Row 0 is pipe1's over-the-top run; **row 45 is forced** — blk8 (the c-relay) sits
at rows 41-44 directly under blk7 (rows 25-40), so its south attachment can only live at
row 45, and blk7 cannot move up without breaking pipe 7.

### Triangle is provably at its floor (checked 2026-07-27, do not re-open)
832 = 64 x 13 and 24 teams are tied there. The op sequence `r M * + W 2 W / s` is 9 ops
and minimal — the `/2` needs B=2 while A holds n²+n, and stashing it costs `W 2 W` no
matter which order you try (`M 2 W /` is also 4). 9 ops + `@` = 10 cells, which needs a
6x2 interior; the two turn cells make the walk 12 cells, so `s` fires at tick 11 and the
2-cell output pipe (the minimum) lands it at 13. The 8x8 frame is just the main room
(8x4) over the two 3x3 I/O rooms. Nothing is left.

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

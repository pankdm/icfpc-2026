# matmul "mm2" — 9-room pipelined MAC engine (replaces opt5's 1-man 4-ring machine)

STATUS 2026-07-26: **the engine is BUILT AS CODE, every nearest-pipe binding is
machine-checked, and ALL SEVEN ROOMS ARE UNIT-TESTED AND PASS** (`scratchpad/mm2/
unit.py`). Nothing is submitted: the open problem is *routing the 12 pipes*, not the
logic. Read "What is left" at the bottom first.

    PCNT  '3 4 5'      -> 5 5 5 5 5 -5 5 5 5 5 -5 5   control stream exact
    AREL  '2 3 4 7 8'  -> 7 7 7 7 8 8 8 8             each A value repeated K times
    SPL   2 2 2 + A,B  -> 2 2 2 1 2 3 4               broadcast + N*M split exact
    BREL  '2 2 3' + B  -> 11 12 13 14 15 16           seeds exactly M*K then stops
    CREL  '5 6 7'      -> 5 6 7
    MUL   gens 3 and 7 -> 0 21 21 21                  the ONE garbage lap, then 3*7
    ACC   PCNT + gen 5 -> 10 10 10 10                 seed, MAC ring, X on -K,
                                                      output ring, re-arm

A room test is cheap: drive it from I with a literal-generator room (`@>5v/ ^s<`,
emits 5 forever, needs no input) for any pipe the test does not drive, and an `@H`
room as a sink.  That found PCNT's return corridor being one cell too long -- a bug
no amount of reading would have caught.

## Why opt5 is 63 ticks/MAC
`matmul-opt5.man` runs ONE man through MAIN-read → classify → MAC → return, so every
per-MAC op is *serial*: 18 ops + ~45 glide/turn ticks. Two structural taxes: the
accumulator and `a` both want register B (so `a` round-trips the H1 ring), and
classify costs 8 ops to tell a real `b` from a MARK.

Measured per-case ticks for opt5 (Rust engine, public cases):

| case | 2x2 | 2x3x2 | identity | **16x16x16** | 16x2x16 | neg | 7x5x9 |
|---|---|---|---|---|---|---|---|
| ticks | 1677 | 2145 | 6985 | **259873** | 41053 | 12237 | 25079 |

Local avg 49,864 × box 3721 = 185.5M local, 230.1M server (ratio 1.24). Case 3 is
74.5% of the total — optimise it and little else matters.

Rank payoff (measured from the live board, `scratchpad/mm2/rank.py`): 1.5x → +0.03,
3x → +0.08, **5x → +0.15, 8x → +0.28, 10x → +0.31**, max +0.41. The curve is steep
between 5x and 10x, which is exactly what mm2 targets; a 2x rebuild is not worth it.

## mm2: split the MAC across two men so the ops overlap
`C[i][j] += A[i][m]*B[m][j]`, iterated (i, m, j) with j innermost — so `a=A[i][m]` is
constant for K MACs, A is drained once **in arrival order**, and B is replayed N times
**in arrival order too**. Neither matrix ever needs transposing; that is the whole
reason this loop order was chosen.

| room | body | ops |
|---|---|---|
| **MUL** | `*` `s_PP` `r_AR` \| `M` `r_BR` `s_BF` | 6, branch-free, **10 ticks/MAC** |
| **ACC** | `r_CR` `M` `r_PP` \| `+` `s_CF` `m` (+`d` corner) | 6, **10 ticks/MAC** |
| **AREL** | reads N,M,K then emits every A value **K times** | keeps MUL branch-free |
| **PCNT** | emits `K,K` then forever `[K]*(M-1), -K, K` | 1 in / 1 out, no ambiguity |
| **BREL** | seed phase (`r_SD`) then ring-relay phase (`r_BF`), separate code | |
| **SPL** | `S`-broadcasts N,M,K, then routes N*M to AP and M*K to SD | |
| **CREL** | plain 6-tick C-ring relay | 1 in / 1 out |

Estimated case 3: 4096 MACs × 10 + ~5k load ≈ 46k ticks vs opt5's 260k.

### Control flow (fully resolved — this is what `mm2rooms.py` implements)
ACC has ONE MAC racetrack and one output racetrack, joined by a single merge node:

```
INIT: r_CTL ; b ; SEED ring x K (0, s_CF, m) ; r_PP (discard) ; -> MERGE
MERGE: r_CTL ; X      A>0 -> b ; MAC ring x K -> MERGE
                      A<0 -> N ; b ; MAC ring x K ; r_CTL ; b ; OUT ring x K -> MERGE
```
PCNT's `-K` is what tells ACC "this pass finished a row of C"; the extra `K` after it
re-arms BP for the next block. **Nobody needs two counters**, which is why the design
works: the only room that needs three live constants (PCNT) is the one with no data.

**MUL emits exactly ONE garbage product** (its ring is entered at `*` with A=B=0, so
lap 1 sends 0 and consumes no `b`). ACC's INIT discards it with a single `r_PP`.
Entering the ring anywhere else either pollutes the B ring or desynchronises it.

### Storage sizing (do not shrink these)
* **A queue** `SPL → AP(long) → AREL → AR → MUL`, holds `N*M ≤ 256`. It must be
  ≥ N*M or SPL blocks before it can seed B and the machine **deadlocks**.
* **B ring** `MUL → BF → BREL → BR(long) → MUL`, holds `M*K ≤ 256`. A ring of L cells
  holding V values flows at only `(L-V)/L` values/tick (holes propagate backwards at
  1 cell/tick), so a 260-cell ring holding 256 values delivers 1 value per 65 ticks.
  **L ≈ 1.15 × V** is the floor for a 10-tick MAC; use ~300.
* **C ring** `ACC → CF → CREL → CR → ACC`, holds K ≤ 16. Round-trip latency is the
  binding constraint for small K: at 30 pipe cells a K=2 case runs at ~15 t/MAC.

### The seeding race, and why BREL's two phases fix it
SPL feeds B into BREL while MUL is already returning b's on BF. `R` would interleave
them and scramble the ring. BREL instead runs its **seed loop (`r_SD` only, M*K times)
to completion before it ever executes an `r_BF`**, so MUL simply blocks on `s_BF`
until seeding ends. No gate pipe, no token, no ordering hazard.

## Facts measured while building this (do not re-derive)
* **A pipe whose source and destination are the same room is a LOAD ERROR**
  (`pipe self-loop`). Every ring needs a relay room. `scratchpad/mm2/probe1.py`.
* **A gapless serpentine parses as ONE pipe and transports in order** — rows may be
  adjacent with no spacing; the engine reports it as a single src→dst pipe.
  `scratchpad/mm2/probe2.py`. This is what makes a 300-cell queue affordable.
* **matmul has no multi-round private cases.** opt5 scores 20/20 yet *times out* on a
  hand-built 2-round case, so no graded case has more than one round — mm2 does not
  need to reset between rounds.
* `tools/router.py`'s `route_pipe` uses a **margin-6 A\* box** around the two
  endpoints. Any net that must detour around a 40-cell serpentine is unroutable until
  that margin is raised (patch it at the call site).

## What is left: routing, not logic
`build_mm2.py` stamps all nine rooms, hand-lays the two serpentines and hands the ten
short nets to `tools/router.py`. Individually every net routes; the failure is always
the same shape and it is worth stating plainly:

> **The two long pipes cut the canvas in half.** A 300-cell serpentine plus its
> lead-in and lead-out is a wall; every short net that must cross it competes for the
> two or three free columns beside it, and greedy BFS (or a lead-in that wanders) then
> seals a room's attachment into a pocket.

Approaches tried and their outcome:
* sequential BFS with hand-reserved corridors — routes 9 or 10 of 12, never all;
* `tools/router.py` global rip-up — converges only when the canvas is sparse, and is
  slow (minutes) once the A\* margin is large enough to detour a serpentine;
* pinning both long pipes to explicit corridors (`outside(ALLOWED)`) — this is the
  most promising and is already implemented (`mm2route.route_long(lead_avoid=,
  exit_avoid=)`); what is missing is a *channel discipline* that assigns each of the
  12 nets its own row and column so no two can cross.

Concrete next step: lay the rooms in ONE row with the two serpentines side by side
below them and route every net through a dedicated channel row (classic channel
routing, guaranteed to succeed), get it graded to prove the engine, and only then
fold the channel out. A 2x rebuild is worth +0.04 so the folded version is the point,
not the channel version — but the channel version is what turns "designed" into
"measured".

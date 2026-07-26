# Matrix Multiply: the 27.7x gap is a rewrite, not a tuning job (measured 2026-07-26)

Live: `61x61 / box 3,721 x 61,830 avg ticks = 230,073,151`. Board best **8,320,307**
(fixstars) = **27.7x** ahead. We are **rank 32 of 74 full-solvers**.

## Why this is the best target on the board

The cluster below us is dense, so speedups convert to ranks unusually well:

| speedup | score | rank (of 74) | places gained |
|---|---|---|---|
| 1.5x | 153,382,101 | 29 | +3 |
| 2x | 115,036,576 | 28 | +4 |
| 5x | 46,014,630 | 20 | +12 |
| **10x** | 23,007,315 | **8** | **+24** |
| 27x | 8,521,228 | 2 | +30 |

Compare LLM, where the unreachable ideal (2.78x) buys **+5** places. A 10x here is worth
~0.32 pts — the largest single-problem prize available.

## Why the current design cannot get there

`build_opt5.py` is a **4-ring stationary-C streaming machine**: rings SA (matrix A),
SB (matrix B), SC (K accumulators), H1, all of them **FIFO pipes**.

**Pipe capacity IS pipe length.** For the dominant 16x16x16 case the algorithm needs
`SA=257 + SB=272 + SC=17 + H1=1 = 547` ring cells, and the grid actually spends **880
non-space cells outside all rooms** (728 of them vertical `|`) on those rings. Storage is
one-dimensional, so it costs *perimeter*, and the perimeter is what sets the envelope.

That single decision drives **both** halves of the score:

- **Box.** 547+ cells of ring cannot be folded into a small square. `decompose.py` puts the
  leader at ~`29x29 x 9,893 ticks` (or `16x16 x 32,501`) — a 29x29 box has only ~112
  perimeter cells, so **the leader cannot be storing values in pipes at all.**
- **Ticks.** Every MAC rotates the rings, so latency scales with ring length. 16^3 = 4,096
  MACs settle at 259,873 ticks = **63 ticks per MAC**.

Tuning cannot fix a 4.4x box gap whose cause is that storage is perimeter-bound. The fix
is **2-D storage** (area, not perimeter): parked men as a register file, or a RAM room.
Recall that blocked men park indefinitely and for free.

## Do NOT reach for the existing RAM components

- `tools/fast_ram.py` has two hard, size-independent blockers: the caller's **command pipe
  must be <= 19 cells** (20+ deadlock) and the command port **must be fed by an input room,
  not a man**. Both trace to decode workers spawned on a fixed schedule.
- `split_ram` is **48x48 = 2,304 for every size** — 2.7x the leader's entire box.

A competitive matmul needs bespoke dense storage sized to this problem.

## Cheap consolation prize

If a rewrite is not affordable, the current design still has ordinary folding headroom
(control room is 34x49 inside a 61x61 envelope, and the rings are hand-routed). A 1.5-2x
from geometry alone is worth +3 to +4 places, but nothing beyond that is reachable without
changing how values are stored.

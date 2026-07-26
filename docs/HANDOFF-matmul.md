# Handoff prompt — finish the carousel matmul

Copy everything below into a fresh agent.

---

Continue the **carousel matmul rewrite**. Work in the git worktree
`/Users/dmitrykorolev/projects/icfpc-2026-smtopt` on branch `smt-llm-lllm`
(it is a worktree of `main`; `tl` needs `export TL_DIR=/Users/dmitrykorolev/projects/icfpc-2026/.tl`).

**Read first:** `docs/matmul-carousel-design.md` (the design, the improvement ranking,
the probe results, and the resolved control flow) and `docs/matmul-needs-a-rewrite.md`
(why a rewrite is the only path). Then `solutions/matmul/build_carousel.py`.

## Goal

Matrix Multiply is live at `61x61 x 61,830 avg ticks = 230,073,151`, **rank 32 of 74**.
Board best is 8,320,307. The cluster is dense — 10x is worth about +24 places (~0.32 pts),
the largest single-problem prize available. Nothing else on matmul is reachable:
floorplanning, `compact_man`, and `autotune` are all exhausted or blocked (documented).

Target: a working carousel at P=1, then fold, then raise P with `Y`.
Even P=1 at box ~2,025 is ~21.4M, about 10.7x better than live.

## What already works — do not rebuild

Five stages, each independently gradable:

```bash
cd /Users/dmitrykorolev/projects/icfpc-2026-smtopt
python3 solutions/matmul/build_carousel.py --stage hdr     # controller arith + I/O
# then in python: bc.grade(bc.build_ring(), ...) etc, or use --stage {ring,loop,seedA,lap}
```

| stage | proves | status |
|---|---|---|
| `hdr` | read N,M -> emit N*M | pass |
| `ring` | ctrl -> relay -> ctrl storage | pass |
| `loop` | `BP`/`m`/`d` counted loop | pass n=1,3,5 |
| `seedA` | seed N*M values into a ring, drain back | pass 2x2, 2x3, 1x1 |
| `lap` | **the MAC**: b<-input, a<-ring re-pushed every lap, emit a*b | pass K=1,3,4,5, negatives |

Probed and confirmed (`scratchpad/mm_probe.py`): **`s` preserves A**, **`*` preserves B**,
and **a pipe may NOT connect a room to itself** (`loaderror: pipe self-loop`) — every ring
costs a relay room plus two pipes.

## The remaining work

Compose the stages into the full machine. The algorithm is validated 7/7 in
`solutions/matmul/model_carousel.py` (run it).

Rings: **A-ring** (N*M raw a-values, drains once), **b-ring** (M*K values + one ROWMARK,
cycles once per output row), **c-ring** (K accumulators, self-aligns), **a-holder**,
**K-ring**. Five relays. No i/k counters, no N/M rings.

Loop: reload `BP`=K from the K-ring; pop `b`; if ROWMARK, push it back and emit the row;
else fetch the next `a`; then run the 10-op lap K times counted down in `BP`.

Accumulators carry a **+1e6 offset** (addition preserves it, every c stays positive, a
negative marker is testable with one `X`; |c| <= 156,816).

Order left: (1) `seedB` — seed both rings, push the ROWMARK, init the c-ring with K zeros;
(2) join to `lap`; (3) ROWMARK branch and row emit; (4) fold the box square; (5) raise P
with `Y` — but read the "why ticks/MAC cannot go below ~2" section before adding men.

## Three traps that already cost real debugging time

1. **Nearest-pipe binding silently steals ops.** This bit three times. `s`/`r` bind to the
   nearest pipe of the right direction by Manhattan distance from the *instruction cell*;
   an unintended winner produces no error, just a hang at the tick cap or wrong output.
   **Lay out all five relays' pipe columns BEFORE placing any ops** — op order is pinned by
   the register dance, pipe columns are free. When two pipes compete for a cell, move the
   losing pipe, never reorder the ops.
2. **A pipe attaches to its source room via the backward neighbour of its FIRST cell, taken
   along the FIRST SEGMENT's direction.** A pipe leaving a bottom wall must head *south*
   first; start it east and it attaches to nothing and every `s` in that room dies
   `no-pipe`.
3. **A shuttle loop's re-entry cell heading north must be `>`**, so `@` cannot live there —
   start the man one cell along. Otherwise the relay man walks into the wall and kills the
   whole program.

Also: markers may only live in the ring the lap pops **first**, because pushing a wrongly
popped value back sends it to the ring's TAIL and corrupts FIFO order. The lap pops `b`
first, so markers go in the b-ring.

## Verify with

```bash
python3 tools/grade_fast.py matmul <file.man>     # Rust engine, the fast pre-filter
node tools/grade.js matmul <file.man>             # oracle, the real judge
./interp/target/release/lm --grade f.man --input="..." --expected="..." --cap=5000
./interp/target/release/lm f.man 40 --input="..."  # per-tick trace; how both bugs were found
```

Grade on the Rust engine while iterating, re-grade on the oracle before believing anything,
and **commit before submitting** — git is the only copy of what we submit.

## Do not redo (all measured, all documented)

- smtplace on LLM, LLLM, Snake **and matmul** — all four are UNSAT / no-improvement at their
  floorplan optimum (`docs/smt-floorplan-limits.md`).
- The `smtrows` -> `boustro` port for LLM: ceiling is 2.78x, moves rank 17 -> 12 of 42, and
  the leader is 156x ahead. Not worth it.
- matmul `compact_man` (61x61 -> 61x61), and `autotune` (its builder `build_opt5.py run`
  dies with `PIPE COLLISION (15,-10)` and cannot regenerate the champion).

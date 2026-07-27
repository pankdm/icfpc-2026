# What governs boustrophedon controller size — measured, 2026-07-26

Every Semester-4 controller (LLM, LLLM, snake, pathfinder) is laid out as a
**boustrophedon ribbon**: the man snakes east/west across rows, and every `r`/`s`
must land on the column where its pipe attaches, because binding is
*nearest-pipe*. This file records what actually drives the box, and — more
usefully — **eight levers that were measured and do not work**, so nobody
re-runs them.

Score is `max(w,h)² × avgTicks`, so height is squared. On LLLM the controller was
377–421 rows against 107–131 columns, at **4.7% row density** (median 5 occupied
cells per row). It looks like there must be an easy 5x. There is not.

## The governing law

> **Ribbon cost ≈ the number of DIRECTION REVERSALS in the column sequence.**

A row ends when the next addressable token's column is not reachable in the
current direction. So height ≈ blocks + wraps. On LLLM: 388 rows = ~191 block
rows + **197 wraps**.

Two corollaries, both counter-intuitive and both measured:

1. **Spreading state across many columns is GOOD.** Many columns each visited
   once, in an order matching the access pattern, sweep monotonically and cost
   almost nothing.
2. **Concentrating state on few columns is BAD.** Replacing 20 holders (40
   columns) with one indexed RAM (2 columns) made rows **271 → 489**, because
   those two columns get revisited 364 times and most revisits reverse direction.
   Fewer ports is *worse*, not better.

## Measured dead ends — do not repeat

| lever | result |
|---|---|
| `CODE_SLACK` / `op_slack` (columns east of the last port) | **Inert.** 14/60/140 give byte-identical footprints. Measured independently on LLM (`cx50-o0`…`o600`: width 282→882, height **exactly 1137** every time). Extra columns east cannot reduce wraps, because a wrap depends on the next port's column being *behind* the cursor — a function of ORDER, not spacing. |
| `BAND_TIERS` | Zero effect on footprint (1/2/3 identical). |
| `HOLDER_PITCH` | Trades width for height at a losing rate: 3→131×421, 4→150×412, 6→188×407. Height falls ~5 rows per step while width climbs ~19. Never converges to square. `pitch=2` collides. |
| **Block packing** (several blocks per row) | Capped at 14/75. **61 of 75 blocks are branch targets**, entered from the WEST via a lane column with the man then walking east; two entry-targets cannot share a row because the second's entry path would walk through the first's ops and *execute* them. |
| **Column permutation** (anneal holder/block order + flip) | **Converged.** 40k iters × 6 restarts moved the score 1.1% and returned the *identical* holder order. `search_layout.py` already anneals against the real objective (`box×ticks`, exact model, 4 ms/candidate). |
| **Column replication, all ports ×2** | Would work — 267→158 rows, box 88,209→35,344 — but **is not buildable**: replicating a READ needs the holder to know which replica pipe the controller will read from. `S` sends to both and leaves a stale value in the unread pipe; draining it needs an op at the very column the replica existed to avoid. |
| **Column replication, sends only** (the buildable subset) | 25 of 47 columns are sends. Gives 240×240 vs baseline 298×298 — but calibrated that is **25.93B vs a 22.01B champion, i.e. worse than doing nothing**. The whole win lived in the unbuildable half. |
| **Mirrored holders** (two rooms per variable, to make reads replicable) | **Worse**: rows 271→433, box 90,601→214,369. Reads gain, but every WRITE must reach *both* copies and that forces more wraps than the reads save. |
| **`BP` as a variable slot** | No eligible variable. `BP` is write-only from `A` (`b` sets it, nothing reads it back), so it can only hold values never needed in `A` again. Of 191 holder reads, the dominant pattern is `hr V` → `hw X` — the value must be in `A` to be sent. Exactly **1 read in 191** qualifies. `BP`'s real uses are counters (`b`/`m`/`d`/`a`) and bit dispatch (`x`/`]`), already used. |
| **`Y` for state** | Forked men cannot read each other's registers, so a Y-held variable still needs a pipe to be read — the column and the wrap both remain. Y removes room *walls*, but the holders sit in the band above the controller, which is not the height driver. |

## Where the square point is

`box = max(w,h)²`, so minimising the box **is** targeting square, and the optimum
is a **broad basin**, not a knife edge — on LLLM, 8.62B at the optimum vs 8.81B
one step away. Any width/height-aware layout should choose its free parameter by
minimising `max(width, rows + chrome)` rather than hard-coding it.

If replicas are ever used, they must be **whole ORDERED copies** of the column
set. A greedy that replicated the single highest-wrap column and parked it at the
far east moved rows **zero** across twelve additions: jumping east to a lone
replica puts every other column *behind* the cursor, trading one wrap for many.

## Where `Y` and `BP` genuinely pay

Not in controller layout — in **replacing a memory**. Snake's board is 16×16 =
256 bits = **four 64-bit words**, held in forked men and selected by a 2-bit `BP`
decode (`b`, then two `x` turns) in ~10 ticks with no belt rotation. That works
because occupancy is *tested* (`&`, shifts) rather than round-tripped through
`A` — the opposite of LLLM's holder traffic.

## Method notes that cost real time

- **`grade_fast` averages avgTicks over PASSING cases only.** A candidate that
  does not pass every case has its average taken over a *different* case set and
  **is not comparable**. This produced a bogus 2.13x claim (see `ae9d3ee`).
- **Simulators drift.** The ribbon simulator here predicts 267 rows where the
  real build is 377 — **1.41x optimistic**. Calibrate before quoting a score.
- **The champion is a moving target.** LLLM went 168.89B → 29.31B → 22.01B in one
  session. Re-read the bar *before* committing to a build, not after.

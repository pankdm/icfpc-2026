# LLLM: where the box actually goes (measured 2026-07-26)

`score = max(w,h)^2 * avgTicks`. LLLM has two live lineages and the box binds
differently in each, so read the section that matches what you are editing.

| build | w x h | box | avgTicks | score |
|---|---|---|---|---|
| hand-built v2b champion (submitted `00ac26d8`) | 215x221 | 48,841 | 543,041 | 26.52B |
| champion after `polish` + `fold` + `stairfold` | 203x211 | 44,521 | 494,017 | 22.01B |
| generated `gen-tier2` (`build_lllm.py`, f7cd694) | 131x421 | 177,241 | 243,959 | 43.24B |

The generated build already has **2.0x better ticks** than the champion and
**4.0x worse box**. Its box is the whole gap, and it is 3.2x off square
(131 wide, 421 tall) — every row removed is worth 0.47% of its score, and there
are ~130 columns of width available for free before width starts to bind.

## Row budget of the generated controller

Measured on `build_lllm.py` @ f7cd694 (389 code rows + 30 band rows = 419):

| cause | rows | share |
|---|---|---|
| **port-column wrap** (next port lies behind the cursor) | **196** | **50%** |
| block first row | 75 | 19% |
| `go` / fall-through exit row | 75 | 19% |
| branch exit row | 41 | 11% |
| ran out of columns (`need()`) | 0 | 0% |

No block is ever length-forced to wrap: the widest block is 62 op cells against
~90 available columns. **Every wrap is port-column ORDER, not width.** That is
why widening the grid does nothing on its own (measured: `port_gap` 1 -> 17 adds
110 columns and removes exactly 0 rows).

### The floor

Give every port token a free column (`Columns.of()` returns `None`, i.e.
infinite replicas at zero routing cost) and the controller still needs
**187 code rows** — that is 75 + 75 + 41 of pure CFG shape. So:

* absolute ceiling of this architecture ≈ 217 rows tall -> box 47,089 -> **11.5B**
  at today's ticks;
* and it is **unreachable**, see "replicas are impossible" below.

Height is CFG-shape-bound, exactly as `CLAUDE.md` already records for LLM.

## Replicas are impossible here — do not design around them

The obvious fix for order-driven wraps is to give a hot holder several port
columns. It cannot work, for a reason that is structural rather than
geometric:

> A holder room's ring is `s -> r -> s -> r ...`. It sends its value, then
> blocks waiting for the controller's write. So the controller **must** access
> each holder in strict `hr, hw, hr, hw` alternation. Two `hr X` in a row
> deadlock: the holder is parked on `r`, so nothing is in the pipe.

Consequences:

* **A write-through replica desyncs or deadlocks.** If a read touches only
  replica *j*, the other replicas stay parked on `s` with a full pipe, and the
  next write blocks on them.
* **Touching every replica on every access buys nothing.** All replicas hold the
  same value, so the order within one access is free — but you must still visit
  all of them, which leaves the cursor at the extreme replica column instead of a
  chosen one. That is strictly worse than one column.
* **Two pipes to one room does not help either.** `r` binds to the *nearest*
  incoming pipe and `s` to the nearest outgoing one, so the second pair is dead
  weight. Two men in one room hold two independent values.

## Levers that were measured, with their real cost

All numbers on the pre-tier builder unless noted; `->` is box, and the tick
column is what killed most of them.

| lever | rows | width | box | ticks | verdict |
|---|---|---|---|---|---|
| `TAIL_PAD` 2 -> 0 | -2 | 0 | 177,241 -> 175,561 | unchanged | **free win, take it** |
| holder read->write gap 1 -> 2 (wider holder room) | -9 | +20 | -5.4% | **+8.0%** | net loss |
| ... gap 1 -> 4 | -14 | +60 | -7.7% | **+23.8%** | net loss |
| ... gap 1 -> 10 | -24 | +180 | -12.9% | worse still | net loss |
| block chaining (order blocks so in-degree-1 `go`s fall through) | -3 | -5 | -2.4% | untested | marginal |
| `HOLDER_PITCH` 3 -> 5 (undo the tiered band) | -14 | +38 | -6.6% | +19% (per f7cd694) | net loss |
| `port_gap` 1 -> 17 | 0 | +110 | worse | worse | useless |
| `RING_LIFT`, `DISP_GAP`, `CODE_SLACK` | 0 | varies | 0 | — | width-only, never binds |

The read->write gap deserves the detail, because the *diagnosis* is right even
though the fix loses. The single largest wrap cause is the pair
`(hr X, hw X)` — read a holder, compute, write it back — 17 occurrences for
`AD` alone, 55 across all holders. `hw` sits at `hr+1`, so **any** op between the
read and the write overruns it and costs a row. Widening the gap fixes only the
eastward half of them, because the placer is boustrophedon and a westward row
wants `hw` on the *other* side; and the width it costs shows up immediately in
ticks. The cheap fix is not geometry but **scheduling**: emit
`` lit 1; M; hr X; +; hw X `` instead of `` hr X; M; lit 1; +; hw X ``, which
needs only one op cell between the read and the write. That is a `lllm_flow.py`
change, not a placer change.

## Holder column order is exhausted — and searching it on rows is a trap

Already recorded in `build_lllm.py`, repeated here because it is the first thing
everyone tries: annealing `HOLDER_ORDER` on row count (16 restarts x 20k moves)
reaches 369 rows vs the incumbent 375, but grades **27% worse on ticks**
(411,684 -> 520,968), i.e. 67.5B -> 82.9B. Order sets both the wrap count and the
walk length and they trade off. Any future search must optimise `box x ticks`.

## The hand-built champion is converged under mechanical geometry

`polish` (blank/pipe row, blank/dash column deletion) then `fold` (merge two
adjacent grid lines) then `stairfold` (flatten walk staircases) then `polish`
again took it 215x221 / 26.52B -> 203x211 / 22.01B, and both passes then report
no further legal move. Two notes for whoever picks this up:

* **Use `--engine fast`.** The WASM oracle OOMs on LLLM, so `polish.py` and
  `fold.py` could not run on this problem at all until that flag existed.
* **`polish` only gates on the 10 public cases, and pipe/dash deletion shrinks
  rooms and pipes.** Re-gate on `tests/lllm-stress.json`
  (`scratchpad/lllm_mkstress.py`): 17 generated cases covering dense 16x16 grids
  over 13 rounds, every op class, a 14-lap ring, 3x3/3x16/16x3/blank minima,
  immediate halt, run-into-wall, and 40 rounds of k=1.

`k = 0` rounds crash the **unmodified** champion with a wall hit. Either k=0
cannot occur or it is a pre-existing bug in every build we have; it is excluded
from the stress set rather than silently passed.

# How Snake went 120x — a memo

**15,110,173,429 → 126,034,384 on the server (17/17), rank 42/64 → 19/64, from 508x off the
leader to 5.1x.** Builder: `solutions/snake/build_micro.py` (read its docstring — it is the
best layout document we have). This memo is what to copy.

## Where the benefit actually came from

| step | score | factor |
|---|---|---|
| old stateflow + split_ram build | 15,110,173,429 | — |
| **architecture rewrite** — O(1) state, RAM deleted (`07d42c1`) | 698,839,843 | **21.6x** |
| **layout refinements** — seven commits (`e68355c`…`68a73df`) | 85,499,669 | **8.2x** |

So: architecture ~21.6x, layout ~8.2x. **Do not stop after the rewrite** — the layout work
more than tripled it again. And the single biggest layout commit was worth 2.6x on its own.

## The one idea that mattered most

**Delete a pipe pair.** `847787f` removed the scratch ring: box 24,964 → 13,689 *and* ticks
18,482 → 12,733 — **2.6x from one deletion**. Why:

> **Lane width = room width ÷ number of pipes, and lane width sets HEIGHT.**

Every controller pipe attaches to the top wall, so the y-term cancels and binding is decided by
**column** alone. The interior splits into vertical lanes; a pipe op may only be emitted inside
its lane's window; a token that cannot reach its lane on the current row forces a **wrap** — a
whole row. With 4 in + 4 out pipes on a 34-wide room the state lane was **5 columns** and one
`r`/`s` pair cost half a row. Down to 3 + 3, the lane became **15 columns** and seven pairs fit
on one row.

**Count your controller pipes. Every one you remove widens every lane.**

## What made the deletion possible

- **One canonical-order state ring.** 8 scalars `[dy,hy,dx,hx,da,ha,fa,K]` popped and pushed in a
  fixed order once per round — O(8)/round. A rotating ring is cheap **iff** accessed in canonical
  order and pessimal under random access (LLLM's ring is random-accessed at O(ring)/access and
  that is exactly why LLLM is slow). Design the state so a canonical order exists.
- **Park a value in the ring** past the live count and recover it with one extra lap, instead of
  adding a scratch ring (SPAWN parks the fruit's x).
- **A DRIVER room** owning the display's ADDR/DATA/SWAP pipes, exposing **one** incoming pipe:
  `addr ≥ 0 then colour → write pixel; -1 → commit frame`. Three pipes collapse into one lane.

## Op idioms worth stealing

- **Exact range test with no `B`:** `b ] ] ] ] x` — `BP = v>>4` is 0 for 0..15, 1 for 16, −1 for
  −1, so `x` (turn on BP's low bit) is an exact in-range branch. Perfect for 16×16 bounds.
- **XOR involution to preserve `B`:** `M r W ~` computes `a^b` while `B` keeps `b`; one arm
  recovers `a` with a second `~`, the other finds it already in `B`. No scratch slot.
- **Keep a ring intact across a conditional:** pop, push back, *then* branch. Every popped value
  is pushed back, so the ring survives either outcome — the death repaint just pops K and paints.
- **Occupancy in registers, not memory:** a 16×16 board is 256 bits = four 64-bit words in men,
  selected by a 2-bit `BP` decode. ~10 ticks, no belt rotation, no RAM.

## Traps that cost us

- **Pipe length IS capacity.** The body ring was cut 85 → 65 and a 4,062-case fuzz found it
  **deadlocks at snake length 66**. It passed 17/17 only because no graded case gets that long.
  Size rings from the worst case, then fuzz before submitting.
- **`grade_fast` averages avgTicks over PASSING cases only.** A candidate that does not pass every
  case has its average over a *different* case set and **is not comparable**. This produced a bogus
  2.13x claim elsewhere.
- **Never put `@` inside a ring** — it is a no-op, so the man walks through it into the wall, which
  is fatal for the whole program. A relay ring must also strictly alternate `r`,`s`: two adjacent
  `r` silently drop a value.
- **Check for unsubmitted builds.** Twice a finished improvement sat in the repo ungraded. After
  any build agent runs, grade the newest `.man` and submit if it wins.

## Does this transfer?

**Pathfinder: yes** — it is bound by exactly the RAM Snake deleted (BFS = 67.8% of ticks =
12.24 scalar reads/pop at ~345–396 ticks each), and its state maps onto the same three gadgets
(bitset in registers, frontier FIFO ring, canonical state ring). Note its lanes are *already* wide
(12 pipes on a 174-wide room), so do not spend effort there — just don't regress it.

**LLLM: partly.** It needs a **box** breakthrough, not a tick one — at 50×50 its *current* ticks
already beat the leader. Its data architecture is already right; its controller is a compiled CFG
ribbon whose height is wrap-bound and unfoldable (nine measured dead ends in
`docs/boustrophedon-layout-limits.md`). The fix is Snake's: hand-structured lanes instead of an
emitted CFG.

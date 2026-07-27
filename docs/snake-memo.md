# How Snake went 136x — a memo

**15,110,173,429 → 111,249,327 on the server (17/17), rank 42/64 → 18/64, from 508x off the
leader to 4.5x.** Champion `micro9`: 86×86, box 7,396, local oracle 75,282,405. Builder:
`solutions/snake/build_micro.py` (read its docstring — it is the best layout document we have).
This memo is what to copy.

## Where the benefit actually came from

| step | score | factor |
|---|---|---|
| old stateflow + split_ram build | 15,110,173,429 | — |
| **architecture rewrite** — O(1) state, RAM deleted (`07d42c1`) | 698,839,843 | **21.6x** |
| **layout refinements** — `e68355c`…`98a0fcb` (micro2→micro9) | 75,282,405 | **9.3x** |

So: architecture ~21.6x, layout ~9.3x. **Do not stop after the rewrite** — the layout work
gained *more* than the rewrite did, across a dozen small commits, and it was still finding
~1% wins at micro9. The single biggest layout commit was worth 2.6x on its own.

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
- **One unified transaction beats an opcode.** Instead of separate set/clear/test commands, send
  `(or_mask, and_mask)` and let the quarter run a fixed branchless 8-op loop:
  `r | W ~ s` then `r & M`. The `s` emits *the bits this OR newly set*, which **is** the occupancy
  test (nonzero = cell was free). `SET(i)` = send `(mask, -1)` and it tests-and-sets in one pass;
  `CLR(i)` = send `(0, ~mask)`. If head and tail share a quarter, ONE transaction does
  clear-tail + set-head + loss-test together. Halves the pipe count and each controller arm is
  three cells.
- **Occupancy in registers, not memory:** a 16×16 board is 256 bits = four 64-bit words in men,
  selected by a 2-bit `BP` decode. ~10 ticks, no belt rotation, no RAM.

## Traps that cost us

- **A FIFO ring imposes a hard frame-rate floor.** With ring capacity `C` and body length `K`, a
  pushed value must travel `C-K` cells before it can be popped and has `K` frames to do it, so
  **`ticks_per_frame >= (C-K)/K`**, worst case `K=1` giving `ticks_per_frame >= C-1`. Size `C` from
  the true bound (≤100 rounds, each growth costs a spawn round plus a tick round ⇒ max body ≈49),
  not from 256. **Re-check this invariant every time you shrink the frame** — optimising below
  ~55 ticks/frame starts blocking the snake-length-1 frames.
- **`Program.pipe` will silently overwrite a room wall.** Starting a pipe at the room's own
  wall column destroys the wall; the program still *loads*, but that room now has zero outgoing
  pipes, so the controller blocks on `r` forever and you get a **bare timeout with no error**.
  This was hit twice. Use `tools/layout.py` `Layout`, or assert the pipe's first cell is one
  column outside the room.
- **`r` nearest-pipe ties are real** and resolve by reading order (top-to-bottom, then
  left-to-right). Break ties by moving cells rather than relying on it; where a room genuinely
  needs "any ready pipe", use a collector room (`R`, `s`) so every controller `r` has an
  unambiguous nearest pipe.

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

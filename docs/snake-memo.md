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

- **Pipe length is capacity AND latency — so size it, do NOT over-provision.** Measured on
  pathfinder's frontier ring: the *same* ring costs **15.5 ticks/op at capacity 45 and 58.4 at
  capacity 253** (~0.21 ticks/op per extra cell), so a "provably safe" 196-cell ring runs **3.8x
  slower** than a sized one. But undersizing deadlocks: snake's body ring cut 85 → 65 was found by
  a 4,062-case fuzz to **hang at snake length 66**, and it passed 17/17 only because no graded case
  gets that long. Measure the true worst case, add a modest margin, then fuzz. Pathfinder's
  frontier: measured max depth 30 adversarially, hard bound 196, built at **49**.
  **Overflow is silent** — the single controller man's `s` blocks forever, so the case TIMES OUT
  with no error rather than crashing.
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


## LIVE EXAMPLE of the ring trap (2026-07-27) — a 1.10x local win that fails PRIVATE cases

`push2.man` graded **5/5 public on the oracle**, box 5,184, avgTicks 7,274.8, local 37,712,563 —
a clean 1.10x over the champion's 41,550,213. Submitted, it came back **15/17, score None**.

`tools/equiv.py` had called it in advance, in one line:

    pipe structure changed (count, length or endpoints) — length is latency AND capacity

Pipe profiles: champion `[3,5,5,6,8,11,16,31,38]` vs push1/push2 `[3,5,5,5,7,8,11,31,46]`. The
rings were re-sized, and the 2 failing cases are the long ones no public case reaches — exactly
the failure mode already recorded here (the body ring cut 85 -> 65 hangs at snake length 66 and
still passes every public case).

**The operational rule this gives us: run `equiv` on every candidate, and when it reports a PIPE
LENGTH change, treat the build as unproven no matter how good the public grade looks.** Either
fuzz to the true worst case before submitting, or expect to burn a slot. `push1.man` has the
IDENTICAL pipe profile to push2, so it was not submitted — same rings, same expected failure.

Contrast with the wins that held: `fold10` and `fold11` both changed only a man's path length
(`equiv` reported no pipe change) and both scored 17/17 on the server.


## Snake is ALREADY SQUARE — reshaping caps at 1.06x (measured 2026-07-27, live 71x69 build)

The LLM squaring insight does NOT transfer. LLM was 356x793 (area 282,308 scored as 793^2), so
squaring was worth 2.23x. Snake's live champion is **71x69, box 5,041, area 4,899** — the same
area square is 69x69 = 4,761, i.e. **1.059x and that is the entire ceiling of any reshape.**
Moving the top band to the side trades height for width when they are already balanced, which is
neutral at best and usually worse.

Where the air actually is (921 content cells, 18.8% density):

    y0..7    content spans x19..61  ->  x0..18  empty  = 19 x 8  = 152 cells  (top band)
    y32..68  content spans x0..49   ->  x50..70 empty  = 21 x 37 = 777 cells  (lower right)

Width 71 exists ONLY because rows 14..31 reach x70; everything below y31 stops at x49. So the one
reshape worth doing is the inverse of "move the top gadgets sideways": pull the x62..70 content of
rows 14..31 DOWN into the dead lower-right rectangle, dropping width 71 -> ~62 so the box becomes
69^2 = 4,761.

**The 1.79x to the leader is a DENSITY problem, not a shape problem**: 921 cells at 35% density is
51x51 = 2,601, smaller than the leader's own 53x53. Both dimensions have to come down together,
which is why the lever is reflow (fewer wraps => fewer rows), not rearrangement.


## Shrink the room in the BINDING direction — the balance law (measured 2026-07-27, 67x67 build)

`box = max(w,h)^2`, so only the binding dimension counts, and on snake the two dimensions are
driven by DIFFERENT structures:

    grid_h = 6  + controller_h     (6 = the top band: two 6x4 relays, the 3x3 input)
    grid_w = 20 + controller_w     (20 = the driver 11x7 at x48..58 plus the display stack)

Live champion `live-4d96c89f.man`: 67x67, box 4,489, 885 cells, 19.7% density; controller
(room 4) is **47w x 61h** at x0..46, y6..66. Local 30,978,589 (5/5 oracle), server ~45.4e6.

**Balance condition: `controller_h = controller_w + 14`.** The controller should stay 14 rows
TALLER than it is wide, because the east stack costs 20 columns while the top band costs only 6
rows. Shrinking the non-binding dimension moves the box by exactly zero — this is the whole
reason a reflow must be aimed, not merely applied.

What controller density buys, at ~800 controller cells:

| controller density | controller | grid | box |
|---|---|---|---|
| 20% | 57x71 | 77x77 | 5,929 |
| ~30% (today) | 46x60 | 66x66 | 4,356 |
| 40% | 39x53 | 59x59 | 3,481 |
| **50%** | **34x48** | **54x54** | **2,916** |

The leader's 53x53 = 2,809 implies **~50% controller density**. So the target is not "make it
smaller" but specifically: **hold `ch = cw + 14` while driving controller density from ~30% to
~50%.** Two independent ways to move the east 20 columns are worth checking first, since they
shrink WIDTH without touching the controller at all: the driver room (11x7) and the display
stack sit entirely in the top-right, and rows below the driver leave that whole column band free.

# Littleman: how multiple little men interact

Based on the official [`Y, precisely`](https://icfpcontest2026.com/split) clarification, supplemented
by black-box experiments against the reference interpreter. The official clarification supersedes
earlier reverse-engineered interpretations of split identity, birth timing, swaps, and runner limits.

Coordinate convention (from oracle snapshots): `pos = [x, y] = [col, row]`; `dir` is a unit vector,
`east=[1,0]`, `south=[0,1]` (y increases downward), `north=[0,-1]`, `west=[-1,0]`.

---

## 1. How multiple men come to exist

There are exactly two sources of multiplicity:

1. **Separate rooms.** A program may contain many rooms; each may contain **at most one `@`**
   (a second `@` in a room is a load error). Men in different rooms are separated by walls and can
   **never** physically meet — they interact *only* through pipes/displays/IO and the shared clock.
2. **`Y` (split / fork).** The only way to get two men **in the same room**, and therefore the only
   way physical man-to-man interaction ever happens. See §3.

Consequence: **all physical man↔man interaction is a fork phenomenon.** Everything in §4–§6 is
reachable only through `Y`.

---

## 2. The global clock (lockstep)

Time advances in discrete **ticks**; all men across all rooms act in lockstep. The interpreter is an
ECS whose systems (recovered from symbols, in registration order) run each tick:

```
PipeTransportSystem → IORoomSystem → OpDispatchSystem → AdvanceSystem →
WallSystem → RunnerCollisionSystem → RunnerWakeSystem →
StepCapSystem / StepCounterSystem → CleanupSystem / ClearSuppressedSystem → DisplaySystem
```

This matches the prose tick order (pipes shift → I/O → execute → move) and additionally shows that
Ordinary **wall checks and movement-collision resolution happen *after* movement**. A `Y` birth in
a wall and a collision at a birth cell are resolved immediately during the split. Cleanup (reaping
halted men) happens near the end of the tick. Execution is fully deterministic.

---

## 3. `Y` — split / fork

When a man executes `Y`, he disappears and two copies are born immediately:

- the **right copy** is one cell clockwise from the incoming heading and faces away from `Y`;
- the **left copy** is one cell counter-clockwise from the incoming heading and faces away from `Y`;
- both inherit A, B, and Backpack exactly;
- neither executes its birth cell nor moves until the next tick;
- the right copy replaces the splitter in creation order; the left copy is newest and acts last.

`Y` is unconditional. Both births are attempted even when a birth cell is occupied or is a wall.
A wall birth is fatal. A birth on another little man kills both without an error. The live-runner
limit is **65,536**; a split that exceeds it is fatal.

The limit is nowhere near binding in practice: a 4-tick fork loop feeding a long serpentine track
sustained **102 simultaneous men** for 3000 ticks with no error and no refusal to split
(`sim/arb3.js`). Population is a free resource; what costs you is giving every man a planned fate.

---

## 4. Collisions

Every involved man dies, without an error, when:

- two or more men arrive on the same cell in one tick;
- adjacent men exchange cells in one tick;
- a mover enters a blocked or otherwise stationary man's cell;
- a split births a copy on an occupied cell;
- two splits birth copies on the same cell.

Collision resolution is symmetric: a stationary or blocked occupant dies together with the mover.

## 4b. Blocking & phasing — no pass-through (CONFIRMED)

Blocking is **per-man**: a man on `r`/`R`/`U`/`s`/`S` that can't proceed parks on his cell,
stays ACTIVE (not halted, not reaped), and retries each tick; other men proceed in lockstep.
A blocked man on `r` fed by an empty-then-delayed input pipe **unblocks on exactly tick = pipe
length L** — giving tick-exact control for timing experiments.

**Men cannot phase (pass through / swap / slip past each other):**
- **Ramming a blocked man:** a moving man whose step targets a parked man's cell does NOT pass
  through — both halt in place (`reason:"done"`, non-fatal). The stationary blocked man is halted
  too. (Same outcome as the same-cell rule, but note a *blocked* man IS a blocker here, unlike a
  *halted* man which is reaped and transparent.)
- **Unblock-and-swap:** even when a blocked man unblocks and steps out on the *exact* tick a mover
  steps in (verified via register state — the freed man genuinely became a mover), the engine still
  halts both. The stationary→moving asymmetry does not unlock swapping.
- **Convoy-follow (the one benign, non-phasing exception):** if a leader vacates a cell the same
  tick a follower enters it (leader unblocks exactly on time), the follower cleanly takes the freed
  cell — because execute happens before move. The follower ends up *where the leader was*, never
  *past* it. Off-by-one timing is fatal (both halt). Useful for flowing a train through a 1-wide
  gate with no gap.
- **Dense parking:** many *independently* blocked men can sit in adjacent cells indefinitely with no
  collision (movement is what triggers collisions; parked men never do) — a compact holding pen.
- **Pipes never carry men** (arrowheads sit outside the room wall; a man walking at a pipe exit hits
  the wall → fatal). Men move only by walking; only data/backpack values travel pipes.
- **Inter-man processing order** is creation order. On `Y`, the right copy keeps the splitter's place
  and the left copy becomes newest.
- **Pipe contention follows that same creation order (CONFIRMED).** When several men contend for one
  pipe on the same tick, the **oldest wins**, one per tick; the losers stay blocked and retry. Holds
  for both directions:
  - `s` (send): three men reaching `s` on the same tick emitted in creation order, **not** reading
    order (`sim/arb.js` — the four candidate laws predicted four distinct outputs, and only
    ascending id matched).
  - `r` (receive): three men parked on one incoming pipe took values in creation order
    (`sim/arb2.js`).

  Consequence for design: **a crowd of men is a FIFO, not a stack.** Arbitration cannot reverse a
  stream, and position/reading order does not enter into it — you cannot buy an ordering by laying
  men out differently. Reversal has to come from somewhere else (different distance travelled per
  man, or a packed-register LIFO).
- **Parking is free and indefinite (CONFIRMED).** A man blocked on a starved `r` sits ACTIVE for
  unbounded ticks with no error and wakes on the exact tick a value lands, while other men halt and
  are reaped around him (`sim/arb2.js`). Blocked men are cheap storage — but they cannot execute
  `q`, so a parked crowd cannot hear a broadcast; only a spinning crowd can.
- **`q` is a broadcast (CONFIRMED).** Every man in a room can `q` the same pipe on the same tick,
  all get the same depth, and the pipe is **not** consumed (`sim/arb2.js`). One token in a signal
  pipe re-steers an entire crowd through `d`/`a`/`x` — the only channel men in one room have.

---

## 5. Halting, reaping, and fatal errors (CONFIRMED)

- A man **halts** on `H`, or via a collision (§4). A halted man is **removed from the world**
  ("reaped") — confirmed: a man that halted at tick *t* was absent from the runner list at *t+1*.
  Therefore a halted man is **not** a persistent obstacle; you cannot "walk into" a halted man
  (there is nothing there to hit).
- The **program ends** when: every man has halted (`reason:"done"`), a fatal error occurs, or the
  step cap is hit.
- **Fatal errors end the whole program immediately** and are reported as
  `{halted:true, reason:"wall"|..., fatal:{reason, pos, cell}}` in the snapshot. Confirmed fatal:
  `wall` (a man moved onto a wall). Also fatal per the reference: `bad-op` (stepped on a non-instruction)
  and `no-pipe` (pipe op with no pipe on the needed side).
- Because reaping happens near tick-end and the program-end check is "all halted", a program with
  multiple men keeps running while **any** man is still active.

---

## 6. Men in separate rooms (CONFIRMED by model)

- One man per room; walls prevent any physical contact between rooms.
- They share only: the global tick clock (lockstep), pipes between rooms, displays, and IO rooms.
- Contention over shared pipes follows the pipe-targeting rules (nearest = Manhattan to the attachment
  segment, reading-order tie-break; `R`/`U` take from the first ready incoming pipe in reading order;
  `S` writes to all outgoing pipes and blocks if any is full). When men in different rooms act on a
  shared resource in the same tick, they do so in creation order.

---

## 7. Snapshot / oracle reference (for the differential harness)

`load(session, cellsArray, input, expected, framesJson)` where `cellsArray` is an array of row
strings. `step(session)` / `stepN(session, n, stopOnFrame)` return a JSON snapshot:

```json
{ "type":"snapshot",
  "entities": { "runners":[{"id","pos":[x,y],"dir":[dx,dy],"halted","a","b","backpack"}],
                "pipes":..., "rooms":[{"id","min","max","runners":[...]}], "displays":... },
  "output": [...] | null,
  "halted": bool, "reason": "done"|"wall"|..., "fatal": {"reason","pos","cell"}?,
  "step": n }
```

Runners are listed in ascending id order. Reaped (halted) runners disappear from the list.

---

## Summary of the interaction rules

| Situation | Result |
|---|---|
| Man steps on `Y` | Original disappears; right and left copies are born beside `Y`, inherit A/B/BP, and wait until next tick |
| Split birth on occupied cell | New copy and occupant both die; non-fatal |
| Two men → same cell or swap cells | Every involved man dies; non-fatal |
| Several men contend for one pipe | **Oldest wins**, one per tick (both `s` and `r`); losers stay blocked. Men are a FIFO, never a stack |
| Man blocked on a starved `r` | Parks indefinitely, stays ACTIVE, wakes on the exact tick a value lands; costs nothing |
| Many men execute `q` on one tick | All get the same depth — `q` is a **broadcast** and does **not** consume the pipe |
| Man halts (`H` or collision) | Removed from the world next tick (reaped); not an obstacle |
| Man moves onto a wall | **Fatal** error, whole program ends |
| Men in different rooms | No physical contact; interact only via pipes/displays/IO + lockstep clock |
| Program ends | All men halted, or fatal error, or step cap |

The official split clarification resolves the earlier open questions about swaps, creation order,
spawn collisions, and the maximum runner count.

# Littleman: how multiple little men interact

Reverse-engineered from the reference interpreter (`littleman.wasm`, Go 1.25.7, non-stripped)
via (a) embedded symbol/struct/docstring extraction and (b) black-box experiments driving the
WASM oracle headless in Node. Every "CONFIRMED" claim below was observed directly in the oracle;
items marked **OPEN** are deferred to the differential fuzzer built alongside the Rust interpreter.

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
**wall checks and collision resolution happen *after* movement**, and cleanup (reaping halted men)
happens near the end of the tick. Execution is fully deterministic.

---

## 3. `Y` — split / fork (CONFIRMED)

When a man executes `Y`, on that single tick:

- **He turns 90° clockwise** relative to his incoming heading and then takes his normal step that way.
- A **clone** is placed in the cell **90° counter-clockwise** of the `Y` cell, already **facing** that
  counter-clockwise direction.
- The clone inherits **A, B, and Backpack exactly** (verified: `A=5, BP=5` propagated to the copy).
  It is a full duplicate except position and heading. The clone receives a **fresh entity id**
  (ids are shared across runners/rooms and increase; e.g. the first fork produced id `2` while the
  room was id `1`).
- "The incoming heading is lost": neither man keeps the original direction — original → CW, clone → CCW.

General rule, incoming direction `d`: original heading becomes `rotateCW(d)`; clone spawns at
`Ycell + rotateCCW(d)` facing `rotateCCW(d)`.

Worked example — man at `[3,3]` heading east `[1,0]` steps onto `Y`:
- original → `[3,4]` heading south `[0,1]`
- clone (new id) → `[3,2]` heading north `[0,-1]`

Timing: the original executes `Y`, turns CW, and moves one cell that tick (normal execute-then-move).
The clone is **placed** on the CCW-adjacent cell that tick and does not take an extra step until the
next tick.

`Y` is **always enabled** — there is an internal `forkEnabled` flag + `maxRunners` cap in the config
struct, but the public `load(session, cells, input, expected, framesJson)` entrypoint (used by editor
and grader alike) exposes no toggle, and the default is on. `Y` is advertised by `validOps()`.

**Hazards:**
- If the clone's spawn cell, or the original's forward cell, is a **wall**, the normal wall
  consequence fires and **ends the whole program** (see §5). Every spawned man needs a planned fate.
- Re-entrancy: a man may hit the same `Y` repeatedly and fork again each time (confirmed — reflected
  men re-entered a `Y` and produced 2nd/3rd-generation clones).
- **OPEN:** exact value of the `maxRunners` cap (a cap exists; value not yet pinned).

---

## 4. Collision: two men would occupy the same cell (CONFIRMED)

When two active men's moves would place them on the **same cell** in the same tick, **both men stop in
place and halt** — they do *not* enter the shared cell, and neither "wins." This was reproduced across
16 routed head-on configurations: in every case the two men ended up 2 cells apart, each facing the
shared middle cell, then halted.

- The collision-halt is a **clean halt** (`reason:"done"` when it ends the program) — **not** a fatal
  error. It behaves like `H` for the men involved.
- Matches the prose rule "when he touches another little man, both stop."

**Structural note on head-on geometry:** the two children of a *single* fork are always an even
Manhattan distance apart from any common cell, so a single fork can only ever produce the
**same-cell** collision above — the two men can never become adjacent and exchange cells.

**Swap / pass-through: NO (strong empirical evidence).** Men cannot pass through each other. A
randomized search of 4000 multi-fork programs (producing many 3–4 man collisions) detected **zero**
position-swaps: two men never exchange adjacent cells. Combined with the same-cell rule, the engine
prevents both same-cell occupation and adjacent-exchange — colliding men halt. (Empirical, not a
hand-proof.)

**OPEN (deferred to fuzzer):**
- **Perpendicular** same-cell arrival (assumed to follow the same "both halt" rule, not yet isolated).
- **Inter-man processing order** within a tick (by entity id / spawn `seq`, or by reading-order
  position?). Not yet isolated; matters for pipe contention when co-located men send/receive the same
  tick. `insertRunnerID` / `runnerSeq` suggest an id/seq-ordered runner set.

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
  `S` writes to all outgoing pipes and blocks if any is full). Inter-*man* ordering when two men in
  different rooms act on a shared resource the same tick is the same **OPEN** processing-order question
  as §4.

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
| Man steps on `Y` | Forks: original turns CW & steps; clone spawns 1 cell CCW facing CCW, inherits A/B/BP |
| Two men → same cell same tick | Both stop in place and **halt** (clean, `reason:"done"`) |
| Man halts (`H` or collision) | Removed from the world next tick (reaped); not an obstacle |
| Man moves onto a wall | **Fatal** error, whole program ends |
| Men in different rooms | No physical contact; interact only via pipes/displays/IO + lockstep clock |
| Program ends | All men halted, or fatal error, or step cap |

**Open items for the fuzzer:** swap resolution, perpendicular same-cell, inter-man processing order,
`maxRunners` value.

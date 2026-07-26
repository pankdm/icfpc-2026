# Semester-4 fork

A working fork of the Semester-4 compiler infrastructure and programs, so that
optimisation work here does not collide with a teammate developing the same
modules on `main`. **Best ideas get merged back deliberately, as a diff — this
tree is never fast-forwarded into `tools/`.**

Forked 2026-07-26 from `main`.

## What is forked (writable — edit these)

```
s4/tools/                 full copy of tools/*.py at fork time (40 modules)
s4/solutions/snake/                       builders + champion .man
s4/solutions/pathfinder/                  builders + champion .man
s4/solutions/little-little-man/           builders + champion .man
s4/solutions/little-little-little-man/    smt-layout.json + champion .man
```

The compiler stack that matters here: `flowgrid.py`, `stateflow.py`, `boustro.py`,
`reflow.py`, `smt_layout.py`, `smtplace.py`, `smtrows.py`, `walkfold.py`,
`stairfold.py`, `roomfit.py`, `place.py`, `router.py`, plus the program-level
passes `dce.py`, `lift.py`, `equiv.py`, `emit.py`, `blockify3.py`.

## What is shared (symlinks — do NOT edit through them)

`sim/`, `interp/`, `tests/`, `docs/`, `PROBLEM.md` point at the parent tree.
They are inputs and oracles, not fork targets. Editing them defeats the fork.

## How to use it

Run **builders** from inside `s4/`, so `import tools.X` resolves to the fork:

```bash
cd s4 && python3 solutions/pathfinder/build_bitset5.py ...
```

Run **grading and submission** from the repo root, which holds `.env` and the
gitignored `littleman.wasm` / `wasm_exec.js`:

```bash
cd /Users/visenbaev/icfpc26
node tools/grade.js pathfinder s4/solutions/pathfinder/<new>.man
python3 tools/submit.py pathfinder s4/solutions/pathfinder/<new>.man
```

Only champion `.man` files were copied. Historical variants stay readable in the
parent `solutions/` tree; read them there, write new ones here.

## Merging back

Changes here are proposals. When something wins, port the *idea* into `tools/`
in a focused commit rather than copying files over — the teammate's versions
will have moved on. `diff -u tools/X.py s4/tools/X.py` is the review unit.

## Known state at fork time (all measured, all server-confirmed)

| problem | champion in repo | box | server score | live score |
|---|---|---|---|---|
| snake | `linked-compact-reflow-cx10-o0` | 64,009 | 18.435B | 15.110B |
| pathfinder | `reverse-bfs-bitset5-s4-smt` | 115,600 | 293.037B | 240.426B |
| LLLM | `reflow3-233x234` | 54,756 | 224.146B | 168.892B |
| LLM | `pipe-io-banked-dedup-boustro-hw2-fb-anneal` | 848,241 | **9.437T** | (this is live) |

LLM update (2026-07-26): 277x1137 / 15.03T -> 394x921 / **9.437T server, 28/28**,
via a packed hardware band, two-row branches, and a constrained port-column
anneal. See `git log s4/solutions/little-little-man`. Its remaining height is
`194 block rows + 96 goto rows + 213 branch rows + ~373 forced newlines`; the
newlines are the only term left with real slack and they need pipe-band OVERLAP
(duplicate attachments per port), not reordering -- the order is already within
1% of the minimum-feedback-arc optimum.

**Every repo candidate is worse than what is live, and the live builds are not in
git.** Benchmark against the repo candidate's own measured score, not against the
live score. Someone with the dashboard cookie needs to run
`tools/submissions.py --download submitted/`.

**Server ticks are layout-invariant** (three snake layouts spanning 64,009→97,969
box give server avgTicks within ±2.6%). So you can predict the server without
submitting: `server ≈ local grade.js score × 1.54` (snake), `× 1.49` (pathfinder),
`× 1.12` (LLLM).

**...but only under room RE-PLACEMENT.** Corrected 2026-07-26: ticks are *not*
invariant under **port-column** changes, which is what a dense CFG re-lay does.
The controller's row count falls when the hot `sc`/`rr` pair gets long overlapping
Voronoi bands, but the hot ops then sit further apart and the man walks the
difference — snake box −19% / ticks +22%, pathfinder box −7% / ticks +8%, both
near-washes on score. Anything touching port columns must be judged on
**box × ticks**, measured; `solutions/*/search_rail.py` does that on one real
interpreter case.

Snake/pathfinder dense re-lay (2026-07-26), all server-confirmed:

| what | box | server | cases |
|---|---|---|---|
| snake live at fork | 64,009 | 15.110B | — |
| snake `rail-cx10-o0` (rail terminators) | 47,524 | 13.359B | 17/17 |
| snake `rail-cx10-o0-lit` (+ backtick literals) | 44,944 | 12.658B | 17/17 |
| snake `dense-a` (+ searched ports/floor) | 36,481 | **12.477B** | 17/17 |
| pathfinder `rail-bitset5` (rail terminators) | 108,241 | 265.353B | 18/18 |
| pathfinder `dense-b` (+ searched ports/floor) | 96,721 | **240.331B** | 18/18 |

Both champions regenerate byte-identically (`solutions/*/build_rail.py`).
`tools/railflow.py` is the reusable piece: same op placement as `boustro`, but a
jump costs 0 extra rows and a branch 1 instead of 4.

`tools/manlint.py` is what makes a floorplan search safe. Three failure modes bit
in a row, each invisible to the previous check, and all three are now covered:
a crossing pipe (writes the same `|`-over-`-` a room corner does), a pipe end that
misses a room wall (walls cannot be recognised by glyph, since pipe bodies use the
same ones — and components stamped by copying cells never call `room`), and a grid
that loads cleanly and then **deadlocks** (a shrunk pipe is a shrunk FIFO). Only
the last is caught by running the program, so every search champion now pays for
one Rust case.

**LLLM geometry is provably exhausted** — `smtplace.py` returns UNSAT at M=233.
Its only lever is shortening the op stream; its generator source is deleted at
HEAD and must be recovered from commit `0ecfe41` (`lllm_build.py`,
`lllm_layout.py`).

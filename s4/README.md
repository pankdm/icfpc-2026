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

**Every repo candidate is worse than what is live, and the live builds are not in
git.** Benchmark against the repo candidate's own measured score, not against the
live score. Someone with the dashboard cookie needs to run
`tools/submissions.py --download submitted/`.

**Server ticks are layout-invariant** (three snake layouts spanning 64,009→97,969
box give server avgTicks within ±2.6%). So you can predict the server without
submitting: `server ≈ local grade.js score × 1.54` (snake), `× 1.49` (pathfinder),
`× 1.12` (LLLM).

**LLLM geometry is provably exhausted** — `smtplace.py` returns UNSAT at M=233.
Its only lever is shortening the op stream; its generator source is deleted at
HEAD and must be recovered from commit `0ecfe41` (`lllm_build.py`,
`lllm_layout.py`).

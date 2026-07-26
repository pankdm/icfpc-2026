# autotune — the score optimizer

Reads a solution's **builder** (`solutions/<slug>/build*.py`), perturbs the integers in it,
regenerates the `.man`, grades it on the reference oracle, and keeps a change only if the
program **still passes every case** and **scores strictly lower**. Score is
`max(width,height)² × average ticks` — lower is better.

It exists because nearly every 10–20% win in this repo's history was a constant tweak found
by hand (`pitch 16→14`, `band=30`, `XL=4`, `relay -13→-12`). This does that search for you,
and it runs unattended.

```bash
python3 tools/autotune.py <slug> solutions/<slug>/build_x.py --jobs 8 --budget 1200
python3 tools/autotune.py <slug> solutions/<slug>/build_x.py --dry-run     # baseline + knob list
python3 tools/autotune.py tcp solutions/tcp/sweep_build.py -- --full2      # args after `--` go to the builder
```

## The safety contract

**It cannot break a working solution.** If you are tempted to "just let it write in place",
don't — these four properties are what make it safe to run unattended:

1. The builder runs in a **temp sandbox** (symlinked `tools/`, `sim/`, `tests/` plus a copy of
   `solutions/<slug>/`), so a build never writes into the real tree.
2. The **baseline must pass every public case** before tuning starts, else it refuses.
3. A candidate is accepted only if `passed == total` **and** `score < best`.
4. Output goes to **new files** — `<name>-tuned.man`, `<builder>_tuned.py`, and a
   `<name>-tuned.json` record of every accepted change. Nothing existing is overwritten.
   Re-tuning an already-tuned artifact reuses the same names (no `_tuned_tuned` chains).

## Generality: the one real risk

Local grading only sees **public** cases. The contest also runs hidden **private** cases, and
a team scores **zero** on a problem unless it passes at least one private case.

- **Footprint (box) wins are input-independent** — a smaller grid is smaller for every input.
  These are always safe.
- **Tick wins are measured on public cases only.** For a timing-sensitive multi-man design, a
  knob can pass public and still break a private case. Gate those with
  `--cases tests/stress/<slug>.json` (see `tools/stress.py`).

## How the search works

- **Screening** (build-only, no oracle): every knob is probed once with ±1 and classified
  *inert* / *always-breaks* / *live*; only live knobs are searched, box-shrinkers first.
  Measured: 143 knobs → 41 live in 13s, and it cut the build-error rate in a wave from
  71% → 22%. Disable with `--no-screen`.
- **Waves**: all single-knob perturbations of the current best are independent, so each wave
  is one parallel barrier (not one per knob). The best win is applied, then a new wave starts.
- **Line search**: after a win, keep stepping that knob the same direction while it keeps
  paying, instead of restarting a wave per step.
- **Macro knobs**: one knob per *(enclosing function, axis)* over calls whose first two
  positional args are int literals — i.e. shift a whole block of geometry together. A
  per-literal search cannot express "slide this block 3 columns west" at all. `--no-macros`.
- **Cost control**: candidates are capped at `--tick-factor` × the baseline's average ticks
  (a broken candidate otherwise runs to the 5,000,000-tick default); the cheapest case is
  graded first and grading stops at the first failure; identical grids are graded once, and
  results persist in `.autotune-cache.json` across runs and agents (`--no-cache`).
- **Checkpointing**: the best-so-far is written the moment it is accepted, so a crash costs
  nothing.

## Making a builder tunable (read this if you are writing one)

The tuner reaches a solution only through its builder, and a repo-wide audit found it could
originally touch just **4 of 12** solved problems. To keep yours reachable:

- **Emit the grid.** Either save a `.man` under `solutions/<slug>/`, or simply `print()` it —
  stdout is parsed as a fallback (that fallback is what unlocked most of the repo).
- **Be deterministic and side-effect free.** It will be run hundreds of times in parallel.
- **Reproduce the champion.** The tuner reports `reproduces committed <file>: yes/no`. If it
  says no, the builder has drifted and you are tuning something that is not live.
- **Put geometry in integer literals**, not in strings or computed constants — literals are
  what the search can move.
- **Take a CLI flag** if one script builds several variants, and document it.

## What to expect

Honest, measured expectations:

- **Hand-folded champions are usually local optima.** A full sweep of `sort-numbers`
  (712 candidates, then 328 after screening) found **nothing** — that solution is genuinely
  optimal under both single-literal and block moves. Expect the same for any grid that has
  already been squeezed by hand.
- **Wins are typically a few percent.** `sudoku-validity` gave 7,556,863 → 7,125,678 across
  two accepted changes (5.7% on the server) — worthwhile and free, but not architectural.
- **Some builders are brittle rather than optimal.** A `gradebook` sweep produced **0 valid
  candidates out of 876** (563 failed cases, 312 broke the build): its literals mostly encode
  *data* — grade codes, character tables — not geometry, and moving data breaks correctness
  immediately. Check the screening line: many live knobs but no valid candidates means the
  literals are data, and tuning that builder is a dead end regardless of budget.
- **Fresh builders are where it earns its keep** — nobody has swept them by hand yet.
- **It will not close a 5× gap.** When the gap to the board leader is large, the answer is a
  different design, not a different constant. Use `node sim/xray.js <slug> <file.man>` to see
  whether ticks are going to compute, walking, turns, or stalls before assuming tuning helps.

## Extending it

- Knob discovery: `find_knobs` (scalars) and `find_macro_knobs` (block shifts) — both return
  objects with a stable `.key`, a display `.name`, and a `.value`; `patch()` dispatches on type.
- Add a move type by emitting knob-like objects from a new finder and including it in the wave
  planner; nothing else needs to change.
- Grading goes through `tools/grade_json.js` as a subprocess (it accepts `--cap`, `--cases`,
  `--failfast`), so grading logic stays in one place.

Related: `tools/polish.py` mutates a `.man` **directly** for solutions with no working builder;
`tools/autotune_batch.py` sweeps the whole repo unattended; `tools/stress.py` generates the
edge-case suites for `--cases`; `tools/lift.py` + `tools/emit.py` are the compiler front end
and emitter that a placement pass builds on.

# ICFPC 2026 — littleman: guide for agents

We write **littleman** programs (`.man` — a 2D ASCII grid esolang: little men `@` walking
rooms, executing the glyph under them, talking over pipes) and submit them to the contest
grader. `PROBLEM.md` is the language + scoring reference (read it before writing any grid).
This file is the *operational* guide: how we work, what already exists, what not to redo.
For the end-to-end construction, verification, profiling, optimization, and submission
workflow, read `docs/agent-framework-guide.md`.

**Contest clock** (from `/api/v1/public/contest-clock`): started 2026-07-24 12:00Z,
lightning ended 2026-07-25 12:00Z, **ends 2026-07-27 12:00Z**; final standings freeze
2026-07-27 10:00Z. 20 problems, **16 graded** (Semesters 1–4) + 4 ungraded practice.

## Setup

```bash
bash sim/fetch-oracle.sh        # once: downloads littleman.wasm + wasm_exec.js (gitignored)
```
Node 20+ (v25 here) and Python 3 stdlib only — **no npm/pip install**.

- **`.env` holds `API_KEY=...`** (gitignored). It authorises `POST /submissions` and
  `GET /submissions/:id` — nothing else. Team: *Snakes, Monkeys, and Two Smoking Lambdas*.
- **The dashboard needs a browser session cookie**, not the API key: `~/.icfpc-cookie`
  (or `$ICFPC_COOKIE`). The login form sits behind a Cloudflare Turnstile, so it **cannot
  be scripted** — grab the cookie from DevTools → Network → any `/api/v1/` request.
- Rust is installed and `interp/` builds locally. Use it for heavy iteration and profiling;
  the organizer WASM remains the ground-truth final oracle.
- **The submitted program text is not retrievable from anywhere** (checked: Bearer
  `GET /submissions/:id` and every `dashboard/*` route omit it). **git is the only copy of
  what we submitted — never submit a build that is not committed.**

## Dev loop

```bash
python3 tools/grade_fast.py <slug> <f.man>  # ← START HERE. Rust engine, ~17x faster than wasm
node tools/grade.js <slug> <file.man>   # grade one candidate (oracle = the FINAL judge)
node tools/grade.js <slug>              # grade + rank every candidate in solutions/<slug>/
node tools/grade_all.js [--slug X]      # batch regression vs tests/baseline.json (offline)
node sim/xray.js <slug> <file.man>      # WHERE to optimize: box driver, headroom, corridors
node sim/profile.js <slug> <file.man>   # per-cell/per-man tick attribution (compute/turn/glide/stall)
node sim/case.js <file.man> '<json-rounds>'   # run against a hand-written case
python3 tools/status.py                 # live board: best score to beat, solvers, TRUE case counts
python3 tools/compare.js / decompose.py # our scores vs board; guess leader's box×ticks split
python3 tools/submit.py <slug> <file.man>      # submit + poll (needs .env)
python3 tools/fetch_tests.py [slug...]  # refresh tests/<slug>.json spec cache
```

`grade.js` fetches the spec from the API; `grade_all.js` and the scripts above prefer the
cached `tests/<slug>.json`. Local PASS ⇒ public-case PASS (same wasm the server grades with)
— but private cases are **not** covered locally.

**ALWAYS REACH FOR THE RUST ENGINE FIRST** (`interp/target/release/lm`, built with
`cargo build --release --manifest-path interp/Cargo.toml`). It is ~17x faster than the wasm
oracle and it is what makes any search or profiling loop affordable — pathfinder's 7 cases take
~60s on Rust and *minutes* on wasm (`sim/xray.js` on a 2M-tick pathfinder case does not finish
in 10 minutes). Use it as a **pre-filter, not the judge**: fast reject ⇒ discard; fast pass ⇒
`lm` also has `--profile` and `--inspect=N` (single-tick JSON snapshot) which the wasm
harness cannot give you.

**A Rust pass is good enough to SUBMIT, but a Rust FAIL is NOT good enough to discard.**
`node sim/difftest.js` compares the two engines step-by-step (runner states, pipe contents,
output, end reason, parsed topology). It is **NOT green**: measured 2026-07-27 it reports
**57 passed, 4 failed** — `lit-cross-h-digit`, `lit-cross-v-digit`, `lit-two-rooms-same-row`,
`lit-junk-in-col`, i.e. every remaining failure is LITERAL semantics. (An earlier note here
claimed 61/0; that was wrong or has regressed — re-run it, do not trust this paragraph either.)

**Worked example of the false reject, and it is not hypothetical.** The LIVE brackets champion
(`solutions/brackets/live-351bec3e.man`, 15×15, server 97,719 at 26/26) scores **0/9 in the Rust
engine** — eight cases `crash: wall` at tick 10, one `timeout` — while the **oracle passes 9/9**
in 144 ticks with `inputRead` never advancing past 0 in the Rust trace. An agent following
"fast reject ⇒ discard" would have thrown away a champion. So: a Rust reject means
**re-check with `node tools/grade.js` before believing it**, especially on grids with literals
or several small rooms. Since submitting never lowers a score, the cost of a
rare false pass is one submission slot (max 5 pending), not points. Prefer the oracle as a final
check when it is cheap, but do NOT block on it: it OOMs outright on LLLM (`Go program has already
exited`) and `sim/xray.js` on a single 2M-tick pathfinder case does not finish in 10 minutes.
The risk the Rust engine does NOT cover is the same one the oracle misses — PRIVATE cases.
Generality, not engine fidelity, is what loses points. The fixtures also only cover what we
thought to test: they were 54/54 green *while* the literal bug below was silently mis-executing.

**Literal semantics were wrong in `interp/` until 2026-07-26** (fixed, `scratchpad/lit-probe/`):
backticks pair **per room**, per interior row/column — a global row scan pairs two literals in
*different* rooms across the wall and rejects them, which is why the Rust engine could not load
33 of our own files (all of `subset-sum/parallel*`, `sort-numbers/merge-mergercell-v1`). And
literal content is a nop **only along the literal's own axis**: a man crossing a horizontal
literal from above executes the digit he lands on. See `docs/hidden-capabilities.md`.

**`sim/xray.js` defaults to `--cap=120000` ticks.** On a multi-million-tick program that window
may cover only the *setup* phase, and its GLOBAL/HEADROOM percentages will then describe the
wrong phase entirely. Always pass `--cap` above the case's real settle tick, or treat the
numbers as setup-only. This bit during the pathfinder analysis.

**Oracle quirk:** long runs can kill the Go wasm with `Error: Go program has already exited`
(runtime OOM). Grade heavy problems **one file per process**; `subset-sum`'s 20-value case
hits this every time (it also blows the 15M tick cap on the server — that's why we're 12/20).
One process per *case* is not always enough: measured 2026-07-26, the oracle OOMs on **11 of
LLLM's 14 public cases** (every one above ~9M ticks) even alone in a fresh process, and
`--max-old-space-size` does not help (the OOM is inside the Go heap, not V8's). For those the
**Rust engine is the only local grader we have** — which is why `interp/` fidelity matters.

## Repo map

```
solutions/<slug>/*.man     candidate programs (keep every variant; never delete/regress)
solutions/<slug>/build*.py the generator that PRODUCED the .man — edit this, not the grid
tools/littleman.py         Program(): rooms/men/pipes/display + render/footprint/grade/save
tools/layout.py            Layout (collision-checked cursor), place_pipe, route, fifo_ring, auto_pipe
tools/router.py            global A*/rip-up router for pipes + man-corridors (docs/routing-requirements.md)
tools/compact_man.py       mechanically delete redundant rows/cols (validator-checked)
sim/                       reference oracle harness + ~30 probe/measure scripts
interp/                    fast Rust interpreter, full language parity (needs cargo)
interpreter/               dependency-free Python interpreter + unittests
docs/                      semantics plus agent-framework-guide.md (read these)
tests/<slug>.json          cached problem specs incl. publicTestData; index.json = summary
scratchpad/                throwaway probes, gadget prototypes, POC builders
```

The Rust interpreter has full parity for pipes, I/O, literals, displays, and rounds
(`403a927`), plus profiler and pipe-endpoint diagnostics used by the optimization loop.

## Where we actually stand

Run `python3 tools/ours.py` (points/rank/gap, public data) and `python3 tools/submissions.py
--match` (server-side box/ticks per submission, needs the cookie). **Do not trust local
scores or commit messages for this** — local grading only sees public cases, and two entries
below were wrong in exactly that way until the dashboard corrected them.

As of **2026-07-26 ~15:40Z we are 26.88 points, 5.12 available — ALL 16 graded problems now
pass every case**. Semester 4 is solved; the correctness game is over and this is now purely
a *ranking* game (see below). Run `tools/ours.py` for the live table.

**Scoring is now purely rank-based.** With every case passing, `case_pts` is pinned at 1.0 and
the only variable is `rank_pts = (field − rank) / (field − 1)`. So what matters is **not** the
gap to the leader but **how many teams are clustered just below our score**. `tools/ours.py`
sorts by points lost; to see what an *improvement* is actually worth, compute ranks-gained per
speedup factor — the marginal value differs wildly per problem. Measured 2026-07-26:

| problem | rank | +1.5x | +2x | +3x | +5x | +10x | max |
|---|---|---|---|---|---|---|---|
| LLLM | 29/48 | 0.09 | 0.11 | 0.20 | 0.28 | 0.39 | 0.60 |
| Pathfinder | 23/42 | 0.03 | 0.08 | 0.10 | 0.15 | 0.28 | 0.54 |
| Sudoku | 36/78 | 0.11 | 0.15 | 0.34 | 0.43 | 0.47 | 0.45 |
| Snake | 40/55 | 0.04 | 0.06 | 0.14 | 0.18 | 0.24 | 0.72 |
| Grade Book | 22/68 | 0.10 | 0.16 | 0.21 | 0.24 | 0.28 | 0.31 |
| Sort | 32/128 | 0.11 | 0.17 | 0.24 | 0.24 | 0.24 | 0.24 |
| **all 16 combined** | | **0.86** | **1.37** | **2.20** | **2.78** | **3.60** | 5.12 |

Read that bottom row: **a broad 1.5–2x sweep is worth more than a 100x on any single problem.**
Sudoku and Sort have the densest clusters (a 3x on sudoku ≈ 0.34 pts); Snake/LLLM/Subset Sum
are 200–480x off the leader, so even a 10x barely moves them.

Also: **the field improves while you sleep.** We drifted 26.91 → 26.88 in ~90 minutes on
2026-07-26 without touching anything. Standing still loses points.

### Champion inventory — do not re-do this archaeology

Every live build **is already the best one available anywhere** (verified 2026-07-26 by grading
all 118 unique `.man` files across all 19 worktrees against the oracle and comparing per problem).
There are **no unsubmitted improvements** lying around. Two traps found doing it:

- **`tools/submissions.py --match` matches by DIMENSIONS ONLY.** It reported sudoku's live build
  as `multi2.man` (42×40) — but the real champion is a different 42×40 build with 4.1k ticks vs
  multi2's 19.3k. Submitting the "matched" file scored **32.4M against our live 7.23M**. Identify
  champions by SCORE, never by box.
- Champions live on several branches; `main` (7190033) is the most complete. Commit `54c1eb5`
  ("commit every live champion, including five that existed nowhere in git") is the recovery.
  The `-history`, `-gbreflow`, `-pfbits`, `icfpc-pathfinder-opt` worktrees each hold champions
  that are **not** in the others.
- **`git fetch --all` BEFORE STARTING ANY PROBLEM, then search `git log --all`.** Measured
  2026-07-26: `icfpc-2026-main` was three hours and six commits behind on Grade Book because
  origin had never been fetched. `submissions.py --match` reported the live build as "NO local
  `.man` of these dimensions" and a full-disk `find` for recent `.man` files returned nothing —
  it looked like the champion existed only on the server. It did not; it was commit `089b211`
  on `origin/dualhead-reopen`. **Teammates push to branches you do not have.** Checking the
  local tree is not enough, and an unfetched worktree makes you redo work that already shipped.
- **Compare a candidate against the score of the build it was DERIVED FROM**, never against the
  problem's live score. Read the sidecar `.json` next to the archived submission. A 1.074x
  Grade Book win read as a 12x private *regression* purely because it was measured against a
  live champion three generations newer than its own input.

### LLLM: the live champion is NOT in git (measured 2026-07-26 ~21:00Z)

`tools/submissions.py` reports our live LLLM entry as **142x141, box 20,164, avgTicks
311,616, score 6,283,423,104, rank 7/60**. That build exists in **no worktree and no
`submitted/` archive** — every LLLM `.man` on this machine has a box of 41,209 or more,
and the best archived submission JSON is `fa4fb613` (polish-203x200) at **22,459,642,837**.
So a teammate submitted it from another machine. Two consequences:

* **Do not use `polish-203x200.man` as the LLLM baseline.** It is the best build *in git*,
  not the best build *on the board*, and the gap is 3.6x.
* The local:server score ratio for LLLM is **~1.07** (measured on three submissions:
  polish 2.03e10 -> 2.25e10, lane2 1.64e10 -> 1.75e10, lane3 1.42e10 -> 1.51e10). Earlier
  notes claiming 0.309 were reading the board score against the wrong local file.

To beat 6.28e9 on the server a build needs local box x avgTicks < ~5.9e9 — at the lane
build's 292k ticks that is a box under 20,200, i.e. **142x142**.

### Measured dead ends (2026-07-26) — do not repeat these

- **Boustrophedon band widening / replica ports (LLM, Snake, Pathfinder).** 870 of LLM's 994
  controller rows come from band conflicts in `boustro.Cursor.place()`, and Snake/Pathfinder are
  100% band-driven — which *looks* like bands are everything. They are not: overriding every
  port's band to the full op range (i.e. infinite replicas, no routing cost) only takes LLM's
  controller 994 → 588 rows, a **2.4x box ceiling**, because `_lay_once` starts a NEW ROW for
  every block — 194 blocks × 1 row + 98 `br` × 3 rows ≈ 490-row floor. Widening one hot band is
  worth even less (moving `sd` 80→150 doubles `sc`'s band 30→65 cols for 994→981, **1.3%**).
  **LLM height is CFG-shape-bound, not band-bound**; the lever is fewer/packed blocks.
  Re-spacing attachments also breaks pipe routing (≈2000/2000 coordinate-descent moves and 3 of 5
  targeted moves failed `verify_bindings` — trap 3 in `docs/reflow-lessons.md`).
- **Replica pipes have an ordering hazard**: `R` picks among ready incoming pipes in **reading
  order, not arrival order**, so equal-length replicas preserve send order only while at most one
  replica is ready — a guarantee that gets *weaker* as the layout compacts.
- **Snake box is at its floor**: `code_x` ∈ {10,20,40,60} × `op_slack` ∈ {0,10,40,100} ×
  `scalar_belts` × `cell_belts` all leave `ctrlH = 200` and best box 64,009 (= the champion).
- ~~**History Lesson is at its layout floor** (83×83 exact)~~ — **REFUTED 2026-07-26.** That
  claim was about `build_ring.py` only, and a different construction beat it: a folded dispatcher
  plus variable-width feeder bands reach **82×82, box 6724** (`solutions/history-lesson/best/82x82.man`,
  oracle 1/1), with `candidates/81x82.man` also at 6724. Score is pure footprint and it has
  **0 private cases**, so local pass ⇒ server pass. The remaining lever is still *compression*:
  4473 digit cells ≈ 14.9 kbit encode 2810 bytes (ratio 0.66) where gzip gets 1563 B — matching
  gzip would free ~700 cells and reach 76×76, which is the leader's box. **Lesson: "at its floor"
  findings are scoped to the generator that produced them, not to the problem.**
- **LLLM: multiple men on one relay cycle.** A ring rotates no faster than its relay lap,
  and the lap is six cells (four of the six are forced turns, so six is the floor for a
  directed cycle carrying both an `r` and an `s`) — two thirds of LLLM's ticks were the
  controller stalled on that. More men would fix it and cannot be built: a room admits one
  `@` (a second is a load error), and forking with `Y` deadlocks because **walking into a
  stalled man HALTS BOTH** (interp `move_phase`), which a six-cell cycle guarantees within
  a few laps. The lever that did work was fewer rotations, not faster ones.
- **Sudoku `multi2` is not the champion** (see trap above); autotune on it found DX 16→15
  (box 1764→1681) and `DX=14` reaches 40×40 but dies with `loaderror: pipe ends without
  reaching another room`.

## What actually moves the score

Score is `max(w,h)² × avg ticks`. In this repo's history the wins came, in order:

1. **Fold the layout** — biggest, safest lever (pure geometry, no logic risk). Make the box
   *square* (only the larger dimension is squared): matmul 47961→13689, sudoku 5041→1849,
   brackets 961→529→ (`stack6` is a pure layout fold of `stack5`), tcp raised the checker
   purely to square 1936→1681. Delete empty interior rows/cols (`sim/xray.js` BOX DRIVER,
   `tools/compact_man.py`), tuck I/O rooms into dead margins, hang blocks beside each other.
2. **Cut walking** — nop-glides and turns are pure tax. Shorten revisiting loops, keep
   hot loops narrow (`xray.js` CORRIDORS ranks the longest blank runs on the critical man).
3. **Cheaper ops** — e.g. brackets replaced a multiply-classifier with bit-ops (1.75×);
   tcp replaced 16 tree rows with a 3-op `w & X` gadget.
4. **Parallelism** — more men (separate rooms or `Y`) to overlap latency. Remember a crowd
   of men is a **FIFO** (oldest wins pipe contention), never a stack.
5. **Optimize the dominant case** — avg ticks is usually set by one big case (`xray.js` DOMINANT).

Keep short pipes (length adds latency *and* ticks), and remember ticks stop at the **final
correct output** — crashing into a wall afterwards is free, `H` is often unnecessary.

### Automated tuning (`tools/autotune.py` — **full docs: `tools/AUTOTUNE.md`**)

```bash
python3 tools/autotune.py <slug> solutions/<slug>/build*.py --jobs 8 [-- builder args]
```
Perturbs an integer in the builder, regenerates the `.man`, grades it, and keeps the change
only if it still passes every case **and** scores strictly lower — parallel waves of
single-knob moves. Builds run in a temp sandbox and output goes to new `*-tuned.man` /
`*_tuned.py` files, so it cannot damage a working solution. **If you write a builder, read
the "making a builder tunable" section of `tools/AUTOTUNE.md`** — a repo audit found the
tuner could originally reach only 4 of 12 solved problems, almost always because of how the
builder emits its grid.

What it found so far, and what that tells you:
- **sudoku-validity: 7,556,863 → 7,209,468** (box 1849 → 1764) from a single literal
  (`Sx = [1 + i*P …]` → `[0 + …]`, sliding a block one column left). Converged after that.
- **sort-numbers: nothing.** All 712 single-literal perturbations of `select_build_v5.py`
  either broke the build (474), failed cases (224), or scored worse — `select-v5` is a
  local optimum. Hand-tuned champions usually are; expect small or no wins there.
- **tcp: the builder no longer runs** — `sweep_build.py --full2` dies with
  `layout.Collision at (3,21)`, so `tcp-sweep2.man` cannot be regenerated at all.

Use it on *fresh* or *recently hand-built* solutions (Semester 4), where nobody has yet
swept the geometry by hand; it is largely wasted on the old, heavily hand-folded ones.
Ticks measured on public cases are a proxy — pass `--cases stress.json` when a design's
timing is delicate. Box shrinks (like the sudoku one) are always safe.

## Semantics you will get wrong from the spec alone

Read `docs/multi-man-interactions.md` and `docs/hidden-capabilities.md` — everything there
is confirmed against the oracle. The ones that bite most:

- **Footprint = bbox of non-space cells.** Trailing spaces / blank lines / indentation are free.
- **`Y` is released and safe.** Right copy keeps creation order, left copy is newest; birth in
  a wall is fatal, birth on a man kills both. Men never phase through each other.
- **Blocked men park indefinitely and for free** (cheap storage), but a parked man can't `q`.
- **`q` is a broadcast** — every man in a room reads the same pipe depth, nothing is consumed.
  It's the only channel men in one room have (steer a crowd via `d`/`a`/`x`).
- **`r`/`s`/`q` lock onto the *nearest* pipe** (Manhattan, reading-order ties) even when busy;
  `R`/`U` take from any ready incoming; `U`'s turn is **relative to the pipe's position**.
- **`/` with `B=0` → `A=0, B=dividend`** — a one-cell "B:=A, A:=0". `%0 → 0`.
- **Literals load on the closing backtick**, read in the walk direction (reversed westward);
  a corner backtick opens an H+V literal sharing digits; must fit i64 **both** ways.
- Wall-hit / bad-op / no-pipe are **fatal for the whole program**, not just that man.

## Conventions

- One `.man` per approach, freely named; **add variants, never overwrite a working one**.
  The champion is simply the newest/lowest-scoring file — `git log --name-only -- solutions/<slug>`
  is how we track it.
- If a `build*.py` exists next to a `.man`, the grid is **generated** — change the builder and
  regenerate; hand-edits get lost. Builders use `tools/littleman.py` + `tools/layout.py`;
  put reusable patterns below the `# === PATTERNS ===` marker in `littleman.py`.
- Prototype gadgets in `scratchpad/` (probe rigs, `.man` + driver `.js`/`.py` pairs) before
  folding them into a solution.
- Commit style: `<slug> <variant>: <what changed>, <box/ticks before->after>, server <score> (<cases>)`.
  Record the **server** score when known — it's the only number that counts.
- Before submitting: `node tools/grade.js <slug>` (all candidates pass?), sanity-check that
  the solution **generalizes** (n=1, empty, negatives, max size, multiple rounds), then submit.
  Submitting never lowers a score — only the best per problem counts. Max 5 pending (429).
- Practice problems (`atoi`, `hello-world`, `max-element`, `palette`) reject submissions.

## Traps

- **Private cases exist** (~2–3× the public count; the per-problem API reports 0 — trust
  `status.py`'s `cases` column). You need ≥1 private pass to score at all, so never hardcode
  public answers, and stress the shape of the input, not the values.
- A local 6/6 has repeatedly meant 20/20 on the server — but a *generality* bug (fixed n,
  assumed non-empty, assumed positive) shows up only as a private failure.
- Long/thin grids are the #1 score leak: a 69×130 grid is scored as 130² even though half
  the box is empty air.

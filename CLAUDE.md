# ICFPC 2026 — littleman: guide for agents

We write **littleman** programs (`.man` — a 2D ASCII grid esolang: little men `@` walking
rooms, executing the glyph under them, talking over pipes) and submit them to the contest
grader. `PROBLEM.md` is the language + scoring reference (read it before writing any grid).
This file is the *operational* guide: how we work, what already exists, what not to redo.

**Contest clock** (from `/api/v1/public/contest-clock`): started 2026-07-24 12:00Z,
lightning ended 2026-07-25 12:00Z, **ends 2026-07-27 12:00Z**; final standings freeze
2026-07-27 10:00Z. 20 problems, **16 graded** (Semesters 1–4) + 4 ungraded practice.

## Setup

```bash
bash sim/fetch-oracle.sh        # once: downloads littleman.wasm + wasm_exec.js (gitignored)
```
Node 20+ (v25 here) and Python 3 stdlib only — **no npm/pip install**.

- **`.env` with `API_KEY=...` is NOT in the working tree.** Without it `submit.py` exits
  and *nothing can be submitted*. Ask the user for the team key before promising a submit.
- Rust is **not installed** on this machine (`cargo` missing) — `interp/` can't be built
  here. That's fine: the WASM oracle is ground truth, and it's fast.

## Dev loop

```bash
node tools/grade.js <slug> <file.man>   # grade one candidate (oracle = the real judge)
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

**Oracle quirk:** long runs can kill the Go wasm with `Error: Go program has already exited`
(runtime OOM). Grade heavy problems **one file per process**; `subset-sum`'s 20-value case
hits this every time (it also blows the 15M tick cap on the server — that's why we're 12/20).

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
docs/                      reverse-engineered semantics (read these)
tests/<slug>.json          cached problem specs incl. publicTestData; index.json = summary
scratchpad/                throwaway probes, gadget prototypes, POC builders
```

Note `docs/OVERVIEW.md`'s "Interpreter status TODO: pipes…" is **stale** — the Rust interp
got full parity (pipes/IO/literals/display/rounds) in `403a927`.

## Where the scores are today

Local score = `max(w,h)² × avg public ticks`; the server averages over ~2–3× more (private)
cases, so server ≈ local × 1.0–1.6. Board = best full-solver score, **lower is better**.

| problem (set) | our champion | local score | board best | note |
|---|---|---|---|---|
| triangle (S1) | `p2.man` 9×9 | 1,053 | 832 | 6/6 |
| memory (S1) | `belt5.man` 42×42 | 36.0M | 27,867 | server 160.6M — far off board |
| reverse-a-list (S1) | `manual-fork/v2_46k.man` 12×10 | 32,526 | 19,481 | server ~46k; hand-built fork machine |
| sort-numbers (S1) | `select-v5.man` 21×21 | 774k | 27,210 | server ~1.97M (v4) |
| history-lesson (S2) | `history-lesson-with-year.man` 84×84 | 7,056 | 5,929 | **footprint-only** scoring |
| brackets (S2) | `stack6.man` 23×23 | 167k | 300 | server 421k @ stack5 |
| tcp / Packet Reassembly (S2) | `tcp-sweep2.man` 41×41 | 1.83M | 329,349 | server 2,896,783 (20/20) |
| plotter (S2) | `plotter-tight31.man` 81×81 | 202M | 862,560 | server 297,019,750 (20/20) |
| gradebook (S3) | `gradebook-compact.man` 69×130 | 858M | 42.2M | server 3.15B; **box is height-bound → fold it** |
| matmul (S3) | `matmul-tight2.man` 89×82 | 441M | 5.56M | 7/7 |
| sudoku-validity (S3) | `ringfree4.man` 43×41 | 7.56M | 49,720 | server 7,668,172 (20/20) |
| subset-sum (S3) | `parallel256-prefix-compact-*.man` | — | 500 | **12/20 only** (n=20 exceeds tick cap) |
| snake, pathfinder, LLM, LLLM (S4) | — | — | see status.py | **not started**; specs cached in `tests/` |

Everything graded except the four Semester-4 problems is passing all cases; the gap to the
board is almost entirely **score**, not correctness. Semester 4 is untouched — 4 problems ×
up to 2 points is the largest single opportunity left.

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

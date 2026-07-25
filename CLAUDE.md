# ICFPC 2026 — littleman: guide for agents

We write **littleman** programs (`.man` — a 2D ASCII grid esolang: little men `@` walking
rooms, executing the glyph under them, talking over pipes) and submit them to the contest
grader. `PROBLEM.md` is the language + scoring reference (read it before writing any grid).
This file is the *operational* guide: how we work, what already exists, what not to redo.

Task state lives in `tl` (a git-native tracker) — run `tl ready --json` for what to work on
and `tl doctor` for health; load the tl skill or `tl help --json` for how to drive it.

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
- Rust is **not installed** on this machine (`cargo` missing) — `interp/` can't be built
  here. That's fine: the WASM oracle is ground truth, and it's fast.
- **The submitted program text is not retrievable from anywhere** (checked: Bearer
  `GET /submissions/:id` and every `dashboard/*` route omit it). **git is the only copy of
  what we submitted — never submit a build that is not committed.**

## Task tracking (`tl`)

Work items live in `tl`, not in scratch notes — several people and agents run in parallel
here, so claim before you start or two of you will fold the same grid.

```bash
tl ready --json                  # ranked, unblocked work; --json on ANY command
tl claim <id>                    # take it (refuses, with reasons, if not actually ready)
tl close <id> --as done          # finish; discharges anything it was blocking
tl create "<title>" --description "…"
tl dep add <id> <blocked-by>     # <id> becomes blocked by <blocked-by>
tl why <id> / tl unblocks <id>   # transitive blockers / what closing this frees
tl list        tl stats          tl doctor
```

Two things specific to this repo:

- **State is gitignored** (`.tl/.gitignore` is `*`) and lives in `.tl/` at the **main
  checkout only** — it is an append-only op log, not committed files. Sharing happens over
  the `refs/tl/log` git ref via **`tl sync`**, which has **never run yet**, so teammates
  cannot see anything you file until it does. Auto-publish is off; turn it on with
  `git config tl.autosync true`.
- **From the `optimizer` worktree `tl` finds nothing** (it searches up to that worktree's
  own root). Point it at the real state dir:
  `export TL_DIR=/Users/dmitrykorolev/projects/icfpc-2026/.tl` (or pass `--dir`).

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

## Where we actually stand

Run `python3 tools/ours.py` (points/rank/gap, public data) and `python3 tools/submissions.py
--match` (server-side box/ticks per submission, needs the cookie). **Do not trust local
scores or commit messages for this** — local grading only sees public cases, and two entries
below were wrong in exactly that way until the dashboard corrected them.

As of 2026-07-25 ~17:00Z we are **rank 27/235, 21.84 points, 10.16 still available**:

| problem | live build | box | avgTicks | our score | board best | pts | left |
|---|---|---|---|---|---|---|---|
| Pathfinder | 7/18 cases | — | — | — | 11.1B | **0.00** | **2.00** |
| LLM | none | — | — | — | 95.5B | **0.00** | **2.00** |
| Snake | 5/17 cases | — | — | 22.7B | 72.7M | **0.00** | **2.00** |
| LLLM | *not in git* | 149×1469 | 5,078,601 | 10.96T | 1.27B | 1.13 | 0.87 |
| Grade Book | `gradebook-compact.man` | 69×130 | 186,578 | 3.15B | 42.2M | 1.49 | 0.51 |
| Plotter | `plotter-tight31.man` | 81×81 | 45,270 | 297M | 862,560 | 1.51 | 0.49 |
| Sudoku Auditor | `ringfree4.man` | 43×41 | 4,147 | 7.67M | 49,720 | 1.55 | 0.45 |
| Matrix Multiply | `matmul-opt5.man` ← **not** tight2 | 61×61 | 61,831 | 230M | 15.2M | 1.62 | 0.38 |
| Subset Sum | `parallel256-prefix-compact-r13-c21` | 634×588 | 162,350 | 65.3B | **500** | 1.63 | 0.37 |
| Sort | `select-v5.man` | 21×21 | 2,723 | 1.20M | 27,210 | 1.69 | 0.31 |
| Packet Reassembly | ⚠️ **not in git** | 35×35 | 1,738 | 2.13M | 329,349 | 1.71 | 0.29 |
| Brackets | `stack6.man` | 23×23 | 578 | 305,884 | 300 | 1.76 | 0.24 |
| History Lesson | `history-lesson-with-year.man` | 84×84 | — | 7,056 | 5,929 | 1.84 | 0.16 |
| Memory | `manual_4.man` / `addr-compare.man` | 26×26 | 23,556 | 15.9M | 27,867 | 1.95 | 0.05 |
| Reverse a List | `manual-11x11.man` | 11×11 | 187 | 22,603 | 19,481 | 1.97 | 0.03 |
| Triangle | `weave8x8.man` | 8×8 | 13 | **832** | 832 | **2.00** | 0.00 |

**⚠️ Packet Reassembly's live 35×35 build is not in git** (searched every blob in history;
the repo's best is `tcp-sweep2.man` at 41×41 / 2.90M). It cannot be reproduced or improved
from the repo. Same for the LLLM 149×1469 build. Whoever has them locally must commit them.

### What is worth doing (this is the whole strategy)

- **Semester 4 correctness is worth 6.00 points; every score optimisation on all 12 solved
  problems combined is worth ~3.3.** Snake, Pathfinder and LLM currently earn **zero**.
- **Passing only public cases earns nothing.** Eligibility needs ≥1 *private* pass, and a
  partial solve that happens to cover exactly the public cases (Snake 5/17, Pathfinder 7/18
  — the public counts are 5 and 7) scores 0.00, not "partial credit". Generalising a
  half-working Semester-4 solution is worth more than any amount of folding elsewhere.
- Of the tuning targets, **Grade Book (+61 height slack) and LLLM (+1320 height slack)** are
  the only ones with large mechanical box headroom left; the rest are already square.

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

### Automated tuning (`tools/autotune.py`)

```bash
python3 tools/autotune.py <slug> solutions/<slug>/build*.py --jobs 8 [-- builder args]
```
Perturbs one integer literal in the builder, regenerates the `.man`, grades it, and keeps
the change only if it still passes every case **and** scores strictly lower — steepest
descent in parallel waves. Builds run in a temp sandbox and output goes to new
`*-tuned.man` / `*_tuned.py` files, so it cannot damage a working solution.

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

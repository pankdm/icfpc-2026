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

**A Rust pass on the public cases is good enough to SUBMIT.** `node sim/difftest.js` compares
the two engines step-by-step (runner states, pipe contents, output, end reason, parsed topology)
and reports **61 passed, 0 failed** (re-verified 2026-07-27 after the `U` fix below).

**REBUILD BEFORE YOU TRUST IT — a stale `lm` is the most expensive trap here.** Measured
2026-07-27: `interp/target/release/lm` was 3.5 hours older than `interp/src/lib.rs`, so every
`grade_fast` run that day executed an engine predating the literal fix. It presented as four
difftest failures (`lit-cross-h-digit`, `lit-cross-v-digit`, `lit-two-rooms-same-row`,
`lit-junk-in-col`) and led to a wrong entry in this very file claiming difftest was 57/61.
`cargo build --release --manifest-path interp/Cargo.toml` first, every session.

**`U`'s turn is the pipe's END ARROWHEAD, not its last in-path step** (fixed; `pipe_flow_dir`).
They differ whenever a pipe TURNS on its final cell -- a 2-cell L dropping from a bottom wall
and then pointing east has last-step *south* but arrowhead *east*. With the old rule the LIVE
brackets champion (server 97,719 at 26/26) scored **0/9 in Rust**, crashing `wall` at tick 10,
while the oracle passed 9/9; it now scores 9/9 at 230.22 avgTicks, matching the oracle exactly.
So when Rust rejects a program the oracle accepts, suspect the ENGINE, not the program --
re-check with `node tools/grade.js` before discarding a candidate. Since submitting never
lowers a score, the cost of a rare false pass is one submission slot (max 5 pending), not points. Prefer the oracle as a final
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

**LLLM generality is already covered — 321 adversarial cases, all green** (2026-07-26 ~21:40Z).
`python3 scratchpad/lllm_adv.py` regenerates `tests/lllm-{adv,fuzz,oos}.json` (115 structured +
200 seeded-random + 6 deliberately out-of-spec) from `lllm_model.py`, cross-checked against the
independent `scratchpad/lllm_ref.py`. Grade them like any slug:
`python3 tools/grade_fast.py lllm-adv <f.man> --cap 20000000 --jobs 8`. **The WASM oracle does
NOT OOM on these** (all under 801k ticks) — `node tools/grade_json.js lllm-adv <f.man>
--case-index N` is a real oracle check, and it agreed on every case. Coverage: every op class,
every W,H in 4..16, every k in 1..64, 30 rounds, all halt modes, 64-bit A wrap observed through
X, and 71 pairs of consecutive IDENTICAL frames (empty delta). `scratchpad/lllm_adv_power.py`
proves the suite has teeth by injecting 18 classic bugs; wrap32 / no-wrap / M-is-a-swap are
caught by **zero** public cases. `lane3-178x220.man`, the CW=144 rebuild, `polish-203x200` and
`champion-a33a42bd` all pass — a private LLLM failure is now very unlikely, so spend the
remaining time on BOX.

### LLM row budget — measured on the CHAMPION, 2026-07-27 (four ideas killed)

**Measure the CHAMPION, not whatever the builders regenerate.** I claimed LLM had 294 rows of
branch overhead (98 `br` x 3). That is `tools/boustro.py`'s `Cursor.branch3`, whose build is
**1137x277 and is NOT the champion**. The live 735x428 build already spends **exactly one row
per branch** — verified by decoding the grid: 100 rows contain an `X`, 102 `X` glyphs, 98 `br`.
The 294-row saving does not exist.

**There is NO GENERATOR for the 735x428 champion in ANY of the 23 worktrees** (every
`solutions/little-little-man/*.man` was dimensioned). The smallest regenerable build is
1137x277. So an emitter change cannot currently be applied to the champion at all — that is
the first thing to fix before any LLM layout work.

Real row budget of the champion (688 interior controller rows, 9,175 ops):

| rows | what |
|---|---|
| 170 | block-entry op rows |
| **289** | **WRAP / continuation op rows — 42%, THE REAL DRIVER** |
| 98 | branch dispatch (1 per `br`, already optimal) |
| 131 | pure-control rows (102 `go` + branch north arms) |

Four ideas probed against the ORACLE and killed (rigs in `scratchpad/rowbranch/`):

- **In-row 3-way `X`** — worth **0 rows**; the champion already does it. Confirmed working both
  ways though: heading EAST the terminator sits in the block's own op row (`probeA2.man`,
  ZERO extra rows), A>0 -> south, A<0 -> north, A==0 -> continues east.
- **BP trie (`b ] x ] x`)** — executes correctly (4/4 on the oracle) but **costs rows**: `x`
  ALWAYS turns, so it leaves the current axis by construction and a depth-d trie spans ~d rows.
  4-way = 5 rows vs `X`'s 3-way in 1 row. Two stacked `X` give 9 ways in 2 rows. Killed.
- **`Y` for control flow** — dead twice over. Contention among parked men resolves by
  **CREATION ORDER (FIFO by age), not reading order** — measured, the *bottom* man won — so a
  broadcast cannot address block L of 200. And a genuinely parked man is blocked on `r`/`s` and
  therefore **cannot execute `q`**, so he cannot observe the broadcast at all.
- **Zero-row `go`** — real but small. Continuing EAST costs 0 rows (a `v`/`^` in an east
  corridor column inside the block's own op row); a WESTWARD return costs 1 row and there is no
  zero-row 180-degree reversal (a turn is only observed after a move). Applying it needs the CFG
  2-COLOURED so east-running blocks hand off to west-running ones: 200 blocks / 396 edges gave
  **62 monochromatic edges** after local search, so 131 -> ~62 rows, ~69 rows saved = **1.10x**.

Everything together is 736 -> ~667 rows, box 444,889, **1.21x**. Not worth a rewrite. The row
that matters is the WRAP row (289 of 688), and op rows average 20 ops over a 101-column span
inside a 387-column room.

### LLM: forks are FREE but have nothing to do — the hot loop is a POINTER CHASE (2026-07-27)

Three numbers I quoted earlier were wrong; use these:
- **Stall is 138.8 ticks per RAM READ**, not ~51 per transaction. 782,821 stall ticks over only
  **5,638 real receives** on case 0 — the old figure divided by 15,521 SENDS instead of receives.
- **`node sim/difftest.js` is 62/62**, not 61/61.
- **Free width is 437 columns, not 38.** x318..355 *and* x356..792 are unused; width does not
  bind until 793.
- The dominant stall is the **FRAME-RENDER loop** (4 frames x 256 pixels; the 12 hottest `r`
  sites each net exactly 256/257 receives = 16x16), NOT guest-instruction fetch.

**The fork itself is free and works.** `solutions/little-little-man/fork-s1.man` and `fork-s2.man`
(patcher: `scratchpad/llmfork/graft.py`) both grade 14/14 with box AND avgTicks BYTE-IDENTICAL to
the champion, and `lm --profile` shows Y=1/H=1, so the second man is genuinely alive at zero cost.
s2 also proves the east strip is usable: room 0's wall moved x=317 -> x=355 with box unchanged.
See `docs/hidden-capabilities.md` for the reusable zero-cost fork idiom (fork on a `v`->`<` drop
cell) and the measured 3.0x/9.4x/34.6x latency-hiding curve.

**Why it cannot pay HERE — two independent walls:**
1. **No channel.** Forked men share only pipes, and room 0 cannot gain a usable one. A new port on
   the bottom wall at x=318..355 is provably safe (tightest existing site is `r` at (312,196),
   552 vs 549) — but safe and reachable are the same constraint inverted: a port only far-east men
   can bind to is a port only far-east men can USE. A port near the real work instantly hijacks
   existing sends (one at (318,~197) sits ~9 cells from the `s` at (309,196) whose binding is 548).
   Talking through RAM costs a full round trip — the exact latency being hidden.
2. **No independent address stream.** The hot loop is a POINTER CHASE. Row 196 is `0` / `s1s` /
   `rM0` / 157 blanks / `sWsr` — **the value returned by RAM1 IS the address sent to RAM2**, and
   the two biggest stall sites (312,196) and (312,721) at 79,104 ticks each are both downstream of
   a RAM1 read. A prefetcher cannot form the address. Per the rig, when the consumer must hand the
   producer the next address the handoff lands on the critical path and two men score **0.90x**.

Ceiling for reference: removing ALL of room 0's `r` stall is **1.71x** (1,892,707 -> 1,109,886),
score ~1.73e12. Anything beyond needs the 53.89% GLIDE split as well.

### LLM: THE FOLD LOSES ON LATENCY — box is immovable at the grid level (2026-07-27)

**This supersedes the 4.0x squaring plan below. Do not build it.** The plan was arithmetically
sound on box and wrong on ticks.

The deciding measurement, `lm --profile` room-0 glyph histogram on case 0 (1,892,707 ticks):
`' ' 1,020,074 | 'r' 788,459 | 'M' 16,605 | 's' 15,521`. So the controller is
**53.9% blank glide + 41.7% BLOCKED on `r` + ~4% real work**, doing only 15,521 sends and
burning **~51 ticks of stall per transaction**.

A horizontal fold forces slab B's replica ports 300-370 columns from the peripherals (X0>=368
is forced -- any nearer and slab B's leftmost columns bind to slab A's port 315). That is
**+600-740 ticks of round-trip latency per transaction**; even at half the transactions it adds
~4.7M ticks to a 1.89M baseline. **A ~3.5x tick blowup to buy a 1.55x box cut: the fold loses by
~2.3x.** The same arithmetic kills the balanced two-controller cut, which moves half the code
away from the same peripherals. PIPE LENGTH IS LATENCY, and this program is latency-bound.

(The replica protocol IS constructible, recorded so nobody re-derives it: OUT replicas via the
destination switching `r`->`R`, or a 2-in/1-out merge room; the reply direction via a mux room
using `U`, which turns away from the pipe that supplied the value, so it can distinguish
"reply from peripheral" from "slab flag from controller". Sound, and still loses on latency.)

**Everything else at the grid level is measured out:**
- `--proved-only` (equiv-gated) yields ZERO **by construction**: it only accepts transforms that
  preserve every man's path length exactly, and merging or deleting a line always changes one.
  With 0 dead cells, 0 blank rows and 0 blank columns there is nothing left it can take.
- Vertical row packing: **ZERO** consecutive row pairs have disjoint spans, so an order-preserving
  merge cannot fire even once; the order-free bound is still 659/740 = 1.12x.
- Relocatable blocks: the longest run holding no position-bound op (`s S r R q U`) is **13 rows**,
  1.7% of the height.
- Rooms 24/25 are each ONE 13x36 room with 16 wall pipes under an intra-room Voronoi -- not eight
  stackable units. Ceiling 1.04-1.08x, and they cannot move into the free width because the
  shortest connecting pipe is 17 cells (~15 columns of slack).
- Deleting the 28 empty columns at x261..288 silently REBINDS ops at x247..260 from port 236 to
  port 285, and buys zero box anyway since height binds.

**And there is still no generator** -- decisively: the champion is a DIFFERENT ARCHITECTURE from
every builder in the repo (25 men vs 6-7; `d`/`m`/`b` 46/46/34 vs 2/4/4 for BP-driven bank
addressing; 24 `*`; 2 `S`; two 8-bank RAM ladders driven by 20 parked bank-cell men). Writing an
emitter means re-deriving the whole banked-RAM interpreter from the grid -- days, to arrive back
where we already are.

Local baseline for anyone continuing: 14/14, box 628,849, avgTicks 4,693,220.5,
local 2,951,327,018,204.5. A full `grade_fast --jobs 8` takes ~3 minutes, so grading is
affordable here -- the equiv-only gate was never the constraint.

### LLM squaring: WIDTH IS FREE UP TO 793 — the two moves only pay TOGETHER (2026-07-27)

Champion is 356x793: **height binds**, so width is free all the way to 793 and NARROWING THE
PORT BAND BY ITSELF BUYS NOTHING (it costs rows, since narrower lanes mean more wraps).
Measured: controller attachments occupy columns 52,55,113,182,186,230,236,285,295,305,311,315
= a **264-column span**, which is what drags each row out to ~318 columns wide while holding a
median of just **13 glyphs**.

    today                              356 x 793  box 628,849   1.00x
    2-column fold alone                714 x 397  box 509,796   1.23x   (width becomes binder)
    compress port band alone          ~250 x 793+ box >=628,849 <=1.00x  (pointless alone)
    FOLD + compress each band to <=198 396 x 397  box 157,609   **4.0x**  -> ~785e9

Port span only has to fall 264 -> 198, a 1.33x compression.

**Why the naive geometric fold is NOT buildable:** Voronoi binding is Manhattan distance to the
attach cell, so code relocated to columns 400+ silently REBINDS to whatever pipe is nearest.
Each column band therefore needs its OWN ports => two rooms => **two men**, because a man cannot
cross a room wall. That is the *balanced two-controller cut*, already proven feasible in this
repo on pathfinder (`ddc9c18`, `solutions/pathfinder/plan_bitset5_modular.py`).

Fallback if the cut is unbuildable: the plain 2-column fold is a known-safe 1.23x.

### LLM: OUR TICKS NOW BEAT THE LEADER'S — the whole gap is AIR (2026-07-27)

Champion `solutions/little-little-man/live-2b320f4f.man`, **356x793**, box 628,849, server
3,132,597,346,528 at 28/28.

    ours    box 628,849   avgTicks 4,981,478
    leader  box  37,249   avgTicks 5,509,238   (193x193, recovered by tools/leaderbox.py)

**We are 1.11x FASTER on ticks and 16.9x BIGGER on box.** There is nothing left to win on
execution; every remaining point is packing. Note this reverses the previous champion's shape:
045a959c was 428x735 with 11.0M ticks, so the last LLM win traded box UP 1.16x for ticks DOWN
2.21x. Do not repeat that trade — ticks are now spent.

The grid holds **16,800 content cells in a 356x793 area = 6.0% DENSITY**. 94% of it is air.
What that content would score if repacked, at our CURRENT tick count:

    60% density -> 167x167 ->  139e9   (BEATS the 205e9 leader)
    40% density -> 204x204 ->  207e9   (ties it)
    30% density -> 236x236 ->  277e9
    20% density -> 289x289 ->  416e9
    10% density -> 409x409 ->  833e9   (still a 3.8x on today)

Even a 10% density target — under twice today's — is a 3.8x. Sanity check on the cheap version:
splitting the ribbon into 2 side-by-side columns gives 712x397, box 506,944, a 1.24x for free;
3 columns is WORSE (width becomes the binder at 1068). Squaring alone is not enough — the win
is DENSITY.

Two blockers, both real:
- **No generator for the champion exists in any of 23 worktrees** (re-verified 2026-07-27). The
  smallest regenerable build is 1137x277. Rebuilding an emitter that can reproduce the champion
  is the prerequisite for any packing work.
- 289 of 688 controller rows in the *previous* champion were WRAP/continuation rows (42%), and
  op rows averaged 20 ops over a 101-column span inside a 387-column room. Re-measure on the new
  build before designing.

### LLLM is the OPPOSITE of LLM — density alone will NOT get there (2026-07-27)

Champion `solutions/little-little-little-man/live-8e907387.man`, **142x141**, box 20,164,
server 6,283,423,104 at 21/21, avgTicks 311,616, 5,952 content cells = **29.7% density**.

It is already square and already 5x denser than LLM's 6.0%, so there is far less air to
reclaim. Repacking at our CURRENT tick count:

    60% density ->  99x99  -> 3.05e9      leader is 926,759,894 -- still 3.3x off
    50% density -> 109x109 -> 3.70e9
    40% density -> 121x121 -> 4.56e9

So unlike LLM (where 40% density alone ties the leader), **LLLM needs BOTH ~60% density AND
~3x on ticks**. Leader box is ambiguous — candidate sides 29/58/87/174 — but 58x58 (box 3,364,
ticks 275,493) fits the board-wide pattern best: a large box gap with a tick gap near 1.
174x174 can be dismissed; it would mean they out-compute us 10x, which no other problem shows.

**Priority: LLM before LLLM.** LLM is worth 0.16 and is a pure packing problem with our ticks
already ahead; LLLM is worth 0.12 and needs a tick breakthrough on top of a packing one.

### Brackets is at BOTH fixpoints — stop optimising it (2026-07-27)

15x15, box 225, 86.2% density, server 97,719 at 26/26, 1.8x off the leader. Two independent
exhaustion proofs, so its remaining gap is an ALGORITHM difference, not something our tooling
can find:

- **Geometry:** `tools/shrink.py` runs every pass (dce, stairfold, reroute, fold, polish,
  roomfit) to a fixpoint and accepts nothing.
- **Ops:** `tools/peep.py` (superoptimizer, depth-4 table of 61,988 behaviours over a 917-state
  verification set) reports `NOTHING TO DO — every register-op run is already as short as the
  superoptimizer can prove`. Of 64 instruction cells only **9** are even rewritable: 4 are
  refused as multi-heading, 4 as branching, 22 as non-register.

That last line is the general lesson about `peep.py`: on a hand-folded champion almost every
cell is a turn, a branch or a pipe op, so the superoptimizer has nearly nothing to chew on.
It is worth a 3-minute run on any problem where the box is finished and the gap is pure ticks,
but do not expect it to rescue a dense grid.

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
- **Snake `build_fold*` box floor is 5,329 = 73² and it is WIDTH-bound** (measured 2026-07-27).
  width = CW + 21, and *both* terms are on their floor: the 21-column east strip is 18 display +
  3 routing (SWAP descent, DATA descent, DATA's east-turn cell — 2 cannot do it, the SWAP descent
  occupies the only column DATA could turn into), and **CW < 53 is real**: a 1.1M-sample hunt at
  CW=52/51 found configs that build and pass, but every one costs 12–17 extra controller rows
  (box 6,889–7,744). `shrink.py` mechanically folds one column, so 74→73 and no further. Height
  is now 69 with 4 rows of pure slack: **row cuts are worth zero on snake's box, only on ticks.**
- **Re-attaching snake's `r:I` off the single ATT row does NOT pay.** Moving the input attach to
  column 32–33, between the state and body lanes, does what it promises — SPAWN 8→4 rows, INIT
  9→7, its 15 wraps →8 — but it narrows `r:S` from 1..33 to 1..28 and shifts `r:B` to 41..51, and
  the hot blocks pay it all back: DISPATCH +1, TICK +1, NOEAT +2, EAT +1, DIR +2. Net **62 → 63
  controller rows**, i.e. worse. Left/bottom-wall attachment is worse still: with a 62-row
  controller the y-term dominates, so any off-ATT attachment wins a huge pocket of rows next to
  that wall and steals them from `r:S` on every row.
- **Snake knob searches are silently wrong unless gated on generality.** A graded search on the
  5 public cases reached 39.9M (74×70) — and 49/386 on the fuzz, *every* failure a north/west
  death. Cause: the three death highways share one row and the deepest entrant walks east over
  the others' pops, so moving `D_HY`/`D_HX` one column apart lets a pop group spill past the next
  entry arrow. `build_fold3.py` now replays each highway's walk and counts the `r` cells it steps
  on (exact, not a spacing heuristic). Gate every snake search on `tests/snake-sentinel.json`
  (24 cases, 0.5 s); `tests/snake-{mini,stress}.json` are the 60- and 106-case versions.
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

**Two independent confirmations, 2026-07-27: DELETING A PIPE PAIR is the highest-leverage
single move in this repo — WHEN the lanes are narrow.** Snake `847787f` deleted the scratch
ring: box 24,964 -> 13,689 AND ticks 18,482 -> 12,733, **2.6x from one deletion**. Pathfinder's
`one-ring` deleted the NB pair the same day: local **47.5B -> 34.1B, 1.39x**. The mechanism is
`LANE WIDTH = ROOM WIDTH / PIPES IN THAT DIRECTION, AND LANE WIDTH SETS HEIGHT` — every
controller pipe attaching to one wall row throws the Manhattan y-term away, so binding is by
column, and a token that cannot reach its lane on the current row forces a WRAP = a whole row.

**But CHECK THE LANE WIDTH FIRST — it does not always apply.** Measured the same day: LLM's
controller has 5 incoming + 7 outgoing pipes (our most), yet its lanes are already **85 and 61
columns** wide. Deleting a pair there buys 1.26x of lane and *nothing* of height, because LLM's
width is inert (282 -> 882 left height at EXACTLY 1137 — wraps are a function of token ORDER,
not spacing). Snake's lanes were 5 columns; that is why it paid 2.6x. Rule: count the pipes,
then divide. Narrow lanes (single digits) => delete a pair. Wide lanes (tens of columns) =>
the height is coming from somewhere else, and for a compiled CFG that is BRANCH-LANDING
GEOMETRY (LLM: 98 `br` x 3 rows = 294 rows, more than the leader's entire 193-row grid).

**Pathfinder's 2026-07-27 ladder, 240B -> 28.1B local (8.5x), is the model to copy — and NOT
ONE STEP IS AN ALGORITHM CHANGE**: compact ports 240B->74.3B (3.2x), fold apron ->55.4B,
widen frontier sideways ->50.4B, retune compact ports ->47.5B, delete NB pipe pair ->34.1B
(1.39x), square + retune four lanes ->28.1B. All six are port/lane/pipe geometry. This is
exactly what `tools/leaderbox.py` predicts from the leaders' scores: every tick gap on the
board is 1.5-2.6x and every box gap is larger. **Nobody is out-computing us; they out-pack us.**



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

- **The local:server RATIO IS PER-BUILD, so a local win can be a server loss.** Measured
  2026-07-27 on LLLM: `lane3-178x220` scores **14.16e9 local vs the live `polish-203x200`'s
  20.33e9 — a 1.44x WIN** on all 10 public cases, and on the server it returned
  **15.09e9 against the live 6.28e9, a 2.40x LOSS** (21/21, nothing broken). The ratios:
  polish server/local = **0.309**, lane3 = **1.066**. LLLM's 11 private cases are far cheaper
  than its public ones *for polish* and are not for lane3 — a 3.45x relative penalty. This is
  NOT the stale-baseline mistake (the comparison was like-for-like on one case set); it is
  that public ticks do not predict private ticks ACROSS ARCHITECTURES. So: a local improvement
  over a build with a DIFFERENT structure is a hypothesis, not a result. Comparing two
  variants of the same design is still sound. Submit to find out — it never lowers a score.

- **Private cases exist** (~2–3× the public count; the per-problem API reports 0 — trust
  `status.py`'s `cases` column). You need ≥1 private pass to score at all, so never hardcode
  public answers, and stress the shape of the input, not the values.
- A local 6/6 has repeatedly meant 20/20 on the server — but a *generality* bug (fixed n,
  assumed non-empty, assumed positive) shows up only as a private failure.
- Long/thin grids are the #1 score leak: a 69×130 grid is scored as 130² even though half
  the box is empty air.

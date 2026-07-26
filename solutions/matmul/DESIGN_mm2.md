# matmul "mm2" — 6-man pipelined MAC engine (replaces opt5's 1-man 4-ring machine)

## Why opt5 is 63 ticks/MAC
`matmul-opt5.man` runs ONE man through MAIN-read → classify → MAC → return, so every
per-MAC op is *serial*: 18 ops + ~45 glide/turn ticks. Two structural taxes:
* **the accumulator and `a` both want register B**, so a single man must round-trip `a`
  through the H1 ring (`r H1r; s H1f` = 2 ops/MAC) and reload the accumulator every MAC;
* **classify costs 8 ops** (`` `100` ``=5 cells, `N`, `+`, `X`) to tell a real `b` from a
  MARK, and the two lanes sit far apart so each MAC pays two long corridor glides.

## mm2: split the MAC across two men so the ops overlap
`C[i][j] += A[i][m]*B[m][j]`, iterated (i, m, j) with j innermost — so `a=A[i][m]` is
constant for K MACs and B is replayed N times while A is drained once.

| man | body (per MAC) | ops |
|---|---|---|
| **MUL** | `r_br` `M` `s_bf` `r_ar` `*` `s_pp` | 6, **branch-free** |
| **ACC** | `r_cr` `X` `M` `r_pp` `+` `s_cf` | 6, X is a ring corner |

Both bodies are laid on a **closed rectangular racetrack whose every non-corner cell is
an op** — walk tax is 4 corner ticks per lap, amortised by unrolling U MACs per lap
(`ticks/MAC = 6 + 4/U`). MUL is branch-free so U is unlimited; ACC's `X` must sit on a
corner, so U ≤ 4 (one X per corner).

### Storage (values live in pipes, not in men)
* **A queue** `MUL → AF(long) → AREL → AR → MUL`, drained once. Holds `1 + N*M ≤ 257`.
* **B ring** `MUL → BF(long) → BREL → BR → MUL`, replayed N times. Holds `M*K ≤ 256`.
* **ACC ring** `ACC → CF → CREL → CR → ACC`, holds `[acc_0..acc_{K-1}, SENT]`.

### How the control flow costs (almost) nothing
* **No `a` counter in MUL.** AREL emits each `a` **K times** (`s;m;d` loop, K in its B
  register, taken from the first value in the A queue). MUL therefore does a plain
  `r_ar` every MAC and needs no branch at all — that is what makes it unrollable.
* **No group counter in ACC.** CREL holds M in B, counts SENT crossings, and pokes a
  1-value TOK pipe when a row is finished. ACC only does `q`/`d` on the sentinel lap.
* Accumulators are stored **+OFF (200000)** so `X` alone separates a live accumulator
  (positive) from `SENT = -1`; OFF is stripped by a dedicated SUB man holding `-OFF`
  in B forever (`r; +; s_O` — 3 ops).
* `M*K` is computed by **ACC** (which is handed M and K over the product pipe) and sent
  back to MUL on a 2-cell pipe — avoids a `B`-clobber scratch round trip in MUL.

### Nearest-pipe discipline
Every pipe of a room attaches to that room's **top wall**, so `r`/`s` targeting is a
pure *column* comparison (the row term is common). MUL: `BR@2 BF@4 AR@4 PP@2` tight
around a 5-wide racetrack, with `AF@10 IN@12 MK@14` far enough away that no hot-loop
cell can mis-resolve.

## Costing (case 3 = 16x16x16, 4096 MACs, 74% of avgTicks)
| variant | ticks/MAC | case3 | est. server score |
|---|---|---|---|
| opt5 (live) | 63 | 260k | 230.1M |
| mm2 U=1 (minimal racetracks) | ~12 | ~55k | ~22M |
| mm2 U=2..4 (unrolled) | ~7 | ~34k | ~13M |

Floor for the shape: case 3 needs 515 input ticks + 256 output ticks, so ~800 ticks is
the hard bound — mm2 at U=4 is still 40x off it, i.e. there is headroom beyond this.

---

## The blocker I hit, and the technique that solves it (verified on paper, not built)

Every room in mm2 needs 2+ pipes per direction, and `r`/`s`/`q` lock onto the **nearest**
pipe (Manhattan to the attachment cell outside the wall, reading-order ties). A compact
racetrack puts all its ops within ~5 cells of each other, so two same-direction pipes on
the *same* wall differ by only 1–2 in distance and every op cell has to be checked by
hand. That hand-checking is what stalled the build.

**The rule that makes it mechanical — pair same-direction pipes on OPPOSITE walls at
matching offsets.** Then one coordinate decides, with a margin that does not depend on
where in the racetrack the op sits:

* `BF2` on the **top** wall at column *a*, `PP` on the **bottom** wall at column *a*:
  for any cell `(x,y)` both distances share the `|x-a|` term, so the **row** alone picks
  the pipe. Every op on the ring's upper row resolves to BF2, every op on the lower row
  resolves to PP — for *all* x.
* `BR` on the **left** wall at row *r*, `AR` on the **right** wall at row *r*: both share
  `|y-r|`, so the **column** alone picks the pipe (left half → BR, right half → AR).
  Avoid the exact tie column (`x` where `x - x_left = x_right - x`).

### MUL, fully resolved under that rule (room cols 0..7, rows 1..7)
Pipes: `BR` left@row 4 (in), `AR` right@row 4 (in), `BF2` top@col 4 (out), `PP` bottom@col 4 (out).
MAC ring = 10-cell racetrack, cols 2..6, rows 4..5, clockwise:

| ring index | cell | glyph | why it resolves |
|---|---|---|---|
| 9 | (2,5) | `d` | corner: BP>0 turns CW→north = continue; straight→west = exit to group entry |
| 0 | (2,4) | `>` | corner |
| 1 | (3,4) | `r` **BR** | col 3 → left half |
| 2 | (4,4) | `s` **BF2** | row 4 → top wall |
| 3 | (5,4) | `*` | `a` is parked in B and `*` preserves B |
| 4 | (6,4) | `v` | corner |
| 5 | (6,5) | `<` | corner |
| 6 | (5,5) | `s` **PP** | row 5 → bottom wall |
| 7 | (4,5) | `m` | BP-- |
| 8 | (3,5) | `.` | spare |

10 ticks/MAC at U=1. Group entry (`r`AR=K, `b`, `r`AR=a, `M`) hangs off the `d` exit and
costs ~14 ticks per group of K, i.e. ~9% on case 3.

**Storage must sit on the leg that both phases traverse.** The B ring is
`MUL → BF2(short) → BREL → BR(**long, 260**) → MUL`, and SPLIT injects into BREL on a
second short pipe (BREL reads with `R`). Putting the long leg *after* the relay is what
lets one 260-cell serpentine serve both the seeding fill and the run-time ring — the
naive `MUL → BF(long) → BREL` version needs *two* long pipes and does not fit.

Likewise `SPLIT → AF(**long, 260**) → AREL → AR(short) → MUL`, because AREL is the
K-duplicator and the queue must back up *upstream* of it.

### Room split that keeps every room wireable
`I → LOAD → SPLIT → {AF, BF1, H}`; LOAD has exactly 1 in / 1 out (zero ambiguity) and
needs **no B counter** — it forwards `[M, N*M, K]` then A then B and simply blocks on a
dry input pipe forever. SPLIT owns the single `N*M` countdown that separates A from B.

## Status: NOT BUILT
No `.man` was produced and nothing was submitted; `matmul-opt5.man` (server 230,073,151)
remains the champion. The design above is complete enough to implement directly — MUL is
fully resolved, the other five rooms need the same opposite-wall pairing applied.

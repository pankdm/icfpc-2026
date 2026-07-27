# little-little-little-man (LLLM) — FULL SOLVE, server 21/21 cases pass

Interpret an arbitrary LLLM program and render its 16×16 state each round.

## Result
- **FULL SOLVE: server 21/21 cases pass** (submission id `23300081-a1fa-4529-af4b-0d27ee681c40`,
  score `10959422687040`). First complete solve for this problem.
- All 10 public cases pass under the 15M tick cap (max: `around the block` 16×16 at 12.4M ticks;
  `first steps` 393k). Generic interpreter (validated on 420 random programs).

## Architecture (all validated on the real oracle)
1. **Generic interpreter op-stream** (`lllm_build.py`): two-belt C-model, fully **branchless**
   per-tick update, branchless ascii→(op,color) decode, `[addr+1,color,−1(SWAP)]` display stream.
   Frame-exact on all 10 public + 420 random programs in a faithful VM (`vm.py`), under the tick
   cap by VM-op count. Multi-digit constants despined to digit-arithmetic (`a·b`, `a·b+c` via a
   `kbuild` scratch slot) — inline backticks are unsafe (loader pairs them vertically).
2. **Op-stream → grid placer** (`lllm_layout.py`): boustrophedon in a state "home band";
   cells/input/output/cmd as nearest-**column** excursions; cells-heavy loops auto-run in a
   separate cells region so `rc/sc` stay ~1 cell. Back-edge rails for BPLOOP(`m;d`),
   LOOPX(belt-counter `X`), nested loops, and FOREVER — all oracle-validated in isolation
   (m1..m3 + nesting proofs). Display via `driver16.py` (16×16 driver, oracle-proven).
3. **Belts**: straight vertical pipes with batched relays (`r s r s …`) below the gate — state
   short+narrow (low latency), cells long+wide (throughput; cap ≥3·256=768). Capacity = pipe
   length (one value per cell), so the belt must physically hold every circulating slot.

## Files
- `lllm_build.py` — interpreter op-stream assembler (31-slot C-model ring).
- `lllm_layout.py` — op-stream → `.man` placer (two regions, excursions, loop rails, belts, driver).
- `lllm.man` — the SUBMITTED program (server 17/21).
- `vm.py` — faithful op-stream VM; `sim.py` — reference LLLM simulator; `lllm_fuzz.py` — fuzzer.
- `driver16.py` (+ proof), `m1/m2/m3_*` proofs, `lllm_oracle.js` — oracle runner for synthetic cases.

## How the tick cap was met
`EQ`/`GT0` were rewritten register-based (inline-built constant 63, a single scratch slot)
instead of hammering scratch slots with consecutive same-slot accesses (each a full belt
revolution): ~15 belt accesses per EQ → ~4. This cut the op count ~42% (around-the-block
18.75M→12.4M real ticks) and the footprint box 4.56M→2.16M. Further score optimization (ring
ordering, smaller ring) is possible but the solve is complete.

---

## v2 (2026-07-26): op-stream rewrite

Champion: `v2b-215x221.man` — **server 21/21, score 29,308,872,425**
(submission `00ac26d8-f880-4ed2-81d8-fbf45e339344`), from a previous live 168.89B.
Sources: `lllm_build2.py` (op stream) + `build2_man.py` (floorplan), both required
to reproduce it. `lllm_layout.py` supplies the boustrophedon placer unchanged.

| | v1 (`reflow3`) | v2b |
|---|---|---|
| emitted ops | 29,546 | 4,589 |
| belt accesses / input char (`fill`) | 281 | ~22 |
| avg VM ops | 2,296,150 | 173,388 |
| box | 54,756 | 48,841 |
| oracle avgTicks | 3,640,511 | 543,041 |
| server score | 224.15B | 29.31B |

### Where the remaining ticks are (`phases2.py`, dynamic VM ops)

    step 54%   fill 30%   fetch 12%   render 1.5%   other 2.4%

`step` is ~55 belt accesses per emulated LLLM tick. It is branchless, so every
one of the twelve op classes is evaluated and blended on every tick; with only
A/B as registers each three-operand expression costs ~4 accesses. **Real control
flow (a dispatch tree on the class, so only the taken arm runs) is the next
order-of-magnitude lever, and it needs a branch primitive the boustrophedon
placer does not have** — `X`/`d`/`a` are only emitted as loop back-edges today.

### Measured dead ends (do not redo)

* **Ring reordering on v1**: 29,546 → 25,740 ops (13%) and converged. The access
  sequence is near-random over 30 slots. Worth 14% on v2's 20-slot ring.
* **Narrowing the code band** to shorten pipe excursions: `gw` 215 → 160 makes
  ticks slightly *worse* (558k → 565k) as well as the box. Excursion walking is
  not the tick driver.
* **Two Y-forked relay men in two disjoint rings**: grades 8/10 with wrong frames,
  because both belts are FIFOs whose value order *is* the state-slot mapping and
  the program array. It also gives **no speedup** — the 549k → 258k it appeared
  to produce was `avgTicks` averaged over only the 8 *passing* cases, which
  excluded the two 1.69M-tick heavies. Verified: mean of those 8 = 255,120.
* **More relay stations**: 6 → 60 is worth ~1%. One relay man tops out at
  `(2s+2)/(4s+9)` < 0.5 values/tick, which is exactly what the main man's `r`,`s`
  rotation demands, so the belt is balanced and not the bottleneck.
* **`tools/reflow.py fold`** is hardcoded to v1's row numbers and cannot reflow
  anything else.

### Traps this rewrite hit (all invisible except through the loader)

* A multi-digit `('#', k)` is despined by the placer into `d M d *`, which
  **clobbers B**. Every constant must be built from single digits; `bigK` uses an
  octal chain. The whole design depends on B surviving belt rotations.
* `BP` is one register: a nested `BPLOOP` destroys the outer counter, so the
  fill's row loop must be an `X` back-edge (`LOOPX`).
* A belt fold leg that touches the relay room's wall parses as a fresh pipe
  endpoint → `pipe self-loop`. Every fold needs a two-cell tail clear of the
  boustrophedon before the relay room.
* Overlapping folds overwrite silently (`build2_man.py` installs a strict `put`).
* `wrap()` writes at `BR+1`, so the code band must stop at `GW-4`.
* On a westward relay row the `r` must sit at the *higher* column, or the man
  `s`es a stale A into the belt and the main man later dies on a wall.
* The driver's SWAP pipe needs 3 rows above the driver room; at `SOUTH+1` it is
  drawn inside the code room.


---

## v3/v4/v5 (2026-07-26): dense placer + delta fetch

Champion: `v5-142x142.man` -- **server 21/21, score 6,283,423,104**
(submission `8e907387-fe3b-4972-8d32-7e0f3d0ef85b`), from a live 22,459,642,837.
Sources: `lllm_build5.py` (op stream) + `build3_man.py` (placer + floorplan).

    cd s4 && python3 solutions/little-little-little-man/build3_man.py \
        solutions/little-little-little-man/v5-142x142.man --stream lllm_build5 \
        --gw 142 --drv-h 12 --drv-entry 4 --drv-gap 14 --drv-swap-tail 3 \
        --cell-legs 5 --cell-h 26 --state-relay 16 \
        --pinp 2 --pcin 8 --pcout 18 --pcmd 31 --psout 64 --psin 69

| | v2b | v3 | v4 | v5 |
|---|---|---|---|---|
| emitted ops | 4,589 | 4,589 | 4,716 | 4,475 |
| code rows | 160 | 109 | 104 | 99 |
| box | 48,841 | 24,025 | 21,316 | 20,164 |
| oracle avgTicks | 543,041 | 420,929 | 287,586 | 285,128 |
| local score | 26.52B | 10.11B | 6.13B | 5.75B |
| **server** | 29.31B | **11.12B** | **6.70B** | **6.28B** |

### What changed

1. **`build3_man.py` replaces `lllm_layout.py`.**  Nearest-pipe Voronoi bands
   instead of home-band + excursions (a pipe op costs zero extra rows instead of
   three), one-row alternating newlines, and loop back-edges on depth-indexed
   rail columns west of the op area (entry <=1 row, the `d`/`X` tail 2).
2. **Delta fetch** (`lllm_build4.py`).  See the commit; the enabling trick is
   that `sc` does not touch A, so `BPLOOP{rc sc}` leaves the last value read in
   A and a count of `((delta-1) mod N)+1` is both the right rotation and a legal
   (>=1) trip count.
3. **One static render** (`lllm_build5.py`): render at the TOP of the round.

### Measured dead ends (v3+)

* **Fanning the six ports out from a twelve-column cluster** to their real
  targets gives a better box (21,316 at the time) and costs **5.5x in ticks**
  (543k -> 2.98M): the state ring holds only twenty values, so it is
  LATENCY-bound, and the fan-out made it 230 cells long.  Every component must
  sit directly below its own port.  The cells ring is not affected -- it holds
  256 values in ~294 cells and is throughput-bound.
* **Splitting the cold ports east/west** (cold `r` at one end, cold `s` at the
  other) halves the cold-op newline tax, but it is geometrically impossible: a
  planar fan-out needs the targets in the same left-to-right order as the ports,
  and that always separates a belt's two pipes.
* **Widening the `ri` band** by putting INP east of CIN saves ~9k ticks and
  costs ~10% of the box.  Net worse, twice (v2 and v4 streams).
* **Unrolling the fetch loop** to amortise its ~12-tick rail walk over u
  rotations: the split needs `count = u*q + r` with `q,r >= 1`, so any
  `count <= u` has to borrow a full extra revolution (rotations are mod N).
  `delta = +1` (walk east) has `count = 1`, which pushes the average rotation
  count 128 -> 192 and eats the whole saving.
* **Adding `|` (124) to the character hash**, so the left/right border cells
  could go through the ordinary interior decode and `mid_row` become one uniform
  loop: no two-stage hash `((asc*m1)>>s1*m2)>>s2 & 15` exists that separates it
  (`scratchpad/lllm_hash.py`, exhaustive over digit-product multipliers).
  `+` and `-` are ambiguous by position anyway, so the top/bottom border rows
  would still need their own loop.
* **`cell-h 24`** (cells belt 254 cells) fails `around the block`: the ring must
  hold all W*H = 256 values.
* **`--drv-dy 3`** puts the driver's SWAP bulge inside the code room and fails
  every case; its three rows above the driver room are load-bearing.

### Where the ticks are now (285k, from the VM's 172k ops)

`step` 53%, `fill` 32%, `fetch` 10% by VM op count -- but by real ticks the
fetch loop is ~27%, because its three-op body pays a ~12-tick rail walk on every
one of the ~6,000 rotations a case does.  The next order of magnitude is still
the one the v2 agent named: a **dispatch tree on the cell class**, so `step`
stops evaluating all twelve cases branchlessly.  `build3_man.py` already has the
`X`/`d` rail machinery; what it lacks is a general (non-back-edge) branch, which
is what `s4/tools/railflow.py` provides for a `flowgrid.Flow`.

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

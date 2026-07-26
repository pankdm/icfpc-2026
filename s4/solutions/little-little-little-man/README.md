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

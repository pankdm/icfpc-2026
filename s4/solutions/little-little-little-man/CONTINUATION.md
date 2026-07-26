# LLLM layout build — continuation state

The generic interpreter is DONE and validated (see README). Remaining: compile
`lllm_build.build()`'s op-stream into a `.man`. This file is the precise state of that build.

## Oracle-validated milestones (run via `node lllm_oracle.js <man> <case.json>`)
- **Display driver (16×16): PASS** — `driver16-proof.man` + `driver16-case.json`. Command
  protocol `[addr+1, color, …, −1(SWAP)]` → ADDR/DATA/SWAP, one red pixel commits correctly.
  Built by `driver16.py` (adapt the driver room WIDTH to the display, else the SWAP bulge lands
  inside the room → load error).
- **State belt + column-discipline pipe selection + output: PASS** — `m1-belt-proof.man` +
  `m1-belt-case.json` (built by `m1_belt_proof.py`). Pushes 5,7 to a relay belt, reads them
  back FIFO, outputs `[5,7]`. Proves: a relay (`@ > r … s … v` / `< … ^` junction) + two
  non-crossing vertical pipes (belt-out@col, belt-in@col+2), and that an `s` at the state
  column hits belt-out while an `s` excursion to the output column hits the output pipe.

### Relay gadget (working, from m1_belt_proof.py)
```
row ry  : @(j0) >(j0+1) ... r(col_out) ... s(col_in) ... v(endc)
row ry+1: ^(j0+1) ...................................... <(endc)
belt-out pipe: [(col_out, SOUTH), (col_out, RWALL-1)]   # gate wall -> relay top
belt-in  pipe: [(col_in,  RWALL-1), (col_in,  SOUTH)]   # relay top -> gate wall
```
(`SOUTH` = row just below the gate's south wall; `RWALL` = relay top-wall row = SOUTH+3.)
The `^`→`>` junction is REQUIRED: a bare `@` at the loop top lets the man walk north into the
wall (that was the first m1 crash).

## Known issue to fix next (M2 — two belts coexisting)
`m2.py` puts a STATE relay + a CELLS relay + an OUTPUT room and gets a load error
("pipe ends without reaching another room") ONLY when all three coexist — each pair loads fine
in isolation. Likely a pipe/room adjacency or attach-cell conflict between the three south-wall
groups; bisect by depth-staggering the three relays/rooms to distinct row bands so their pipes
can't be mis-attributed. Column discipline itself is sound (m1 proves it).

## Remaining build steps (in order, oracle-test each)
1. **M2**: fix two-belt coexistence (state belt r/s + cells belt rc/sc via a second column
   region far from state so nearest-pipe is unambiguous; suggested cols: input@0, cells-out@12,
   cells-in@14, cmd/out region, state-out@50, state-in@52).
2. **M3**: one counting loop with a back-edge rail — `b`/`m`/`d` (BP loop) and `dec+X` (belt
   counter). Then nest two (FOREVER ⊃ LOOPX ⊃ BPLOOP) on dedicated side rail columns.
3. **General op-placer**: walk `lllm_build.build()`'s op list. Home band = state region;
   `rc/sc`→cells excursion, `ri`→input excursion, `cmd`→cmd excursion (to the driver16 pipe).
   Boustrophedon rows; place each op at a column where its intended pipe is nearest; wrap a row
   when the next op's column would require going backward. Non-pipe ops (M,+,-,*,/,},N,digits)
   go anywhere. Loop nodes emit rails per M3.
4. **Despine constants**: replace `('#',k)` k≥10 with digit-arith (e.g. 63→`9 M 7 *`,
   16→`2 M 8 *`); the tick's multi-digit constants (63,16,10) all factor as a·b, so cheap and
   backtick-free (inline backticks are unsafe — the loader pairs backticks VERTICALLY per
   column and would enclose ops → "non-digit in literal"). Fill's ascii constants use a·b+c
   with a scratch slot.
5. **Validate**: `node tools/grade.js little-little-little-man <man>` (public) + `lllm_oracle.js`
   against fuzzed cases generated from `sim.py`. Then submit.

## Tick budget
VM tick counts (1 op = 1 tick) are ≤9.0M on the two heavy cases; the 15M cap leaves ~1.6×
headroom, so the layout must keep belt-rotation runs ~1 cell/op (home-band, not per-op jogs).

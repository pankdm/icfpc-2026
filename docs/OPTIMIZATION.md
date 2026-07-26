# Optimization playbook — tools, order of attack, gates

For any agent picking up a solved problem to make it score lower. Score =
`max(w,h)^2 * avgTicks`. Everything here exists on `main`; measured wins from
2026-07-26: LLLM 10.91T→261.1B (reflow), Snake 685.1B→73.4B (generator-side),
gradebook 771M (walkfold, earlier). Companion doc: `docs/reflow-lessons.md`
(the pipe-band theory + traps; read it before ANY geometry transform).

## 0. Ground rules

- Baseline from the SERVER, not your branch: `python3 tools/ours.py` (points,
  gap) and `python3 tools/submissions.py --match` (live box/ticks per problem,
  needs `~/.icfpc-cookie`). Local .man files have repeatedly been stale.
- Work in your own worktree off `main`; never touch another checkout's tree.
- Grade with the Rust engine: `python3 tools/grade_fast.py <slug> <file>
  --jobs 4`. The wasm oracle OOMs on heavy runs (`Go program has already
  exited`). If `interp/target/release/lm` is missing, copy it from another
  worktree (e.g. `icfpc-2026-lllm`) — sources are identical, cargo isn't
  installed. Before SUBMITTING, spot-check one case wasm-vs-rust tick-exact:
  `node tools/grade_json.js <slug> <file> --case N`.
- Commit before submitting (git is the only copy of submitted programs), then
  `python3 tools/submit.py <slug> <file>` — it archives the exact bytes under
  `submitted/` and polls the verdict. Submitting never lowers a score.
- Record results as you go: `tl note add <task-id> "<measured outcome>"`
  (see CLAUDE.local.md; negative results are worth recording too).

## 1. Diagnose before touching anything

```bash
python3 tools/grade_fast.py <slug> <champion>      # baseline pass/ticks/score
node sim/xray.js <slug> <champion>                 # BOX DRIVER, HEADROOM, CORRIDORS, dominant case
python3 tools/walkfold.py map <champion>           # rooms, pipe COLUMN BANDS, CFG size
```

Read the three numbers this gives you:
- **Which dimension drives the box** (only the larger one is squared) and how
  much slack the other has.
- **Critical man's tick split** (op/turn/glide/stall). Stall → RAM/pipe
  latency. Glide+turn → walking, i.e. layout spread. Op-dominated → you need
  an algorithm change, not geometry.
- **Hot pipe bands** (walkfold map). A hot pipe whose band is a small slice of
  the wall is the reflow signal — see `docs/reflow-lessons.md`.

## 2. Order of attack (measured yield per effort)

1. **Generated solution? Fix the generator, not the grid.** If a `build*.py`
   exists, geometry knobs there beat every post-hoc pass. For
   stateflow/flowgrid-based builds (Snake, Pathfinder public solver) the big
   levers, in the order they paid on Snake:
   - `code_x` — edge-lane spread; default 380 wastes ~320 blank columns that
     every CFG transfer walks twice. 60 works for a ~40-block flow (-77%).
   - `fast_cell_ram=True, cell_belts=8` + `fast_scalar_ram=True,
     scalar_belts=4` — banked split RAM instead of the recirculating belt
     (belt = ~120-tick average latency on EVERY load/store). Note the
     working/broken configs: scalar 32/4 works, 32/8 fails; cell 256/8 works,
     256/4 hangs.
   - `compact=True` — COMPACT_PORTS map + west→east component floor (walks
     max 250→155 cols, display feeds drop straight in). Another -20%.
   - `boustrophedon=True` — wrap shims become west-heading op rows (safe:
     X is entered heading south, const_ops has no backtick literals, bands
     are column-functions). Snake controller 294→260 rows, -30% score.
2. **Reflow (attachment-band floorplanning)** — `tools/reflow.py`, the LLLM
   41.9x. When walkfold `fuse` refuses because no in-band column assignment
   exists, the fix is moving the hot pipe's ATTACHMENT, not giving up.
3. **Connector passes for control-dense grids** — `stairfold.py` (flatten
   walk staircases), `reroute.py` (A* connector rip-up, empty-row objective):
   gradebook 771M→438M server. Use when blockify shows many branch states.
4. **walkfold passes** (`lift/pull/fuse/norm/squash`) — intra-room
   re-placement; gradebook -69% over its life. `squash` is the box win.
5. **place.py** — rigid room translation + pipe re-routing (the only placement
   move that can't change a man's walk). A few %.
6. **fold.py / polish.py / compact_man.py** — mechanical row/col deletion.
7. **autotune.py** — single-literal perturbation; read `tools/AUTOTUNE.md`.
   Wasted on hand-folded champions, useful on fresh builders.
8. **Algorithm rewrites** (bit-op classifiers, linked-list scans instead of
   full-range scans) — historically the biggest wins (1.5–2x) but manual;
   prototype in `scratchpad/` first.

What does NOT pay (measured zeros, don't redo): DCE on champions (0 dead
cells), instruction scheduling to cut stalls (steady-state stallers aren't the
bottleneck), peephole shortening without re-laying the path.

## 3. Gates — every one is load-bearing

A transform is submit-ready only when ALL hold:
1. Same pass/fail SET as baseline on the Rust engine, score strictly lower.
2. Executed op sequence identical (or `tools/equiv.py` certificate where the
   transform is path-length-neutral). The grade gate alone is NOT safety for
   op-cell edits: a register-level-wrong rewrite once passed all public cases.
3. Pipe bindings preserved — every `r/s/q` binds to the same logical pipe
   (`tools/pipecheck.py`; compare keyed by `(src,dst,len)`, indices renumber).
4. Pipe lengths not shortened (length = latency AND capacity; a "too short"
   FIFO pipe fails only under load, i.e. only on private cases).
5. Reading order of each room's incoming pipes unchanged (`R`/`U` semantics);
   for displays: sa top, sd west, ss bottom — the loader REJECTS right-wall
   display pipes, and attachment reading order is the addr/data/scroll roles.
6. Generality sanity: n=1, empty, negatives, max size, multiple rounds —
   private cases are ~2-3x the public count and punish shape assumptions.

## 4. Layout micro-rules that bite (all verified)

- A pipe running ALONGSIDE a room wall (distance 1, multiple cells) reads as
  attached and steals that room's `s`/`r`. Keep a gap column/row; endpoints
  touching the wall are fine (that's what an attachment is).
- Two different pipes may touch orthogonally (glyph direction disambiguates —
  the classic scratch echo has adjacent in/out pipes) but never share a cell.
- A pipe's last cell must be an arrowhead pointing at the destination wall.
- Port/op column bands are Voronoi cells among same-direction ports; ops walk
  east within a row, so order port columns to match the common op SEQUENCES
  (e.g. sa before sd made display writes single-row… until routing forced the
  swap back — check both directions of that trade).
- Backtick literals are rigid (both axes, reversed westward).

## 5. Current state / where the points are

Run `python3 tools/ours.py` for live numbers. As of 2026-07-26 ~19:30 local:
rank 14/235, 26.95+ pts, 16/16 fully solved. Today's submitted wins: LLLM
41.8x (reflow), Snake 24.8x (generator-side: code_x, banked RAMs, compact
floor, boustrophedon, linked lose-walk), gradebook -43% (connector passes),
subset-sum -7%, pathfinder 18/18 (other lane). Remaining pools: Snake 0.80,
Pathfinder 0.53 (box-dominated, 381x496), LLLM 0.56, Plotter 0.47 (71x,
algorithmic), Sudoku 0.45, Matmul 0.38, Subset 0.37 (MITM rebuild in
flight). Check `tl ready` / notes on `tl-xbyt` (reflow-rollout) before
starting overlapping work.

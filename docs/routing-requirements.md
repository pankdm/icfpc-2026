# Littleman routing tool — requirements & design

The recurring bottleneck on hard problems (sort, plotter, matmul) is NOT algorithm
design — those get validated in Python simulators — it's turning the design into a
**collision-free grid**: routing men and pipes so nothing overlaps, no pipe crosses,
no literal collides, and every `r`/`s` hits its intended pipe. A greedy per-net router
fails because converging corridors hog lanes. This doc specs the router that fixes it.

## Two routing domains (DIFFERENT collision rules)

**Man-corridors** (control flow, inside rooms): a man walks a path; turns/ops are placed
cells, straights are blank *glides*. Two corridors may CROSS at a blank cell (the man's
heading comes from the man, not the cell — a blank is a nop). Conflict only when two paths
need a *different placed glyph* on one cell, or a glide would run over a stray op. Merges
must enter a shared cell with the SAME heading. Stepping on a wall is fatal.

**Pipes** (data flow, outside rooms): every cell is a glyph (`-`/`|`/arrowhead), so pipes
CANNOT cross pipes, walls, or anything non-free. Validity: ≥2 cells; arrowhead at start,
every bend, and end; body matches direction; start's backward neighbour on the source-room
border, end's forward neighbour on a DIFFERENT room's border; no self-loop.

## Typed occupancy grid (not binary)

Every cell is exactly one of:
- `FREE` — routable by anything.
- `GLIDE` — a man-corridor blank; shareable by OTHER man-glides, exclusive vs pipes/placed.
- `PLACED` — an op/turn glyph; exclusive.
- `PIPE` — a pipe cell; exclusive.
- `WALL` — room/display border; exclusive (fatal to walk).
- `ROOM` — room interior (men live here; pipes may not enter).
- `LITERAL` — a backtick-literal block; rigid, must stay clear on BOTH axes (littleman
  parses literals horizontally AND vertically — a stray backtick in the column/row is a
  load error).

The router's collision test keys off these types, not a boolean occupied bit.

## Algorithm

1. **A\* core** shared by both net types. Cost = `steps + BEND·bends + GROW·bbox_growth`.
   `bbox_growth` = how much the route pushes the program's non-space bounding box; since
   score = max(w,h)², staying inside the current box is ~free and extending the max
   dimension is heavily penalised.
2. **Pipe net router**: endpoints on room borders; routes over `FREE` only; emits
   arrowheads at start/bends/end and body glyphs; validated against the parse rules.
3. **Man-corridor net router**: emits turn glyphs at bends, blanks between; may traverse
   other corridors' `GLIDE` cells; refuses `PLACED`/`PIPE`/`WALL`; enforces heading match
   at merges.
4. **Global rip-up / negotiated congestion**: route every net (hardest-first seed); on
   contention, rip up the cheaper-to-move net and reroute with a rising per-cell congestion
   penalty; iterate to convergence or a budget. This is the fix for "one corridor hogs a
   lane and starves the next."
5. **Nearest-pipe solver**: for multi-pipe rooms, place each pipe's attachment cell so every
   `r`/`s`/`q` op resolves to its intended pipe by Manhattan-nearest + reading-order tie.
   Satisfy a given assignment or report infeasible.

## Validators (mirror the oracle, then grade)

- `validate_pipe` on every routed pipe (exact parse rules).
- No man-corridor crosses a `PLACED`/`PIPE`/`WALL` cell.
- Literal blocks clear on both axes.
- Nearest-pipe assignments hold (cheap Manhattan check).
- Final: grade the assembled `.man` on the reference oracle (ground truth).

## API (built on tools/layout.py — reuse Layout / place_pipe / auto_pipe / validate_pipe)

```
r = Router(program)                 # wraps a littleman.Program + typed grid
r.add_room(rect, ports=...)         # register a room (walls -> WALL, interior -> ROOM)
r.add_pipe_net(src_pt, dst_pt, nearest_for=[op_cells])   # a pipe to route
r.add_corridor(a_pt, h_in, b_pt, h_out, glyphs=[...])    # a man-walk to route
r.solve(budget=...)                 # -> ok | UnroutableNet(which, why)
```
`solve()` places everything or returns the specific net it couldn't route (with the
congested region), so the caller can nudge geometry rather than guess.

## Scope

- **v1 (build now):** rooms already placed → globally route all pipes + man-corridors with
  rip-up. Directly unblocks the "converging corridors" failure (sort/plotter/matmul).
- **v2 (later):** control-flow-graph → walk folding — branches via `X`/`d`/`a`, loop-backs,
  automatic room sizing. The bigger compiler; not needed for v1's win.

## Acceptance test

Reconstruct a known-good multi-pipe solution (e.g. `solutions/triangle/weave8x8.man` — two
L-bend pipes — and the reverse `ring-v2` pipe fan) using ONLY the router from fixed room
placements, and grade it: must reproduce the known score with no regression.

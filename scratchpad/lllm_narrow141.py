#!/usr/bin/env python3
"""Build LLLM at 141x141 (box 19,881) from the 142x141 champion (box 20,164).

The room is packed solid from column 48 (the o1|o2 Voronoi floor) to column 139 (the last
op column before the boustrophedon's turn column), so no op can slide left without
re-binding to the wrong pipe.  The two cold `s` pipes are therefore moved first:

    pipe 0  o0  attach 18 -> 22   (room0 -> room4, the 137-cell delay loop: EXACT length)
    pipe 1  o1  attach 31 -> 29   (room0 -> room2, 12 cells: EXACT length)

which drags the o0|o1 and o1|o2 midpoints left far enough that every op in the room can
slide one column west and keep the pipe it had.  Then one blank cell per row is deleted
(`scratchpad/narrow_room.py`), the east wall lands on column 140, and the grid is 141 wide.

Both re-routes keep their length to the cell: pipe 0's length is the LLLM tape's storage
(room 4 is a shift register fed by pipes 0 and 8, 137 each), so a cell either way would
change the machine, not just its timing.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "scratchpad"))
import lift as _lift          # noqa: E402
import narrow_room as nr      # noqa: E402

SRC = os.path.join(REPO, "solutions/little-little-little-man/live-8e907387.man")
DST = sys.argv[1] if len(sys.argv) > 1 else "/tmp/lllm-141.man"

# ---------------------------------------------------------------- new pipe routes
def vrun(x, y0, y1):
    step = 1 if y1 >= y0 else -1
    return [(x, y) for y in range(y0, y1 + step, step)]


def hrun(y, x0, x1):
    step = 1 if x1 >= x0 else -1
    return [(x, y) for x in range(x0, x1 + step, step)]


# pipe 0: (22,102) -> (26,130), exactly 137 cells, spacing-2 serpentine that never sits in
# row 102 (adjacency to room 0's wall) nor row 130 except its own endpoint (room 4's wall).
PIPE0 = (vrun(22, 102, 125) + [(21, 125)] + vrun(20, 125, 103) + [(19, 103)]
         + vrun(18, 103, 129) + hrun(129, 19, 23) + vrun(24, 129, 103) + [(25, 103)]
         + vrun(26, 103, 130))
# pipe 1: (29,102) -> (33,109) on room 2's left wall, exactly 12 cells (was 12).
PIPE1 = vrun(29, 102, 109) + hrun(109, 30, 33)

GLYPH_V = {(0, 1): "v", (0, -1): "^", (1, 0): ">", (-1, 0): "<"}


def draw(cells):
    """Pipe glyph per cell: straight runs are `|`/`-`, every other cell shows the direction
    it hands control on in (matching the champion's own convention, verified against it)."""
    out = {}
    for i, (x, y) in enumerate(cells):
        nxt = cells[i + 1] if i + 1 < len(cells) else None
        d = (nxt[0] - x, nxt[1] - y) if nxt else None
        prv = cells[i - 1] if i else None
        pd = (x - prv[0], y - prv[1]) if prv else None
        if d is None:
            d = pd
        # first and last cell ALWAYS carry a direction glyph: the endpoint is what tells the
        # analyser which room the pipe attaches to, so a straight `|` there orphans the pipe
        # (measured: dst became -1 and the oracle said "pipe runs into wall").
        if pd is not None and pd == d and nxt is not None:
            out[(x, y)] = "|" if d[1] else "-"
        else:
            out[(x, y)] = GLYPH_V[d]
    return out


def main():
    grid, w = nr.load(SRC)
    lf = _lift.Lift(_lift.load_rows(SRC))
    (rx0, ry0), (rx1, ry1) = lf.rooms[0]["min"], lf.rooms[0]["max"]
    newcols = {0: 22, 1: 29}

    # 1. sanity: the new routes have the original lengths and land where they must
    for i, path in ((0, PIPE0), (1, PIPE1)):
        old = [tuple(c["pos"]) for c in lf.pipes[i]["path"]]
        assert len(path) == len(old), (i, len(path), len(old))
        assert len(set(path)) == len(path), f"pipe {i} self-intersects"
        for a, b in zip(path, path[1:]):
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, f"pipe {i} jumps {a}->{b}"
        assert path[0][0] == newcols[i] and path[0][1] == 102
        print(f"pipe {i}: {len(old)} -> {len(path)} cells, "
              f"attach {old[0]} -> {path[0]}, end {old[-1]} -> {path[-1]}")

    # 2. rewrite the two pipes (erase old cells first; the new routes reuse many of them)
    old_cells = set()
    for i in (0, 1):
        old_cells |= {tuple(c["pos"]) for c in lf.pipes[i]["path"]}
    for (x, y) in old_cells:
        grid[y][x] = " "
    for path in (PIPE0, PIPE1):
        for (x, y), ch in draw(path).items():
            if grid[y][x] != " ":
                sys.exit(f"pipe cell ({x},{y}) collides with {grid[y][x]!r}")
            grid[y][x] = ch

    # 3. the slide, judged against the ORIGINAL bindings with the new pipe columns in force
    links = nr.vertical_links(lf)
    ms, mst, bad = nr.pin_ops(lf, grid, 0, rx0 + 1, rx1 - 1, ry0 + 1, ry1 - 1, 1, newcols)
    if bad:
        sys.exit(f"{len(bad)} ops can neither stay nor slide: {bad[:5]}")
    cuts, err = nr.solve_cuts(grid, list(range(ry0 + 1, ry1)), rx0 + 1, rx1 - 1,
                              links, 1, ms, mst)
    if cuts is None:
        sys.exit(f"no cut plan: {err}")
    for y in (ry0, ry1):
        cuts[y] = [rx1 - 1]
    out = []
    for y, row in enumerate(grid):
        drop = set(cuts.get(y, ()))
        out.append("".join(row[c] for c in range(w) if c not in drop))
    txt = "\n".join(r.rstrip() for r in out) + "\n"
    open(DST, "w").write(txt)
    lines = txt.rstrip("\n").split("\n")
    nw, nh = max(len(r) for r in lines), len(lines)
    print(f"wrote {DST}: {nw}x{nh}  box {max(nw, nh) ** 2:,}")


if __name__ == "__main__":
    main()

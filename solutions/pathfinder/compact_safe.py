#!/usr/bin/env python3
"""Pipe-length-preserving compaction for pathfinder reverse-bfs-fifo.

compact_man.py deletes any all-'-' column / all-'|' row, which SHORTENS PIPES —
fatal here: the queue pipe (room14->room0, len 379) and the belt loop
(room1<->room18, 208/81) are FIFO *stores* whose length is capacity.

This pass deletes only rows/columns where every non-space cell is a ROOM WALL
cell that is not part of any pipe path, so every pipe keeps its exact length
and every room just shrinks. Bindings are re-gated afterwards with pipecheck.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import pipecheck


def main(src, dst):
    rows = pipecheck.load_rows(src)
    topo = pipecheck.analyze(rows)
    H, W = len(rows), len(rows[0])

    pipe_cells = set()
    for p in topo["pipes"]:
        for cell in p["path"]:
            pipe_cells.add(tuple(cell["pos"]))

    # Room wall cells: perimeter of each room bbox.
    wall_cells = set()
    for r in topo["rooms"]:
        (x0, y0), (x1, y1) = r["min"], r["max"]
        for x in range(x0, x1 + 1):
            wall_cells.add((x, y0)); wall_cells.add((x, y1))
        for y in range(y0, y1 + 1):
            wall_cells.add((x0, y)); wall_cells.add((x1, y))

    def col_deletable(c):
        for y in range(H):
            ch = rows[y][c]
            if ch == ' ':
                continue
            if (c, y) in pipe_cells:
                return False
            if (c, y) in wall_cells and ch == '-':
                continue          # horizontal wall run shrinks by one, stays a wall
            return False
        return True

    def row_deletable(r):
        for x in range(W):
            ch = rows[r][x]
            if ch == ' ':
                continue
            if (x, r) in pipe_cells:
                return False
            if (x, r) in wall_cells and ch == '|':
                continue
            return False
        return True

    # Columns 631-639 sit BETWEEN the display attachment (x=630) and the queue
    # attachment (x=650) on room 0's bottom wall; deleting them rebinds the five
    # `s` ops at x=641 from pipe 6 (queue) to pipe 5 (display). Keep them.
    forbidden = set(range(631, 640))
    del_cols = sorted(c for c in range(W) if c not in forbidden and col_deletable(c))
    del_rows = sorted(r for r in range(H) if row_deletable(r))
    print(f"deletable: {len(del_cols)} cols, {len(del_rows)} rows")
    print("cols:", del_cols)
    print("rows:", del_rows)

    keep_c = [c for c in range(W) if c not in set(del_cols)]
    keep_r = [r for r in range(H) if r not in set(del_rows)]
    out = ["".join(rows[r][c] for c in keep_c) for r in keep_r]
    with open(dst, "w") as f:
        f.write("\n".join(line.rstrip() for line in out).rstrip("\n") + "\n")
    w2 = max(len(l) for l in out); print(f"{W}x{H} -> {w2}x{len(out)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

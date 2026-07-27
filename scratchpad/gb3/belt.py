#!/usr/bin/env python3
"""belt.py — pull room0's east wall in and re-snake the belt ring into the freed region.

Width is set entirely by the belt (room7 at cols 55-60 plus a pipe reaching col 54), while
room0's own glyphs stop at col 37.  Score is max(w,h)^2, so with h=64 > w=61 every row cut is
worth NOTHING until the width comes down.  This moves the belt into the region freed by
pulling room0's east wall to col 38, taking w 61 -> 46, after which each room0 row cut pays
until h reaches 46.

Pure routing: the ring's two endpoints keep their room0 attachment columns (31 in, 34 out) so
every band and every binding is untouched.  Only the ring's CAPACITY matters, and it must stay
>= N*(K+1)+1 = 81 values.

usage: belt.py <in.man> <out.man> [--room-row 26] [--col-a 39] [--col-b 44]
"""
import sys, os, argparse

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

ARROW = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}
BODY = {(1, 0): "-", (-1, 0): "-", (0, 1): "|", (0, -1): "|"}


def draw(canvas, cells, into):
    """cells: ordered pipe cells (source-side first). `into`: direction of the final step."""
    n = len(cells)
    outs = []
    for i in range(n - 1):
        outs.append((cells[i + 1][0] - cells[i][0], cells[i + 1][1] - cells[i][1]))
    outs.append(into)
    for i, (x, y) in enumerate(cells):
        d = outs[i]
        head = (i == 0) or (outs[i - 1] != d) or (i == n - 1)
        canvas[(x, y)] = ARROW[d] if head else BODY[d]
    return n


def hline(y, x0, x1):
    step = 1 if x1 >= x0 else -1
    return [(x, y) for x in range(x0, x1 + step, step)]


def vline(x, y0, y1):
    step = 1 if y1 >= y0 else -1
    return [(x, y) for y in range(y0, y1 + step, step)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man")
    ap.add_argument("out")
    ap.add_argument("--wall", type=int, default=38)
    ap.add_argument("--room-row", type=int, default=26)
    ap.add_argument("--room-col", type=int, default=40)
    ap.add_argument("--col-a", type=int, default=39)
    ap.add_argument("--col-b", type=int, default=44)
    a = ap.parse_args()

    rows = [list(r) for r in wf.load_rows(a.man)]
    H, W = len(rows), len(rows[0])
    g = wf.Grid(wf.load_rows(a.man))
    (rx0, ry0), (rx1, ry1) = g.rooms[0]["min"], g.rooms[0]["max"]
    old7 = g.rooms[7]

    def put(x, y, ch):
        while y >= len(rows):
            rows.append([" "] * W)
        while x >= len(rows[y]):
            rows[y].append(" ")
        rows[y][x] = ch

    def blank(x, y):
        if 0 <= y < len(rows) and 0 <= x < len(rows[y]):
            rows[y][x] = " "

    # 1. rip up the old belt: pipe5 (room0 -> room7) and pipe11 (room7 -> room0), and room7
    for pi in (5, 11):
        for q in g.pipes[pi].get("path") or []:
            x, y = q["pos"]
            if (x, y) == (34, ry1) or (x, y) == (31, ry1):
                continue                       # room0 wall cells: keep the wall
            blank(x, y)
    for y in range(old7["min"][1], old7["max"][1] + 1):
        for x in range(old7["min"][0], old7["max"][0] + 1):
            blank(x, y)

    # 2. pull room0's east wall in to `--wall`
    for y in range(ry0, ry1 + 1):
        ch = "+" if y in (ry0, ry1) else "|"
        put(a.wall, y, ch)
        for x in range(a.wall + 1, W):
            blank(x, y)

    # 3. new room7: 6x4, interior `>@rv` / `^.s<`
    rc, rr = a.room_col, a.room_row
    for i, s in enumerate(["+----+", "|>@rv|", "|^.s<|", "+----+"]):
        for j, ch in enumerate(s):
            put(rc + j, rr + i, ch)

    # 4. re-route the two belt pipes
    canvas = {}
    stub = ry1 + 1                                   # the pipe-stub row just below room0
    # out: room0 (34, wall) -> east along the stub row -> north -> into room7's bottom wall
    # the first cell must point AWAY from room0 (south), so drop a row before bending east
    cells = vline(34, stub, stub + 1) + hline(stub + 1, 35, a.col_a) + \
        vline(a.col_a, stub, rr + 4) + hline(rr + 4, a.col_a + 1, rc + 1)
    seen, ordered = set(), []
    for c in cells:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    n_out = draw(canvas, ordered, (0, -1))
    # in: room7's bottom wall -> south -> west along a lane below the rings -> north to (31, wall)
    lane = old7["max"][1] - 2
    cells = vline(a.col_b, rr + 4, lane) + hline(lane, a.col_b - 1, 31) + vline(31, lane - 1, stub)
    seen, ordered = set(), []
    for c in cells:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    n_in = draw(canvas, ordered, (0, -1))

    for (x, y), ch in canvas.items():
        put(x, y, ch)

    text = "\n".join("".join(r).rstrip() for r in rows).rstrip("\n") + "\n"
    open(a.out, "w").write(text)
    print(f"wrote {a.out}: belt capacity = {n_out} + {n_in} + 1 man = {n_out + n_in + 1} "
          f"(need >= 81)")


main()

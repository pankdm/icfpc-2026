#!/usr/bin/env python3
"""subset-sum: drop k worker replicas (4 rows each) and re-lay the r3->r0 loop
pipe at EXACTLY its original 238 cells, entirely inside columns <= 83.

Width 95 came from one pipe; height comes from 19 replicas on a 4-row period.
Dropping replicas is worth nothing until the width is below the height, so the
re-route has to come first -- it does, unconditionally, here.

    python3 scratchpad/ss2/ss2_build.py K [out.man]

The pipe's cell COUNT is treated as load-bearing (delay/capacity line): every k
gets its own serpentine with `teeth` sized to land on 238 exactly.  The tail cell
(39,0) never moves, so r0's incoming reading order and nearest-pipe bindings are
identical for every k.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "teammate.man")
PIPE_LEN = 238
ARR = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}


def load():
    g = [list(l.rstrip("\n")) for l in open(SRC).read().split("\n")]
    while g and not "".join(g[-1]).strip():
        g.pop()
    w = max(len(r) for r in g)
    for r in g:
        r += [" "] * (w - len(r))
    return g


def old_pipe_cells():
    cells = [(83, 7)]
    cells += [(84, y) for y in range(7, 90)]
    cells += [(x, 89) for x in range(85, 95)]
    cells += [(94, y) for y in range(88, -1, -1)]
    cells += [(x, 0) for x in range(93, 38, -1)]
    seen = set()
    return [c for c in cells if not (c in seen or seen.add(c))]


def safe_windows(g):
    rows = ["".join(r).rstrip() for r in g]
    return [r for r in range(len(rows) - 8)
            if all(rows[r + i] == rows[r + 4 + i] for i in range(4))]


def build(k):
    g = load()
    for (x, y) in old_pipe_cells():
        g[y][x] = " "
    for _ in range(k):
        w = [r for r in safe_windows(g) if r > 14]
        if not w:
            raise SystemExit("no safe replica window left")
        r = w[len(w) // 2]
        del g[r:r + 4]
    H = len(g)
    path = [(81, 11), (81, 12)]
    path += [(x, 12) for x in range(80, 72, -1)]
    path += [(73, y) for y in range(13, H)]
    path += [(x, H - 1) for x in range(74, 84)]
    # north up col 83 with `teeth` two-cell detours into col 82 to hit PIPE_LEN
    base = len(path) + (H - 1) + 44
    need = PIPE_LEN - base
    if need < 0 or need % 2:
        raise SystemExit("k=%d: cannot hit %d (base %d)" % (k, PIPE_LEN, base))
    teeth = sorted(set(range(13, H - 3, 3)))[:need // 2]
    if len(teeth) * 2 != need:
        raise SystemExit("k=%d: not enough room for %d teeth" % (k, need // 2))
    tset = set(teeth)
    y = H - 2
    while y >= 0:
        path.append((83, y))
        if y in tset:
            path.append((82, y))
            path.append((82, y - 1))
            path.append((83, y - 1))
            y -= 2
        else:
            y -= 1
    path += [(x, 0) for x in range(82, 38, -1)]
    if len(path) != PIPE_LEN:
        raise SystemExit("k=%d: length %d != %d" % (k, len(path), PIPE_LEN))
    if len(set(path)) != len(path):
        raise SystemExit("k=%d: path self-intersects" % k)
    for (x, y) in path:
        if g[y][x] != " ":
            raise SystemExit("k=%d: path hits %r at (%d,%d)" % (k, g[y][x], x, y))
    for i, (x, y) in enumerate(path):
        nxt = path[i + 1] if i + 1 < len(path) else (39, 1)
        d = (nxt[0] - x, nxt[1] - y)
        if d not in ARR:
            raise SystemExit("k=%d: non-unit step %s->%s" % (k, (x, y), nxt))
        g[y][x] = ARR[d]
    return "\n".join("".join(r).rstrip() for r in g) + "\n"


def main():
    k = int(sys.argv[1])
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "ss2-k%d.man" % k)
    out = build(k)
    open(dst, "w").write(out)
    lines = out.split("\n")
    w = max(len(l) for l in lines)
    h = len([l for l in lines if l.strip()])
    print("k=%d -> %s  %dx%d  box=%d" % (k, dst, w, h, max(w, h) ** 2))


if __name__ == "__main__":
    main()

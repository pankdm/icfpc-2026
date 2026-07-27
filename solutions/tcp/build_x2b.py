#!/usr/bin/env python3
"""Splice the 2-wide-interior checker into the champion grid and measure the cost.

Keeps the reader / lanes / sweeper exactly as they are (cols 0..17) and rebuilds
only the right-hand band: checker, both I/O rooms and the four pipes.
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
sys.path.insert(0, '/Users/visenbaev/icfpc26/solutions/tcp')

SRC = '/Users/visenbaev/icfpc26/solutions/tcp/bxdecode-23x23-c15.man'


def load(p, w, h):
    rows = open(p).read().rstrip('\n').split('\n')
    g = [list(r.ljust(w)) for r in rows]
    while len(g) < h:
        g.append([' '] * w)
    return g


def main(cy=5, out='/tmp/x2.man'):
    W, H = 26, 28
    g = load(SRC, W, H)
    for y in range(H):                       # blank the whole right band
        for x in range(18, W):
            g[y][x] = ' '

    def put(x, y, ch):
        if g[y][x] != ' ' and g[y][x] != ch:
            raise SystemExit(f'collision at ({x},{y}): {g[y][x]!r} vs {ch!r}')
        g[y][x] = ch

    class L:
        def put(self, x, y, ch): put(x, y, ch)
        def room(self, x, y, w, h):
            for i in range(w):
                g[y][x + i] = '-'; g[y + h - 1][x + i] = '-'
            for j in range(h):
                g[y + j][x] = '|'; g[y + j][x + w - 1] = '|'
            for cx, cy2 in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
                g[cy2][cx] = '+'

    from checker_x2 import emit_checker_x2
    cx = 18
    hints = emit_checker_x2(L(), cx, cy)
    nwall, swall = hints['nwall'], hints['swall']

    def room(x, y, ch):
        L().room(x, y, 3, 3); put(x + 1, y + 1, ch)

    # input room hugs the checker (cols 19..21): 2-cell L pipe west into reader
    room(19, nwall - 4, 'I')
    put(18, nwall - 2, '^'); put(18, nwall - 3, '<')
    # seq: reader east wall -E-> then S into the checker's north wall
    put(18, nwall - 1, '>'); put(19, nwall - 1, 'v')
    # drain: sweeper east wall -E-> then N into the checker's south wall
    put(18, swall + 1, '>'); put(19, swall + 1, '^')
    # output: off the checker's SE corner, west into the output room's east wall
    put(21, swall + 1, 'v'); put(21, swall + 2, '<')
    room(18, swall + 2, 'O')

    txt = '\n'.join(''.join(r).rstrip() for r in g).rstrip('\n') + '\n'
    open(out, 'w').write(txt)
    rows = txt.rstrip('\n').split('\n')
    ww = max(len(r) for r in rows)
    xs = [x for x in range(ww) if any(len(r) > x and r[x] != ' ' for r in rows)]
    ys = [i for i, r in enumerate(rows) if r.strip()]
    bw, bh = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    print(f'wrote {out}  {bw}x{bh}  box {max(bw,bh)**2}')


main(*( [int(sys.argv[1])] if len(sys.argv) > 1 else [] ),
     **({'out': sys.argv[2]} if len(sys.argv) > 2 else {}))

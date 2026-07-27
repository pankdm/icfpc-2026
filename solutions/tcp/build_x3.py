#!/usr/bin/env python3
"""Splice the 14-row 2-wide checker into the champion grid.

Two edits to the champion:
  1. reader row 2: slide `r b` one column west and insert `N` before the seq
     `s`, so the reader sends -seq. The cells it slides into are blank glide,
     so this is free in both ticks and box.
  2. right band (cols 18..) redrawn around checker_x3.

usage: build_x3.py [cy] [out.man]
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
sys.path.insert(0, '/Users/visenbaev/icfpc26/solutions/tcp')

SRC = '/Users/visenbaev/icfpc26/solutions/tcp/bxdecode-23x23-c15.man'


def main(cy=4, out='/tmp/x3.man'):
    W, H = 26, 28
    rows = open(SRC).read().rstrip('\n').split('\n')
    g = [list(r.ljust(W)) for r in rows]
    while len(g) < H:
        g.append([' '] * W)
    for yy in range(H):                      # blank the whole right band
        for xx in range(18, W):
            g[yy][xx] = ' '

    # --- reader: send -seq -------------------------------------------------
    # The seq send CANNOT be negated before the fork at (13,3): the demux tree
    # reloads BP from A (`b` at (8,4),(10,4),(4,5),(6,5),(12,5),(14,5)), so A
    # must still be +seq when the west copy walks the tree. Move the send onto
    # the EAST copy instead -- it is the main read-loop man and never looks at
    # A again -- using two blank glide cells on its way back to the `<` rail.
    #   row 2: |@r1M>    rb v   |    (s removed from col 12)
    #   row 3: ... Y N ^ ...          N at (14,3) on the east copy's first cell
    #   row 2: s at (15,2), on its climb to the (15,1) turn-around
    assert ''.join(g[2][10:14]) == 'rbsv', ''.join(g[2][:18])
    assert g[3][13] == 'Y' and g[3][14] == ' ' and g[3][15] == '^' and g[2][15] == ' '
    g[2][12] = ' '
    g[3][14] = 'N'
    g[2][15] = 's'

    def put(x, yy, ch):
        if g[yy][x] not in (' ', ch):
            raise SystemExit(f'collision at ({x},{yy}): {g[yy][x]!r} vs {ch!r}')
        g[yy][x] = ch

    class L:
        def put(self, x, yy, ch): put(x, yy, ch)
        def room(self, x, yy, w, h):
            for i in range(w):
                g[yy][x + i] = '-'; g[yy + h - 1][x + i] = '-'
            for j in range(h):
                g[yy + j][x] = '|'; g[yy + j][x + w - 1] = '|'
            for a, b in ((x, yy), (x + w - 1, yy), (x, yy + h - 1), (x + w - 1, yy + h - 1)):
                g[b][a] = '+'

    from checker_x3 import emit_checker_x3
    cx = 18
    hints = emit_checker_x3(L(), cx, cy)
    nwall, swall, sc = hints['nwall'], hints['swall'], hints['seq_col']

    def room3(x, yy, ch):
        L().room(x, yy, 3, 3); put(x + 1, yy + 1, ch)

    room3(20, nwall - 4, 'I')                       # input room, cols 20..22
    put(19, nwall - 3, '<'); put(18, nwall - 3, '<')   # -> reader east wall
    put(18, nwall - 1, '>'); put(sc, nwall - 1, 'v')   # seq -> checker north
    put(18, swall + 1, '>'); put(sc, swall + 1, '^')   # drain -> checker south
    put(21, swall + 1, 'v'); put(21, swall + 2, '<')   # output -> output room
    room3(18, swall + 2, 'O')

    txt = '\n'.join(''.join(r).rstrip() for r in g).rstrip('\n') + '\n'
    open(out, 'w').write(txt)
    ls = txt.rstrip('\n').split('\n')
    ww = max(len(r) for r in ls)
    xs = [x for x in range(ww) if any(len(r) > x and r[x] != ' ' for r in ls)]
    ys = [i for i, r in enumerate(ls) if r.strip()]
    bw, bh = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    print(f'wrote {out}  {bw}x{bh}  box {max(bw, bh) ** 2}')


main(*([int(sys.argv[1])] if len(sys.argv) > 1 else []),
     **({'out': sys.argv[2]} if len(sys.argv) > 2 else {}))

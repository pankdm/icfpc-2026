#!/usr/bin/env python3
"""Step 2 of the dual-belt reopening: does the PLANAR port assignment exist?

Reads the engine's op cells straight out of rewind-v13.man (the live 24x24 /
avgTicks 3589 champion, MEM = the room at (0,0) 19x13), classifies every `r`/`s`
by which pipe it currently binds under v13's known-correct all-on-the-bottom-wall
geometry, and then asks tools/bindsolve.py whether those same cells can bind a
DIFFERENT port arrangement with no change to the internals.

RESULT (see the census printed below):

  the reopening's ask -- CMD on the TOP wall, OX on the BOTTOM, PIN/POUT on the
  inner SIDE wall -- EXISTS:   4 incoming assignments x 1 outgoing assignment.
  So the second closure's "forced crossing" was an artefact of putting all four
  ports on the bottom wall, exactly as the reopening argued.  Not the blocker.

  Better still, engines STACKED with the belts on the horizontal inner walls:
  CMD=LEFT with PIN=TOP (24) or PIN=BOTTOM (17); OX=LEFT with POUT=TOP (50) or
  POUT=BOTTOM (54).  CMD or OX on the RIGHT wall gives ZERO in every combination,
  so both the controller feed and the merge tap must come from the WEST -- which
  is fine for a stacked floorplan (one west column holds CONTROL + MERGE + I/O)
  and is what makes a ~30-wide box conceivable at all.

The design still loses on cell arithmetic -- see tickmodel.py for the verdict.
"""
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from bindsolve import solve, wall_of, _d                      # noqa: E402

MAN = os.path.join(ROOT, 'solutions', 'memory', 'rewind-v13.man')
W, H = 19, 13                       # MEM's outer rect is (0,0)..(18,12)
# v13's live attachment cells, all on the bottom wall (attachment row = 13).
LIVE = {'OUT': (1, 13), 'CMD': (4, 13), 'P2': (9, 13), 'P1': (14, 13)}


def census():
    g = [r.ljust(24) for r in open(MAN).read().split('\n')]
    recv, send = [], []
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            c = g[y][x]
            if c in 'rRUq':
                recv.append((x, y))
            if c in 'sS':
                send.append((x, y))

    def nearest(cell, names):
        return min(names, key=lambda n: (_d(cell, LIVE[n]),
                                         LIVE[n][1], LIVE[n][0]))
    want_in = {'CMD': [], 'PIN': []}
    for c in recv:
        want_in['CMD' if nearest(c, ['CMD', 'P2']) == 'CMD' else 'PIN'].append(c)
    want_out = {'OX': [], 'POUT': []}
    for c in send:
        if g[c[1]][c[0]] == 'S':
            continue                # `S` hits every outgoing pipe: no constraint
        want_out['OX' if nearest(c, ['OUT', 'P1']) == 'OUT' else 'POUT'].append(c)
    return want_in, want_out


def rep(tag, want, walls):
    s = solve(W, H, want, walls=walls)
    ex = {k: (v, wall_of(v, W, H)) for k, v in s[0].items()} if s else ''
    print('%-44s %4d   %s' % (tag, len(s), ex))
    return s


if __name__ == '__main__':
    want_in, want_out = census()
    print('recv cells -> CMD %s' % (want_in['CMD'],))
    print('              PIN %s' % (want_in['PIN'],))
    print('send cells -> OX  %s' % (want_out['OX'],))
    print('              POUT %s\n' % (want_out['POUT'],))

    print('--- the reopening: CMD top / OX bottom / belts on the inner SIDE ---')
    rep('IN   CMD=Top,    PIN=Right', want_in, {'CMD': 'T', 'PIN': 'R'})
    rep('IN   CMD=Top,    PIN=Left', want_in, {'CMD': 'T', 'PIN': 'L'})
    rep('OUT  OX=Bottom,  POUT=Right', want_out, {'OX': 'B', 'POUT': 'R'})
    rep('OUT  OX=Bottom,  POUT=Left', want_out, {'OX': 'B', 'POUT': 'L'})

    print('\n--- STACKED engines: belts on the horizontal inner wall ---')
    for cw in 'LR':
        for pw in 'TB':
            rep('IN   CMD=%s,   PIN=%s' % (cw, pw), want_in,
                {'CMD': cw, 'PIN': pw})
    for ow in 'LR':
        for pw in 'TB':
            rep('OUT  OX=%s,    POUT=%s' % (ow, pw), want_out,
                {'OX': ow, 'POUT': pw})

    print('\n--- reference: v13 as built (everything on the bottom wall) ---')
    rep('IN   CMD=B,      PIN=B', want_in, {'CMD': 'B', 'PIN': 'B'})
    rep('OUT  OX=B,       POUT=B', want_out, {'OX': 'B', 'POUT': 'B'})
    rep('IN   unconstrained', want_in, None)
    rep('OUT  unconstrained', want_out, None)

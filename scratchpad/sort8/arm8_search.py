#!/usr/bin/env python3
"""Enumerate lap-entry chain placements for the arm8 loop and emit .man candidates."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arm8 import DIRCH, INTERIOR, Q_ROWS, cw, ccw, loop_cells

STRAIGHT_OPS = {'q', 'm', 'R', 'M'}
SEQS = []
for pre in (('q', 'Y'), ('Y', 'q')):
    for tail in (('m', 'R', 'M'), ('R', 'm', 'M'), ('R', 'M', 'm')):
        SEQS.append(list(pre) + ['T'] + list(tail))


def nbrs(p):
    for d in DIRCH:
        yield d, (p[0] + d[0], p[1] + d[1])


def kind_of(dirn, nd):
    if nd == dirn:
        return 'S'
    return 'CW' if nd == cw(dirn) else 'CCW'


def lap_paths(ux, uy, free, maxlen=11, reserved=None):
    """DFS every lap chain.  Returns list of dicts describing a candidate."""
    m0 = (ux + 1, uy - 1)
    goals = {((ux + 1, uy + 2), (0, -1)), ((ux + 2, uy + 1), (-1, 0))}
    if reserved:
        free = set(free) - {reserved}
        goals = {g for g in goals if g[0] != reserved}
    out = []

    def dfs(pos, dirn, si, cells, order, ycell, tcell, texit, seq):
        # `pos` is the cell we are standing on, `dirn` how we arrived
        if len(cells) > maxlen:
            return
        for nd, nn in nbrs(pos):
            if nd == (-dirn[0], -dirn[1]):
                continue
            k = kind_of(dirn, nd)
            want = seq[si] if si < len(seq) else None
            nsi, nyc, ntc, nte = si, ycell, tcell, texit
            if k == 'S':
                if want in STRAIGHT_OPS:
                    if want == 'q' and pos[1] not in Q_ROWS:
                        continue
                    ch, nsi = want, si + 1
                else:
                    ch = ' '
            elif want == 'Y':
                other = (pos[0] - nd[0], pos[1] - nd[1])
                if other not in free or other in cells:
                    continue
                ch, nsi, nyc = 'Y', si + 1, (pos, nd, other)
            elif want == 'T':
                ex = (pos[0] + dirn[0], pos[1] + dirn[1])
                if ex not in free or ex in cells:
                    continue
                if not any((ex[0] + d[0], ex[1] + d[1]) in free
                           for d in DIRCH if d != (-dirn[0], -dirn[1])):
                    continue
                ch = 'd' if k == 'CW' else 'a'
                nsi, ntc, nte = si + 1, pos, (ex, dirn)
            else:
                ch = DIRCH[nd]
            c2 = dict(cells)
            c2[pos] = ch
            o2 = order + [pos]
            if (pos, nd) in goals and nsi == len(seq):
                out.append(dict(cells=c2, order=o2, y=nyc, test=ntc,
                                texit=nte, entry=(pos, nd), ticks=len(c2) + 2))
                continue
            if nn not in free or nn in c2:
                continue
            dfs(nn, nd, nsi, c2, o2, nyc, ntc, nte, seq)

    for seq in SEQS:
        for d0 in DIRCH:
            nn = (m0[0] + d0[0], m0[1] + d0[1])
            if nn not in free:
                continue
            dfs(nn, d0, 0, {m0: DIRCH[d0]}, [m0], None, None, None, seq)
    return out


def walk(start, sdir, free, ops, goal, maxlen=24, xlimit=None):
    """BFS shortest op-placing walk.  Returns a cell->char dict or None."""
    from collections import deque

    def cells_of(st, par):
        c = {}
        while par[st] is not None:
            prev, pos, ch = par[st]
            c[pos] = ch
            st = prev
        return c

    st0 = (start, sdir, 0)
    par = {st0: None}
    dq = deque([st0])
    while dq:
        st = dq.popleft()
        pos, dirn, oi = st
        cells = cells_of(st, par)
        for nd, _ in nbrs(pos):
            if nd == (-dirn[0], -dirn[1]):
                continue
            k = kind_of(dirn, nd)
            noi = oi
            if k == 'S':
                if oi < len(ops):
                    op = ops[oi]
                    if xlimit and op in xlimit and pos[0] not in xlimit[op]:
                        ch = ' '
                    else:
                        ch, noi = op, oi + 1
                else:
                    ch = ' '
            else:
                ch = DIRCH[nd]
            if pos in cells and cells[pos] != ch:
                continue
            c2 = dict(cells)
            c2[pos] = ch
            r = goal(pos, nd, noi, c2)
            if r is not None:
                return r
            nn = (pos[0] + nd[0], pos[1] + nd[1])
            if nn not in free or nn in c2:
                continue
            nst = (nn, nd, noi)
            if nst in par or len(c2) > maxlen:
                continue
            par[nst] = (st, pos, ch)
            dq.append(nst)
    return None

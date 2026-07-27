#!/usr/bin/env python3
"""brk6_pack.py placed the five rooms but reserved nothing for the FOUR pipes.
M 10x11 + P 6x8 + C 14x5 + two 3x3 leaves 10 free cells, all in cols 14-15, and
M/P are flush against each other -- the M->P pipe has nowhere to go.

brackets needs I -> C -> M -> P -> O.  A pipe is >= 2 cells, its head must step
directly AWAY from its room (an arrow that does not is silently not a pipe), and
its tail must point into the destination wall.  So this re-runs the enumeration
and additionally routes all four pipes through the leftover cells.

    python3 scratchpad/brk6/brk6_pack2.py [max_fill]
"""
import sys
from collections import deque

BOX = 16
M_CELLS, P_CELLS, C_CELLS = 57, 21, 29
MAXFILL = float(sys.argv[1]) if len(sys.argv) > 1 else 0.90
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def rects(need):
    out = []
    for w in range(5, BOX + 1):
        for h in range(5, BOX + 1):
            iw, ih = w - 2, h - 2
            if min(iw, ih) < 3 or need > iw * ih * MAXFILL:
                continue
            out.append((w, h, need / (iw * ih)))
    return out


def cellset(x, y, w, h):
    return {(a, b) for a in range(x, x + w) for b in range(y, y + h)}


def border(x, y, w, h):
    s = set()
    for a in range(x, x + w):
        s.add((a, y)); s.add((a, y + h - 1))
    for b in range(y, y + h):
        s.add((x, b)); s.add((x + w - 1, b))
    return s


def route(free, ba, bb, budget=8):
    """shortest pipe from room A (border ba) to room B (border bb) through `free`"""
    starts = [(c, d) for c in free for d in STEPS
              if (c[0] - d[0], c[1] - d[1]) in ba]
    for c0, d0 in starts:
        seen = {(c0, d0)}
        q = deque([(c0, d0, [c0])])
        while q:
            c, d, path = q.popleft()
            nxt = (c[0] + d[0], c[1] + d[1])
            if nxt in bb:
                if len(path) >= 2:
                    return path
                continue
            if nxt not in free or nxt in path or len(path) >= budget:
                continue
            for nd in STEPS:
                if (nxt[0] - nd[0], nxt[1] - nd[1]) in ba | bb:
                    continue          # would be a second pipe start
                if (nxt, nd) in seen:
                    continue
                seen.add((nxt, nd))
                q.append((nxt, nd, path + [nxt]))
    return None


def main():
    grid = cellset(0, 0, BOX, BOX)
    out = []
    for mw, mh, mf in rects(M_CELLS):
        for pw, ph, pf in rects(P_CELLS):
            if mw + pw > BOX:
                continue
            for cw, ch, cf in rects(C_CELLS):
                top = max(mh, ph)
                if top + ch > BOX or cw > BOX:
                    continue
                if mw * mh + pw * ph + cw * ch > BOX * BOX - 18:
                    continue
                rooms = {'M': (0, 0, mw, mh), 'P': (mw, 0, pw, ph),
                         'C': (0, top, cw, ch)}
                used = set()
                bad = False
                for r in rooms.values():
                    cs = cellset(*r)
                    if cs & used:
                        bad = True
                        break
                    used |= cs
                if bad:
                    continue
                spots = [(x, y) for y in range(BOX - 2) for x in range(BOX - 2)
                         if cellset(x, y, 3, 3) <= grid - used]
                for i, a in enumerate(spots):
                    ca = cellset(a[0], a[1], 3, 3)
                    for b in spots[i + 1:]:
                        cb = cellset(b[0], b[1], 3, 3)
                        if ca & cb:
                            continue
                        allused = used | ca | cb
                        free = grid - allused
                        bd = {k: border(*v) for k, v in rooms.items()}
                        bd['I'] = border(a[0], a[1], 3, 3)
                        bd['O'] = border(b[0], b[1], 3, 3)
                        f = set(free)
                        ok = True
                        pipes = []
                        for s, t in (('I', 'C'), ('C', 'M'), ('M', 'P'), ('P', 'O')):
                            p = route(f, bd[s], bd[t])
                            if not p:
                                ok = False
                                break
                            pipes.append((s, t, p))
                            f -= set(p)
                        if ok:
                            out.append((round(max(mf, pf, cf), 3),
                                        "M %dx%d P %dx%d C %dx%d I%s O%s free%d"
                                        % (mw, mh, pw, ph, cw, ch, a, b, len(free))))
    out.sort()
    print("BUILDABLE (rooms + all four pipes routed): %d" % len(out))
    seen = set()
    for f, s in out:
        if s[:26] in seen:
            continue
        seen.add(s[:26])
        print("  fill %.0f%%  %s" % (100 * f, s))
        if len(seen) >= 14:
            break


if __name__ == "__main__":
    main()

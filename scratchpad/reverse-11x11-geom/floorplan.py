"""Brute force: maximise total usable interior cells of an 11x11 littleman program
containing one 3x3 input room, one 3x3 output room, and 1..2 ordinary rooms,
allowing rooms to share a single corner cell but nothing more, and requiring a
routable pipe I->main and main->O (>=2 free cells each, disjoint).

Rooms are w x h rectangles (w,h>=3); interior = (w-2)*(h-2).
"""
import itertools, sys
from collections import deque

N = 11

def cells(r):
    x, y, w, h = r
    return {(x + i, y + j) for i in range(w) for j in range(h)}

def wallcells(r):
    x, y, w, h = r
    s = set()
    for i in range(w):
        s.add((x + i, y)); s.add((x + i, y + h - 1))
    for j in range(h):
        s.add((x, y + j)); s.add((x + w - 1, y + j))
    return s

def corners(r):
    x, y, w, h = r
    return {(x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)}

def compatible(a, b):
    ov = cells(a) & cells(b)
    if not ov:
        return True
    # single shared cell, and it must be a corner of both
    return len(ov) == 1 and ov <= corners(a) and ov <= corners(b)

def rects(minw=3, minh=3, maxw=N, maxh=N):
    for w in range(minw, maxw + 1):
        for h in range(minh, maxh + 1):
            for x in range(0, N - w + 1):
                for y in range(0, N - h + 1):
                    yield (x, y, w, h)

def attach_sites(r):
    """(wallcell, outward-neighbour) for non-corner wall cells."""
    x, y, w, h = r
    out = []
    for i in range(1, w - 1):
        out.append(((x + i, y), (x + i, y - 1)))
        out.append(((x + i, y + h - 1), (x + i, y + h)))
    for j in range(1, h - 1):
        out.append(((x, y + j), (x - 1, y + j)))
        out.append(((x + w - 1, y + j), (x + w, y + j)))
    return out

def pipe_paths(src, dst, free):
    """shortest pipe (list of cells, len>=2) from room src to room dst through free cells."""
    starts = [(o, wc) for wc, o in attach_sites(src) if o in free]
    goals = {}
    for wc, o in attach_sites(dst):
        if o in free:
            goals[o] = wc
    if not starts or not goals:
        return None
    best = None
    for s, _ in starts:
        # BFS
        seen = {s: None}
        q = deque([s])
        while q:
            c = q.popleft()
            if c in goals:
                path = []
                cur = c
                while cur is not None:
                    path.append(cur); cur = seen[cur]
                path.reverse()
                if len(path) >= 2 and (best is None or len(path) < len(best)):
                    best = path
                break
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (c[0] + d[0], c[1] + d[1])
                if nb in free and nb not in seen:
                    seen[nb] = c
                    q.append(nb)
    return best

def main():
    io_rects = [r for r in rects(3, 3, 3, 3)]
    best = []
    # ---- one main room ----
    for m in rects():
        mi = (m[2] - 2) * (m[3] - 2)
        if mi <= 0:
            continue
        for I in io_rects:
            if not compatible(m, I):
                continue
            for O in io_rects:
                if not compatible(m, O) or not compatible(I, O):
                    continue
                occupied = cells(m) | cells(I) | cells(O)
                free = {(x, y) for x in range(N) for y in range(N)} - occupied
                p1 = pipe_paths(I, m, free)
                if not p1:
                    continue
                p2 = pipe_paths(m, O, free - set(p1))
                if not p2:
                    continue
                best.append((mi, "1room", m, I, O, len(p1), len(p2)))
    best.sort(reverse=True)
    print("BEST single-main-room interiors:")
    seen = set()
    for b in best[:200]:
        key = (b[0], b[2][2], b[2][3])
        if key in seen:
            continue
        seen.add(key)
        print("  interior=%d  main=%s (%dx%d)  I=%s O=%s pipes=%d,%d" %
              (b[0], b[2][:2], b[2][2], b[2][3], b[3][:2], b[4][:2], b[5], b[6]))
        if len(seen) >= 8:
            break

    # ---- two main rooms ----
    print("BEST two-main-room total interiors:")
    allr = [r for r in rects() if (r[2] - 2) * (r[3] - 2) > 0]
    top = []
    for i, m1 in enumerate(allr):
        i1 = (m1[2] - 2) * (m1[3] - 2)
        if i1 + 49 <= 54:   # upper bound on partner; prune hopeless
            pass
        for m2 in allr[i + 1:]:
            i2 = (m2[2] - 2) * (m2[3] - 2)
            if i1 + i2 <= 54:
                continue
            if not compatible(m1, m2):
                continue
            base = cells(m1) | cells(m2)
            for I in io_rects:
                if not compatible(m1, I) or not compatible(m2, I):
                    continue
                for O in io_rects:
                    if not compatible(m1, O) or not compatible(m2, O) or not compatible(I, O):
                        continue
                    occupied = base | cells(I) | cells(O)
                    free = {(x, y) for x in range(N) for y in range(N)} - occupied
                    ok = False
                    for a, b in ((m1, m2), (m2, m1)):
                        p1 = pipe_paths(I, a, free)
                        if not p1:
                            continue
                        p2 = pipe_paths(b, O, free - set(p1))
                        if not p2:
                            continue
                        p3 = pipe_paths(a, b, free - set(p1) - set(p2))
                        if p3:
                            ok = True
                    if ok:
                        top.append((i1 + i2, m1, m2, I, O))
    top.sort(reverse=True)
    if not top:
        print("  none exceed 54")
    else:
        for t in top[:5]:
            print("  total=%d m1=%s m2=%s" % (t[0], t[1], t[2]))

main()

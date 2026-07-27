"""Largest free (all-space) rectangles in a .man, so a band can be re-folded into one.

A serpentine band of V values needs ~1.15*V cells and any aspect ratio works, so
what matters is finding a free rectangle of the right AREA whose height is small.
Prints the free rectangles that are at least MINA cells, widest-first.
"""
import sys

MINA = 200


def main(path, mina=MINA):
    rows = open(path).read().rstrip('\n').split('\n')
    w = max(len(r) for r in rows)
    rows = [r.ljust(w) for r in rows]
    h = len(rows)
    free = [[rows[y][x] == ' ' for x in range(w)] for y in range(h)]

    best = []
    # for each top row, grow downward tracking the free-run intervals
    for y0 in range(h):
        # height[x] = free run starting at y0
        for y1 in range(y0, h):
            hh = y1 - y0 + 1
            if hh * w < mina:
                continue
            # maximal horizontal runs free over rows y0..y1
            run = 0
            for x in range(w + 1):
                ok = x < w and all(free[y][x] for y in range(y0, y1 + 1))
                if ok:
                    run += 1
                else:
                    if run * hh >= mina:
                        best.append((run * hh, run, hh, x - run, y0))
                    run = 0
    # keep only maximal ones (not contained in another reported rect)
    best.sort(key=lambda t: (-t[0], t[2]))
    seen, out = set(), []
    for a, rw, rh, x0, y0 in best:
        key = (x0, y0, rw, rh)
        if key in seen:
            continue
        seen.add(key)
        # skip if strictly inside an already-kept rect
        if any(x0 >= X and y0 >= Y and x0 + rw <= X + W and y0 + rh <= Y + H
               for _, W, H, X, Y in out):
            continue
        out.append((a, rw, rh, x0, y0))
    print(f'{path}: {w}x{h}')
    for a, rw, rh, x0, y0 in out[:30]:
        print(f'  area {a:5d}  {rw:2d}w x {rh:2d}h  at col {x0:2d} row {y0:2d} '
              f'(rows {y0}..{y0+rh-1}, cols {x0}..{x0+rw-1})')


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else MINA)

#!/usr/bin/env python3
"""Per-column / per-row occupancy of a .man's room interiors, plus free-cell map.

  python3 geom.py <file.man> [--cols] [--rows] [--map]

Prints, for every room found, the interior occupancy counts by column and by
row, and lists the sparsest columns with the exact rows they occupy -- which is
what decides whether a column can be relocated into its neighbours.
"""
import sys


def load(path):
    rows = open(path, encoding='utf-8').read().split('\n')
    while rows and not rows[-1].strip():
        rows.pop()
    w = max(len(r) for r in rows)
    return [r.ljust(w) for r in rows], w, len(rows)


def rooms(g, W, H):
    """Every axis-aligned room rectangle: '+' corners, '-' top/bottom, '|' sides."""
    found = []
    for y in range(H):
        for x in range(W):
            if g[y][x] != '+':
                continue
            for x2 in range(x + 2, W):
                if g[y][x2] == '+':
                    break
                if g[y][x2] not in '-=':
                    x2 = -1
                    break
            else:
                x2 = -1
            if x2 < 0 or g[y][x2] != '+':
                continue
            for y2 in range(y + 2, H):
                if g[y2][x] == '+':
                    break
                if g[y2][x] not in '|:':
                    y2 = -1
                    break
            else:
                y2 = -1
            if y2 < 0 or g[y2][x] != '+':
                continue
            if g[y2][x2] != '+':
                continue
            found.append((x, y, x2, y2))
    return found


def main():
    path = sys.argv[1]
    g, W, H = load(path)
    print(f'{path}: {W}x{H} box {max(W, H) ** 2}')
    for (x1, y1, x2, y2) in rooms(g, W, H):
        iw, ih = x2 - x1 - 1, y2 - y1 - 1
        if iw < 1 or ih < 1:
            continue
        cells = {(x, y): g[y][x] for x in range(x1 + 1, x2)
                 for y in range(y1 + 1, y2) if g[y][x] != ' '}
        print(f'\nroom ({x1},{y1})-({x2},{y2})  outer {x2-x1+1}x{y2-y1+1}  '
              f'interior {iw}x{ih}  ops {len(cells)}  fill {len(cells)/(iw*ih):.0%}')
        colc = {x: sum(1 for y in range(y1 + 1, y2) if (x, y) in cells)
                for x in range(x1 + 1, x2)}
        rowc = {y: sum(1 for x in range(x1 + 1, x2) if (x, y) in cells)
                for y in range(y1 + 1, y2)}
        print('  col:', ' '.join(f'{x:>3}' for x in colc))
        print('  cnt:', ' '.join(f'{c:>3}' for c in colc.values()))
        print('  row:', ' '.join(f'{y:>3}' for y in rowc))
        print('  cnt:', ' '.join(f'{c:>3}' for c in rowc.values()))
        for x, c in sorted(colc.items(), key=lambda kv: kv[1])[:5]:
            occ = [(y, cells[(x, y)]) for y in range(y1 + 1, y2) if (x, y) in cells]
            print(f'   col {x:>3} ({c}): ' + ' '.join(f'{y}:{ch!r}' for y, ch in occ))
        for y, c in sorted(rowc.items(), key=lambda kv: kv[1])[:4]:
            occ = [(x, cells[(x, y)]) for x in range(x1 + 1, x2) if (x, y) in cells]
            print(f'   row {y:>3} ({c}): ' + ' '.join(f'{x}:{ch!r}' for x, ch in occ))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Group hot cells into connected structures and rank the structures.

Single-cell rankings hide the shape of the cost: an 8-cell relay ring shows up
as eight middling entries. Flood-filling the hot cells into connected clusters
shows the ring as ONE object with its true total, and its cell count tells you
directly how many ticks each pass costs.

usage: pf3_clusters.py <profile.txt> <file.man>
"""
import ast, sys, collections

prof = sys.argv[1] if len(sys.argv) > 1 else '/tmp/pf3prof.txt'
man = sys.argv[2] if len(sys.argv) > 2 else '/Users/visenbaev/icfpc26/scratchpad/pf3/pf3-base.man'
txt = open(prof).read()


def grab(key):
    i = txt.index('PROFILE ' + key + '=')
    j = txt.index('=', i) + 1
    d, k = 0, j
    while k < len(txt):
        if txt[k] == '[':
            d += 1
        elif txt[k] == ']':
            d -= 1
            if d == 0:
                break
        k += 1
    return dict(ast.literal_eval(txt[j:k + 1]))


cells, stalls = grab('cells'), grab('stalls')
grid = [list(l) for l in open(man).read().split('\n')]
gl = lambda p: grid[p[1]][p[0]] if p[1] < len(grid) and p[0] < len(grid[p[1]]) else ' '
work = {p: c - stalls.get(p, 0) for p, c in cells.items() if c - stalls.get(p, 0) > 0}
tot = sum(work.values())

hot = {p for p, w in work.items() if w >= 200}
seen, clusters = set(), []
for p in hot:
    if p in seen:
        continue
    comp, stack = [], [p]
    seen.add(p)
    while stack:
        q = stack.pop()
        comp.append(q)
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            n = (q[0] + d[0], q[1] + d[1])
            if n in hot and n not in seen:
                seen.add(n)
                stack.append(n)
    clusters.append(comp)

clusters.sort(key=lambda c: -sum(work[p] for p in c))
print(f'total working cell-ticks {tot}')
print(f'\n{"work":>8} {"%":>5} {"cells":>5} {"passes":>7}  bbox                 glyphs')
for c in clusters[:14]:
    w = sum(work[p] for p in c)
    xs = [p[0] for p in c]
    ys = [p[1] for p in c]
    passes = max(work[p] for p in c)
    g = ''.join(sorted(gl(p) for p in c if gl(p) != ' '))
    print(f'{w:8d} {100*w/tot:5.1f} {len(c):5d} {passes:7d}  '
          f'x{min(xs)}-{max(xs)},y{min(ys)}-{max(ys)}'.ljust(21) + f'  {g[:28]}')

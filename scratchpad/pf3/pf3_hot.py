#!/usr/bin/env python3
"""Rank pathfinder cells by REAL cost = executions - stalls.

`lm --profile` counts a blocked `r` once per tick, so the raw `cells` ranking is
dominated by ~18 parked men polling their pipes -- which cost nothing. The
difference (cells - stalls) is the work that actually advances the clock.

usage: pf3_hot.py [profile.txt] [file.man]
"""
import ast, sys, collections

prof = sys.argv[1] if len(sys.argv) > 1 else '/tmp/pf3prof.txt'
man = sys.argv[2] if len(sys.argv) > 2 else '/Users/visenbaev/icfpc26/scratchpad/pf3/pf3-base.man'
txt = open(prof).read()


def grab(key):
    i = txt.index('PROFILE ' + key + '=')
    j = txt.index('=', i) + 1
    depth, k = 0, j
    while k < len(txt):
        if txt[k] == '[':
            depth += 1
        elif txt[k] == ']':
            depth -= 1
            if depth == 0:
                break
        k += 1
    return dict(ast.literal_eval(txt[j:k + 1]))


cells = grab('cells')
stalls = grab('stalls')
grid = [list(l) for l in open(man).read().split('\n')]
gl = lambda p: grid[p[1]][p[0]] if p[1] < len(grid) and p[0] < len(grid[p[1]]) else ' '

work = {p: c - stalls.get(p, 0) for p, c in cells.items()}
tot = sum(work.values())
print(f'total working cell-ticks {tot}   (raw {sum(cells.values())}, stalls {sum(stalls.values())})')

by_glyph = collections.Counter()
for p, w in work.items():
    by_glyph[gl(p)] += w
print('\nwork by glyph (top 14):')
print('  ' + '  '.join(f'{g!r}:{n}' for g, n in by_glyph.most_common(14)))

print('\nhottest cells by real work (top 20):')
for p, w in sorted(work.items(), key=lambda kv: -kv[1])[:20]:
    print(f'  {p} {gl(p)!r:4s} {w}')

# column/row histogram of blank-glide work -- where the walking is
glide = collections.Counter()
for p, w in work.items():
    if gl(p) == ' ':
        glide[p[0]] += w
print('\nblank-glide work by column (top 12):')
print('  ' + '  '.join(f'x={c}:{n}' for c, n in glide.most_common(12)))

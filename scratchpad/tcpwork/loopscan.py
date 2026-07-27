#!/usr/bin/env python3
"""Find how much of forkdecode's main-loop return detour is actually required.

The main man's loop ends at the `Y`; the spawned copy is born facing EAST at
(10,2), glides east to a turn-around column, goes north and comes back west to
the `r` at (8,2). That detour is not waste: it delays the main man so the CLONE
reads `val` (the `r` row) before he reads the next `seq` off the shared input
FIFO. Cutting it to nothing scores 1/6.

This scans the turn-around column to find the true margin, so any shortening we
keep is backed by a measured breaking point rather than a guess.
"""
import json, subprocess, sys

SRC = '/Users/visenbaev/icfpc26/solutions/tcp/forkdecode-24x24.man'
GRADE = '/Users/visenbaev/icfpc26/tools/grade_fast.py'


def variant(k, path):
    g = [list(l) for l in open(SRC).read().rstrip('\n').split('\n')]
    w = max(len(r) for r in g)
    g = [r + [' '] * (w - len(r)) for r in g]
    assert g[1][17] == '<' and g[2][17] == '^', (g[1][17], g[2][17])
    g[1][17] = ' '; g[2][17] = ' '
    g[1][k] = '<'; g[2][k] = '^'
    open(path, 'w').write('\n'.join(''.join(r).rstrip() for r in g) + '\n')


def main():
    for k in range(10, 18):
        p = f'/tmp/fd_k{k}.man'
        variant(k, p)
        out = subprocess.run([sys.executable, GRADE, 'tcp', p],
                             capture_output=True, text=True).stdout.strip().splitlines()
        v = json.loads(out[-1])
        print(f"turn-around col {k:2d}  detour {2*k-16:2d}  "
              f"{v['passed']}/{v['total']}  ticks {v.get('avgTicks')}  score {v.get('score')}")


main()

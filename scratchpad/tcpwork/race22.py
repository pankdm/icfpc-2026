#!/usr/bin/env python3
"""Measure the read-order race in the 22x22 build.

Both the main loop man and each demux clone pull from the SAME input pipe. The
clone must take packet k's value before the main man takes packet k+1's seq.
This reports, per tick, who is standing on an `r` cell and about to move off it
-- i.e. who actually consumes a value, and in what order.

usage: race22.py <file.man> [input] [expected] [ticks]
"""
import json, subprocess, sys

ROOT = '/Users/visenbaev/icfpc26'
LM = ROOT + '/interp/target/release/lm'


def snap(man, t, inp, exp):
    out = subprocess.run([LM, man, f'--inspect={t}', '--input=' + inp,
                          '--expected=' + exp], capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return None


def main():
    man = sys.argv[1]
    inp = sys.argv[2] if len(sys.argv) > 2 else '6 0 100/1 101/2 102'
    exp = sys.argv[3] if len(sys.argv) > 3 else '100/101/102'
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 60
    grid = [list(l) for l in open(man).read().split('\n')]
    gl = lambda x, y: grid[y][x] if y < len(grid) and x < len(grid[y]) else ' '

    prev = {}
    for t in range(1, N + 1):
        d = snap(man, t, inp, exp)
        if d is None:
            print(t, 'no snapshot'); break
        here = {}
        for r in d.get('runners', []):
            if r.get('halted'):
                continue
            here[r['id']] = (tuple(r['pos']), r['a'], r['b'], r['backpack'])
        for rid, (pos, a, b, bp) in prev.items():
            if rid in here and here[rid][0] != pos and gl(*pos) == 'r':
                print(f'tick {t:3d}: runner {rid} consumed at {pos} -> A={here[rid][1]}')
        prev = here
        if str(d.get('end','')).lower() not in ('running','none',''):
            print(t, 'end', d['end'], 'output', d.get('output'))
            break
    else:
        d = snap(man, N, inp, exp)
        print('output so far', d.get('output'))


main()

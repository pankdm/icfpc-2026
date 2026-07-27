#!/usr/bin/env python3
"""Measure the per-op tick cost of a memory .man as a function of rotation.

The belt advances one position per tap, so a stream whose addresses step by
(1 + k) mod 100 costs exactly k rotation positions per op.  Sweeping k and
fitting a line separates the FIXED per-op cost (tap walk + CONTROL loop + pipe
latency) from the ROTATION cost, which is what any packing scheme attacks.

  python3 tickmodel.py <file.man>
"""
import os
import subprocess
import sys

REPO = '/Users/visenbaev/icfpc26'
LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')
N = 40


def run(man, stream, expected):
    p = subprocess.run([LM, '--grade', man,
                        '--input=' + ' '.join(map(str, stream)),
                        '--expected=' + ' '.join(map(str, expected)),
                        '--cap=5000000'], capture_output=True, text=True)
    import json
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    man = os.path.abspath(sys.argv[1])
    base = None
    for k in (0, 1, 2, 3, 5, 6, 11, 12, 25, 50, 99):
        addr, stream = 0, []
        for _ in range(N):
            stream += [0, addr]
            addr = (addr + 1 + k) % 100
        v = run(man, stream, [0] * N)
        t = v.get('settleTick')
        if v.get('status') != 'pass':
            print(f'k={k:>3}  {v.get("status")}')
            continue
        if base is None:
            base, k0 = t, k
        print(f'rot/op={k:>3}  settle={t:>7}  d(vs k=0)={t - base:>7}  '
              f'per-op-delta={(t - base) / N:>7.2f}')


if __name__ == '__main__':
    main()

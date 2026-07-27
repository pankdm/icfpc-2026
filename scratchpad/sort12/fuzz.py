#!/usr/bin/env python3
"""Randomised multi-round fuzz for a sort-numbers .man, plus the edge shapes the
private cases are likely to probe: n=1, n=16, all-equal, all-negative, extremes.

usage: python3 fuzz.py <file.man> [rounds_per_case] [cases]
"""
import json
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LM = os.path.join(ROOT, 'interp', 'target', 'release', 'lm')


def run(man, rounds):
    inp = " / ".join(" ".join(str(v) for v in ([len(r)] + r)) for r in rounds)
    exp = " / ".join(" ".join(str(v) for v in sorted(r)) for r in rounds)
    p = subprocess.run([LM, '--grade', man, '--input=' + inp, '--expected=' + exp,
                        '--cap=6000000'], capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {'status': 'ERR', 'raw': p.stdout[:200] + p.stderr[:200]}


def main():
    man = sys.argv[1]
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    cases = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    random.seed(1234)
    fixed = [
        [[1]], [[16] and list(range(16, 0, -1))], [[-10000] * 16],
        [[10000] * 16], [[0]], [[-1, 1]], [[5, 5, 5, 5, 5, 5, 5, 5]],
        [list(range(1, 17))], [list(range(16, 0, -1))],
        [[1], [1] * 16, [2, 1], [16] * 3],
        [[-10000, 10000, 0, -1, 1], [3, 3, 3], [7]],
    ]
    bad = 0
    for i, rounds in enumerate(fixed):
        r = run(man, rounds)
        if r.get('status') != 'pass':
            bad += 1
            print('FIXED %d FAIL %s ns=%s' % (i, r.get('status'), [len(x) for x in rounds]))
    for c in range(cases):
        rounds = []
        for _ in range(random.randint(2, per)):
            n = random.randint(1, 16)
            lo, hi = random.choice([(-10000, 10000), (-5, 5), (0, 0), (-10000, -9990)])
            rounds.append([random.randint(lo, hi) for _ in range(n)])
        r = run(man, rounds)
        if r.get('status') != 'pass':
            bad += 1
            print('RAND %d FAIL %s ns=%s' % (c, r.get('status'), [len(x) for x in rounds]))
            if bad > 5:
                break
    print('fuzz done: %d failures of %d' % (bad, len(fixed) + cases))


if __name__ == '__main__':
    main()

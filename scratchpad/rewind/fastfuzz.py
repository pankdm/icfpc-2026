#!/usr/bin/env python3
"""Fast fuzz for the memory rewind engine, on the Rust interpreter.

Same stream set as scratchpad/rewind/fuzz.py but each stream is graded with
`lm --grade` instead of the wasm oracle, so 89 streams take seconds not minutes.

  python3 fastfuzz.py <file.man> [nrandom] [--jobs N]
"""
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = '/Users/visenbaev/icfpc26'
LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')


def reference(stream):
    mem, out, i = [0] * 100, [], 0
    while i < len(stream):
        if stream[i] == 0:
            out.append(mem[stream[i + 1]]); i += 2
        else:
            mem[stream[i + 1]] = stream[i + 2]; i += 3
    return out


def streams(nrandom):
    yield 'rot==0 same addr repeated', [0, 7, 0, 7, 1, 7, 5, 0, 7, 0, 7]
    yield 'addr 0 and 99 only', [1, 0, 11, 1, 99, 22, 0, 0, 0, 99, 0, 0, 0, 99]
    yield 'value 0 written', [1, 4, 0, 0, 4, 1, 4, 9, 0, 4, 1, 4, 0, 0, 4]
    yield 'huge negatives', [1, 3, -1000000, 0, 3, 1, 50, -999999, 0, 50, 0, 3]
    yield 'read before any write', [0, 0, 0, 50, 0, 99, 0, 1]
    yield 'writes only, no output', [1, 0, 1, 1, 50, 2, 1, 99, 3]
    yield 'single read', [0, 42]
    yield 'walk every addr', [x for a in range(100) for x in (1, a, a * 7 - 300)] + \
                             [x for a in range(100) for x in (0, a)]
    yield 'max rotation 99 each op', [x for k in range(12)
                                      for x in (0, (k * 99) % 100)]
    # every rotation distance from a fixed base, both parities of address
    yield 'sweep deltas', [x for d in range(100) for x in (0, d)]
    yield 'adjacent pairs', [x for a in range(0, 100, 2)
                             for x in (1, a, a + 1, 1, a + 1, -a - 1, 0, a, 0, a + 1)]
    rnd = random.Random(20260726)
    for i in range(nrandom):
        s, n = [], rnd.randint(1, 60)
        for _ in range(n):
            a = rnd.choice([0, 99, rnd.randrange(100), rnd.randrange(100)])
            if rnd.random() < 0.5:
                s += [1, a, rnd.choice([0, -1000000, 1000000, rnd.randint(-999, 999)])]
            else:
                s += [0, a]
        yield f'random #{i}', s


def run_one(man, name, stream, cap):
    exp = reference(stream)
    cmd = [LM, '--grade', man, '--input=' + ' '.join(map(str, stream)),
           '--expected=' + ' '.join(map(str, exp)), f'--cap={cap}']
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    txt = (p.stdout or '').strip()
    ok = '"status":"pass"' in txt.replace(' ', '')
    return name, ok, txt[:200]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    man = os.path.abspath(args[0])
    nrandom = int(args[1]) if len(args) > 1 else 78
    jobs = 8
    for a in sys.argv[1:]:
        if a.startswith('--jobs'):
            jobs = int(a.split('=')[1])
    cases = list(streams(nrandom))
    bad = []
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for name, ok, txt in ex.map(lambda c: run_one(man, c[0], c[1], 5_000_000), cases):
            if not ok:
                bad.append((name, txt))
    print(f'{len(cases) - len(bad)}/{len(cases)} streams pass')
    for name, txt in bad[:8]:
        print('  FAIL', name, txt)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

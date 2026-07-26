#!/usr/bin/env python3
"""Random-stream fuzz for the `memory` rewind engine, against the real oracle.

Each stream is run as its OWN single-round case: the belt is filled with 100
zeros once at program start, so packing several streams into one program run as
multiple rounds would not re-initialise it and would report bogus failures.

Covers the shapes public cases miss: rot==0 (same address twice in a row),
addr 0 and 99, value 0, huge negative values, read-before-write, and long
random streams that exercise every rotation distance.

  python3 fuzz.py <file.man> [nrandom]
"""
import json, random, subprocess, sys, os

REPO = '/Users/visenbaev/icfpc26'
CASE = os.path.join(REPO, 'sim', 'case.js')


def reference(stream):
    """The problem statement's memory semantics, straight from the spec."""
    mem, out, i = [0] * 100, [], 0
    while i < len(stream):
        op = stream[i]
        if op == 0:
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


def main():
    # The runner is invoked with cwd=REPO (it needs the oracle wasm there), so
    # the .man path must be absolute or it resolves against the wrong tree.
    man = os.path.abspath(sys.argv[1])
    nrandom = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    bad = 0
    for name, stream in streams(nrandom):
        want = reference(stream)
        case = [{'in': [str(v) for v in stream], 'out': [str(v) for v in want]}]
        r = subprocess.run(['node', CASE, man, json.dumps(case)],
                           capture_output=True, text=True, cwd=REPO)
        # The runner can also emit oracle noise (e.g. the Go wasm's
        # "program has already exited" on long runs), so pick the last line
        # that actually parses as a result object rather than assuming line -1.
        j = None
        for line in r.stdout.strip().splitlines():
            try:
                cand = json.loads(line)
            except Exception:
                continue
            if isinstance(cand, dict) and 'status' in cand:
                j = cand
        if j is None:
            print(f'FAIL {name}: no result from runner: '
                  f'{r.stdout[-200:]!r} {r.stderr[-200:]!r}')
            bad += 1
            continue
        got = [str(v) for v in j.get('output', [])]
        if j['status'] != 'pass' or got != [str(v) for v in want]:
            bad += 1
            print(f'FAIL {name} [{j["status"]}] {j.get("reason","")}')
            print(f'   stream  {stream[:24]}{"..." if len(stream) > 24 else ""}')
            print(f'   want {want[:12]}')
            print(f'   got  {got[:12]}')
    total = 9 + nrandom
    print(f'{total - bad}/{total} streams pass')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

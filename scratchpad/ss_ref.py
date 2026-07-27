#!/usr/bin/env python3
"""Reference subset-sum (lex-smallest index set) + test driver for chainfield.

usage:
  python3 scratchpad/ss_ref.py solve 6 "5 3 8 2 9 4" 11
  python3 scratchpad/ss_ref.py run <file.man> <nv> <n> "<values>" <t> [cap]
  python3 scratchpad/ss_ref.py sweep <file.man> <nv> <trials> [seed]
"""
import json
import os
import random
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LM = os.path.join(REPO, "interp", "target", "release", "lm")


def solve(vals, t):
    """Lex-smallest index set == largest mask with bit weight 2^(n-1-i)."""
    n = len(vals)
    best = None
    for mask in range(1 << n):
        s = sum(vals[i] for i in range(n) if mask >> (n - 1 - i) & 1)
        if s == t:
            best = mask
            break_mask = mask
    # descending order: the first hit when iterating masks downward
    for mask in range((1 << n) - 1, -1, -1):
        s = sum(vals[i] for i in range(n) if mask >> (n - 1 - i) & 1)
        if s == t:
            idx = [i for i in range(n) if mask >> (n - 1 - i) & 1]
            return [len(idx)] + [vals[i] for i in idx]
    return [0]


def run(path, nv, vals, t, cap=2000000):
    exp = solve(vals, t)
    inp = " ".join(str(x) for x in [len(vals)] + list(vals) + [t])
    p = subprocess.run([LM, "--grade", path, "--input=" + inp,
                        "--expected=" + " ".join(map(str, exp)), "--cap=%d" % cap],
                       capture_output=True, text=True)
    d = json.loads(p.stdout)
    return exp, d


def actual(path, nv, vals, t, cap=2000000):
    inp = " ".join(str(x) for x in [len(vals)] + list(vals) + [t])
    p = subprocess.run([LM, path, str(cap), "--input=" + inp],
                       capture_output=True, text=True)
    last = p.stdout.strip().split("\n")[-1]
    d = json.loads(last)
    return d.get("output"), d.get("end"), d.get("fatal")


def main():
    cmd = sys.argv[1]
    if cmd == "solve":
        vals = [int(x) for x in sys.argv[3].split()]
        print(solve(vals, int(sys.argv[4])))
    elif cmd == "run":
        path, nv = sys.argv[2], int(sys.argv[3])
        vals = [int(x) for x in sys.argv[5].split()]
        t = int(sys.argv[6])
        cap = int(sys.argv[7]) if len(sys.argv) > 7 else 2000000
        exp, d = run(path, nv, vals, t, cap)
        print("expected", exp, "->", d)
        if d.get("status") != "pass":
            print("got", actual(path, nv, vals, t, cap))
    elif cmd == "sweep":
        path, nv, trials = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1
        rng = random.Random(seed)
        bad = 0
        for k in range(trials):
            n = rng.randint(min(10, nv), nv)
            vals = [rng.randint(1, 40) for _ in range(n)]
            t = rng.randint(5, sum(vals))
            exp, d = run(path, nv, vals, t)
            if d.get("status") != "pass":
                bad += 1
                print("FAIL n=%d vals=%s t=%d exp=%s -> %s" % (n, vals, t, exp, d))
                print("   got", actual(path, nv, vals, t))
                if bad >= 3:
                    break
        print("sweep done, %d failures" % bad)


main()

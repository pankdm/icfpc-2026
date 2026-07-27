#!/usr/bin/env python3
"""Differential fuzz: does straightening the input pipe change any behaviour?

An agent reported that direct-straight.man hangs on repeated same-address
reads.  The server graded it 24/24, so if a hang exists no graded case hits it
— but a latent one still matters for anything built on top.  Run both builds on
the same random streams and compare, rather than trusting either report.

    python3 scratchpad/dm_regress.py [n_cases]
"""
import json
import random
import subprocess
import sys

LM = "interp/target/release/lm"
A = "/tmp/dm.man"                                   # original
B = "solutions/memory/direct-straight.man"          # straightened


def model(tokens):
    """Reference: returns the expected output for an op stream."""
    mem, out, i = [0] * 100, [], 0
    while i < len(tokens):
        if tokens[i] == 0:
            out.append(mem[tokens[i + 1]])
            i += 2
        else:
            mem[tokens[i + 1]] = tokens[i + 2]
            i += 3
    return out


def run(man, tokens, expected):
    r = subprocess.run(
        [LM, "--grade", man,
         "--input=" + " ".join(map(str, tokens)),
         "--expected=" + " ".join(map(str, expected)),
         "--cap=800000"],
        capture_output=True, text=True, timeout=180)
    try:
        return json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        return {"status": "ERROR"}


def gen(rng, shape):
    """Shapes chosen to stress the reported failure mode."""
    t = []
    if shape == "same_addr_reads":
        a = rng.randrange(100)
        for _ in range(rng.randrange(5, 40)):
            t += [0, a]
    elif shape == "write_then_same":
        a = rng.randrange(100)
        t += [1, a, rng.randrange(-1000000, 1000000)]
        for _ in range(rng.randrange(5, 40)):
            t += [0, a]
    elif shape == "same_block":                 # all inside one k25 block
        base = rng.choice([0, 25, 50, 75])
        for _ in range(rng.randrange(5, 30)):
            a = base + rng.randrange(25)
            t += ([0, a] if rng.random() < .5
                  else [1, a, rng.randrange(-1000, 1000)])
    else:                                        # uniform
        for _ in range(rng.randrange(5, 40)):
            a = rng.randrange(100)
            t += ([0, a] if rng.random() < .5
                  else [1, a, rng.randrange(-1000000, 1000000)])
    return t


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    rng = random.Random(20260727)
    shapes = ["same_addr_reads", "write_then_same", "same_block", "uniform"]
    bad = 0
    for k in range(n):
        shape = shapes[k % len(shapes)]
        t = gen(rng, shape)
        exp = model(t)
        if not exp:
            continue
        ra, rb = run(A, t, exp), run(B, t, exp)
        if ra["status"] != rb["status"]:
            bad += 1
            print("DIVERGE [%s] orig=%s straight=%s  ops=%d"
                  % (shape, ra["status"], rb["status"], len(t)))
            print("  tokens:", " ".join(map(str, t))[:160])
        elif rb["status"] != "pass":
            bad += 1
            print("BOTH FAIL [%s] %s  ops=%d" % (shape, rb["status"], len(t)))
    print("%d/%d cases diverged or failed" % (bad, n))


main()

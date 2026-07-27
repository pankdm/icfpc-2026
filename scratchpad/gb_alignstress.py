#!/usr/bin/env python3
"""Generate alignment-invariant stress cases for gradebook and run them.

The lazyalign build relies on: AVG/TOP re-align the belt themselves, GET/SET may
leave it anywhere.  These cases interleave every op ordering so any residual
"belt must be aligned" assumption shows up as a wrong answer.
usage: gb_alignstress.py <file.man>   (writes tests/stress/gradebook-align.json)
"""
import json, random, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
MAN = sys.argv[1] if len(sys.argv) > 1 else \
    f"{REPO}/solutions/gradebook/gradebook-lazyalign.man"
OUT = f"{REPO}/tests/stress/gradebook-align.json"


def make(name, N, K, rounds, seed, order=None):
    rnd = random.Random(seed)
    ids = rnd.sample(range(1000, 10000), N)
    st = {i: [rnd.randint(0, 100) for _ in range(K)] for i in ids}
    rs = [{"in": [str(N), str(K)] + [str(x) for i in ids for x in (i, *st[i])],
           "out": []}]
    for r in range(rounds):
        ops, flat, out = [], [], []
        n = rnd.randint(1, 8)
        for j in range(n):
            kind = order[(r * 8 + j) % len(order)] if order else rnd.randint(1, 4)
            if kind == 1:
                ops.append((1, rnd.choice(ids), rnd.randint(1, K)))
            elif kind == 2:
                ops.append((2, rnd.choice(ids), rnd.randint(1, K), rnd.randint(0, 100)))
            else:
                ops.append((kind, rnd.randint(1, K)))
        flat.append(str(len(ops)))
        for op in ops:
            flat += [str(x) for x in op]
            if op[0] == 1:
                out.append(str(st[op[1]][op[2] - 1]))
            elif op[0] == 2:
                st[op[1]][op[2] - 1] = op[3]
            elif op[0] == 3:
                s = op[1]
                out.append(str(sum(st[i][s - 1] for i in ids) // N))
            else:
                s = op[1]
                best = max(st[i][s - 1] for i in ids)
                out.append(str(min(i for i in ids if st[i][s - 1] == best)))
        rs.append({"in": flat, "out": out})
    return {"name": name, "rounds": rs}


cases = []
# every 2-op ordering of the four op kinds, so each op runs right after each other op
for a in (1, 2, 3, 4):
    for b in (1, 2, 3, 4):
        cases.append(make(f"order {a}->{b} N=16 K=4", 16, 4, 6, 100 * a + b, [a, b]))
for a in (1, 2, 3, 4):
    for b in (1, 2, 3, 4):
        cases.append(make(f"order {a}->{b} N=4 K=1", 4, 1, 6, 900 + 10 * a + b, [a, b]))
for i, (N, K) in enumerate([(4, 4), (5, 3), (7, 2), (11, 1), (13, 4), (16, 2), (16, 1), (4, 3)]):
    cases.append(make(f"random N={N} K={K}", N, K, 10, 4242 + i))

json.dump({"cases": cases}, open(OUT, "w"))
print(f"wrote {OUT}: {len(cases)} cases")

p = subprocess.run(["node", f"{REPO}/tools/grade_json.js", "gradebook", MAN,
                    "--cases", OUT], capture_output=True, text=True, cwd=REPO)
d = json.loads(p.stdout.strip().splitlines()[-1])
# public cases are included by grade_json; report only totals + failures
print(d["passed"], "/", d["total"])
for r in d["results"]:
    if r["status"] != "pass":
        print("  FAIL", r["name"], r.get("status"), r.get("reason"))

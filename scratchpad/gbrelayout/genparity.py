#!/usr/bin/env python3
"""Generate a gradebook case suite that hammers the roster-count parity path.

count = N*(K+1) is odd exactly when N is odd and K is even, which is the branch
the pair-read loop takes only on its final iteration.  Cover every (N odd, K in
{2,4}) plus the even neighbours, each with all four ops over several rounds.

  python3 scratchpad/gbrelayout/genparity.py > tests/stress/gradebook-parity.json
"""
import json, random

random.seed(20260727)


def make(n, k, rounds=3):
    ids = random.sample(range(1000, 10000), n)
    grades = {i: [random.randint(0, 100) for _ in range(k)] for i in ids}
    rs = [{"in": [str(n), str(k)] + [str(x) for i in ids for x in [i] + grades[i]], "out": []}]
    for _ in range(rounds):
        ops, out = [], []
        for _ in range(random.randint(1, 8)):
            op = random.randint(1, 4)
            s = random.randint(1, k)
            if op == 1:
                i = random.choice(ids)
                ops += ["1", str(i), str(s)]
                out.append(str(grades[i][s - 1]))
            elif op == 2:
                i, v = random.choice(ids), random.randint(0, 100)
                ops += ["2", str(i), str(s), str(v)]
                grades[i][s - 1] = v
            elif op == 3:
                ops += ["3", str(s)]
                out.append(str(sum(grades[i][s - 1] for i in ids) // n))
            else:
                ops += ["4", str(s)]
                best = max(grades[i][s - 1] for i in ids)
                out.append(str(min(i for i in ids if grades[i][s - 1] == best)))
        rs.append({"in": [str(len(ops) and sum(1 for _ in []) or 0)], "out": out})
        # recount ops properly: number of operations, not tokens
        cnt = 0
        j = 0
        while j < len(ops):
            o = int(ops[j])
            j += {1: 3, 2: 4, 3: 2, 4: 2}[o]
            cnt += 1
        rs[-1]["in"] = [str(cnt)] + ops
    return rs


cases = []
for n in [5, 7, 9, 11, 13, 15]:
    for k in [2, 4]:
        cases.append({"name": "odd count N=%d K=%d (%d values)" % (n, k, n * (k + 1)),
                      "rounds": make(n, k)})
for n, k in [(4, 1), (16, 4), (5, 1), (9, 3), (16, 1), (15, 4), (13, 2)]:
    cases.append({"name": "N=%d K=%d (%d values)" % (n, k, n * (k + 1)),
                  "rounds": make(n, k)})
print(json.dumps({"cases": cases}))

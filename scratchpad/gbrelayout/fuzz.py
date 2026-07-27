#!/usr/bin/env python3
"""Randomized gradebook cases with a reference model, over the full constraint box.

  4 <= N <= 16, 1 <= K <= 4, ids distinct in 1000..9999, grades 0..100,
  1-10 batch rounds, 1-8 ops per batch, one roster per case.

Deliberately over-samples the shapes today's changes touched:
  * N*(K+1) odd (the roster pair-read's final single-value pass)
  * grade 0 and grade 100 (the id/grade classifier's boundaries)
  * ties for TOP (smallest id wins) and repeated demotion via SET
  * ids at 1000 and 9999 (the XOR compare in GET/SET)

  python3 scratchpad/gbrelayout/fuzz.py <n-cases> <seed> > tests/stress/<f>.json
"""
import json, random, sys

NCASES = int(sys.argv[1]) if len(sys.argv) > 1 else 60
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 1)

ARITY = {1: 3, 2: 4, 3: 2, 4: 2}


def case(idx):
    n = random.randint(4, 16)
    k = random.randint(1, 4)
    if idx % 3 == 0:                       # force an odd roster length
        n |= 1
        k = random.choice([2, 4])
    ids = random.sample(range(1000, 10000), n)
    if idx % 5 == 0:
        ids[0], ids[-1] = 1000, 9999
    def g():
        return random.choice([0, 0, 100, 100, random.randint(0, 100)])
    grades = {i: [g() for _ in range(k)] for i in ids}
    if idx % 4 == 0:                       # everyone tied on subject 1
        for i in ids:
            grades[i][0] = 77
    rounds = [{"in": [str(n), str(k)] + [str(x) for i in ids for x in [i] + grades[i]],
               "out": []}]
    for _ in range(random.randint(1, 10)):
        ops, out = [], []
        for _ in range(random.randint(1, 8)):
            op = random.randint(1, 4)
            s = random.randint(1, k)
            if op == 1:
                i = random.choice(ids)
                ops += ["1", str(i), str(s)]
                out.append(str(grades[i][s - 1]))
            elif op == 2:
                i, v = random.choice(ids), g()
                ops += ["2", str(i), str(s), str(v)]
                grades[i][s - 1] = v
            elif op == 3:
                ops += ["3", str(s)]
                out.append(str(sum(grades[i][s - 1] for i in ids) // n))
            else:
                ops += ["4", str(s)]
                best = max(grades[i][s - 1] for i in ids)
                out.append(str(min(i for i in ids if grades[i][s - 1] == best)))
        cnt, j = 0, 0
        while j < len(ops):
            j += ARITY[int(ops[j])]
            cnt += 1
        rounds.append({"in": [str(cnt)] + ops, "out": out})
    return {"name": "fuzz%02d N=%d K=%d count=%d" % (idx, n, k, n * (k + 1)),
            "rounds": rounds}


print(json.dumps({"cases": [case(i) for i in range(NCASES)]}))

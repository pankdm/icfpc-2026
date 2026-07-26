#!/usr/bin/env python3
"""Op-kind mix + predicted tick attribution for the gradebook public cases."""
import json

spec = json.load(open("/Users/visenbaev/icfpc26/tests/gradebook.json"))
ARITY = {1: 2, 2: 3, 3: 1, 4: 1}
NAME = {1: "GET", 2: "SET", 3: "AVG", 4: "TOP"}

tot = {k: 0 for k in NAME}
for tc in spec["publicTestData"]:
    rs = tc["rounds"]
    roster = [int(x) for x in rs[0]["in"]]
    N, K = roster[0], roster[1]
    cnt = {k: 0 for k in NAME}
    for r in rs[1:]:
        v = [int(x) for x in r["in"]]
        i, O = 1, v[0]
        for _ in range(O):
            op = v[i]
            cnt[op] += 1
            tot[op] += 1
            i += 1 + ARITY[op]
    print(f"{tc['name']:26s} N={N:2d} K={K} " +
          " ".join(f"{NAME[k]}={cnt[k]:2d}" for k in NAME))
print("TOTAL " + " ".join(f"{NAME[k]}={tot[k]}" for k in NAME))

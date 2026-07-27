#!/usr/bin/env python3
"""Build tests/sort-stress.json = sort-numbers public cases + stress suite + extra edge
cases, so `python3 tools/grade_fast.py sort-stress <f.man>` gates on generality."""
import json, os, random

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = json.load(open(os.path.join(REPO, "tests", "sort-numbers.json")))
stress = json.load(open(os.path.join(REPO, "tests", "stress", "sort-numbers.json")))
cases = list(spec.get("publicTestData") or []) + list(stress.get("cases") or [])


def mk(name, rounds):
    return {"name": name, "rounds": [{"in": [str(len(r))] + [str(v) for v in r],
                                      "out": [str(v) for v in sorted(r)]} for r in rounds]}


rng = random.Random(20260726)
extra = []
# n=16 in every arrangement that stresses the ring/settling
extra.append(mk("n16 x6 random", [[rng.randint(-10000, 10000) for _ in range(16)] for _ in range(6)]))
extra.append(mk("n16 all equal x6", [[7] * 16 for _ in range(6)]))
extra.append(mk("n16 reverse x6", [list(range(16, 0, -1)) for _ in range(6)]))
extra.append(mk("n16 sorted x6", [list(range(-8, 8)) for _ in range(6)]))
extra.append(mk("n16 extremes", [[-10000, 10000] * 8, [10000] * 16, [-10000] * 16]))
extra.append(mk("n16 then n1 then n16", [[rng.randint(-10000, 10000) for _ in range(16)],
                                         [5],
                                         [rng.randint(-10000, 10000) for _ in range(16)]]))
extra.append(mk("varying lengths", [[3, 1, 2], [9] * 16, [0], [-1, -1], list(range(16))[::-1],
                                    [4, 4, 4, 4, 4]]))
extra.append(mk("n1 x6", [[rng.randint(-10000, 10000)] for _ in range(6)]))
extra.append(mk("n2 x6", [[rng.randint(-10000, 10000) for _ in range(2)] for _ in range(6)]))
extra.append(mk("dup heavy n16", [[rng.choice([-3, 0, 3]) for _ in range(16)] for _ in range(6)]))
for k in range(6):
    extra.append(mk(f"rand mixed {k}",
                    [[rng.randint(-10000, 10000) for _ in range(rng.randint(1, 16))]
                     for _ in range(rng.randint(2, 6))]))
cases += extra
spec["publicTestData"] = cases
spec["name"] = "Sort (stress)"
json.dump(spec, open(os.path.join(REPO, "tests", "sort-stress.json"), "w"))
print("cases:", len(cases))

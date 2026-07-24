#!/usr/bin/env python3
"""Branch-and-bound DFS model for the ICFPC-2026 subset-sum problem.

This is the reference algorithm the littleman machine `ss-dfs.man` realizes.
It is validated against all 7 public cases (parsed from the oracle JSON).

Algorithm (all values positive):
  DFS over indices 0..n-1, running sum `s`, suffix sums `suf`.
  At index i: try INCLUDE i first, then EXCLUDE i.
    - prune (overshoot):  s + v[i] > target  -> skip include branch
    - prune (can't-reach): s + suf[i] < target -> prune whole node
  First complete solution found (s == target) is the lexicographically
  smallest index set, because we walk indices low->high preferring include.
  Emit chosen values in index order; emit `0` if none.
"""
import json
import os
import sys


def solve(values, target):
    n = len(values)
    # suffix sums: suf[i] = sum(values[i:]);  suf[n] = 0
    suf = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suf[i] = suf[i + 1] + values[i]

    chosen = [False] * n
    result = {"found": False, "nodes": 0}

    def dfs(i, s):
        result["nodes"] += 1
        if s == target:
            result["found"] = True
            return True
        if i == n:
            return False
        # prune 2: can't reach even taking everything remaining
        if s + suf[i] < target:
            return False
        # INCLUDE branch first (prune 1: overshoot)
        if s + values[i] <= target:
            chosen[i] = True
            if dfs(i + 1, s + values[i]):
                return True
            chosen[i] = False
        # EXCLUDE branch
        if dfs(i + 1, s):
            return True
        return False

    dfs(0, 0)
    if not result["found"]:
        return [], result["nodes"]
    out = [values[i] for i in range(n) if chosen[i]]
    return out, result["nodes"]


def load_cases(path):
    d = json.load(open(path))
    ptd = d["publicTestData"]
    cases = []
    for c in ptd:
        r = c["rounds"][0]
        ints = [int(x) for x in r["in"]]
        n = ints[0]
        values = ints[1 : 1 + n]
        target = ints[1 + n]
        expected = [int(x) for x in r["out"]]
        cases.append((c["name"], values, target, expected))
    return cases


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        here, "..", "..", "scratchpad", "ss_problem.json")
    cases = load_cases(path)
    all_ok = True
    for name, values, target, expected in cases:
        out, nodes = solve(values, target)
        got = [len(out)] + out
        ok = got == expected
        all_ok &= ok
        print(f"[{'OK ' if ok else 'FAIL'}] {name:32s} n={len(values):2d} "
              f"nodes={nodes:7d}  got={got}")
        if not ok:
            print(f"        expected={expected}")
    print("\nALL PASS" if all_ok else "\nSOME FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

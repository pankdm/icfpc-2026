#!/usr/bin/env python3
"""Guess the board leader's footprint & avg-ticks from their composite score.

For footprint-tick problems: score = m^2 * (total_ticks / casesTotal), so
  score * casesTotal = m^2 * total_ticks   (exact integer),
i.e. m (max program dimension) must have m^2 dividing that product. We enumerate
feasible m and report each (m x m, avgTicks) with an integer total_ticks, filtered
by the HARD tick cap (avgTicks <= cap; the run dies at the cap) and avgTicks >= 1.
For footprint-only problems: score = m^2 directly, so m = sqrt(score).

Same score = several decompositions in general; narrow by what physically fits
(two 3x3 I/O rooms + compute usually need m>=8; storage/round-heavy problems need
more ticks -> larger m). The tick cap alone often forces a large minimum footprint.

  python3 tools/decompose.py [slug ...]
"""
import sys
import os
import json
import math
import lib

M_MAX = 66
TOL = 0.02
DEFAULT_CAP = 5_000_000


def cached_spec(slug):
    p = os.path.join(lib.REPO, "tests", f"{slug}.json")
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    return lib.fetch_problem(slug) or {}


def main():
    slugs = sys.argv[1:]
    probs = [p for p in lib.list_problems() if p.get("status") != "practice"]
    if slugs:
        probs = [p for p in probs if p["slug"] in slugs]
    probs.sort(key=lambda p: (p.get("problemSetName") or "", p.get("orderInSet") or 0))
    for p in probs:
        st = lib.problem_standings(p["id"])
        full = [r for r in (st or {}).get("rows", []) if r.get("rank") is not None and r.get("score") is not None]
        if not full:
            print(f"\n{p['name']}: no full-solver on the board yet")
            continue
        best = min(full, key=lambda r: r["score"])
        score, cases = best["score"], best["casesTotal"]
        spec = cached_spec(p["slug"])
        scoring = spec.get("scoring", "footprint-tick")
        cap = spec.get("tickCap") or DEFAULT_CAP

        if scoring == "footprint":
            m = math.isqrt(round(score))
            exact = "" if m * m == round(score) else "  (~, not a perfect square?)"
            print(f"\n{p['name']}  [footprint-only]  board-best {score:g}  ->  {m}x{m}{exact}")
            continue

        prod = score * cases
        cands = []
        for m in range(3, M_MAX + 1):
            tt = prod / (m * m)
            if abs(tt - round(tt)) <= TOL and round(tt) >= 1:
                avg = round(tt) / cases
                if 1 <= avg <= cap:
                    cands.append((m, m * m, avg))
        print(f"\n{p['name']}  (board-best {score:g}, {cases} cases, {len(full)} solvers, cap {cap:,})")
        if not cands:
            print("  no clean square factorization within the tick cap")
            continue
        for m, box, avg in cands:
            print(f"    {m}x{m} (footprint {box:>5})  x  {avg:>12,.2f} avg ticks")
    print("\nSame score => several rows possible. Narrow by: fit (m>=8 for two I/O rooms),")
    print("and work (avgTicks must exceed the per-case workload, e.g. >= input length).")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""For each problem: how many RANKS (=points) do we gain per Nx score improvement?"""
import os, sys
sys.path.insert(0, "/Users/dmitrykorolev/projects/icfpc-2026/tools")
import lib

TEAM = "Snakes, Monkeys, and Two Smoking Lambdas"
FACTORS = [1.5, 2, 3, 5, 10, 30, 100]

rows_out = []
for p in [q for q in lib.list_problems() if q.get("status") != "practice"]:
    st = lib.problem_standings(p["id"]) or {}
    board = st.get("rows") or []
    mine = next((r for r in board if (r.get("teamName") or "") == TEAM), None)
    if not mine or mine.get("rank") is None: continue
    full = [r for r in board if r.get("rank") is not None and r.get("score") is not None
            and r.get("casesPassed") == r.get("casesTotal")]
    field = len([r for r in board if r.get("rank") is not None])
    my = mine["score"]; myrank = mine["rank"]
    per_rank = 1.0/(field-1)
    # scores strictly better (lower) than ours among full solvers
    better = sorted([r["score"] for r in full if r["score"] < my])
    gains = []
    for f in FACTORS:
        target = my / f
        # how many teams would we pass
        passed = sum(1 for s in better if s > target)
        gains.append(passed * per_rank)
    rows_out.append((p.get("name") or p["slug"], myrank, field, per_rank, gains, my, better[:1]))

rows_out.sort(key=lambda r: -max(r[4]))
hdr = f"{'problem':20}{'rank':>8}{'pts/rank':>9}" + "".join(f"{('+'+str(f)+'x'):>8}" for f in FACTORS)
print(hdr); print("-"*len(hdr))
for name, rk, field, pr, gains, my, best in rows_out:
    print(f"{name[:19]:20}{str(rk)+'/'+str(field):>8}{pr:>9.4f}" + "".join(f"{g:>8.2f}" for g in gains))
print("-"*len(hdr))
print(f"{'TOTAL':20}{'':8}{'':9}" + "".join(f"{sum(r[4][i] for r in rows_out):>8.2f}" for i in range(len(FACTORS))))

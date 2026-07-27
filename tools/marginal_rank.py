#!/usr/bin/env python3
"""marginal_rank.py — what is a speedup on ONE problem actually worth in points?

`tools/ours.py` shows the gap to the leader, which is the wrong number to optimise:
ranking points are `(other eligible teams ranked below or tied) / (other eligible teams)`,
so what pays is how densely the field is packed just BELOW our score, not how far the
leader is. A 10x on a problem where nobody sits between us and the leader is worth almost
nothing; a 1.25x into a cluster of four teams is worth four ranks.

  python3 tools/marginal_rank.py <slug> [our_score]

Prints, for a range of speedup factors, the rank and ranking points we would reach, plus
the scores of the teams immediately above us (the ones an improvement would overtake).
Only teams passing every case are ranked on score, so only those are counted.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

FACTORS = (1.1, 1.25, 1.5, 2, 3, 5, 10)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    slug = sys.argv[1]
    problem = lib.fetch_problem(slug)
    if not problem:
        sys.exit(f"no such problem: {slug}")
    standings = lib.problem_standings(problem["id"])
    if not standings:
        sys.exit("standings unavailable")
    rows = standings.get("rows", standings if isinstance(standings, list) else [])
    full = sorted(r["score"] for r in rows
                  if r.get("score") and r.get("casesPassed") == r.get("casesTotal"))
    if not full:
        sys.exit("no full-passing teams")
    n = len(full)

    ours = float(sys.argv[2]) if len(sys.argv) > 2 else None
    if ours is None:
        mine = [r for r in rows if r.get("teamName", "").startswith("Snakes")]
        if not mine or not mine[0].get("score"):
            sys.exit("pass our score explicitly (team row not found)")
        ours = float(mine[0]["score"])

    def rank_pts(score):
        rank = sum(1 for s in full if s < score) + 1
        below = sum(1 for s in full if s > score)
        ties = sum(1 for s in full if s == score) - 1
        return rank, 1.0 + (below + max(ties, 0)) / (n - 1)

    r0, p0 = rank_pts(ours)
    print(f"{slug}: {n} full-passing teams; ours {ours:,.0f} -> rank {r0}/{n}, {p0:.3f} pts")
    for f in FACTORS:
        r, p = rank_pts(ours / f)
        print(f"  {f:5.2f}x -> {ours / f:>15,.0f}  rank {r:3d}  {p:.3f} pts  (+{p - p0:.3f})")
    r, p = rank_pts(full[0] * 0.999)
    print(f"  best  -> {full[0]:>15,.0f}  rank {r:3d}  {p:.3f} pts  (+{p - p0:.3f})")
    above = [s for s in full if s < ours][-10:]
    print("  teams to overtake next: " + ", ".join(f"{s:,.0f}" for s in reversed(above)))


if __name__ == "__main__":
    main()

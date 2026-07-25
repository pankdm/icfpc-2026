#!/usr/bin/env python3
"""Where WE stand, per problem — the "what to optimize next" dashboard.

Reads the public standings (no auth needed) and reports, for every graded problem:
our score and cases, our rank among full-solvers, the board best, how far off we are,
and the contest points we are currently earning vs. the 2.0 available.

  python3 tools/ours.py [--team "<name>"] [--sort gap|points|name]

Points model (from PROBLEM.md): per problem you get
  case points  = passed / total                     (max 1.0)
  rank points  = other eligible teams ranked below or tied / other eligible teams
so the biggest wins are problems where we pass few cases, or where we pass everything
but sit near the bottom of the full-solver ranking.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

TEAM = "Snakes, Monkeys, and Two Smoking Lambdas"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", default=TEAM)
    ap.add_argument("--sort", choices=("gap", "points", "name"), default="gap")
    args = ap.parse_args()

    problems = [p for p in lib.list_problems() if p.get("status") != "practice"]
    rows = []
    for p in problems:
        st = lib.problem_standings(p["id"]) or {}
        board = st.get("rows") or []
        mine = next((r for r in board if (r.get("teamName") or "") == args.team), None)
        full = [r for r in board if r.get("rank") is not None and r.get("score") is not None]
        best = min((r["score"] for r in full), default=None)
        total = max((r.get("casesTotal") or 0) for r in board) if board else 0
        passed = (mine or {}).get("casesPassed")
        score = (mine or {}).get("score")
        rank = (mine or {}).get("rank")

        # Points, matching the official dashboard exactly:
        #   rank_pts  = (fieldSize - rank) / (fieldSize - 1)   [verified against /dashboard]
        #   ELIGIBILITY: a null rank means we passed no PRIVATE case, and an ineligible team
        #   scores ZERO on that problem — passing every public case is worth nothing by
        #   itself. That is why a partial solve (Snake 5/17, Pathfinder 7/18) earns 0.00.
        field = len([r for r in board if r.get("rank") is not None])
        eligible = rank is not None
        case_pts = (passed / total) if (eligible and passed and total) else 0.0
        rank_pts = ((field - rank) / (field - 1)) if (eligible and field > 1) else (1.0 if eligible else 0.0)
        rows.append({
            "name": p.get("name") or p["slug"], "slug": p["slug"],
            "passed": passed, "total": total, "score": score, "rank": rank,
            "best": best, "solvers": len([r for r in board if r.get("rank") is not None]),
            "ratio": (score / best) if (score and best) else None,
            "points": case_pts + rank_pts,
        })

    key = {"gap": lambda r: -(2.0 - r["points"]),
           "points": lambda r: r["points"],
           "name": lambda r: r["name"]}[args.sort]
    rows.sort(key=key)

    print(f"team: {args.team}\n")
    print(f"{'problem':22}{'cases':>9}{'our score':>16}{'board best':>15}{'x off':>8}{'rank':>7}{'pts':>7}{'lost':>7}")
    print("-" * 91)
    lost_total = 0.0
    for r in rows:
        cases = f"{r['passed']}/{r['total']}" if r["passed"] is not None else f"-/{r['total']}"
        score = f"{r['score']:,.0f}" if r["score"] else "-"
        best = f"{r['best']:,.0f}" if r["best"] else "-"
        ratio = f"{r['ratio']:.1f}x" if r["ratio"] else "-"
        rank = f"{r['rank']}/{r['solvers']}" if r["rank"] else f"-/{r['solvers']}"
        lost = 2.0 - r["points"]
        lost_total += lost
        print(f"{r['name'][:21]:22}{cases:>9}{score:>16}{best:>15}{ratio:>8}{rank:>7}"
              f"{r['points']:>7.2f}{lost:>7.2f}")
    print("-" * 91)
    print(f"{'TOTAL':22}{'':9}{'':16}{'':15}{'':8}{'':7}"
          f"{sum(r['points'] for r in rows):>7.2f}{lost_total:>7.2f}")
    print("\n'lost' = points still available on that problem (2.0 - earned). Sorted worst-first.")


if __name__ == "__main__":
    main()

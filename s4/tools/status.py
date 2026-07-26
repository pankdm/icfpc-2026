#!/usr/bin/env python3
"""Live server standings per graded problem: best (lowest) score on the board, how
many teams fully solved it, and the true total case count (public + private, which
the per-problem API masks). API-only, no auth.

  python3 tools/status.py
"""
import lib


def main():
    probs = lib.list_problems()
    graded = [p for p in probs if p.get("status") != "practice"]
    graded.sort(key=lambda p: (p.get("problemSetName") or "", p.get("orderInSet") or 0))
    print(f"{'problem':27} {'set':12} {'board-best':>12} {'solvers':>8} {'cases':>7}")
    print("-" * 74)
    for p in graded:
        st = lib.problem_standings(p["id"])
        best, solvers, total = "-", 0, "?"
        if st and isinstance(st.get("rows"), list):
            # full passers only — the board's cheapest scores are partial-passers (see ours.py)
            full = [r for r in st["rows"] if r.get("rank") is not None and r.get("score") is not None
                    and r.get("casesPassed") == r.get("casesTotal")]
            solvers = len(full)
            if full:
                best = round(min(r["score"] for r in full), 2)
            if st["rows"]:
                total = max((r.get("casesTotal") or 0) for r in st["rows"])
        print(f"{(p.get('name') or p['slug']):27} {(p.get('problemSetName') or ''):12} {str(best):>12} {solvers:>8} {'->'+str(total):>7}")
    print("\n(best = lowest footprint^2 x ticks among full-solvers; cases = public+private total)")


if __name__ == "__main__":
    main()

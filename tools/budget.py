#!/usr/bin/env python3
"""budget.py — what (box, avgTicks) would it take to beat the leader, per problem?

Score is max(w,h)^2 x avgTicks, so for any problem the leader's score defines a
HYPERBOLA of acceptable (box, ticks) pairs. This prints, for each problem:
our current split, the leader, and the ticks we would need at a few candidate
box sizes -- which is the input to a budget-aware redesign.

Our box comes from the committed champion .man (solutions/<slug>/champion-*.man);
avgTicks is derived as score/box, since the dashboard reports only the product.

  python3 tools/budget.py [--slug X] [--boxes 10000,14400,22500]
"""
import argparse, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

TEAM = "Snakes, Monkeys, and Two Smoking Lambdas"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def box_of(path):
    rows = [l.rstrip("\n") for l in open(path, encoding="utf-8", errors="replace")]
    nz = [(i, l) for i, l in enumerate(rows) if l.strip()]
    if not nz:
        return None
    lo = min(len(l) - len(l.lstrip()) for _, l in nz)
    hi = max(len(l.rstrip()) for _, l in nz)
    w, h = hi - lo, nz[-1][0] - nz[0][0] + 1
    return w, h, max(w, h) ** 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--boxes", default="")
    args = ap.parse_args()

    rows = []
    for p in [q for q in lib.list_problems() if q.get("status") != "practice"]:
        slug = p["slug"]
        if args.slug and slug != args.slug:
            continue
        st = lib.problem_standings(p["id"]) or {}
        board = st.get("rows") or []
        mine = next((r for r in board if (r.get("teamName") or "") == TEAM), None)
        full = [r for r in board if r.get("rank") is not None and r.get("score") is not None
                and r.get("casesPassed") == r.get("casesTotal")]
        best = min((r["score"] for r in full), default=None)
        if not mine or not mine.get("score") or not best:
            continue
        champs = glob.glob(f"{REPO}/solutions/{slug}/champion-*.man")
        b = box_of(champs[0]) if champs else None
        rows.append((p.get("name") or slug, slug, mine["score"], best, b))

    rows.sort(key=lambda r: -(r[2] / r[3]))
    for name, slug, score, best, b in rows:
        gap = score / best
        print(f"\n=== {name}  ({slug})   {gap:,.1f}x off the leader")
        if b:
            w, h, box = b
            ticks = score / box
            print(f"    ours   {w}x{h} box={box:,}  x avgTicks {ticks:,.0f}  = {score:,.0f}")
        else:
            box = None
            print(f"    ours   box unknown (no champion-*.man committed)  score {score:,.0f}")
        print(f"    leader {best:,.0f}")
        cand = [int(x) for x in args.boxes.split(",") if x] or (
            [box, box // 2, box // 4, 22500, 14400, 10000] if box else [22500, 14400, 10000])
        seen = set()
        print(f"      {'box':>12} {'side':>6} {'avgTicks needed':>18}  {'vs our ticks':>13}")
        for c in sorted({c for c in cand if c and c > 0}, reverse=True):
            if c in seen:
                continue
            seen.add(c)
            need = best / c
            rel = f"{(score/box)/need:,.1f}x faster" if box else "-"
            print(f"      {c:>12,} {int(c**0.5):>6} {need:>18,.0f}  {rel:>13}")


if __name__ == "__main__":
    main()

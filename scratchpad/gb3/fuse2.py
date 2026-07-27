#!/usr/bin/env python3
"""fuse2.py — generalised walkfold `fuse`: the RETURN row may carry ops.

walkfold.plan_fuse only fires when the middle row of a hairpin triple is a pure return
(exactly two turn glyphs).  On gradebook every return row carries work, so it finds zero
candidates.  Here the middle row's ops are lifted onto row A as well, in their EXECUTION
order (the W row runs east->west, so its ops are read in decreasing column order and then
re-placed in increasing columns).  Arithmetic ops may take any column; r/s/q must stay
inside their pipe band.

Three rows (A, return, B) collapse into one; `walkfold squash` then deletes the two empty
rows, so every accepted fusion is -2 height.

usage: fuse2.py <in.man> <out.man> [--rounds N] [--limit N] [-v]
"""
import sys, os, argparse

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)


def plan(g, succ, room=0, verbose=False):
    st = wf.state_map(succ)
    tab, pure, _, _ = wf.bands(g, room)
    if not pure:
        print("  room attachments are not pure-column; abort")
        return []
    (rx0, ry0), (rx1, ry1) = g.rooms[room]["min"], g.rooms[room]["max"]
    plans, refused = [], []

    def priv(cell, dirs):
        return st.get(cell, set()) <= set(dirs)

    def movable(ch):
        return not (ch in wf.BRANCH or ch == "`" or ch in wf.TURNS or ch in "@HY")

    for yA in range(ry0 + 1, ry1 - 2):
        cA = [x for x in range(rx0 + 1, rx1)
              if g.at(x, yA) == "v" and priv((x, yA), [E])]
        if len(cA) != 1:
            refused.append((yA, f"row A has {len(cA)} private E-reached 'v'"))
            continue
        cA = cA[0]
        if g.at(cA, yA + 1) != "<" or not priv((cA, yA + 1), [S]):
            refused.append((yA, f"below 'v'@{cA} is {g.at(cA, yA+1)!r} dirs={sorted(st.get((cA,yA+1),()))}"))
            continue
        ret = [x for x in range(rx0 + 1, rx1) if g.at(x, yA + 1) != " "]
        t = min(ret)
        if t >= cA or g.at(t, yA + 1) != "v" or not priv((t, yA + 1), [W]):
            refused.append((yA, "return row has no private 'v' terminator"))
            continue
        # the return row's own ops: strictly between t and cA, private to W, movable
        rops = []
        bad = False
        for x in range(cA - 1, t, -1):
            ch = g.at(x, yA + 1)
            if ch == " ":
                if not priv((x, yA + 1), [W, N, S]):
                    bad = True
                continue
            if not movable(ch) or not priv((x, yA + 1), [W]):
                bad = True
                break
            rops.append((x, ch))
        if bad:
            refused.append((yA, "return row holds an immovable or shared glyph"))
            continue
        if g.at(t, yA + 2) != ">" or not priv((t, yA + 2), [S]):
            continue
        bcells = [x for x in range(t + 1, rx1) if g.at(x, yA + 2) != " "]
        if not bcells:
            refused.append((yA, "row B is empty"))
            continue
        cB = max(bcells)
        if any(not priv((x, yA + 2), [E, N, S]) for x in range(t + 1, cB + 1)):
            refused.append((yA, "row B is shared"))
            continue
        if g.at(cB, yA + 2) not in wf.VERT or not priv((cB, yA + 2), [E]):
            refused.append((yA, "row B has no private vertical terminator"))
            continue
        bops = [(x, g.at(x, yA + 2)) for x in bcells if x != cB]
        if any(not movable(ch) for _, ch in bops):
            refused.append((yA, "row B holds a branch/literal/turn"))
            continue
        ops = [ch for _, ch in rops] + [ch for _, ch in bops]

        acols = [x for x in range(rx0 + 1, rx1) if g.at(x, yA) != " "]
        cur = max(acols)
        place, ok = [], True
        for ch in ops:
            lo, hi = wf.op_band(g, tab, ch, (cur, yA), room)
            nx = max(cur + 1, lo)
            while nx <= hi and (g.at(nx, yA) != " " or not priv((nx, yA), [E])):
                nx += 1
            if nx > hi:
                ok = False
                break
            place.append((nx, ch))
            cur = nx
        if not ok:
            refused.append((yA, f"no increasing in-band assignment for {ops}"))
            continue
        # terminator column: at or east of everything placed, and clear on row yA
        term = max(cB, cur + 1)
        while term < rx1 and (g.at(term, yA) != " " or not priv((term, yA), [E, N, S])):
            term += 1
        if term >= rx1:
            refused.append((yA, "no free terminator column"))
            continue
        if any(g.at(x, yA) != " " or not priv((x, yA), [E, N, S])
               for x in range(cA + 1, term + 1) if x not in {c for c, _ in place}):
            refused.append((yA, "destination row is not clear"))
            continue
        plans.append({"yA": yA, "cA": cA, "t": t, "term": term,
                      "place": place, "glyph": g.at(cB, yA + 2),
                      "rcols": [x for x, _ in rops], "bcols": bcells})
    if verbose:
        for y, why in refused:
            print(f"    refused row {y}: {why}")
    return plans


def patch_of(p):
    patch = {}
    patch[f"{p['cA']},{p['yA']}"] = " "
    patch[f"{p['cA']},{p['yA'] + 1}"] = " "
    patch[f"{p['t']},{p['yA'] + 1}"] = " "
    patch[f"{p['t']},{p['yA'] + 2}"] = " "
    for x in p["rcols"]:
        patch[f"{x},{p['yA'] + 1}"] = " "
    for x in p["bcols"]:
        patch[f"{x},{p['yA'] + 2}"] = " "
    for (x, ch) in p["place"]:
        patch[f"{x},{p['yA']}"] = ch
    patch[f"{p['term']},{p['yA']}"] = p["glyph"]
    return patch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man"); ap.add_argument("out")
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--only", type=int, default=-1)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    rows = wf.load_rows(a.man)
    total = 0
    for it in range(a.rounds):
        g = wf.Grid(rows)
        ps = plan(g, g.walk(g.starts()[0]), 0, a.verbose and it == 0)
        if a.only >= 0:
            ps = [p for p in ps if p["yA"] == a.only]
        ps = ps[:a.limit] if a.limit else ps
        if not ps:
            break
        for p in ps:
            print(f"  fused rows {p['yA']+1},{p['yA']+2} into {p['yA']}: "
                  + " ".join(f"{ch}@{x}" for x, ch in p["place"])
                  + f" term {p['glyph']}@{p['term']}")
            total += 1
        pt = {}
        for p in ps:
            pt.update(patch_of(p))
        rows = ["".join(r) for r in wf.apply_patch(rows, pt)]
    open(a.out, "w").write(wf.render([list(r) for r in rows]))
    print(f"  wrote {a.out} ({total} fusions)")


main()

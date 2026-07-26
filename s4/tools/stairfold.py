#!/usr/bin/env python3
"""stairfold — flatten walk staircases so their shim rows empty, then squash.

Pattern (southbound; h in {E, W}):
    row y1:  ... run heading h ...  v@c1
    row y2:  turn@(c1,y2) heading h2, glide h2, v@c2      (h2 = h staircase, -h U-shim)
    below:   (c2, y2+1..) continues south
Rewrite: put the drop at c2 already on row y1 (the run there is blank glide),
erase the three turn glyphs on y2/c1, and let the man fall straight through y2.
Everything the man executes is unchanged — only blank cells walked change, so
ticks change (shorter) but the op sequence is identical. Gate = grade + oracle.
"""
import sys, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)


def plan_stairs(g, succ, room=0, verbose=False):
    st = wf.state_map(succ)
    (rx0, ry0), (rx1, ry1) = g.rooms[room]["min"], g.rooms[room]["max"]
    plans = []

    def priv(cell, dirs):
        return st.get(cell, set()) <= set(dirs)

    VGLYPH = {S: "vV", N: "^"}
    ARROW = {S: "v", N: "^"}
    for ((c1, y1), d) in list(succ):
        for vd in (S, N):
            if g.at(c1, y1) not in VGLYPH[vd] or d not in (E, W):
                continue
            if not priv((c1, y1), [d]):
                continue                  # the v is shared -> a merge, don't touch
            # follow the vertical glide down/up to the turn row y2
            y2 = y1 + vd[1]
            ok = True
            mid = []
            while g.walkable(c1, y2) and g.at(c1, y2) == " ":
                if not priv((c1, y2), [vd]):
                    ok = False
                    break
                mid.append(y2)
                y2 += vd[1]
            if not ok or not g.walkable(c1, y2):
                continue
            t = g.at(c1, y2)
            if t not in "<>":
                continue
            if not priv((c1, y2), [vd]):
                continue
            h2 = E if t == ">" else W
            # follow the y2 run to its own vertical turn (same vertical sense vd)
            c2 = c1 + (1 if h2 == E else -1)
            ok = True
            while g.walkable(c2, y2) and g.at(c2, y2) == " ":
                if not priv((c2, y2), [h2]):
                    ok = False
                    break
                c2 += 1 if h2 == E else -1
            if not ok or not g.walkable(c2, y2) or g.at(c2, y2) not in VGLYPH[vd]:
                continue
            if not priv((c2, y2), [h2]):
                continue
            # y1 corridor between c1 and c2 must be blank & private to heading d
            lo, hi = min(c1, c2), max(c1, c2)
            span = [x for x in range(lo, hi + 1) if x not in (c1, c2)]
            if any(g.at(x, y1) != " " or not priv((x, y1), [d]) for x in span):
                continue
            if g.at(c2, y1) != " " or not priv((c2, y1), [d]):
                continue
            # the new vertical (c2, y1..y2) must be blank & private-vd,
            # except (c2, y2) itself which we erase
            ys = range(y1 + vd[1], y2, vd[1])
            if any(g.at(c2, yy) != " " or not priv((c2, yy), [vd]) for yy in ys):
                continue
            plans.append({"y1": y1, "y2": y2, "c1": c1, "c2": c2, "d": d,
                          "glyph": ARROW[vd], "mid": list(mid)})
    return plans


def apply_plans(rows, plans):
    patch = {}
    for p in plans:
        patch[f"{p['c1']},{p['y1']}"] = " "
        patch[f"{p['c1']},{p['y2']}"] = " "
        patch[f"{p['c2']},{p['y2']}"] = " "
        patch[f"{p['c2']},{p['y1']}"] = p["glyph"]
    return wf.apply_patch(rows, patch)


def main():
    src, out = sys.argv[1], sys.argv[2]
    rows = wf.load_rows(src)
    total = 0
    for rnd in range(40):
        g = wf.Grid(rows)
        succ = g.walk(g.starts()[0])
        plans = plan_stairs(g, succ)
        # disjoint row sets only, one wave per round
        chosen, taken = [], set()
        for p in plans:
            lo, hi = min(p["c1"], p["c2"]), max(p["c1"], p["c2"])
            ylo, yhi = min(p["y1"], p["y2"]), max(p["y1"], p["y2"])
            key = {(x, y) for x in range(lo, hi + 1)
                   for y in range(ylo, yhi + 1)}
            if any(k in taken for k in key):
                continue
            chosen.append(p)
            taken |= key
        if not chosen:
            break
        for p in chosen:
            print(f"  round {rnd}: flatten stair v@({p['c1']},{p['y1']}) -> col {p['c2']}")
        total += len(chosen)
        rows = ["".join(r) for r in apply_plans(rows, chosen)]
    open(out, "w").write(wf.render([list(r) for r in rows]))
    print(f"wrote {out} ({total} stairs flattened)")


if __name__ == "__main__":
    main()

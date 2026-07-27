#!/usr/bin/env python3
"""absorb.py — pull the NEXT horizontal segment of the man's walk up onto the current row.

walkfold's `fuse` only fires on a textbook hairpin triple whose middle row is empty; this
grid's fold long ago turned every return into a multi-row vertical glide with ops sitting
on it, so `fuse` finds nothing.

Here we follow the flow out of row A's terminator: down a vertical glide (ops on it are
collected), optionally through a reversed segment and a second glide, into the next
segment running the SAME way as row A.  Every op collected is re-placed on row A beyond
row A's last glyph, inside its own pipe band (arithmetic ops may take any column).  The
terminator glyph is re-planted at the column it already used, so the drop leaving the
merged row lands exactly where the old one did.  Rows left glyph-free are then squashed.

Works for east-bound and west-bound rows alike.  Every candidate is graded individually
with the Rust engine and kept only if it still passes every public case and scores lower.

usage: absorb.py <in.man> <out.man> [--rounds N] [-v]
"""
import sys, os, json, subprocess, tempfile, argparse

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)
HORZ = {">": E, "<": W}
GLYPH = {E: ">", W: "<"}


def movable(ch):
    return not (ch in wf.BRANCH or ch == "`" or ch in wf.TURNS or ch in "@HY"
                or ch in "><^vV")


def candidates(g, succ, room=0, verbose=False):
    st = wf.state_map(succ)
    tab, pure, _, _ = wf.bands(g, room)
    if not pure:
        return []
    (rx0, ry0), (rx1, ry1) = g.rooms[room]["min"], g.rooms[room]["max"]
    out, refused = [], []

    def priv(cell, dirs):
        return st.get(cell, set()) <= set(dirs)

    def glide(x, y, dirn):
        ops, kill = [], []
        cx, cy = x + dirn[0], y + dirn[1]
        for _ in range(80):
            if not g.walkable(cx, cy):
                return None
            ch = g.at(cx, cy)
            if ch == " ":
                allow = [dirn, N, S] if dirn in (E, W) else [dirn, E, W]
                if not priv((cx, cy), allow):
                    return None
            elif ch in "><^vV":
                return ops, kill, (cx, cy)
            elif not movable(ch) or not priv((cx, cy), [dirn]):
                return None
            else:
                ops.append(ch)
                kill.append((cx, cy))
            cx, cy = cx + dirn[0], cy + dirn[1]
        return None

    for yA in range(ry0 + 1, ry1 - 1):
        acols = [x for x in range(rx0 + 1, rx1) if g.at(x, yA) != " "]
        if not acols:
            continue
        for dA in (E, W):
            edge = max(acols) if dA == E else min(acols)
            if g.at(edge, yA) not in wf.VERT or not priv((edge, yA), [dA]):
                continue
            cA = edge
            ops, kill = [], [(cA, yA)]
            step = glide(cA, yA, S)
            if step is None:
                refused.append((yA, dA, "S-glide not private"))
                continue
            o1, k1, (tx, ty) = step
            ops += o1; kill += k1
            ch = g.at(tx, ty)
            if ch not in HORZ or not priv((tx, ty), [S]):
                refused.append((yA, dA, f"S-glide lands on {ch!r} dirs={sorted(st.get((tx,ty),()))}"))
                continue
            kill.append((tx, ty))
            if HORZ[ch] != dA:                       # reversed leg + second glide
                step = glide(tx, ty, HORZ[ch])
                if step is None:
                    refused.append((yA, dA, "reverse leg not private"))
                    continue
                o2, k2, (ux, uy) = step
                ops += o2; kill += k2
                if g.at(ux, uy) not in wf.VERT or not priv((ux, uy), [HORZ[ch]]):
                    refused.append((yA, dA, "reverse leg has no private terminator"))
                    continue
                kill.append((ux, uy))
                step = glide(ux, uy, S)
                if step is None:
                    refused.append((yA, dA, "second S-glide not private"))
                    continue
                o3, k3, (vx, vy) = step
                ops += o3; kill += k3
                if g.at(vx, vy) != GLYPH[dA] or not priv((vx, vy), [S]):
                    refused.append((yA, dA, f"second glide lands on {g.at(vx,vy)!r}"))
                    continue
                kill.append((vx, vy))
                bx, by = vx, vy
            else:
                bx, by = tx, ty
            step = glide(bx, by, dA)
            if step is None:
                refused.append((yA, dA, "final leg not private"))
                continue
            o4, k4, (cB, yB) = step
            ops += o4; kill += k4
            term = g.at(cB, yB)
            if term not in wf.VERT or not priv((cB, yB), [dA]):
                refused.append((yA, dA, f"final leg ends on {term!r}"))
                continue
            kill.append((cB, yB))
            sgn = dA[0]
            if (cB - cA) * sgn <= 0:
                refused.append((yA, dA, f"terminator col {cB} not beyond {cA}"))
                continue
            killset = set(kill)

            def free(x, y, dirs):
                return ((x, y) in killset or g.at(x, y) == " ") and priv((x, y), dirs)

            cur = cA
            place, ok = [], True
            for c in ops:
                lo, hi = wf.op_band(g, tab, c, (cur, yA), room)
                nx = cur + sgn
                while lo <= nx <= hi and (nx - cB) * sgn < 0 and not free(nx, yA, [dA, N, S]):
                    nx += sgn
                if not (lo <= nx <= hi) or (nx - cB) * sgn >= 0:
                    ok = False
                    break
                place.append((nx, c))
                cur = nx
            if not ok:
                refused.append((yA, dA, f"cannot place {ops} beyond {cA} before {cB}"))
                continue
            used = {x for x, _ in place}
            bad = None
            for y in range(yA, yB + 1):
                if (cB, y) in killset:
                    continue
                if not free(cB, y, [dA, N, S] if y == yA else [N, S]):
                    bad = f"drop column {cB} blocked at row {y}"
            x = cA + sgn
            while (x - cB) * sgn < 0:
                if x not in used and not free(x, yA, [dA, N, S]):
                    bad = f"destination row blocked at col {x}"
                x += sgn
            if bad:
                refused.append((yA, dA, bad))
                continue
            patch = {f"{x},{y}": " " for (x, y) in kill}
            for (x, c) in place:
                patch[f"{x},{yA}"] = c
            patch[f"{cB},{yA}"] = term
            out.append({"yA": yA, "dir": "E" if dA == E else "W", "cA": cA, "cB": cB,
                        "yB": yB, "ops": ops, "place": place, "patch": patch})
    if verbose:
        for y, d, why in refused:
            print(f"    refused row {y} {'E' if d == E else 'W'}: {why}")
    return out


def grade(path):
    p = subprocess.run(["python3", "tools/grade_fast.py", "gradebook", path, "--cap", "60000"],
                       capture_output=True, text=True)
    try:
        d = json.loads(p.stdout)
    except Exception:
        return None
    if d["passed"] != d["total"]:
        return None
    return d["score"], d["footprint"], d["avgTicks"]


def squash(rows):
    g = wf.Grid(rows)
    (x0, y0), (x1, y1) = g.rooms[0]["min"], g.rooms[0]["max"]
    drop = {y for y in range(y0 + 1, y1) if not rows[y][x0 + 1:x1].strip()}
    return [r for i, r in enumerate(rows) if i not in drop]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man"); ap.add_argument("out")
    ap.add_argument("--rounds", type=int, default=60)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    rows = wf.load_rows(a.man)
    tmp = tempfile.mkstemp(suffix=".man")[1]
    open(tmp, "w").write(wf.render([list(r) for r in rows]))
    base = grade(tmp)
    print(f"base {base}")
    accepted = 0
    for it in range(a.rounds):
        g = wf.Grid(rows)
        cands = candidates(g, g.walk(g.starts()[0]), 0, a.verbose)
        print(f"round {it}: {len(cands)} candidates")
        best = None
        for c in cands:
            new = ["".join(r) for r in wf.apply_patch(rows, c["patch"])]
            new = squash(new)
            open(tmp, "w").write(wf.render([list(r) for r in new]))
            r = grade(tmp)
            if r is None:
                continue
            if best is None or r[0] < best[0]:
                best = (r[0], new, c, r)
        if best is None or best[0] >= base[0]:
            print("  nothing accepted")
            break
        rows, c = best[1], best[2]
        base = best[3]
        accepted += 1
        print(f"  absorbed row {c['yA']} {c['dir']} ops={c['ops']} -> {base}")
        open(a.out, "w").write(wf.render([list(r) for r in rows]))
    print(f"done: {accepted} absorptions; {a.out}")


main()

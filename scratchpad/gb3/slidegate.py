#!/usr/bin/env python3
"""slidegate.py — grade-gated U-turn slider.

`walkfold lift` refuses every hairpin on this grid because the turn glyphs are merge
points (loop back-edges share them).  Static refusal is conservative: sliding a shared
turn is often still correct, because every flow that reaches the turn reaches the new
column too by gliding one cell further.  So propose the slide anyway and let the Rust
grader decide -- a candidate is kept only when all 7 public cases still pass and the score
strictly improves.

Also proposes: single-glyph column slides (which free the columns a U-turn wants), and
turn-glyph deletion.

usage: slidegate.py <in.man> <out.man> [--rounds N] [--jobs N] [--span N]
"""
import sys, os, json, subprocess, tempfile, argparse, concurrent.futures

REPO = "/Users/visenbaev/icfpc26"
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)
VERTG = set("vV^")
HORZG = set("><")


def grade_file(path):
    p = subprocess.run(["python3", "tools/grade_fast.py", "gradebook", path, "--cap", "60000"],
                       capture_output=True, text=True)
    try:
        d = json.loads(p.stdout)
    except Exception:
        return None
    if d["passed"] != d["total"]:
        return None
    return d["score"]


def grade_rows(rows):
    fd, tmp = tempfile.mkstemp(suffix=".man")
    os.close(fd)
    open(tmp, "w").write(wf.render([list(r) for r in rows]))
    s = grade_file(tmp)
    os.unlink(tmp)
    return s


BOX = None                                    # (x0,y0,x1,y1) of room0, set once per round


def squash(rows):
    x0, y0, x1, y1 = BOX
    drop = {y for y in range(y0 + 1, y1)
            if not rows[y].ljust(x1)[x0 + 1:x1].strip()}
    return [r for i, r in enumerate(rows) if i not in drop]


def proposals(g, rows, span):
    """(label, patch) pairs."""
    (rx0, ry0), (rx1, ry1) = g.rooms[0]["min"], g.rooms[0]["max"]
    out = []
    # 1. U-turn slides: a VERT at (c,y1) whose vertical glide reaches a HORZ at (c,y2)
    for y1 in range(ry0 + 1, ry1):
        for c in range(rx0 + 1, rx1):
            ch = g.at(c, y1)
            if ch not in VERTG:
                continue
            vd = S if ch in "vV" else N
            y2 = y1 + vd[1]
            mids = []
            while ry0 < y2 < ry1 and g.at(c, y2) == " " and len(mids) < 7:
                mids.append(y2)
                y2 += vd[1]
            if not (ry0 < y2 < ry1) or g.at(c, y2) not in HORZG:
                continue
            g2 = g.at(c, y2)
            for d in range(-span, span + 1):
                if d == 0:
                    continue
                nc = c + d
                if not (rx0 < nc < rx1):
                    continue
                if g.at(nc, y1) != " " or g.at(nc, y2) != " ":
                    continue
                if any(g.at(nc, m) != " " for m in mids):
                    continue
                p = {f"{c},{y1}": " ", f"{c},{y2}": " ",
                     f"{nc},{y1}": ch, f"{nc},{y2}": g2}
                out.append((f"U({c},{y1})/({c},{y2})->{nc}", p))
    # 2. single glyph column slide
    for y in range(ry0 + 1, ry1):
        for x in range(rx0 + 1, rx1):
            ch = g.at(x, y)
            if ch == " " or ch in "`@H0123456789":
                continue
            for d in (-1, 1, -2, 2):
                nx = x + d
                if not (rx0 < nx < rx1) or g.at(nx, y) != " ":
                    continue
                out.append((f"g{ch}({x},{y})->{nx}", {f"{x},{y}": " ", f"{nx},{y}": ch}))
    # 4. block shift: within a 1..3 row window, move every glyph west of (or east of)
    #    a split column by dx, closing the blank gap a hairpin loop wastes on every lap.
    for y in range(ry0 + 1, ry1):
        for h in (1, 2, 3):
            if y + h > ry1:
                continue
            ys = range(y, y + h)
            for c in range(rx0 + 2, rx1):
                for side, sgn in ((-1, 1), (1, -1)):     # west block east / east block west
                    for dx in range(1, 6):
                        cells = []
                        okk = True
                        for yy in ys:
                            for x in range(rx0 + 1, rx1):
                                if (x - c) * side >= 0:
                                    continue
                                ch = g.at(x, yy)
                                if ch != " ":
                                    cells.append((x, yy, ch))
                        if not cells or len(cells) > 14:
                            continue
                        src = {(x, yy) for x, yy, _ in cells}
                        for (x, yy, ch) in cells:
                            nx = x + sgn * dx
                            if not (rx0 < nx < rx1) or ((nx, yy) not in src and g.at(nx, yy) != " "):
                                okk = False
                        if not okk:
                            continue
                        p = {f"{x},{yy}": " " for x, yy, _ in cells}
                        for (x, yy, ch) in cells:
                            p[f"{x + sgn * dx},{yy}"] = ch
                        out.append((f"blk y{y}+{h} c<{c} {sgn*dx:+d}" if side < 0
                                    else f"blk y{y}+{h} c>{c} {sgn*dx:+d}", p))
    # 3. turn glyph deletion
    for y in range(ry0 + 1, ry1):
        for x in range(rx0 + 1, rx1):
            if g.at(x, y) in VERTG | HORZG:
                out.append((f"del({x},{y})", {f"{x},{y}": " "}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man"); ap.add_argument("out")
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--span", type=int, default=6)
    a = ap.parse_args()
    rows = wf.load_rows(a.man)
    base = grade_rows(rows)
    print(f"base {base:.0f}")
    for it in range(a.rounds):
        g = wf.Grid(rows)
        global BOX
        (bx0, by0), (bx1, by1) = g.rooms[0]["min"], g.rooms[0]["max"]
        BOX = (bx0, by0, bx1, by1)
        props = proposals(g, rows, a.span)
        seen, uniq = set(), []
        for lab, p in props:
            k = tuple(sorted(p.items()))
            if k in seen:
                continue
            seen.add(k)
            uniq.append((lab, p))
        props = uniq
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            futs = {}
            for (lab, p) in props:
                new = squash(["".join(r) for r in wf.apply_patch(rows, p)])
                futs[ex.submit(grade_rows, new)] = (lab, new)
            for f in concurrent.futures.as_completed(futs):
                s = f.result()
                if s is not None and s < base - 1e-6:
                    results.append((s, futs[f][0], futs[f][1]))
        if not results:
            print(f"round {it}: {len(props)} proposals, none improve")
            break
        results.sort(key=lambda t: t[0])
        s, lab, new = results[0]
        rows, base = new, s
        print(f"round {it}: {len(props)} proposals, {len(results)} improve; took {lab} -> {base:.0f}")
        open(a.out, "w").write(wf.render([list(r) for r in rows]))
    print(f"done -> {a.out} ({base:.0f})")


main()

#!/usr/bin/env python3
"""roomfit.py — shrink each room to the content it actually holds.

The one geometry pass that needs no placer. Everything else that frees space (dead-code
elimination, peephole, scheduling) only opens a HOLE, and a hole does not shrink
`max(w,h)` — ticks here are cells WALKED, not instructions executed, so you need a placer to
close the gap before any of it turns into score. Moving a room's WALL inward is different:
nothing inside has to move, so it pays immediately.

A side may be pulled in by one line when that line is:
  * blank in the room's interior,
  * not walked by any man (a man gliding through blank space still needs the space, and
    stepping onto a wall is a fatal whole-program abort), and
  * not carrying a pipe attachment on the wall being moved (the pipe would no longer meet
    the room, which is a load error).

Then the score only improves if that wall was on the bounding box's binding dimension, so
candidates are ranked by whether they actually reduce max(w,h).

Every candidate is verified twice: `tools/pipecheck.py` for silent pipe rebinding (s/r/q
bind to the NEAREST pipe, and moving a wall moves attachment distances), and the real grader
for everything else. Output goes to a NEW file; the input is never modified.

  python3 tools/roomfit.py <slug> <file.man> [--jobs N] [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_rows(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows) if rows else 0
    return [r.ljust(w) for r in rows]


def lift(path):
    r = subprocess.run(["python3", os.path.join(REPO, "tools", "lift.py"), path, "--json"],
                       capture_output=True, text=True, cwd=REPO)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit(f"lift failed: {(r.stderr or r.stdout)[:200]}")


def reachable(ir):
    out = set()
    for m in ir["men"]:
        for b in m["blocks"]:
            for p, _ in b:
                out.add(tuple(p))
        for k in m["op_cells"]:
            out.add(tuple(int(t) for t in k.split(",")))
    return out


def pipe_touch(ir):
    """Cells a pipe occupies plus the wall cell each end points at."""
    cells = set()
    for p in ir["pipes"]:
        path = p.get("path") or []
        for step in path:
            x, y = step["pos"]
            cells.add((x, y))
            dx, dy = step["dir"]
            cells.add((x + dx, y + dy))
            cells.add((x - dx, y - dy))
    return cells


def box_of(rows):
    ys = [i for i, r in enumerate(rows) if r.strip()]
    if not ys:
        return 0, 0, 0
    w = max(len(r) for r in rows)
    xs = [x for x in range(w) if any(len(r) > x and r[x] != " " for r in rows)]
    W, H = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    return W, H, max(W, H) ** 2


def redraw(rows, room, side, n):
    """Return new rows with one wall of `room` pulled in by n lines, or None if illegal."""
    (x0, y0), (x1, y1) = room["min"], room["max"]
    grid = [list(r) for r in rows]

    def clear(x, y):
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            grid[y][x] = " "

    if side == "R":
        nx1 = x1 - n
        if nx1 - x0 < 2:
            return None
        for y in range(y0, y1 + 1):
            clear(x1, y)
        for y in range(y0, y1 + 1):
            grid[y][nx1] = "+" if y in (y0, y1) else "|"
        for x in range(nx1 + 1, x1 + 1):
            for y in (y0, y1):
                clear(x, y)
    elif side == "L":
        nx0 = x0 + n
        if x1 - nx0 < 2:
            return None
        for y in range(y0, y1 + 1):
            clear(x0, y)
        for y in range(y0, y1 + 1):
            grid[y][nx0] = "+" if y in (y0, y1) else "|"
        for x in range(x0, nx0):
            for y in (y0, y1):
                clear(x, y)
    elif side == "B":
        ny1 = y1 - n
        if ny1 - y0 < 2:
            return None
        for x in range(x0, x1 + 1):
            clear(x, y1)
        for x in range(x0, x1 + 1):
            grid[ny1][x] = "+" if x in (x0, x1) else "-"
        for y in range(ny1 + 1, y1 + 1):
            for x in (x0, x1):
                clear(x, y)
    elif side == "T":
        ny0 = y0 + n
        if y1 - ny0 < 2:
            return None
        for x in range(x0, x1 + 1):
            clear(x, y0)
        for x in range(x0, x1 + 1):
            grid[ny0][x] = "+" if x in (x0, x1) else "-"
        for y in range(y0, ny0):
            for x in (x0, x1):
                clear(x, y)
    else:
        return None
    return ["".join(r).rstrip() for r in grid]


def free_lines(rows, room, side, reach, pipes):
    """How many lines this side can be pulled in before hitting content."""
    (x0, y0), (x1, y1) = room["min"], room["max"]

    def cell_free(x, y):
        ch = rows[y][x] if y < len(rows) and x < len(rows[y]) else " "
        return ch == " " and (x, y) not in reach and (x, y) not in pipes

    n = 0
    if side in ("R", "L"):
        rng = range(x1 - 1, x0, -1) if side == "R" else range(x0 + 1, x1)
        for x in rng:
            if all(cell_free(x, y) for y in range(y0 + 1, y1)) and \
               all((x, wy) not in pipes for wy in (y0, y1)):
                n += 1
            else:
                break
    else:
        rng = range(y1 - 1, y0, -1) if side == "B" else range(y0 + 1, y1)
        for y in rng:
            if all(cell_free(x, y) for x in range(x0 + 1, x1)) and \
               all((wx, y) not in pipes for wx in (x0, x1)):
                n += 1
            else:
                break
    # never move a wall a pipe attaches to
    wall = [(x1, y) for y in range(y0, y1 + 1)] if side == "R" else \
           [(x0, y) for y in range(y0, y1 + 1)] if side == "L" else \
           [(x, y1) for x in range(x0, x1 + 1)] if side == "B" else \
           [(x, y0) for x in range(x0, x1 + 1)]
    if any(c in pipes for c in wall):
        return 0
    return n


def grade(slug, path, cap=None):
    cmd = ["node", os.path.join(REPO, "tools", "grade_json.js"), slug, path, "--failfast"]
    if cap:
        cmd += ["--cap", str(int(cap))]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=600)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stderr or "grade failed")[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("man")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = load_rows(args.man)
    ir = lift(args.man)
    reach, pipes = reachable(ir), pipe_touch(ir)
    W, H, box = box_of(rows)
    binding = "H" if H >= W else "W"
    print(f"{os.path.basename(args.man)}: {W}x{H} box {box} (binding {binding}), "
          f"{len(ir['rooms'])} rooms")

    cands = []
    for i, room in enumerate(ir["rooms"]):
        for side in ("R", "L", "B", "T"):
            n = free_lines(rows, room, side, reach, pipes)
            if n:
                cands.append((i, room, side, n))
                print(f"  room{i} {room['min']}-{room['max']}: {side} can pull in {n}")
    if not cands:
        print("  no room has a free margin — nothing to do")
        return
    if args.dry_run:
        return

    base = grade(args.slug, args.man)
    if base.get("error") or base["passed"] != base["total"]:
        sys.exit(f"baseline does not pass: {base}")
    print(f"  baseline {base['passed']}/{base['total']} score {base['score']:,.0f}")

    best_rows, best_score, applied = rows, base["score"], []
    tmp = os.path.join(REPO, ".roomfit_tmp.man")

    # ALL-AT-ONCE FIRST. Shrinks on different rooms are independent, but individually
    # worthless: if two rooms both touch the binding edge, pulling either one in leaves
    # max(w,h) untouched, so neither a strict nor a lateral rule ever fires and the pair
    # that would have paid is never tried. Rooms are disjoint, so applying every free
    # shrink at once is legal and is the candidate that actually moves the box.
    combo = rows
    for i, room, side, n in cands:
        step = redraw(combo, room, side, n)
        if step is not None:
            combo = step
    if combo is not rows:
        open(tmp, "w").write("\n".join(combo) + "\n")
        g = grade(args.slug, tmp)
        cW, cH, cbox = box_of(combo)
        ok = not g.get("error") and g["passed"] == g["total"] and g.get("score") is not None
        status = (f"{g['passed']}/{g['total']} score {g['score']:,.0f}" if not g.get("error")
                  else str(g["error"])[:60])
        print(f"  all {len(cands)} shrinks at once: box {box}->{cbox} ({cW}x{cH})  {status}")
        if ok and g["score"] < best_score:
            best_rows, best_score = combo, g["score"]
            applied.append(("all", "combined", len(cands), g["score"], False))
    for i, room, side, n in sorted(cands, key=lambda c: -c[3]):
        for take in range(n, 0, -1):
            cur_ir = lift_rows(best_rows, tmp)
            room_now = cur_ir["rooms"][i] if i < len(cur_ir["rooms"]) else None
            if room_now is None:
                break
            cand = redraw(best_rows, room_now, side, take)
            if cand is None:
                continue
            open(tmp, "w").write("\n".join(cand) + "\n")
            nW, nH, nbox = box_of(cand)
            g = grade(args.slug, tmp)
            ok = not g.get("error") and g["passed"] == g["total"] and g.get("score") is not None
            # LATERAL MOVES. Two rooms can both touch the binding edge, so shrinking either
            # one alone leaves max(w,h) unchanged and a strict-improvement rule rejects both
            # — and the pair that would have paid is never reached. Accept a score-NEUTRAL
            # shrink when it strictly reduces bounding-box area, which still terminates.
            cur_area = box_of(best_rows)[0] * box_of(best_rows)[1]
            lateral = ok and g["score"] == best_score and nW * nH < cur_area
            if ok and (g["score"] < best_score or lateral):
                pc = subprocess.run(["python3", os.path.join(REPO, "tools", "pipecheck.py"),
                                     args.man, tmp], capture_output=True, text=True, cwd=REPO)
                rebound = "REBOUND" in pc.stdout
                print(f"  room{i} {side} -{take}: box {box}->{nbox} score {g['score']:,.0f}"
                      f"  {'LATERAL' if lateral else 'ACCEPT'}"
                      f"{'  (WARNING: pipe rebinding!)' if rebound else ''}")
                best_rows, best_score = cand, g["score"]
                applied.append((i, side, take, g["score"], rebound))
                break
    if os.path.exists(tmp):
        os.remove(tmp)
    if not applied:
        print("  no shrink improved the score")
        return
    stem = os.path.splitext(args.man)[0]
    out = f"{stem}-roomfit.man"
    open(out, "w").write("\n".join(best_rows) + "\n")
    nW, nH, nbox = box_of(best_rows)
    print(f"\n{base['score']:,.0f} -> {best_score:,.0f} "
          f"({base['score'] / best_score:.2f}x), box {box} -> {nbox} ({nW}x{nH})")
    print(f"wrote {os.path.relpath(out, REPO)}")
    print(f"verify: node tools/grade.js {args.slug} {os.path.relpath(out, REPO)}")


def lift_rows(rows, tmp):
    open(tmp, "w").write("\n".join(rows) + "\n")
    return lift(tmp)


if __name__ == "__main__":
    main()

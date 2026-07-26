#!/usr/bin/env python3
"""pipecheck.py — does this transformation silently rebind a pipe operation?

The nastiest failure mode for ANY pass that moves cells. `s` sends to the nearest OUTGOING
pipe, `r` and `q` read the nearest INCOMING one, where "nearest" is Manhattan distance from
the instruction cell to the pipe segment attached to the room, ties broken in reading order
(top-to-bottom, then left-to-right). Nothing announces a change: move an op one column, or
delete a row between it and its pipe, and it can bind to a DIFFERENT pipe. The program still
loads, still runs, and quietly computes the wrong thing — and if the public cases happen not
to exercise that path, grading says PASS.

So this compares bindings BEFORE and AFTER a transformation rather than trusting a grade.

  python3 tools/pipecheck.py <file.man>                  bindings in one program
  python3 tools/pipecheck.py <before.man> <after.man>    what a transformation changed

Not affected, and deliberately not flagged: `R` and `U` take from any READY incoming pipe in
reading order, and `S` sends to every outgoing pipe — none of them use geometric distance, so
moving those ops cannot rebind them.
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEAREST_OUT = set("s")          # nearest outgoing
NEAREST_IN = set("rq")          # nearest incoming
ORDER_BASED = set("RUS")        # position-independent; listed so they are not confused


def load_rows(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows) if rows else 0
    return [r.ljust(w) for r in rows]


def analyze(rows):
    # NOTE: output goes through a temp file, not stdout — `process.exit()` truncates
    # unflushed stdout at 64KB, and a big grid's analysis JSON (pipe paths list every
    # cell) blows straight past that.
    import tempfile
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as tf:
        outpath = tf.name
    script = ("const {boot}=require(process.argv[1]+'/sim/harness.js');"
              "(async()=>{const w=await boot();"
              "require('fs').writeFileSync(process.argv[3],String(w.analyze(JSON.parse(process.argv[2]))));"
              "process.exit(0)})()"
              ".catch(e=>{require('fs').writeFileSync(process.argv[3],JSON.stringify({type:'error',message:String(e)}));process.exit(1)})")
    r = subprocess.run(["node", "-e", script, REPO, json.dumps(rows), outpath],
                       capture_output=True, text=True, cwd=REPO)
    try:
        with open(outpath) as f:
            return json.load(f)
    except (ValueError, IndexError, OSError):
        sys.exit(f"analyze failed: {(r.stderr or '')[:200]}")
    finally:
        os.unlink(outpath)


def room_of(rooms, x, y):
    for i, r in enumerate(rooms):
        (x0, y0), (x1, y1) = r["min"], r["max"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return i
    return None


def attachments(topo):
    """Per room: the incoming and outgoing pipes, with the cell where each meets the room.

    A pipe's FIRST cell is what its source room sees; its LAST cell is what the destination
    room sees. That attachment cell is what the distance is measured to."""
    out, inc = {}, {}
    for pi, p in enumerate(topo.get("pipes") or []):
        path = p.get("path") or []
        if not path:
            continue
        src, dst = p.get("src"), p.get("dst")
        if src is not None:
            out.setdefault(src, []).append((pi, tuple(path[0]["pos"])))
        if dst is not None:
            inc.setdefault(dst, []).append((pi, tuple(path[-1]["pos"])))
    return inc, out


def bind(cell, candidates):
    """Nearest by Manhattan; ties in reading order of the attachment cell."""
    if not candidates:
        return None
    x, y = cell
    return min(candidates, key=lambda c: (abs(c[1][0] - x) + abs(c[1][1] - y),
                                          c[1][1], c[1][0]))[0]


def bindings(path):
    rows = load_rows(path)
    topo = analyze(rows)
    if topo.get("type") == "error":
        sys.exit(f"{path}: {topo.get('message')}")
    rooms = topo.get("rooms") or []
    inc, out = attachments(topo)
    interior = set()
    for r in rooms:
        (x0, y0), (x1, y1) = r["min"], r["max"]
        for yy in range(y0 + 1, y1):
            for xx in range(x0 + 1, x1):
                interior.add((xx, yy))
    found = []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if (x, y) not in interior:
                continue                      # only a cell inside a room is an instruction
            if ch in NEAREST_OUT or ch in NEAREST_IN:
                ri = room_of(rooms, x, y)
                cands = out.get(ri, []) if ch in NEAREST_OUT else inc.get(ri, [])
                found.append({"cell": (x, y), "op": ch, "room": ri,
                              "pipe": bind((x, y), cands), "n_candidates": len(cands)})
    return found, topo


def report(path):
    found, topo = bindings(path)
    amb = [f for f in found if f["n_candidates"] > 1]
    print(f"{os.path.basename(path)}: {len(topo.get('rooms') or [])} rooms, "
          f"{len(topo.get('pipes') or [])} pipes, {len(found)} distance-bound ops "
          f"({len(amb)} in rooms with a CHOICE of pipe — only these can rebind)")
    for f in found:
        flag = "  <-- ambiguous" if f["n_candidates"] > 1 else ""
        print(f"  {f['op']} at {f['cell']} in room {f['room']} -> pipe {f['pipe']}"
              f" (of {f['n_candidates']}){flag}")
    return found


def compare(before, after):
    """Match ops in reading order per room and report any that changed pipe."""
    b, _ = bindings(before)
    a, _ = bindings(after)
    print(f"{os.path.basename(before)} -> {os.path.basename(after)}: "
          f"{len(b)} vs {len(a)} distance-bound ops")
    if len(b) != len(a):
        print("  WARNING: the transformation changed how many distance-bound ops exist; "
              "positional matching below is unreliable")
    by_room_b, by_room_a = {}, {}
    for f in b:
        by_room_b.setdefault((f["room"], f["op"]), []).append(f)
    for f in a:
        by_room_a.setdefault((f["room"], f["op"]), []).append(f)
    changed, checked = [], 0
    for key, bl in sorted(by_room_b.items(), key=lambda kv: (kv[0][0] is None, kv[0])):
        al = by_room_a.get(key, [])
        for i, fb in enumerate(bl):
            if i >= len(al):
                changed.append((key, fb, None))
                continue
            checked += 1
            fa = al[i]
            if fb["pipe"] != fa["pipe"]:
                changed.append((key, fb, fa))
    if not changed:
        print(f"  OK — all {checked} distance-bound ops still resolve to the same pipe")
        return 0
    print(f"  REBOUND: {len(changed)} op(s) now resolve to a different pipe")
    for key, fb, fa in changed:
        room, op = key
        if fa is None:
            print(f"    '{op}' in room {room} at {fb['cell']} -> op no longer present")
        else:
            print(f"    '{op}' in room {room}: {fb['cell']} pipe {fb['pipe']}"
                  f"  ->  {fa['cell']} pipe {fa['pipe']}")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    if len(args.files) == 1:
        report(args.files[0])
        return
    rc = 0
    for i in range(0, len(args.files) - 1, 2):
        rc |= compare(args.files[i], args.files[i + 1])
    sys.exit(rc)


if __name__ == "__main__":
    main()

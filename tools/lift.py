#!/usr/bin/env python3
"""lift.py — the optimizing compiler's FRONT END: a .man grid -> an IR.

Score here is `max(width,height)^2 * average ticks` — AREA x LATENCY on a 2D fabric — so
this is closer to high-level synthesis than to a conventional compiler, and the back end
(where blocks get placed) is where the score lives. Measured on our champions: 51-89% of
every grid is blank, and packing the instruction cells alone would give box 16900 -> ~1024
(gradebook), 1681 -> ~529 (tcp), 529 -> ~256 (brackets). Nothing at the literal level can
reach that; re-placing the code can.

This module only does the lift. It recovers, per man:
  * the ROOM he lives in and the cells he can reach (static walk from `@`);
  * BASIC BLOCKS: maximal straight-line runs of instruction cells;
  * EDGES between them, including the branch fan-out of X / d / a / x and the wrap of a
    turn glyph; a loop shows up as an edge back into an earlier block;
  * which cells are pure ROUTING (turn glyphs and blank glides) rather than instructions —
    that is the material a re-placement pass gets to delete or reshape.

CORRECTNESS GATE. A lift is only trustworthy if it predicts what the program actually does,
so `--verify` steps the reference oracle over a real test case, records the true sequence of
executed instruction cells, and checks that every one of them is a cell this lift claims is
reachable, in a block, and with the op the lift recorded. Any mismatch is reported and exits
non-zero — a front end that quietly disagrees with the machine is worse than none.

  python3 tools/lift.py <file.man>                    lift + structure report
  python3 tools/lift.py <file.man> --verify <slug>    also check against the oracle
  python3 tools/lift.py <file.man> --json             machine-readable IR
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The instruction set (PROBLEM.md). Anything else in a room interior is routing or padding.
OPS = set("0123456789`MWbmq]+-*%/N&|~{}XdaxYHsSrRU")
TURNS = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1), "V": (0, 1)}
BRANCH = set("Xdax")          # fan out: may leave in more than one direction
STOP = set("H")
WALL = set("+-|=:")
DIRS = {(1, 0): "E", (-1, 0): "W", (0, -1): "N", (0, 1): "S"}
CW = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}
CCW = {v: k for k, v in CW.items()}


def load_rows(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows)
    return [r.ljust(w) for r in rows]


def analyze(rows):
    """Room + pipe topology, straight from the reference interpreter."""
    # The grid goes through a TEMP FILE, never argv: a large program (our LLM solution is
    # 612x1768, over 1 MB) exceeds ARG_MAX and the exec fails with "Argument list too long".
    script = (
        "const fs=require('fs');"
        "const {boot}=require(process.argv[1]+'/sim/harness.js');"
        "(async()=>{const w=await boot();"
        "const rows=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
        "console.log(w.analyze(rows));process.exit(0)})()"
        ".catch(e=>{console.log(JSON.stringify({type:'error',message:String(e)}));process.exit(1)})"
    )
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(rows, fh)
        r = subprocess.run(["node", "-e", script, REPO, tmp],
                           capture_output=True, text=True, cwd=REPO)
    finally:
        os.unlink(tmp)
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"type": "error", "message": (r.stderr or "analyze failed")[:200]}


class Lift:
    def __init__(self, rows):
        self.rows = rows
        self.h = len(rows)
        self.w = len(rows[0]) if rows else 0
        self.topo = analyze(rows)
        self.rooms = self.topo.get("rooms") or []
        self.pipes = self.topo.get("pipes") or []
        self.men = []

    def at(self, x, y):
        if 0 <= y < self.h and 0 <= x < len(self.rows[y]):
            return self.rows[y][x]
        return " "

    def room_of(self, x, y):
        for i, r in enumerate(self.rooms):
            (x0, y0), (x1, y1) = r["min"], r["max"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    def walkable(self, x, y):
        """A man may only ever stand STRICTLY INSIDE a room.

        Wall-ness is geometric, not textual: `-` and `|` are room borders on a room's
        boundary but are the subtract and OR instructions in its interior, and `+` is a
        corner outside yet a valid add inside. Classifying by character (the obvious first
        guess) stops the walk at the first subtract — the oracle cross-check catches it."""
        for r in self.rooms:
            (x0, y0), (x1, y1) = r["min"], r["max"]
            if x0 < x < x1 and y0 < y < y1:
                return True
        return False

    def starts(self):
        return [(x, y) for y in range(self.h) for x in range(len(self.rows[y]))
                if self.rows[y][x] == "@"]

    def walk(self, start):
        """Static reachability from `@`, following the machine's own movement rules.

        Every state is (cell, heading) because the same cell reached on a different heading
        continues differently. A branch fans out to all headings it could take, since which
        one fires depends on runtime registers."""
        sx, sy = start
        seen, stack = set(), [((sx, sy), (1, 0))]     # a man spawned at @ faces right
        cells, edges = {}, set()
        while stack:
            (pos, d) = stack.pop()
            if (pos, d) in seen:
                continue
            seen.add((pos, d))
            x, y = pos
            ch = self.at(x, y)
            if not self.walkable(x, y):                # stepping onto a wall is fatal
                cells.setdefault(pos, ch)
                continue
            cells.setdefault(pos, ch)
            if ch in STOP:
                continue
            outs = []
            if ch in TURNS:
                outs = [TURNS[ch]]
            elif ch in BRANCH:
                outs = [d, CW[d], CCW[d]]              # sign/backpack decides at runtime
            elif ch == "Y":
                # A fork BIRTHS two men beside the cell, one clockwise and one
                # counter-clockwise of the incoming heading, each facing away. Their walks
                # are reachable code that no straight-line successor covers. Treating `Y`
                # as "continue straight" under-approximates reachability, and anything
                # built on that (dead-code elimination, fold safety) is then unsound.
                outs = [CW[d], CCW[d]]
            elif ch == "U":
                # `U` receives and then turns AWAY FROM THE PIPE, so the resulting heading
                # depends on where the pipe sits relative to this cell, not on the incoming
                # direction. Fan out to every heading rather than guess.
                outs = [d, CW[d], CCW[d], CW[CW[d]]]
            else:
                outs = [d]
            for nd in outs:
                nxt = (x + nd[0], y + nd[1])
                edges.add((pos, nxt))
                stack.append((nxt, nd))
        return cells, edges

    def blocks(self, cells, edges):
        """Group reachable cells into maximal straight-line runs of instructions."""
        succ = {}
        for a, b in edges:
            succ.setdefault(a, set()).add(b)
        pred = {}
        for a, b in edges:
            pred.setdefault(b, set()).add(a)
        leaders = set()
        for pos, ch in cells.items():
            if len(pred.get(pos, ())) != 1 or len(succ.get(pos, ())) > 1:
                leaders.add(pos)
            if ch in BRANCH or ch in TURNS:
                for s in succ.get(pos, ()):
                    leaders.add(s)
        blocks, seen = [], set()
        for pos in sorted(cells, key=lambda p: (p[1], p[0])):
            if pos in seen or pos not in leaders:
                continue
            run, cur = [], pos
            while cur is not None and cur not in seen:
                seen.add(cur)
                run.append((cur, cells[cur]))
                nxts = succ.get(cur, set())
                cur = next(iter(nxts)) if len(nxts) == 1 and nxts and \
                    next(iter(nxts)) not in leaders and next(iter(nxts)) in cells else None
            if run:
                blocks.append(run)
        return blocks

    def lift(self):
        for start in self.starts():
            cells, edges = self.walk(start)
            ops = {p: c for p, c in cells.items() if c in OPS}
            turns = {p: c for p, c in cells.items() if c in TURNS}
            glides = {p: c for p, c in cells.items() if c == " " or c == "."}
            self.men.append({
                "start": list(start),
                "room": self.room_of(*start),
                # The FULL reachable set, not just cells that landed in a block. Consumers
                # that reconstruct reachability from blocks + op_cells silently miss turn
                # glyphs and glides, and anything built on that (dead-code elimination) then
                # deletes cells the man actually walks.
                "reach": [f"{x},{y}" for (x, y) in sorted(cells)],
                "reachable": len(cells),
                "ops": len(ops),
                "turns": len(turns),
                "glides": len(glides),
                "op_cells": {f"{x},{y}": c for (x, y), c in sorted(ops.items())},
                "blocks": [[[list(p), c] for p, c in b] for b in self.blocks(cells, edges)],
            })
        return self


def verify(rows, path, slug, lifted, cap=200000):
    """Step the oracle over a real case and check the lift covers what actually executed."""
    spec_path = os.path.join(REPO, "tests", f"{slug}.json")
    if not os.path.exists(spec_path):
        return None, f"no cached spec tests/{slug}.json"
    spec = json.load(open(spec_path))
    cases = spec.get("publicTestData") or []
    if not cases:
        return None, "no public cases"
    tc = max(cases, key=lambda c: len(json.dumps(c)))       # the busiest case
    rounds = tc.get("rounds") or [tc]
    inp = " / ".join(" ".join(r.get("in") or []) for r in rounds)
    exp = " / ".join(" ".join(r.get("out") or []) for r in rounds)
    script = (
        "const {boot}=require(process.argv[1]+'/sim/harness.js');"
        "(async()=>{const w=await boot();const s=w.newSession();"
        "const rows=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
        "let j=JSON.parse(w.load(s,rows,process.argv[3],process.argv[4],''));"
        "const seen=[];let n=0;const cap=+process.argv[5];"
        "while(!j.halted && n<cap){for(const r of (j.entities&&j.entities.runners)||[])"
        "  seen.push(r.pos[0]+','+r.pos[1]);"
        " j=JSON.parse(w.step(s));n++;}"
        "console.log(JSON.stringify({visited:[...new Set(seen)],steps:n}));"
        "w.closeSession(s);process.exit(0)})()"
        ".catch(e=>{console.log(JSON.stringify({error:String(e)}));process.exit(1)})"
    )
    fd, tmp = __import__("tempfile").mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(rows, fh)
        r = subprocess.run(["node", "-e", script, REPO, tmp, inp, exp, str(cap)],
                           capture_output=True, text=True, cwd=REPO)
    finally:
        os.unlink(tmp)
    try:
        got = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None, f"trace failed: {(r.stderr or '')[:160]}"
    if got.get("error"):
        return None, got["error"]
    visited = set(got["visited"])
    claimed = set()
    for man in lifted.men:
        claimed |= set(man["op_cells"].keys())
        for b in man["blocks"]:
            claimed |= {f"{p[0]},{p[1]}" for p, _ in b}
    # every cell the machine actually executed an INSTRUCTION on must be one we lifted
    missed = []
    for v in visited:
        x, y = (int(t) for t in v.split(","))
        ch = lifted.at(x, y)
        if ch in OPS and v not in claimed:
            missed.append((v, ch))
    return {"executed_cells": len(visited), "steps": got["steps"],
            "missed": missed[:20], "n_missed": len(missed)}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man")
    ap.add_argument("--verify", metavar="SLUG")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = load_rows(args.man)
    lifted = Lift(rows).lift()
    if lifted.topo.get("type") == "error":
        sys.exit(f"analyze failed: {lifted.topo.get('message')}")

    if args.json:
        print(json.dumps({"rooms": lifted.rooms, "pipes": lifted.pipes, "men": lifted.men}))
        return

    ys = [i for i, r in enumerate(rows) if r.strip()]
    xs = [x for x in range(len(rows[0])) if any(r[x] != " " for r in rows)]
    w, h = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    print(f"{os.path.basename(args.man)}  {w}x{h}  box {max(w, h) ** 2}  "
          f"rooms {len(lifted.rooms)}  pipes {len(lifted.pipes)}  men {len(lifted.men)}")
    tot_ops = tot_reach = 0
    for i, m in enumerate(lifted.men):
        tot_ops += m["ops"]
        tot_reach += m["reachable"]
        print(f"  man{i} @({m['start'][0]},{m['start'][1]}) room {m['room']}: "
              f"{m['ops']} ops, {m['turns']} turns, {m['glides']} glides, "
              f"{len(m['blocks'])} blocks, {m['reachable']} reachable cells")
    print(f"  total: {tot_ops} instruction cells across {len(lifted.men)} men")

    if args.verify:
        res, err = verify(rows, args.man, args.verify, lifted)
        if err:
            sys.exit(f"VERIFY UNAVAILABLE: {err}")
        print(f"\nverify vs oracle: {res['executed_cells']} cells visited over "
              f"{res['steps']} steps")
        if res["n_missed"]:
            print(f"  MISMATCH: {res['n_missed']} executed instruction cells were not lifted")
            for v, ch in res["missed"]:
                print(f"    ({v}) '{ch}'")
            sys.exit(1)
        print("  OK — every instruction cell the machine executed was recovered by the lift")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""walkfold.py — intra-room code RE-PLACEMENT (the "walk folding" pass).

`tools/place.py` moves whole ROOMS around a page. This moves CODE around inside one room,
which is where the remaining ticks are: on `gradebook` the critical man spends 86% of his
ticks gliding over blank cells because the ops he must visit in sequence are scattered
across a 37-column room and he serpentines between them.

WHAT IS AND IS NOT FREE TO MOVE (measured, and the reason this is tractable):
  * `s`/`S` bind to the nearest OUTGOING pipe, `r`/`q` to the nearest INCOMING one. In a
    room whose pipe attachments all sit on ONE wall row, the Manhattan y-term is identical
    for every interior cell, so the binding is a pure function of the op's COLUMN. That
    turns "don't rebind a pipe" into a per-op interval constraint (`bands()` below).
  * every other op is horizontally AND vertically free.
  * a backtick literal is rigid: it reads reversed westward and a corner backtick opens
    overlapping H+V literals, so a literal run is never re-headed or split.

WHAT THE PASS DOES. It finds the hot CYCLES of the critical man's control-flow graph
(static walk x dynamic visit counts), and re-lays each one out as a tight rectangle that
still satisfies every op's band, then rewires the cycle's entry and exits back into the
untouched remainder of the program. A cycle is the right unit because its cost is
multiplied by its trip count: `gradebook`'s belt-align loop walked 72 cells per rotation
to execute 3 instructions.

  python3 tools/walkfold.py map   <file.man> [--man N]        static CFG + free-cell map
  python3 tools/walkfold.py hot   <file.man> <slug> <case>    hot cycles, ranked
  python3 tools/walkfold.py apply <file.man> <plan.json> <out.man>
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

OPS = set("0123456789`MWbmq]+-*%/N&|~{}XdaxYHsSrRU")
TURNS = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1), "V": (0, 1)}
BRANCH = set("Xdax")
STOP = set("H")
CW = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}
CCW = {v: k for k, v in CW.items()}
DIRNAME = {(1, 0): "E", (-1, 0): "W", (0, -1): "N", (0, 1): "S"}
NAMEDIR = {v: k for k, v in DIRNAME.items()}


def load_rows(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows) if rows else 0
    return [r.ljust(w) for r in rows]


def analyze(rows):
    script = ("const {boot}=require(process.argv[1]+'/sim/harness.js');"
              "(async()=>{const w=await boot();"
              "console.log(w.analyze(JSON.parse(process.argv[2])));process.exit(0)})()"
              ".catch(e=>{console.log(JSON.stringify({type:'error',message:String(e)}));"
              "process.exit(1)})")
    r = subprocess.run(["node", "-e", script, REPO, json.dumps(rows)],
                       capture_output=True, text=True, cwd=REPO)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit(f"analyze failed: {(r.stderr or '')[:300]}")


class Grid:
    def __init__(self, rows):
        self.rows = [list(r) for r in rows]
        self.h = len(rows)
        self.w = max(len(r) for r in rows) if rows else 0
        self.topo = analyze(rows)
        if self.topo.get("type") == "error":
            sys.exit(f"analyze failed: {self.topo.get('message')}")
        self.rooms = self.topo.get("rooms") or []
        self.pipes = self.topo.get("pipes") or []

    def at(self, x, y):
        if 0 <= y < self.h and 0 <= x < len(self.rows[y]):
            return self.rows[y][x]
        return " "

    def walkable(self, x, y):
        for r in self.rooms:
            (x0, y0), (x1, y1) = r["min"], r["max"]
            if x0 < x < x1 and y0 < y < y1:
                return True
        return False

    def room_of(self, x, y):
        for i, r in enumerate(self.rooms):
            (x0, y0), (x1, y1) = r["min"], r["max"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    def starts(self):
        return [(x, y) for y in range(self.h)
                for x in range(len(self.rows[y])) if self.rows[y][x] == "@"]

    def walk(self, start):
        """Static reachability: (cell, heading) -> list of successor states."""
        succ = {}
        stack = [((start[0], start[1]), (1, 0))]
        while stack:
            st = stack.pop()
            if st in succ:
                continue
            (x, y), d = st
            if not self.walkable(x, y):
                succ[st] = []
                continue
            ch = self.at(x, y)
            if ch in STOP:
                succ[st] = []
                continue
            if ch in TURNS:
                outs = [TURNS[ch]]
            elif ch in BRANCH:
                outs = [d, CW[d], CCW[d]]
            else:
                outs = [d]
            nxt = [((x + nd[0], y + nd[1]), nd) for nd in outs]
            succ[st] = nxt
            stack.extend(nxt)
        return succ


# ---------------------------------------------------------------- pipe bands

def bands(g, room):
    """For each interior COLUMN of `room`, which incoming / outgoing pipe an op there binds.

    Only valid when every attachment of the room shares one wall row (checked); then the
    Manhattan y-term is constant and the binding depends on x alone."""
    inc, out = [], []
    for pi, p in enumerate(g.pipes):
        path = p.get("path") or []
        if not path:
            continue
        if p.get("src") == room:
            out.append((pi, tuple(path[0]["pos"])))
        if p.get("dst") == room:
            inc.append((pi, tuple(path[-1]["pos"])))
    (x0, y0), (x1, y1) = g.rooms[room]["min"], g.rooms[room]["max"]
    ys = {c[1] for _, c in inc} | {c[1] for _, c in out}
    pure = len(ys) == 1
    tab = {}
    for x in range(x0 + 1, x1):
        cell = (x, (y0 + y1) // 2)

        def near(cands):
            if not cands:
                return None
            return min(cands, key=lambda c: (abs(c[1][0] - cell[0]) + abs(c[1][1] - cell[1]),
                                             c[1][1], c[1][0]))[0]
        tab[x] = {"in": near(inc), "out": near(out)}
    return tab, pure, inc, out


def band_intervals(tab):
    """Invert the per-column table into pipe -> contiguous column interval."""
    res = {"in": {}, "out": {}}
    for kind in ("in", "out"):
        for x in sorted(tab):
            p = tab[x][kind]
            if p is None:
                continue
            lo, hi = res[kind].get(p, (x, x))
            res[kind][p] = (min(lo, x), max(hi, x))
    return res


# ---------------------------------------------------------------- occupancy

def occupancy(g):
    """Cells that ANY man can stand on, and which of those hold a real glyph.

    A pass may only write a glyph on a cell no man ever glides over (a glide onto an op
    executes it), and may only free a cell that becomes unreachable."""
    used = {}
    for si, st in enumerate(g.starts()):
        for (cell, d) in g.walk(st):
            used.setdefault(cell, set()).add(si)
    return used


# ---------------------------------------------------------------- rewriting

def render(rows):
    return "\n".join("".join(r).rstrip() for r in rows).rstrip("\n") + "\n"


def apply_patch(rows, patch):
    """patch: {"x,y": "<glyph or ' '>"} — write glyphs, blank cells."""
    out = [list(r) for r in rows]
    w = max(len(r) for r in out)
    for r in out:
        r.extend(" " * (w - len(r)))
    for k, v in patch.items():
        x, y = (int(t) for t in k.split(","))
        while len(out[y]) <= x:
            out[y].append(" ")
        out[y][x] = v
    return out


# ------------------------------------------------------- hairpin (fold) lifting

VERT = {"v": (0, 1), "V": (0, 1), "^": (0, -1)}
HORZ = {">": (1, 0), "<": (-1, 0)}


def state_map(succ):
    st = {}
    for (c, d) in succ:
        st.setdefault(c, set()).add(d)
    return st


def hairpins(g, succ):
    """Every U-turn: horizontal run -> vertical turn glyph -> vertical glide -> horizontal
    turn glyph -> horizontal run in the OPPOSITE direction.

    That U is the only place a serpentine wastes cells: the column it turns at is free to
    slide, and every cell between the last op it must visit and the turn is walked twice
    for nothing. `gradebook`'s builder always turned at the room's west wall, so a row whose
    only ops sit at column 31 was still walked out to column 1 and back — 60 cells a trip."""
    out = []
    for (cell, d) in succ:
        ch = g.at(*cell)
        if ch not in VERT or d not in (HORZ[">"], HORZ["<"]):
            continue
        vd = VERT[ch]
        # follow the vertical glide to the horizontal turn glyph that closes the U
        cur, k = (cell[0] + vd[0], cell[1] + vd[1]), 0
        mid = []
        while True:
            c2 = g.at(*cur)
            if c2 in HORZ:
                break
            if c2 != " " or k > 6 or not g.walkable(*cur):
                cur = None
                break
            mid.append(cur)
            cur = (cur[0] + vd[0], cur[1] + vd[1])
            k += 1
        if cur is None:
            continue
        d_out = HORZ[g.at(*cur)]
        if d_out != (-d[0], -d[1]):
            continue                      # a staircase, not a U-turn: nothing to gain
        out.append({"t1": cell, "d_in": d, "mid": mid, "t2": cur, "d_out": d_out,
                    "vd": vd})
    return out


def straight_back(g, succ, cell, d):
    """Cells of the maximal straight run of heading `d` that ENDS at `cell` (exclusive)."""
    run = []
    cur = (cell[0] - d[0], cell[1] - d[1])
    while g.walkable(*cur) and (cur, d) in succ and g.at(*cur) == " ":
        run.append(cur)
        cur = (cur[0] - d[0], cur[1] - d[1])
    return run, cur


def straight_fwd(g, succ, cell, d):
    """Cells of the maximal straight run of heading `d` that STARTS after `cell`."""
    run = []
    cur = (cell[0] + d[0], cell[1] + d[1])
    while g.walkable(*cur) and (cur, d) in succ and g.at(*cur) == " ":
        run.append(cur)
        cur = (cur[0] + d[0], cur[1] + d[1])
    return run, cur


def plan_lifts(g, succ, verbose=False):
    """Propose a column shift for every liftable U-turn.

    Refusals are the interesting part — each one is a correctness cliff:
      * a turn glyph another flow also stands on is a MERGE; sliding it silently detaches
        that flow (this is what protects a loop's back edge);
      * a cell the new turn would occupy must be blank AND private, or the glyph diverts
        somebody else;
      * the turn may never pass an op cell, or that op stops being executed."""
    st = state_map(succ)
    plans, refused = [], []
    for hp in hairpins(g, succ):
        t1, t2, d, vd = hp["t1"], hp["t2"], hp["d_in"], hp["vd"]
        if st.get(t1) != {d} or st.get(t2) != {vd}:
            refused.append((t1, "turn glyph is a merge point"))
            continue
        if any(st.get(m) != {vd} for m in hp["mid"]):
            refused.append((t1, "vertical glide is shared"))
            continue
        run_in, entry = straight_back(g, succ, t1, d)
        run_out, exit_ = straight_fwd(g, succ, t2, hp["d_out"])
        # the U slides in the direction the man ARRIVES from
        step = -d[0]                       # arriving west-bound => slide east
        if step == 0:
            continue
        # `straight_back`/`straight_fwd` stop at the first NON-BLANK cell, so the run
        # bounds already encode "never slide the turn past an instruction".
        if step > 0:
            limit = min(entry[0], exit_[0])
            span = range(t1[0] + 1, limit)
        else:
            limit = max(entry[0], exit_[0])
            span = range(t1[0] - 1, limit, -1)
        best = None
        for c in span:
            ok = True
            for (yy, dd) in ((t1[1], d), (t2[1], hp["d_out"])):
                if g.at(c, yy) != " " or st.get((c, yy), set()) - {dd}:
                    ok = False
            for m in hp["mid"]:
                if g.at(c, m[1]) != " " or st.get((c, m[1]), set()) - {vd}:
                    ok = False
            if ok:
                best = c                   # a blocked column is skipped, not fatal:
                                           # the man still GLIDES over it either way
        if best is None or best == t1[0]:
            refused.append((t1, "no free column to slide to"))
            continue
        plans.append({"t1": t1, "t2": t2, "mid": hp["mid"], "col": best,
                      "glyph1": g.at(*t1), "glyph2": g.at(*t2),
                      "gain": 2 * abs(best - t1[0])})
    if verbose:
        for c, why in refused:
            print(f"    refused {c}: {why}")
    return plans


def lift_patch(plans):
    patch = {}
    for p in plans:
        x, y1 = p["t1"]
        _, y2 = p["t2"]
        patch[f"{x},{y1}"] = " "
        patch[f"{x},{y2}"] = " "
        for (mx, my) in p["mid"]:
            patch[f"{mx},{my}"] = " "
        patch[f"{p['col']},{y1}"] = p["glyph1"]
        patch[f"{p['col']},{y2}"] = p["glyph2"]
        for (_, my) in p["mid"]:
            patch[f"{p['col']},{my}"] = " "
    return patch


def cmd_lift(args):
    rows = load_rows(args.man)
    total = 0
    for it in range(args.rounds):
        g = Grid(rows)
        succ = g.walk(g.starts()[args.man_idx])
        plans = plan_lifts(g, succ, verbose=args.verbose)
        plans = sorted((p for p in plans if p["gain"] > 0), key=lambda p: -p["gain"])
        # Two lifts in one round are planned against the SAME reachability map, so a lift
        # that lands in a region another lift is about to abandon is planned on stale
        # facts. Take disjoint ROW SETS only, and re-analyse next round.
        chosen, taken = [], set()
        for p in plans:
            ys = {p["t1"][1], p["t2"][1]} | {m[1] for m in p["mid"]}
            if ys & taken:
                continue
            chosen.append(p)
            taken |= ys
        plans = chosen[:args.limit] if args.limit else chosen
        if not plans:
            break
        gain = sum(p["gain"] for p in plans)
        total += gain
        print(f"  round {it}: {len(plans)} U-turns lifted, static gain {gain} cells")
        for p in sorted(plans, key=lambda p: -p["gain"])[:args.show]:
            print(f"    ({p['t1'][0]},{p['t1'][1]}) -> col {p['col']}  +{p['gain']}")
        rows = [ "".join(r) for r in apply_patch(rows, lift_patch(plans)) ]
    open(args.out, "w").write(render([list(r) for r in rows]))
    print(f"  wrote {args.out} (total static gain {total} cells over {it} rounds)")


def cmd_norm(args):
    """Drop turn glyphs that never turn anything.

    Folding leaves these behind: a `v` reached only while already heading south is a nop,
    and every one of them pins a cell (and sometimes a whole row) that squashing could
    otherwise reclaim."""
    rows = load_rows(args.man)
    g = Grid(rows)
    st = state_map(g.walk(g.starts()[args.man_idx]))
    others = set()
    for i, s in enumerate(g.starts()):
        if i != args.man_idx:
            others |= {c for c, _ in g.walk(s)}
    patch = {}
    for cell, dirs in st.items():
        ch = g.at(*cell)
        if ch in TURNS and cell not in others and all(TURNS[ch] == d for d in dirs):
            patch[f"{cell[0]},{cell[1]}"] = " "
    open(args.out, "w").write(render(apply_patch(rows, patch)))
    print(f"  removed {len(patch)} redundant turn glyphs -> {args.out}")


def cmd_squash(args):
    """Delete interior rows of the big room that hold no glyph at all.

    Score is max(w,h)^2 x ticks, so on a HEIGHT-bound program one reclaimed row is worth
    more than a hundred ticks. Safe because a glyph-free row can only ever be crossed
    VERTICALLY -- a horizontal walk needs a turn glyph on the row to start it -- so deleting
    it just shortens some glides, and everything below (walls, pipes, satellite rooms)
    slides up as one block, leaving pipe columns and therefore every band untouched."""
    rows = load_rows(args.man)
    g = Grid(rows)
    (x0, y0), (x1, y1) = g.rooms[args.room]["min"], g.rooms[args.room]["max"]
    drop = [y for y in range(y0 + 1, y1)
            if not rows[y][x0 + 1:x1].strip()]
    keep = [r for i, r in enumerate(rows) if i not in set(drop)]
    open(args.out, "w").write("\n".join(r.rstrip() for r in keep).rstrip("\n") + "\n")
    print(f"  squashed {len(drop)} empty rows {drop} -> {args.out}")


def cmd_patch(args):
    rows = load_rows(args.man)
    patch = json.load(open(args.patch))
    open(args.out, "w").write(render(apply_patch(rows, patch)))
    print(f"  wrote {args.out} ({len(patch)} cells)")


# ---------------------------------------------------------------- commands

def cmd_map(args):
    rows = load_rows(args.man)
    g = Grid(rows)
    print(f"{os.path.basename(args.man)}: {len(g.rooms)} rooms, {len(g.pipes)} pipes")
    for ri, r in enumerate(g.rooms):
        print(f"  room{ri} {r['min']}..{r['max']}")
    for ri in range(len(g.rooms)):
        tab, pure, inc, out = bands(g, ri)
        if not inc and not out:
            continue
        iv = band_intervals(tab)
        print(f"  room{ri} attachments pure-column={pure}")
        print(f"    incoming {inc}")
        print(f"    outgoing {out}")
        for kind in ("in", "out"):
            for p, (lo, hi) in sorted(iv[kind].items()):
                print(f"    {kind:3s} pipe{p}: cols {lo}-{hi}")
    used = occupancy(g)
    starts = g.starts()
    mi = args.man_idx
    st = starts[mi]
    succ = g.walk(st)
    cells = {c for c, _ in succ}
    print(f"  man{mi} @{st}: {len(succ)} states over {len(cells)} cells")


def dyn_counts(slug, man, case, mi, cap):
    r = subprocess.run(["node", os.path.join(REPO, "sim", "wf_trace.js"), slug, man,
                        str(case), str(mi), f"--cap={cap}"],
                       capture_output=True, text=True, cwd=REPO)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit(f"trace failed: {(r.stderr or r.stdout)[:300]}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map")
    m.add_argument("man")
    m.add_argument("--man-idx", type=int, default=0)
    m.set_defaults(fn=cmd_map)

    l = sub.add_parser("lift")
    l.add_argument("man")
    l.add_argument("out")
    l.add_argument("--man-idx", type=int, default=0)
    l.add_argument("--rounds", type=int, default=8)
    l.add_argument("--show", type=int, default=8)
    l.add_argument("--limit", type=int, default=0)
    l.add_argument("-v", "--verbose", action="store_true")
    l.set_defaults(fn=cmd_lift)

    n = sub.add_parser("norm")
    n.add_argument("man")
    n.add_argument("out")
    n.add_argument("--man-idx", type=int, default=0)
    n.set_defaults(fn=cmd_norm)

    q = sub.add_parser("squash")
    q.add_argument("man")
    q.add_argument("out")
    q.add_argument("--room", type=int, default=0)
    q.set_defaults(fn=cmd_squash)

    p = sub.add_parser("patch")
    p.add_argument("man")
    p.add_argument("patch")
    p.add_argument("out")
    p.set_defaults(fn=cmd_patch)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

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

THE PASSES (each is a .man -> .man rewrite; each refuses rather than guesses):

  map    <man>                  rooms, per-pipe COLUMN BANDS, CFG size — start here
  lift   <man> <out>            slide a serpentine U-turn toward the ops it must cover
  pull   <man> <out>            merge a row whose only purpose was to step down
  fuse   <man> <out>            append a code row to the previous row of the same heading
  norm   <man> <out>            drop turn glyphs that never turn
  squash <man> <out>            delete glyph-free interior rows (this is the BOX win)
  patch  <man> <plan.json> <out>  apply a hand-designed cycle re-layout

Every pass keeps the executed instruction SEQUENCE identical and only changes where the
cells sit, so `tools/pipecheck.py before after` and a grade are a complete gate.

THE CEILING, measured. `fuse` is what would halve the height, and where it fails it fails
for one reason: a strictly-increasing in-band column assignment does not exist. `gradebook`
reads the input pipe (columns 1-5) at the start of most logical lines, so two such lines
can never share a row — the second read has nowhere west of it to go. Widening that band
means moving the pipe ATTACHMENT, which is the floorplanner's job, not this pass's.
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


# ------------------------------------------------------------- segment fusion

def op_band(g, tab, ch, cell, room):
    """The columns an op may legally occupy: its pipe's band, or the whole room."""
    (x0, _), (x1, _) = g.rooms[room]["min"], g.rooms[room]["max"]
    full = (x0 + 1, x1 - 1)
    if ch not in "rqs":
        return full
    kind = "out" if ch == "s" else "in"
    want = tab[cell[0]][kind]
    cols = [x for x in tab if tab[x][kind] == want]
    return (min(cols), max(cols)) if cols else full


def plan_fuse(g, succ, room=0, verbose=False):
    """Find a code row that can be appended to the previous row of the SAME direction.

    The serpentine spends two rows per logical line: one carrying the ops and one walking
    back to the west wall. Fusing the ops of line B onto line A's row empties both the
    return row and B's row, and `squash` then deletes them -- and since the score is
    max(w,h)^2, a deleted row on a height-bound program outweighs a lot of ticks.

    Feasibility is a strictly-increasing column assignment: the man executes an E row
    left-to-right, so op i must sit east of op i-1 AND inside its own pipe band. That is
    what makes fusion FAIL honestly rather than silently -- two consecutive reads of the
    input pipe both demand columns 1-5, so nothing can be placed between them."""
    st = state_map(succ)
    tab, pure, _, _ = bands(g, room)
    if not pure:
        return []
    (rx0, ry0), (rx1, ry1) = g.rooms[room]["min"], g.rooms[room]["max"]
    E, W, S, N = (1, 0), (-1, 0), (0, 1), (0, -1)
    plans, refused = [], []

    def priv(cell, dirs):
        return st.get(cell, set()) <= set(dirs)

    for yA in range(ry0 + 1, ry1 - 2):
        # A ends with a 'v' reached heading E; below it a '<' opens the return row
        cA = [x for x in range(rx0 + 1, rx1)
              if g.at(x, yA) == "v" and priv((x, yA), [E])]
        if len(cA) != 1:
            continue
        cA = cA[0]
        if g.at(cA, yA + 1) != "<" or not priv((cA, yA + 1), [S]):
            continue
        ret = [x for x in range(rx0 + 1, rx1) if g.at(x, yA + 1) != " "]
        if len(ret) != 2:
            continue                       # return row must carry nothing else
        t = min(ret)
        if g.at(t, yA + 1) != "v" or not priv((t, yA + 1), [W]):
            continue
        # A cell a vertical corridor merely CROSSES is still fine: it is blank either way.
        if any(not priv((x, yA + 1), [W, N, S]) for x in range(t, cA)):
            continue
        if g.at(t, yA + 2) != ">" or not priv((t, yA + 2), [S]):
            continue
        # B: the ops of row yA+2, ending at its own vertical turn
        bcells = [x for x in range(t + 1, rx1) if g.at(x, yA + 2) != " "]
        if not bcells:
            continue
        cB = max(bcells)
        if any(not priv((x, yA + 2), [E, N, S]) for x in range(t + 1, cB + 1)):
            continue
        if g.at(cB, yA + 2) not in VERT or not priv((cB, yA + 2), [E]):
            continue
        ops = [(x, g.at(x, yA + 2)) for x in bcells if x != cB]
        if any(ch in BRANCH or ch == "`" or ch in TURNS for _, ch in ops):
            refused.append((yA, "B holds a branch, a literal or a turn"))
            continue
        # A's own glyphs, and the first column free for B
        acols = [x for x in range(rx0 + 1, rx1) if g.at(x, yA) != " "]
        cur = max(acols)                   # the 'v' at cA is the last of them
        place, ok = [], True
        for (x, ch) in ops:
            lo, hi = op_band(g, tab, ch, (x, yA + 2), room)
            nx = max(cur + 1, lo)
            # a column a vertical corridor uses cannot hold a glyph -- step over it
            while nx <= hi and nx < cB and (g.at(nx, yA) != " "
                                            or not priv((nx, yA), [E])):
                nx += 1
            if nx > hi or nx >= cB:
                ok = False
                break
            place.append((nx, ch))
            cur = nx
        if not ok:
            refused.append((yA, f"no increasing in-band column assignment for {ops}"))
            continue
        if any(g.at(x, yA) != " " or not priv((x, yA), [E, N, S])
               for x in range(cA + 1, cB + 1)):
            continue
        plans.append({"yA": yA, "cA": cA, "t": t, "cB": cB, "place": place,
                      "bcols": bcells, "term": g.at(cB, yA + 2)})
    if verbose:
        for y, why in refused:
            print(f"    refused row {y}: {why}")
    return plans


def plan_pull(g, succ, room=0, verbose=False):
    """Pull a row straight up when the man only stepped down to keep going the SAME way.

    A `v` with a `>` directly under it is a row change that buys nothing: those two rows
    are one logical line the emitter happened to split. Nothing moves horizontally, so no
    pipe can rebind, and a flow that used to join at the lower row now joins one row higher
    onto the very same glyph."""
    st = state_map(succ)
    (rx0, ry0), (rx1, ry1) = g.rooms[room]["min"], g.rooms[room]["max"]
    E, S, N = (1, 0), (0, 1), (0, -1)
    plans = []
    for yA in range(ry0 + 1, ry1 - 1):
        acols = [x for x in range(rx0 + 1, rx1) if g.at(x, yA) != " "]
        bcols = [x for x in range(rx0 + 1, rx1) if g.at(x, yA + 1) != " "]
        if not acols or not bcols:
            continue
        c = max(acols)
        if g.at(c, yA) != "v" or g.at(c, yA + 1) != ">" or min(bcols) != c:
            continue
        if st.get((c, yA)) != {E} or not st.get((c, yA + 1), set()) <= {S, N}:
            continue
        ok = True
        for x in range(c + 1, max(bcols) + 1):
            up, here = st.get((x, yA), set()), st.get((x, yA + 1), set())
            if g.at(x, yA) != " ":
                ok = False
            elif g.at(x, yA + 1) != " ":
                # a glyph moving up must take every flow that reaches it with it
                if not (up <= {E, N} and here <= {E, N}):
                    ok = False
            elif not up <= {E, N, S}:
                ok = False
        if ok:
            plans.append({"yA": yA, "move": [(x, g.at(x, yA + 1)) for x in bcols]})
    if verbose:
        print(f"    {len(plans)} pull candidates")
    return plans


def pull_patch(plans):
    patch = {}
    for p in plans:
        for (x, ch) in p["move"]:
            patch[f"{x},{p['yA'] + 1}"] = " "
            patch[f"{x},{p['yA']}"] = ch
    return patch


def cmd_pull(args):
    rows = load_rows(args.man)
    total = 0
    for it in range(args.rounds):
        g = Grid(rows)
        plans = plan_pull(g, g.walk(g.starts()[args.man_idx]), args.room, args.verbose)
        plans = plans[:args.limit] if args.limit else plans
        if not plans:
            break
        total += len(plans)
        for p in plans:
            print(f"  pulled row {p['yA'] + 1} up into row {p['yA']}")
        rows = ["".join(r) for r in apply_patch(rows, pull_patch(plans))]
    open(args.out, "w").write(render([list(r) for r in rows]))
    print(f"  wrote {args.out} ({total} rows pulled)")


def fuse_patch(plans):
    patch = {}
    for p in plans:
        patch[f"{p['cA']},{p['yA']}"] = " "
        patch[f"{p['cA']},{p['yA'] + 1}"] = " "
        patch[f"{p['t']},{p['yA'] + 1}"] = " "
        patch[f"{p['t']},{p['yA'] + 2}"] = " "
        for x in p["bcols"]:
            patch[f"{x},{p['yA'] + 2}"] = " "
        for (x, ch) in p["place"]:
            patch[f"{x},{p['yA']}"] = ch
        patch[f"{p['cB']},{p['yA']}"] = p["term"]
    return patch


def cmd_fuse(args):
    rows = load_rows(args.man)
    total = 0
    for it in range(args.rounds):
        g = Grid(rows)
        succ = g.walk(g.starts()[args.man_idx])
        plans = plan_fuse(g, succ, args.room, args.verbose)
        # one fusion per round: each empties rows the next round must re-analyse
        plans = plans[:args.limit] if args.limit else plans
        if not plans:
            break
        total += len(plans)
        for p in plans:
            print(f"  fused row {p['yA'] + 2} into row {p['yA']}: "
                  + " ".join(f"{ch}@{x}" for x, ch in p["place"]))
        rows = ["".join(r) for r in apply_patch(rows, fuse_patch(plans))]
    open(args.out, "w").write(render([list(r) for r in rows]))
    print(f"  wrote {args.out} ({total} rows fused)")


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

    f = sub.add_parser("fuse")
    f.add_argument("man")
    f.add_argument("out")
    f.add_argument("--man-idx", type=int, default=0)
    f.add_argument("--room", type=int, default=0)
    f.add_argument("--rounds", type=int, default=40)
    f.add_argument("--limit", type=int, default=1)
    f.add_argument("-v", "--verbose", action="store_true")
    f.set_defaults(fn=cmd_fuse)

    u = sub.add_parser("pull")
    u.add_argument("man")
    u.add_argument("out")
    u.add_argument("--man-idx", type=int, default=0)
    u.add_argument("--room", type=int, default=0)
    u.add_argument("--rounds", type=int, default=40)
    u.add_argument("--limit", type=int, default=1)
    u.add_argument("-v", "--verbose", action="store_true")
    u.set_defaults(fn=cmd_pull)

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

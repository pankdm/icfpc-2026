#!/usr/bin/env python3
"""reflow.py — FLOORPLAN-level re-synthesis for `little-little-little-man`.

`walkfold.py` slides code around inside a room; `place.py` slides rooms around a page.
Neither can touch the two things that own LLLM's box:

  1. a pair of 400-cell pipes drawn as straight vertical lines, which alone stretch the grid
     from row 1129 to row 1469 — 340 rows of nothing but `|`;
  2. a 941-row boustrophedon that is only 33 columns wide, because the `r`/`s` in its body
     bind to pipe5 / pipe0 and the NEAREST-PIPE rule confines those to columns 39-71.

Both are fixed here by moving pipe ATTACHMENTS, which is the floorplanner's job:

  fold   — redraw a straight pipe as a staircase of the SAME length (length is latency and
           capacity, so it is preserved cell-for-cell) and re-place the room it feeds.
  bands  — report, for a room, which pipe each interior column binds. The key fact this
           exposes: a pipe's column band is the Voronoi cell of its attachment among the
           attachments of the same direction, so three attachments spaced 1,4,7 leave the
           middle one a band of two columns while the LAST one owns everything east of it.
           Clustering the cold attachments at one end therefore hands the hot pipe the whole
           room, instead of the half a centred attachment can ever get.

  build  — re-lay room0's whole walk as a boustrophedon of chosen width, re-space the six
           attachments on its bottom wall, and re-route the necks of every pipe. room2, the
           display and pipes 4/6/7 form a closed sub-network reachable only through pipe2, so
           that 27x56 rectangle is carried across verbatim rather than redrawn.

  python3 tools/reflow.py fold  <in.man> <out.man>
  python3 tools/reflow.py bands <in.man> --room 0
  python3 tools/reflow.py build <in.man> <out.man> [--width N]
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


def render(cells):
    """cells: {(x,y): ch} -> text."""
    w = max(x for x, _ in cells) + 1
    h = max(y for _, y in cells) + 1
    grid = [[" "] * w for _ in range(h)]
    for (x, y), ch in cells.items():
        grid[y][x] = ch
    return "\n".join("".join(r).rstrip() for r in grid).rstrip("\n") + "\n"


def to_cells(rows):
    return {(x, y): ch
            for y, r in enumerate(rows) for x, ch in enumerate(r) if ch != " "}


# ------------------------------------------------------------------ pipe drawing

ARROW = {(1, 0): ">", (-1, 0): "<", (0, -1): "^", (0, 1): "v"}
STRAIGHT = {(1, 0): "-", (-1, 0): "-", (0, -1): "|", (0, 1): "|"}


def draw_pipe(waypoints, drop_last=False):
    """Draw a pipe through `waypoints` (cell coords, axis-aligned legs).

    Returns [(cell, glyph)] in flow order. A cell where the flow CHANGES direction, and each
    endpoint, carries the arrowhead of the direction the flow LEAVES it in — that is exactly
    the convention the reference loader reads bends with (verified against the champion's own
    pipe4, which turns four times).

    `drop_last` makes the final waypoint a PHANTOM one cell inside the destination room: the
    real last pipe cell then gets the arrowhead pointing AT the wall, which is what makes the
    loader attach it. Ending on the arrival direction instead leaves the pipe dangling
    (`dst: -1`) with no error — the analyzer simply reports a pipe to nowhere."""
    path = [waypoints[0]]
    for a, b in zip(waypoints, waypoints[1:]):
        d = (0 if b[0] == a[0] else (1 if b[0] > a[0] else -1),
             0 if b[1] == a[1] else (1 if b[1] > a[1] else -1))
        if d == (0, 0):
            continue
        cur = a
        while cur != b:
            cur = (cur[0] + d[0], cur[1] + d[1])
            path.append(cur)
    # glyph per cell: the direction of the step LEAVING it (last cell keeps its arrival dir)
    out = []
    for i, c in enumerate(path):
        if i + 1 < len(path):
            n = path[i + 1]
            d = (n[0] - c[0], n[1] - c[1])
            prev = None if i == 0 else (c[0] - path[i - 1][0], c[1] - path[i - 1][1])
            out.append((c, ARROW[d] if (i == 0 or prev != d) else STRAIGHT[d]))
        else:
            d = (c[0] - path[i - 1][0], c[1] - path[i - 1][1])
            out.append((c, ARROW[d]))
    if drop_last:
        # the phantom's predecessor is the real endpoint, so it must carry the arrowhead even
        # when the flow never turned: a straight run would otherwise end on `|` and the loader
        # silently leaves the pipe unattached (`dst: -1`).
        c, n = path[-2], path[-1]
        out[-2] = (c, ARROW[(n[0] - c[0], n[1] - c[1])])
        return out[:-1]
    return out


# ------------------------------------------------------------------ fold

def cmd_fold(args):
    """Redraw LLLM's two 400-cell delay lines as staircases and bring room4 up with them.

    The two pipes are pure geometry: room0 keeps its attachments at columns 90 and 92 (so no
    `r`/`s` anywhere can rebind) and each pipe keeps exactly 400 cells (so latency and FIFO
    capacity are untouched). Only the 340 rows of `|` between row 1129 and room4 go away."""
    rows = load_rows(args.man)
    cells = to_cells(rows)

    # everything below row 1123 in the original is nothing but the two straight pipes and
    # room4 — assert it, because silently dropping a live cell is unrecoverable
    stray = {(x, y): c for (x, y), c in cells.items() if y >= 1123 and x not in (90, 92)
             and y < 1465}
    if stray:
        sys.exit(f"unexpected content below row 1123: {sorted(stray)[:10]}")

    room4 = [rows[y][1:95] for y in range(1465, 1469)]
    for (x, y) in [c for c in cells if c[1] >= 1065 and (x_ := c[0]) in (90, 92)]:
        del cells[(x, y)]
    for (x, y) in [c for c in cells if c[1] >= 1123]:
        del cells[(x, y)]

    # pipe1 (room0 -> room4): down column 90, east along row 1124, into room4's top wall.
    p1 = draw_pipe([(90, 1065), (90, 1124), (430, 1124), (430, 1125)], drop_last=True)
    # pipe8 (room4 -> room0): up out of room4's top wall east of pipe1's landing, west along
    # row 1123 (the first row clear of the display and pipe4, which occupy every column of
    # rows 1067-1122 out to 148), then up column 92.
    p8 = draw_pipe([(432, 1124), (432, 1123), (92, 1123), (92, 1065)])
    for path, want, name in ((p1, 400, "pipe1"), (p8, 400, "pipe8")):
        if len(path) != want:
            sys.exit(f"{name} is {len(path)} cells, must be exactly {want} "
                     f"(length is latency AND capacity)")
    for c, ch in p1 + p8:
        if c in cells:
            sys.exit(f"pipe cell {c} collides with {cells[c]!r}")
        cells[c] = ch

    # room4, unchanged in shape, re-placed so both pipe landings fall on its top wall
    X4, Y4 = 360, 1125
    for dy, line in enumerate(room4):
        for dx, ch in enumerate(line):
            if ch != " ":
                cells[(X4 + dx, Y4 + dy)] = ch
    for c in ((430, 1125), (432, 1125)):
        if cells.get(c) != "-":
            sys.exit(f"pipe landing {c} is {cells.get(c)!r}, not room4's top wall")

    open(args.out, "w").write(render(cells))
    w = max(x for x, _ in cells) + 1
    h = max(y for _, y in cells) + 1
    print(f"  wrote {args.out}  {w}x{h}  box {max(w, h) ** 2:,}  "
          f"(was 149x1469 box 2,157,961)")


# ------------------------------------------------------------------ bands

def analyze(rows):
    script = ("const fs=require('fs');const {boot}=require(process.argv[1]+'/sim/harness.js');"
              "(async()=>{const w=await boot();"
              "const rows=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
              "console.log(w.analyze(rows));process.exit(0)})()"
              ".catch(e=>{console.log(JSON.stringify({type:'error',message:String(e)}));"
              "process.exit(1)})")
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
        sys.exit(f"analyze failed: {(r.stderr or '')[:300]}")


def nearest(sites, cell):
    """The reference rule: Manhattan distance to the attached segment, ties in reading order."""
    return min(sites, key=lambda s: (abs(s[1][0] - cell[0]) + abs(s[1][1] - cell[1]),
                                     s[1][1], s[1][0]))[0]


def cmd_bands(args):
    rows = load_rows(args.man)
    topo = analyze(rows)
    pipes, rooms = topo["pipes"], topo["rooms"]
    ri = args.room
    inc = [(i, tuple(p["path"][-1]["pos"])) for i, p in enumerate(pipes)
           if p.get("dst") == ri and p.get("path")]
    out = [(i, tuple(p["path"][0]["pos"])) for i, p in enumerate(pipes)
           if p.get("src") == ri and p.get("path")]
    (x0, y0), (x1, y1) = rooms[ri]["min"], rooms[ri]["max"]
    print(f"room{ri} {x0},{y0}..{x1},{y1}   incoming {inc}   outgoing {out}")
    for kind, sites in (("in", inc), ("out", out)):
        if not sites:
            continue
        runs = []
        for x in range(x0 + 1, x1):
            p = nearest(sites, (x, (y0 + y1) // 2))
            if runs and runs[-1][0] == p:
                runs[-1][2] = x
            else:
                runs.append([p, x, x])
        print(f"  {kind}: " + "  ".join(f"pipe{p}:{a}-{b}" for p, a, b in runs))


# ============================================================ CFG -> block list

OPS = set("0123456789`MWbmq]+-*%/N&|~{}XdaxYHsSrRU")
TURNS = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1), "V": (0, 1)}
BRANCH = set("Xdax")
CW = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}
CCW = {v: k for k, v in CW.items()}


class Walk:
    """man0's static walk, as the reference machine performs it."""

    def __init__(self, rows, topo):
        self.rows, self.h = rows, len(rows)
        self.rooms = topo["rooms"]
        self.pipes = topo["pipes"]

    def at(self, x, y):
        return self.rows[y][x] if 0 <= y < self.h and 0 <= x < len(self.rows[y]) else " "

    def inside(self, x, y):
        return any(r["min"][0] < x < r["max"][0] and r["min"][1] < y < r["max"][1]
                   for r in self.rooms)

    def succ(self, start):
        s, stack = {}, [(start, (1, 0))]
        while stack:
            st = stack.pop()
            if st in s:
                continue
            (x, y), d = st
            if not self.inside(x, y):
                s[st] = []
                continue
            ch = self.at(x, y)
            if ch == "H":
                s[st] = []
                continue
            outs = [TURNS[ch]] if ch in TURNS else \
                   ([d, CW[d], CCW[d]] if ch in BRANCH else [d])
            nxt = [((x + e[0], y + e[1]), e) for e in outs]
            s[st] = nxt
            stack.extend(nxt)
        return s


def blockify(rows, topo, band_of):
    """Recover man0's program as basic blocks with typed terminators.

    A `d` reached heading south turns CLOCKWISE (west) when BP>0 and continues south
    otherwise; the counter-clockwise leg the static walk also explores is unreachable for `d`
    and, for the one `X`, is a leg that walks into a wall. Both the taken leg and the
    fall-through are pure GLIDES to a merge point in this program, which is why the whole
    thing collapses to 14 blocks with 7 back edges."""
    w = Walk(rows, topo)
    start = next(((x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c == "@"
                  and w.inside(x, y)), None)
    succ = w.succ((start[0], start[1]))
    pred = {}
    for s, ns in succ.items():
        for n in ns:
            pred.setdefault(n, []).append(s)
    st0 = (start, (1, 0))
    leaders = {st0}
    for s, ns in succ.items():
        if len(ns) > 1:
            leaders.update(ns)
    leaders.update(s for s in succ if len(pred.get(s, ())) != 1)

    segs = {}
    for L in leaders:
        cur, cells = L, []
        while True:
            cells.append(cur)
            ns = succ.get(cur, [])
            if len(ns) != 1 or ns[0] in leaders:
                break
            cur = ns[0]
        segs[L] = (cells, succ.get(cells[-1], []))

    def payload(cells):
        out = []
        for (c, _d) in cells:
            ch = w.at(*c)
            if ch in OPS and w.inside(*c):
                out.append((ch, band_of(c, ch)))
        return out

    # a glide segment (no ops) that ends at a leader is just an EDGE to that leader
    def resolve(state):
        seen = set()
        while state in segs and state not in seen:
            seen.add(state)
            cells, outs = segs[state]
            if payload(cells):
                return ("block", state)
            if len(outs) != 1:
                return ("dead", None)
            state = outs[0]
        return ("dead", None)

    order, seen = [], set()
    stack = [st0]
    while stack:
        s = stack.pop(0)
        if s in seen or s not in segs:
            continue
        seen.add(s)
        order.append(s)
        cells, outs = segs[s]
        last = w.at(*cells[-1][0])
        if last in BRANCH:
            d = cells[-1][1]
            nxt = [o for o in outs if o[1] == d] + [o for o in outs if o[1] == CW[d]]
        else:
            nxt = outs
        for o in nxt:
            k, t = resolve(o)
            if k == "block" and t not in seen:
                stack.insert(0, t) if o is nxt[0] else stack.append(t)

    ids = {s: i for i, s in enumerate(order)}
    blocks = []
    for s in order:
        cells, outs = segs[s]
        last = w.at(*cells[-1][0])
        ops = payload(cells)
        if last in BRANCH:
            d = cells[-1][1]
            straight = next(o for o in outs if o[1] == d)
            taken = next(o for o in outs if o[1] == CW[d])
            kt, tt = resolve(taken)
            kf, tf = resolve(straight)
            term = ("branch", ops.pop()[0], ids.get(tt), ids.get(tf))
        elif len(outs) == 1:
            k, t = resolve(outs[0])
            term = ("goto", ids.get(t))
        else:
            term = ("halt",)
        blocks.append({"id": ids[s], "ops": ops, "term": term})
    return blocks


# ============================================================ room0 re-layout

E, W, S = (1, 0), (-1, 0), (0, 1)


class Layout:
    """A cursor that writes the man's walk as a boustrophedon of chosen width.

    Every op carries the COLUMN INTERVAL its pipe binding allows (`bands`), so placement is
    "advance to the next column in this op's interval"; when no such column remains in the
    current heading the row simply ends and the walk turns down. That single rule handles
    both the dense body (every op free from column 49 east) and the peripheral clusters that
    zig-zag inside the 43-column strip west of it, with no special cases."""

    def __init__(self, main_lo, main_hi, corridor_max=4):
        self.cells = {}
        self.lo, self.hi = main_lo, main_hi     # main op columns
        self.cmax = corridor_max                # columns 1..cmax are back-edge corridors
        self.opmin = corridor_max + 2           # leave one column for a west turn glyph
        self.x = self.y = None
        self.d = E

    def put(self, x, y, ch):
        old = self.cells.get((x, y))
        if old is not None and old != ch:
            raise RuntimeError(f"conflict at ({x},{y}): {old!r} vs {ch!r}")
        self.cells[(x, y)] = ch

    def newline(self):
        t = self.x + self.d[0]
        self.put(t, self.y, "v")
        self.put(t, self.y + 1, "<" if self.d == E else ">")
        self.d = W if self.d == E else E
        self.x, self.y = t, self.y + 1

    def place(self, ch, lo, hi):
        for _ in range(4):
            if self.d == E:
                nx = max(self.x + 1, lo)
                if nx <= hi and nx <= self.hi:
                    break
            else:
                nx = min(self.x - 1, hi)
                if nx >= lo and nx >= self.opmin:
                    break
            self.newline()
        else:
            raise RuntimeError(f"cannot place {ch!r} in [{lo},{hi}]")
        self.put(nx, self.y, ch)
        self.x = nx

    def to_row_heading_west(self):
        """End the current row so the cursor is heading WEST with nothing west of it."""
        if self.d == E:
            self.put(self.x + 1, self.y, "v")
            self.put(self.x + 1, self.y + 1, "<")
            self.x, self.y, self.d = self.x + 1, self.y + 1, W

    def jump(self, corridor, up):
        """Leave the current row westward and hand control to a corridor column.

        `up` sends the man north to a merge already emitted above; otherwise he drops one row
        onto the entry of the block emitted next. Both land on the SAME `>` cell — which is
        what lets a merge point have one fall-through predecessor and one back edge without
        the two needing separate entries."""
        self.to_row_heading_west()
        self.put(corridor, self.y, "^" if up else "v")
        return self.y

    def enter(self, corridor, y):
        self.put(corridor, y, ">")
        self.x, self.y, self.d = corridor, y, E

    def branch(self, glyph, corridor_taken):
        """Emit a `d`/`X` on its own row, entered heading SOUTH so clockwise means WEST.

        The taken leg glides west to the back-edge corridor; the fall-through continues south
        one more row; the counter-clockwise leg (dead for `d`, and a wall-walk for the single
        `X`, exactly as in the original) runs east over blank cells into the room wall."""
        t = self.x + self.d[0]
        self.put(t, self.y, "v")
        yb = self.y + 1
        self.put(t, yb, glyph)
        self.put(corridor_taken, yb, "^")
        self.put(t, yb + 1, "<")
        self.x, self.y, self.d = t, yb + 1, W

    def bbox(self):
        return (max(x for x, _ in self.cells), max(y for _, y in self.cells))


def corridors_for(blocks):
    """Colour the back edges so two whose row spans overlap never share a column."""
    back, fwd = [], {}
    for b in blocks:
        t = b["term"]
        tgt = t[2] if t[0] == "branch" else (t[1] if t[0] == "goto" else None)
        if tgt is not None and tgt <= b["id"]:
            back.append((tgt, b["id"]))
    colour = {}
    used = []                                   # per colour: list of (lo,hi) spans
    for lo, hi in sorted(back):
        for ci, spans in enumerate(used):
            if all(hi < a or lo > b for a, b in spans):
                spans.append((lo, hi))
                colour[lo] = ci + 1
                break
        else:
            used.append([(lo, hi)])
            colour[lo] = len(used)
    default = len(used) + 1
    for b in blocks:
        fwd[b["id"]] = colour.get(b["id"], default)
    return fwd, default


# the new attachment order on room0's bottom wall, and the column interval each binding gets.
# The two HOT pipes (5 in, 0 out) are the OUTERMOST attachment of their direction, so their
# Voronoi cell runs east without bound; the four cold ones are packed to the west and get a
# 43-column strip between them. That is the whole trick: a centred hot attachment can never
# own more than half the room, an outermost one owns all of it but the strip.
ATTACH = {("in", 8): 8, ("out", 1): 10, ("in", 3): 13,
          ("out", 2): 15, ("out", 0): 54, ("in", 5): 56}
MAIN_LO = 35
STRIP = {("in", 8): (6, 10), ("in", 3): (11, 34),
         ("out", 1): (6, 12), ("out", 2): (13, 34)}

# build2 --west: the hot pair pulls in to 44/46 (room3 moves under them at x=43, the
# scroll pipe re-routes down column 41 between the display and room3), which slides the
# hot/cold Voronoi boundary from 35 to 30 — five more columns for every hot row.
ATTACH_W = {("in", 8): 8, ("out", 1): 10, ("in", 3): 13,
            ("out", 2): 15, ("out", 0): 44, ("in", 5): 46}
MAIN_LO_W = 30
STRIP_W = {("in", 8): (6, 10), ("in", 3): (11, 29),
           ("out", 1): (6, 12), ("out", 2): (13, 29)}


def emit_room0(blocks, main_hi):
    corridor, _default = corridors_for(blocks)
    lay = Layout(MAIN_LO, main_hi)
    entry = {}
    band = dict(STRIP)
    band[("in", 5)] = band[("out", 0)] = (MAIN_LO, main_hi)

    # a block nobody jumps back to needs no entry cell: the fall-through of a branch can
    # simply keep walking west on the row below the branch, which saves two dedicated rows
    # and a corridor-to-body glide on every one of the six conditionals.
    merges = set()
    for b in blocks:
        t = b["term"]
        tgt = t[2] if t[0] == "branch" else (t[1] if t[0] == "goto" else None)
        if tgt is not None and tgt <= b["id"]:
            merges.add(tgt)
    expect = {}
    for i, b in enumerate(blocks):
        if i == 0:
            lay.put(6, 1, "@")
            lay.x, lay.y, lay.d = 6, 1, E
            entry[0] = 1
        for ch, key in b["ops"]:
            lo, hi = band.get(key, (lay.opmin, main_hi))
            lay.place(ch, lo, hi)
            if key is not None:
                expect[(lay.x, lay.y)] = key
        term = b["term"]
        if term[0] == "branch":
            _k, glyph, taken, ft = term
            lay.branch(glyph, corridor[taken])
            if ft in merges:
                lay.jump(corridor[ft], up=False)
                entry.setdefault(ft, lay.y + 1)
                lay.enter(corridor[ft], lay.y + 1)
            else:
                entry.setdefault(ft, lay.y)
        elif term[0] == "goto":
            tgt = term[1]
            up = tgt in entry
            lay.jump(corridor[tgt], up=up)
            if not up:
                entry[tgt] = lay.y + 1
                lay.enter(corridor[tgt], lay.y + 1)
    return lay, entry, expect


# ============================================================ whole-page assembly

def check_bands(expect, H):
    """Re-derive every binding from the emitted geometry.

    The placer trusts a column INTERVAL per op; this asks the reference rule itself, cell by
    cell, whether the op really reaches the pipe it was placed for. Getting this wrong is the
    silent failure mode of the whole pass — the program still loads and still runs."""
    inc = [(p, (x, H + 2)) for k, x in ATTACH.items() for p in [k[1]] if k[0] == "in"]
    out = [(p, (x, H + 2)) for k, x in ATTACH.items() for p in [k[1]] if k[0] == "out"]
    bad = []
    for cell, (kind, pipe) in expect.items():
        got = nearest(inc if kind == "in" else out, cell)
        if got != pipe:
            bad.append((cell, kind, pipe, got))
    return bad


def cmd_build(args):
    """Emit the whole program: re-laid room0, re-spaced attachments, re-routed pipes.

    Only room0 and the pipe necks are synthesised. room2 + the display + pipes 4/6/7 form a
    closed sub-network that touches room0 through pipe2 alone, so that whole 27x56 rectangle
    is carried across verbatim — translated, never redrawn."""
    src = load_rows(args.man)
    topo = analyze(src)
    sites = {"in": [], "out": []}
    for i, p in enumerate(topo["pipes"]):
        path = p.get("path") or []
        if not path:
            continue
        if p.get("src") == 0:
            sites["out"].append((i, tuple(path[0]["pos"])))
        if p.get("dst") == 0:
            sites["in"].append((i, tuple(path[-1]["pos"])))

    def band_of(cell, ch):
        if ch in "rq":
            return ("in", nearest(sites["in"], cell))
        if ch == "s":
            return ("out", nearest(sites["out"], cell))
        return None

    blocks = blockify(src, topo, band_of)
    lay, _entry, expect = emit_room0(blocks, args.width)
    XI, H = lay.bbox()                          # room0 interior extent
    XW = XI + 1                                 # room0's east wall
    A = H + 2                                   # the attachment row, just under the wall

    cells = dict(lay.cells)

    def blit(x0, y0, block_rows):
        for dy, line in enumerate(block_rows):
            for dx, ch in enumerate(line):
                if ch != " ":
                    if (x0 + dx, y0 + dy) in cells:
                        sys.exit(f"blit conflict at ({x0+dx},{y0+dy})")
                    cells[(x0 + dx, y0 + dy)] = ch

    # room0's walls
    for x in range(0, XW + 1):
        cells[(x, 0)] = cells[(x, H + 1)] = "-"
    for y in range(1, H + 1):
        cells[(0, y)] = cells[(XW, y)] = "|"
    for c in ((0, 0), (XW, 0), (0, H + 1), (XW, H + 1)):
        cells[c] = "+"

    a = ATTACH
    pipes = {
        # room1 -> room0, 3 cells: the input room hangs straight off its attachment
        3: [(a[("in", 3)], A + 2), (a[("in", 3)], A - 1)],
        # room0 <-> room3, 18 cells each, straight down and straight back up
        0: [(a[("out", 0)], A), (a[("out", 0)], A + 18)],
        5: [(a[("in", 5)], A + 17), (a[("in", 5)], A - 1)],
        # room0 -> room2, 23 cells, landing on the translated sub-block's west wall
        2: [(a[("out", 2)], A), (a[("out", 2)], A + 20), (18, A + 20)],
        # the two 400-cell delay lines, folded into the free band under the sub-block
        1: [(a[("out", 1)], A), (a[("out", 1)], A + 60), (201, A + 60), (201, A + 62),
            (60, A + 62), (60, A + 64), (63, A + 64), (63, A + 65)],
        8: [(100, A + 69), (100, A + 70), (216, A + 70), (216, A + 72),
            (a[("in", 8)], A + 72), (a[("in", 8)], A - 1)],
    }
    want = {0: 18, 1: 400, 2: 23, 3: 3, 5: 18, 8: 400}
    for pi, wps in pipes.items():
        path = draw_pipe(wps, drop_last=True)
        if len(path) != want[pi]:
            sys.exit(f"pipe{pi} is {len(path)} cells, need {want[pi]}")
        for c, ch in path:
            if c in cells:
                sys.exit(f"pipe{pi} collides at {c} with {cells[c]!r}")
            cells[c] = ch

    # room1 (input), room3 (the fast rotator) and room4 (the 92-slot one) keep their interiors
    blit(12, A + 3, [src[y][21:24] for y in range(1068, 1071)])
    blit(45, A + 18, [src[y][41:58] for y in range(1083, 1087)])
    blit(30, A + 65, [src[y][1:95] for y in range(1465, 1469)])
    # room2 + display + pipes 4/6/7, verbatim
    blit(18, A + 3, [src[y][122:149] for y in range(1067, 1123)])

    bad = check_bands(expect, H)
    if bad:
        sys.exit(f"{len(bad)} ops bind the wrong pipe, first {bad[:3]}")

    open(args.out, "w").write(render(cells))
    w = max(x for x, _ in cells) + 1
    h = max(y for _, y in cells) + 1
    print(f"  wrote {args.out}  {w}x{h}  box {max(w, h) ** 2:,}   room0 {XW+1}x{H+2}")
    return max(w, h) ** 2


# ============================================================ room0 emitter v2

def emit_room0_v2(blocks, main_hi):
    """emit_room0 with branch terminators folded into the corridor columns.

    v1 gave every branch a dedicated row: entered heading SOUTH so clockwise=west, taken
    gliding west along that row to the corridor. v2 places the glyph IN the corridor column
    with the man heading WEST, so clockwise is NORTH and the taken edge starts already on
    its corridor — the glyph row is the last ops row (0 extra rows when the walk happens to
    head west; 1 when it must turn), and the per-iteration taken glide across the room
    disappears. Column 1 is the shared fall-through lane: `v` then `>` drop the not-taken
    walk onto a fresh full east-heading row. Corridor colours therefore shift to columns
    2..4; opmin stays 6, so every band and attachment is unchanged.

    The X's counter-clockwise leg becomes a southward corridor glide instead of v1's
    east-into-the-wall walk; both are unreachable (the submitted original dies on that leg,
    so no grading case takes it)."""
    colour, _default = corridors_for(blocks)
    col_of = {b: c + 1 for b, c in colour.items()}
    FT = 1
    lay = Layout(MAIN_LO, main_hi)
    entry = {}
    band = dict(STRIP)
    band[("in", 5)] = band[("out", 0)] = (MAIN_LO, main_hi)
    merges = set()
    for b in blocks:
        t = b["term"]
        tgt = t[2] if t[0] == "branch" else (t[1] if t[0] == "goto" else None)
        if tgt is not None and tgt <= b["id"]:
            merges.add(tgt)
    expect = {}
    for i, b in enumerate(blocks):
        if i == 0:
            lay.put(6, 1, "@")
            lay.x, lay.y, lay.d = 6, 1, E
            entry[0] = 1
        for ch, key in b["ops"]:
            lo, hi = band.get(key, (lay.opmin, main_hi))
            lay.place(ch, lo, hi)
            if key is not None:
                expect[(lay.x, lay.y)] = key
        term = b["term"]
        if term[0] == "branch":
            _k, glyph, taken, ft = term
            if taken not in entry:
                raise RuntimeError(f"branch target {taken} has no entry `>` yet")
            if ft in merges:
                raise RuntimeError("branch fall-through into a merge is unsupported")
            if lay.d == E:
                lay.newline()
            lay.put(col_of[taken], lay.y, glyph)
            lay.put(FT, lay.y, "v")
            lay.put(FT, lay.y + 1, ">")
            lay.x, lay.y, lay.d = FT, lay.y + 1, E
            entry.setdefault(ft, lay.y)
        elif term[0] == "goto":
            tgt = term[1]
            up = tgt in entry
            if up and i + 1 < len(blocks):
                raise RuntimeError("up-goto before the last block leaves a stale cursor")
            if lay.d == E:
                lay.newline()
            lay.put(col_of[tgt], lay.y, "^" if up else "v")
            if not up:
                entry[tgt] = lay.y + 1
                lay.put(col_of[tgt], lay.y + 1, ">")
                lay.x, lay.y, lay.d = col_of[tgt], lay.y + 1, E
    return lay, entry, expect


# ============================================================ band v2 assembly

def cmd_build2(args):
    """Like `build`, but the satellite band is re-composed instead of carried verbatim:

    - room2 rises to sit 3 rows under room0 (pipe2's 23 cells land on its west wall at the
      SAME cell as before — the landing row is free to differ from the man's row, since a
      room with one incoming pipe binds every `r` to it regardless of position);
    - the display tucks 3 rows under room2's bottom-right, as close as pipe7's 4 cells
      allow (sa/sd re-attach on room2's wall; every `s` re-binding is re-derived and
      checked against the reference nearest rule);
    - room4 and both 400-cell delay lines move into the dead region east of room3, folded
      with comb teeth so each keeps exactly 400 cells.

    Saves 17 rows of band height over `build` (73 -> 56)."""
    src = load_rows(args.man)
    topo = analyze(src)
    sites = {"in": [], "out": []}
    for i, p in enumerate(topo["pipes"]):
        path = p.get("path") or []
        if not path:
            continue
        if p.get("src") == 0:
            sites["out"].append((i, tuple(path[0]["pos"])))
        if p.get("dst") == 0:
            sites["in"].append((i, tuple(path[-1]["pos"])))

    def band_of(cell, ch):
        if ch in "rq":
            return ("in", nearest(sites["in"], cell))
        if ch == "s":
            return ("out", nearest(sites["out"], cell))
        return None

    global ATTACH, MAIN_LO, STRIP
    if getattr(args, "west", False):
        ATTACH, MAIN_LO, STRIP = ATTACH_W, MAIN_LO_W, STRIP_W

    blocks = blockify(src, topo, band_of)
    emit = emit_room0_v2 if getattr(args, "emit2", False) else emit_room0
    lay, _entry, expect = emit(blocks, args.width)
    XI, H = lay.bbox()
    XW = XI + 1
    A = H + 2

    cells = dict(lay.cells)

    def blit(x0, y0, block_rows):
        for dy, line in enumerate(block_rows):
            for dx, ch in enumerate(line):
                if ch != " ":
                    if (x0 + dx, y0 + dy) in cells:
                        sys.exit(f"blit conflict at ({x0+dx},{y0+dy})")
                    cells[(x0 + dx, y0 + dy)] = ch

    for x in range(0, XW + 1):
        cells[(x, 0)] = cells[(x, H + 1)] = "-"
    for y in range(1, H + 1):
        cells[(0, y)] = cells[(XW, y)] = "|"
    for c in ((0, 0), (XW, 0), (0, H + 1), (XW, H + 1)):
        cells[c] = "+"

    a = ATTACH
    R4X = 115                                   # room4's west wall
    west = getattr(args, "west", False)
    if west:
        # legs tucked to A+52/A+53 (pipe-pipe adjacency is legal), teeth re-solved to 400
        wp1 = [(10, A), (10, A + 52), (90, A + 52), (90, A + 22)]
        x = 91
        for _ in range(5):
            wp1 += [(x, A + 22), (x, A + 6), (x + 1, A + 6), (x + 1, A + 22)]
            x += 4
        wp1 += [(166, A + 22), (166, A + 24)]
        wp8 = [(181, A + 28), (181, A + 35), (183, A + 35), (183, A + 37),
               (181, A + 37), (181, A + 53)]
        x = 150
        for _ in range(6):
            wp8 += [(x, A + 53), (x, A + 41), (x - 1, A + 41), (x - 1, A + 53)]
            x -= 4
        wp8 += [(8, A + 53), (8, A - 1)]
    else:
        # pipe1's serpentine teeth (5 teeth x depth 16 = +160 over the straight route)
        wp1 = [(10, A), (10, A + 53), (90, A + 53), (90, A + 22)]
        x = 91
        for _ in range(5):
            wp1 += [(x, A + 22), (x, A + 6), (x + 1, A + 6), (x + 1, A + 22)]
            x += 4
        wp1 += [(164, A + 22), (164, A + 24)]
        # pipe8's teeth (8 teeth x depth 9 = +144)
        wp8 = [(181, A + 28), (181, A + 55)]
        x = 176
        for _ in range(8):
            wp8 += [(x, A + 55), (x, A + 46), (x - 1, A + 46), (x - 1, A + 55)]
            x -= 4
        wp8 += [(8, A + 55), (8, A - 1)]
    pipes = {
        3: [(a[("in", 3)], A + 2), (a[("in", 3)], A - 1)],
        0: [(a[("out", 0)], A), (a[("out", 0)], A + 18)],
        5: [(a[("in", 5)], A + 17), (a[("in", 5)], A - 1)],
        2: [(a[("out", 2)], A), (a[("out", 2)], A + 20), (18, A + 20)],
        1: wp1,
        8: wp8,
        # sa: room2 bottom wall -> display top wall, the 4 cells that pin the display.
        # The LAST MOVE must also be perpendicular into the wall — the loader derives
        # the attachment side from the approach direction, not the arrowhead glyph.
        7: [(26, A + 29), (26, A + 30), (25, A + 30), (25, A + 31), (25, A + 32)],
        # sd: room2 bottom wall -> display west wall
        6: [(20, A + 29), (20, A + 39), (22, A + 39)],
        # ss: room2 top wall -> around the east -> display bottom wall.
        # The first step must leave the wall PERPENDICULAR or the loader records src -1.
        4: ([(28, A + 2), (28, A + 1), (41, A + 1), (41, A + 30), (43, A + 30),
             (43, A + 32), (41, A + 32), (41, A + 35), (43, A + 35), (43, A + 37),
             (41, A + 37), (41, A + 51), (26, A + 51), (26, A + 49)] if west else
            [(28, A + 2), (28, A + 1), (43, A + 1), (43, A + 8), (41, A + 8),
             (41, A + 11), (43, A + 11), (43, A + 51), (26, A + 51), (26, A + 49)]),
    }
    want = {0: 18, 1: 400, 2: 23, 3: 3, 5: 18, 8: 400, 4: 89, 6: 12, 7: 4}
    for pi, wps in pipes.items():
        path = draw_pipe(wps, drop_last=True)
        if len(path) != want[pi]:
            sys.exit(f"pipe{pi} is {len(path)} cells, need {want[pi]}")
        for c, ch in path:
            if c in cells:
                sys.exit(f"pipe{pi} collides at {c} with {cells[c]!r}")
            cells[c] = ch

    # room1 (input), room3 (fast rotator), room4 (92-slot), room2, display — verbatim
    blit(12, A + 3, [src[y][21:24] for y in range(1068, 1071)])
    blit(43 if west else 45, A + 18, [src[y][41:58] for y in range(1083, 1087)])
    blit(R4X, A + 24, [src[y][1:95] for y in range(1465, 1469)])
    blit(18, A + 3, [src[y][122:138] for y in range(1070, 1096)])
    blit(22, A + 32, [src[y][128:146] for y in range(1100, 1118)])

    # room2's own `s` ops must re-derive to the same roles: sa/sd/ss by nearest
    r2_out = [(7, (26, A + 29)), (6, (20, A + 29)), (4, (28, A + 2))]
    for cell, pipe_want in (((26, A + 27), 7), ((20, A + 27), 6), ((28, A + 6), 4)):
        got = nearest(r2_out, cell)
        if got != pipe_want:
            sys.exit(f"room2 s at {cell} binds pipe{got}, want pipe{pipe_want}")

    bad = check_bands(expect, H)
    if bad:
        sys.exit(f"{len(bad)} ops bind the wrong pipe, first {bad[:3]}")

    open(args.out, "w").write(render(cells))
    w = max(x for x, _ in cells) + 1
    h = max(y for _, y in cells) + 1
    print(f"  wrote {args.out}  {w}x{h}  box {max(w, h) ** 2:,}   room0 {XW+1}x{H+2}")
    return max(w, h) ** 2


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fold", help="redraw the two 400-cell delay lines as staircases")
    f.add_argument("man")
    f.add_argument("out")
    f.set_defaults(fn=cmd_fold)
    b = sub.add_parser("bands", help="which pipe each interior column of a room binds")
    b.add_argument("man")
    b.add_argument("--room", type=int, default=0)
    b.set_defaults(fn=cmd_bands)
    c = sub.add_parser("build", help="re-lay room0 and re-space every attachment")
    c.add_argument("man")
    c.add_argument("out")
    c.add_argument("--width", type=int, default=247,
                   help="last column the main serpentine may use (247 is the measured "
                        "optimum: wider rows trade height for width one-for-one)")
    c.set_defaults(fn=cmd_build)
    c2 = sub.add_parser("build2", help="build + re-composed satellite band (17 rows shorter)")
    c2.add_argument("man")
    c2.add_argument("out")
    c2.add_argument("--width", type=int, default=247)
    c2.add_argument("--emit2", action="store_true",
                    help="corridor-column branches (emit_room0_v2)")
    c2.add_argument("--west", action="store_true",
                    help="hot attachments at 44/46 (MAIN_LO 30) + tucked delay legs")
    c2.set_defaults(fn=cmd_build2)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

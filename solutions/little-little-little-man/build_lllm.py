#!/usr/bin/env python3
"""Generate a complete LLLM interpreter as a littleman .man program.

    python3 solutions/little-little-little-man/build_lllm.py [--out FILE]

Semantics live in lllm_flow.py and are gated by lllm_sim.py (10/10 public cases
in Python).  This file is *only* geometry, and it is built around one invariant
that makes both the pipe bindings and the control flow provable at build time:

  PORTS ARE COLUMNS.  Every device (holder, ring, input, display) attaches to
  the controller's TOP wall only.  The distance from an instruction at (x, y)
  to an attachment at (c, top-1) is (y-top+1) + |x-c|, so among attachments
  that all share row top-1 the NEAREST is simply the one with the closest
  column -- an `r`/`s` placed exactly on a device's column can never rebind.
  build-time assert_bindings() re-derives every binding the way the oracle does.

  CONTROL FLOW GOES EAST OR SOUTH.  A block is a row of ops entered from the
  west; `b d` turns a taken branch SOUTH, a fall-through keeps heading EAST.
  Each exit drops onto its own private row, runs WEST to a per-target highway
  column, and rides it to the target's entry row.  Highways cross exit rows on
  BLANK cells (a blank preserves heading), so no two routes ever share a turn
  glyph -- the classic generated-grid misroute cannot happen here.

Knobs are module constants / default args so tools/autotune.py can sweep them;
all DATA (colour table, character classes, the classifier hash) is computed
from dicts in lllm_tables.py, never written as a bare integer.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import layout as lay
import littleman as lm
import lllm_flow as F

# ---- tunable integer knobs -------------------------------------------------
HOLDER_PITCH = 5        # columns between neighbouring holder rooms
HOLDER_W = 4            # holder room outer width
HOLDER_H = 6            # holder room outer height
PIPE_GAP = 3            # rows between the device band and the controller
PORT_GAP = 4            # columns between the non-holder port columns
HWY_GAP = 0             # columns between neighbouring highway lanes
LEAD_IN = 2             # blank columns between the entry column and the ops
RING_LIFT = 26          # how far above the band the ring relay sits
DISP_GAP = 6            # routing columns between the band and the display
TAIL_PAD = 2            # spare rows under the last block
CODE_SLACK = 14         # spare code columns east of the last port column

ARROW_S, ARROW_W, ARROW_E, ARROW_N = "v", "<", ">", "^"

# Port columns run west to east in this order.  It is load-bearing: every pipe
# that has to leave the band routes EAST, so a port may never have to cross the
# vertical of a port to its right.
PORT_ORDER = ("in", "ot", "rs", "rr", "ds", "da", "dd")


# ===========================================================================
# 1.  CFG shape
# ===========================================================================
def split_blocks(flow):
    """[(label, tokens)] in fall-through order; tokens keep their inline branches."""
    out = []
    for label in flow.order:
        toks = flow.blocks[label]
        assert isinstance(toks[-1], tuple) and toks[-1][0] == "go", label
        out.append((label, toks))
    return out


def entry_labels(blocks):
    """Labels reached by an edge that is not a plain fall-through."""
    index = {b[0]: i for i, b in enumerate(blocks)}
    need = set()
    for i, (label, toks) in enumerate(blocks):
        for tok in toks:
            if not isinstance(tok, tuple):
                continue
            if tok[0] in ("br", "brbp"):
                need.add(tok[1])
            elif tok[0] == "go" and index[tok[1]] != i + 1:
                need.add(tok[1])
    return need


# ===========================================================================
# 2.  column plan
# ===========================================================================
class Columns(object):
    def __init__(self, blocks, holder_order, pitch=HOLDER_PITCH,
                 port_gap=PORT_GAP, hwy_gap=HWY_GAP, lead_in=LEAD_IN):
        self.hwy_targets = sorted(entry_labels(blocks))
        x = 1
        self.hwy = {}
        for label in self.hwy_targets:
            self.hwy[label] = x
            x += 1 + hwy_gap
        self.entry_col = x + 1
        x = self.entry_col + lead_in
        self.port = {}
        for name in PORT_ORDER:
            self.port[name] = x
            x += port_gap
        self.holder_room_x = {}
        self.hr = {}
        self.hw = {}
        for name in holder_order:
            self.holder_room_x[name] = x
            self.hr[name] = x + 1
            self.hw[name] = x + 2
            x += pitch
        self.code_hi = x + CODE_SLACK
        self.width = self.code_hi + 3

    def of(self, tok):
        if isinstance(tok, tuple):
            if tok[0] == "hr":
                return self.hr[tok[1]]
            if tok[0] == "hw":
                return self.hw[tok[1]]
            if tok[0] in self.port:
                return self.port[tok[0]]
        return None


GLYPH = {"hr": "r", "hw": "s", "in": "r", "rr": "r", "ot": "s",
         "rs": "s", "da": "s", "dd": "s", "ds": "s"}


def tok_cells(tok, direction):
    """The glyph run a token occupies, IN WALK ORDER.

    A literal is read in the direction the man walks, so on a westward row the
    grid must hold it mirrored -- but the placer already writes these cells in
    walk order (it steps the cursor by the heading), so the digits must NOT be
    reversed here.  Reversing them too produced `61` where `16` was meant and
    was invisible on eastward rows, which is exactly how it survived until a
    16-wide raster row hit it.
    """
    if isinstance(tok, tuple):
        if tok[0] == "lit":
            return "`" + str(tok[1]) + "`"
        return GLYPH[tok[0]]
    return tok


# ===========================================================================
# 3.  place the code
# ===========================================================================
class CodePlacer(object):
    """Lays every block as a boustrophedon ribbon of op rows.

    A branch is INLINE: `b d` on an eastward row turns the taken arm south onto
    a private exit row and leaves the fall-through walking east on the same row,
    so a chain of branches costs one row each instead of a round trip each.
    Exit rows are handed out in the order the branches appear, i.e. in
    increasing column order, which is exactly what makes the drops legal: a
    later branch's southward drop crosses only the lanes of branches that turn
    off further west, and it crosses them on blank cells.
    """

    def __init__(self, grid, cols, top_row):
        self.g = grid
        self.c = cols
        self.y = top_row
        self.entry_row = {}
        self.joins = []
        self.lits = set()          # (row, x_open, x_close) of every REAL literal

    def place(self, blocks):
        c = self.c
        targets = set(c.hwy_targets)
        labels = [b[0] for b in blocks]
        st = {"x": c.entry_col + 1, "y": self.y, "d": 1, "pend": 0}
        fresh = True                     # next block must be entered at entry_col

        def put(ch):
            self.g.put(st["x"], st["y"], ch)
            st["x"] += st["d"]

        def descend(reverse):
            """Turn south, fall past every pending exit row, then face `reverse`."""
            self.g.put(st["x"], st["y"], ARROW_S)
            st["y"] += 1 + st["pend"]
            st["pend"] = 0
            self.g.put(st["x"], st["y"], ARROW_W if reverse < 0 else ARROW_E)
            st["d"] = reverse
            st["x"] += reverse

        def wrap():
            descend(-st["d"])

        def need(n):
            if st["d"] > 0 and st["x"] + n - 1 > c.code_hi:
                wrap()
            elif st["d"] < 0 and st["x"] - (n - 1) < c.entry_col + 1:
                wrap()

        def face_east(n):
            """Guarantee n free cells ahead on an EASTWARD row.

            `d` only turns a taken branch south while the man walks east; on a
            westward row it would turn him NORTH, straight into the ceiling.
            """
            if st["d"] < 0:
                wrap()
            if st["x"] + n - 1 > c.code_hi:
                wrap()                        # -> westward on a blank row
                st["x"] = c.entry_col + 2     # glide west over the blanks
                wrap()                        # -> eastward again

        for bi, (label, toks) in enumerate(blocks):
            nxt = labels[bi + 1] if bi + 1 < len(labels) else None
            if fresh or label in targets:
                if not fresh:
                    raise RuntimeError("target %s reached by fall-through" % label)
                st["x"], st["d"] = c.entry_col + 1, 1
                self.g.put(c.entry_col, st["y"], "@" if bi == 0 else ARROW_E)
            self.entry_row[label] = st["y"]
            fresh = False

            for tok in toks:
                kind = tok[0] if isinstance(tok, tuple) else None
                if kind in ("br", "brbp"):
                    face_east(4)
                    if kind == "br":
                        put("b")
                    put("d")
                    st["pend"] += 1
                    self._lane(st["x"] - 1, st["y"] + st["pend"], tok[1], False)
                elif kind == "go":
                    tgt = tok[1]
                    if tgt == nxt and nxt not in targets:
                        descend(-st["d"])        # keep walking, no round trip
                    else:
                        self.g.put(st["x"], st["y"], ARROW_S)
                        row = st["y"] + st["pend"] + 1
                        self._lane(st["x"], row, tgt, tgt == nxt)
                        st["y"] = row + 1
                        st["pend"] = 0
                        fresh = True
                elif kind is not None and c.of(tok) is not None:
                    want = c.of(tok)
                    if (st["d"] > 0 and want < st["x"]) or \
                       (st["d"] < 0 and want > st["x"]):
                        wrap()
                    st["x"] = want
                    put(GLYPH[kind])
                else:
                    need(len(tok_cells(tok, st["d"])))
                    text = tok_cells(tok, st["d"])
                    x0 = st["x"]
                    for ch in text:
                        put(ch)
                    if text[0] == "`":
                        x1 = st["x"] - st["d"]
                        self.lits.add((st["y"], min(x0, x1), max(x0, x1)))
        self.y = st["y"] + 1
        return self.y

    def _lane(self, x, y, target, is_fall):
        dest = self.c.entry_col if is_fall else self.c.hwy[target]
        self.g.put(x, y, ARROW_W)
        if is_fall:
            self.g.put(dest, y, ARROW_S)
        self.joins.append((dest, y, target, is_fall))


def break_stray_literals(g, intended=(), verbose=False):
    """Kill every ACCIDENTAL literal the grid grew by coincidence.

    A backtick closes a literal for the backtick before it *in the direction the
    man walks*, so any two backticks with nothing but digits and spaces between
    them form one -- including a pair made of the closing tick of one intended
    literal and the opening tick of the next, and including pairs that line up
    VERTICALLY down a column the man drops through.  Crossing one silently
    overwrites A.  Intended literals are solid digit runs with no blanks, so
    dropping a '.' (an explicit no-op) into a blank cell of an offending span
    breaks the accident and can never break a real literal.
    """
    fixed = 0
    for axis in (0, 1):
        minx, miny, maxx, maxy = g.p.bounds()
        outer = range(minx, maxx + 1) if axis == 0 else range(miny, maxy + 1)
        inner = range(miny, maxy + 1) if axis == 0 else range(minx, maxx + 1)
        for a in outer:
            ticks = []
            for b in inner:
                x, y = (a, b) if axis == 0 else (b, a)
                if g.get(x, y) == "`":
                    ticks.append(b)
            for lo, hi in zip(ticks, ticks[1:]):
                if axis == 1 and (a, lo, hi) in intended:
                    continue
                span = [(a, b) if axis == 0 else (b, a) for b in range(lo + 1, hi)]
                cells = [g.get(x, y) for x, y in span]
                if not any(c.isdigit() for c in cells):
                    continue
                if not all(c.isdigit() or c == " " for c in cells):
                    continue
                blanks = [pt for pt, c in zip(span, cells) if c == " "]
                if not blanks:
                    raise RuntimeError("stray literal with no blank to break: "
                                       "axis=%d line=%d span=%d..%d" % (axis, a, lo, hi))
                x, y = blanks[len(blanks) // 2]
                g.put(x, y, ".")
                fixed += 1
    if verbose:
        print("broke %d stray literal spans" % fixed)
    return fixed


def checked_room(g, x, y, w, h, glyphs="+-|"):
    cor, hor, ver = glyphs
    for cx, cy in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
        g.put(cx, cy, cor)
    for i in range(1, w - 1):
        g.put(x + i, y, hor)
        g.put(x + i, y + h - 1, hor)
    for j in range(1, h - 1):
        g.put(x, y + j, ver)
        g.put(x + w - 1, y + j, ver)
    rect = lm.Rect(x, y, x + w - 1, y + h - 1, x + 1, y + 1, x + w - 2, y + h - 2)
    g.p.rooms.append(rect)
    return rect


# ===========================================================================
# 4.  whole program
# ===========================================================================
def build(holder_order=None, pitch=HOLDER_PITCH, ring_lift=RING_LIFT):
    flow = F.build_flow()
    blocks = split_blocks(flow)
    holder_order = holder_order or list(F.HOLDERS)
    cols = Columns(blocks, holder_order, pitch=pitch)

    p = lm.Program()
    g = lay.Layout(p)

    # controller room: top wall row 0, interior from row 1
    ctrl_top = 0
    placer = CodePlacer(g, cols, ctrl_top + 1)
    placer.place(blocks)
    code_bottom = placer.y + TAIL_PAD

    # highway turn glyphs: 'v' above the target row, '^' below it
    for dest, row, target, is_fall in placer.joins:
        if is_fall:
            continue
        trow = placer.entry_row[target]
        g.put(dest, row, ARROW_S if trow > row else ARROW_N)
        g.put(dest, trow, ARROW_E)

    ctrl_bot = code_bottom
    # draw the controller walls THROUGH the collision-checked Layout: the raw
    # Program.room is a bare dict store and would silently overwrite code.
    ctrl = checked_room(g, 0, ctrl_top, cols.width, ctrl_bot - ctrl_top + 1)

    # ---- device band above the controller ------------------------------
    band_bot = ctrl_top - PIPE_GAP - 1          # bottom wall row of the rooms
    band_top = band_bot - (HOLDER_H - 1)
    pipes = {"in": [], "out": []}

    def drop_pipe(col, room_bottom_row):
        """device -> controller (a value falls into the controller)."""
        path = [(col, room_bottom_row + 1)]
        while path[-1][1] < ctrl_top - 1:
            path.append((col, path[-1][1] + 1))
        lay.place_pipe(g, path, (0, 1))
        pipes["in"].append((col, ctrl_top - 1))

    def lift_pipe(col, room_bottom_row):
        """controller -> device."""
        path = [(col, ctrl_top - 1)]
        while path[-1][1] > room_bottom_row + 1:
            path.append((col, path[-1][1] - 1))
        lay.place_pipe(g, path, (0, -1))
        pipes["out"].append((col, ctrl_top - 1))

    for name in holder_order:
        rx = cols.holder_room_x[name]
        p.room(rx, band_top, HOLDER_W, HOLDER_H)
        ix, iy = rx + 1, band_top + 1                # interior 2 x (H-2)
        # 6-cell ring: s first, then r, with '@' parked outside it
        # 6-cell ring  s -> '<' -> 'v' -> r -> '>' -> '^' -> s.  Every turn is a
        # real glyph and '@' sits OUTSIDE the cycle, on a ramp that joins it at
        # the '^': an '@' inside a ring is a no-op and walks the man into a wall.
        g.put(ix, iy + 3, "@")
        g.put(ix + 1, iy + 3, ARROW_N)               # entry ramp
        g.put(ix + 1, iy + 2, ARROW_N)
        g.put(ix + 1, iy + 1, "s")
        g.put(ix + 1, iy, ARROW_W)
        g.put(ix, iy, ARROW_S)
        g.put(ix, iy + 1, "r")
        g.put(ix, iy + 2, ARROW_E)
        drop_pipe(cols.hr[name], band_bot)
        lift_pipe(cols.hw[name], band_bot)

    # ---- debug output room (only wired when lllm_flow.DEBUG_EMIT is set) --
    if F.DEBUG_EMIT:
        ot_col = cols.port["ot"]
        ot_bot = band_top - 12
        p.output_room(ot_col - 1, ot_bot - 2)
        lift_pipe(ot_col, ot_bot)

    # ---- input room: above the band, clear of every other pipe ---------
    in_col = cols.port["in"]
    in_bot = band_top - 6
    p.input_room(in_col - 1, in_bot - 2)
    drop_pipe(in_col, in_bot)

    # ---- ring relay: long pipes so all 32 words fit in flight ------------
    relay_bot = band_top - ring_lift
    relay_x = 1
    p.room(relay_x, relay_bot - (HOLDER_H - 1), HOLDER_W, HOLDER_H)
    rix, riy = relay_x + 1, relay_bot - (HOLDER_H - 1) + 1
    g.put(rix, riy + 3, "@")
    g.put(rix + 1, riy + 3, ARROW_N)
    g.put(rix + 1, riy + 2, ARROW_N)
    g.put(rix + 1, riy + 1, "r")                 # the relay takes first, then sends
    g.put(rix + 1, riy, ARROW_W)
    g.put(rix, riy, ARROW_S)
    g.put(rix, riy + 1, "s")
    g.put(rix, riy + 2, ARROW_E)

    def run(path, x=None, y=None):
        cx, cy = path[-1]
        if x is not None:
            step = 1 if x > cx else -1
            for xx in range(cx + step, x + step, step):
                path.append((xx, cy))
        if y is not None:
            cx, cy = path[-1]
            step = 1 if y > cy else -1
            for yy in range(cy + step, y + step, step):
                path.append((cx, yy))
        return path

    # controller -> relay, entering the relay's bottom wall
    c2r = cols.port["rs"]
    path = run(run([(c2r, ctrl_top - 1)], y=relay_bot + 2), x=rix)
    path = run(path, y=relay_bot + 1)
    lay.place_pipe(g, path, (0, -1))
    pipes["out"].append((c2r, ctrl_top - 1))

    # relay -> controller, leaving the relay's right wall
    r2c = cols.port["rr"]
    path = run(run([(relay_x + HOLDER_W, relay_bot - 2)], x=r2c), y=ctrl_top - 1)
    lay.place_pipe(g, path, (0, 1))
    pipes["in"].append((r2c, ctrl_top - 1))

    # ---- display --------------------------------------------------------
    disp_x = cols.code_hi + DISP_GAP
    disp_y = band_bot - 17
    p.display(disp_x, disp_y, 18, 18)

    # The display consumes ADDR, DATA and SWAP in that order within one tick, so
    # a value must never overtake the one it belongs behind: keep
    # len(ADDR) <= len(DATA) <= len(SWAP).  The column order ds < da < dd and the
    # turn rows below are the unique arrangement that gets both that AND a
    # crossing-free routing -- ADDR turns above DATA so DATA's descent to the
    # left wall never meets ADDR's eastward run.
    lens = {}

    # SWAP -> bottom wall, all the way round the east side of the display
    path = run(run([(cols.port["ds"], ctrl_top - 1)], y=disp_y - 6), x=disp_x + 20)
    path = run(run(path, y=ctrl_top - 2), x=disp_x + 2)
    path = run(path, y=ctrl_top - 3)
    lay.place_pipe(g, path, (0, -1))
    pipes["out"].append((cols.port["ds"], ctrl_top - 1))
    lens["ds"] = len(path)

    # ADDR -> top wall
    path = run(run([(cols.port["da"], ctrl_top - 1)], y=disp_y - 2), x=disp_x + 4)
    path = run(path, y=disp_y - 1)
    lay.place_pipe(g, path, (0, 1))
    pipes["out"].append((cols.port["da"], ctrl_top - 1))
    lens["da"] = len(path)

    # DATA -> left wall, entering low so the pipe stays longer than ADDR's
    path = run(run([(cols.port["dd"], ctrl_top - 1)], y=disp_y - 1), x=disp_x - 2)
    path = run(run(path, y=disp_y + 15), x=disp_x - 1)
    lay.place_pipe(g, path, (1, 0))
    pipes["out"].append((cols.port["dd"], ctrl_top - 1))
    lens["dd"] = len(path)

    assert lens["da"] <= lens["dd"] <= lens["ds"], lens

    break_stray_literals(g, placer.lits)
    return p, g, cols, blocks, pipes, ctrl


def render(p):
    return p.render()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--pitch", type=int, default=HOLDER_PITCH)
    ap.add_argument("--ring-lift", type=int, default=RING_LIFT)
    args = ap.parse_args()
    p, g, cols, blocks, pipes, ctrl = build(pitch=args.pitch,
                                            ring_lift=args.ring_lift)
    w, h, box = p.footprint()
    out = args.out or os.path.join(HERE, "m1-%dx%d.man" % (w, h))
    p.save(out)
    print("blocks=%d  width=%d  code_hi=%d  footprint=%dx%d box=%d"
          % (len(blocks), cols.width, cols.code_hi, w, h, box))
    print("saved", out)


if __name__ == "__main__":
    main()

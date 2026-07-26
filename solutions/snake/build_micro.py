#!/usr/bin/env python3
"""snake micro-design: a small, O(1)-state Snake solver.

ARCHITECTURE (see the header comment blocks below for the exact op sequences)

  STATE RING   a FIFO ring holding 8 scalars in a fixed canonical order
                   [dx, hx, dy, hy, da, ha, fa, K]
               dx,dy  direction step in board coords      (-1/0/1)
               da     direction step in DISPLAY ADDRESS   (-16/-1/+1/+16)
               hx,hy  head column/row                     (0..15)
               ha     head display address = 16*hy + hx   (0..255)
               fa     fruit display address, or -1        (-1..255)
               K      snake length
               Every round pops the 8 values in order and pushes them back in
               the same order, so the ring is a rotating register file.

  BODY RING    a FIFO ring holding the K body cells as display addresses,
               oldest (tail) first.  Sized for the worst case: at most 100
               rounds per case => at most 49 growths => K <= 50.

  SCRATCH RING a short FIFO used to stash one or three values (spawn / dir /
               init only -- the tick path needs no scratch).

  DRIVER       owns the display's ADDR/DATA/SWAP pipes.  Protocol on its single
               incoming pipe:   addr (>=0) then colour     -> write one pixel
                                -1                         -> commit the frame
               So the controller never has to disambiguate three display pipes.

  WALL TEST    hx' and hy' are each tested with   b ] ] ] ] x  :  BP = v>>4 is
               0 for 0..15, 1 for 16 and -1 for -1, so `x` (turn on BP's low
               bit) is an exact in-range/out-of-range branch and needs no B.

  EAT TEST     ha' ^ fa computed as  M(B=ha') r(A=fa) W ~   so B keeps fa; the
               no-eat arm recovers ha' with a second `~` and the eat arm finds
               ha' already sitting in B (because ha'==fa there).

  COLLISION    one lap of the body ring: pop, push back, xor with ha', X.  The
               first value (the tail) is skipped, matching the rule that the
               tail moves before the head.  Because every popped value is
               pushed back, the ring is intact whatever the outcome, so the
               death repaint can just pop K values and paint them red.

PIPE BINDING.  `s`/`r` pick the nearest attached pipe (Manhattan to the pipe's
first/last cell, ties in reading order).  Every controller pipe attaches to the
TOP wall of the controller room, so the y term is identical for all of them and
the binding is decided by the column alone.  The controller interior is
therefore divided into four vertical LANES; a pipe op is only ever placed in
the part of a lane where both the send- and the receive-binding are
unambiguous, and _assert_bindings() re-derives every binding from the finished
grid and checks it against what the emitter intended.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm                      # noqa: E402
from layout import Layout, place_pipe       # noqa: E402

GREEN = 10
RED = 9
BLACK = 0
GRID = 16


# ──────────────────────────────────────────────────────────────────────────
# geometry knobs (integers -- autotune can sweep them)
# ──────────────────────────────────────────────────────────────────────────
def geometry(CX0=0, CY0=16, CW=36, CBOT=66,
             IN_IN=3, ST_OUT=9, ST_IN=11, BD_OUT=17, BD_IN=21,
             SC_OUT=27, SC_IN=29, DRV_OUT=33,
             DRVX=34, DRVY=10, DRVW=9, DRVH=22,
             DISX=45, DISY=12):
    g = dict(CX0=CX0, CY0=CY0, CW=CW, CBOT=CBOT)
    g["CX1"] = CX0 + CW - 1                      # controller right wall
    g["IXLO"], g["IXHI"] = CX0 + 1, CX0 + CW - 2  # interior columns
    g["IYLO"], g["IYHI"] = CY0 + 1, CBOT - 1      # interior rows
    g["ATT"] = CY0 - 1                            # pipe attach row
    g["attach_out"] = {"S": ST_OUT, "B": BD_OUT, "C": SC_OUT, "D": DRV_OUT}
    g["attach_in"] = {"I": IN_IN, "S": ST_IN, "B": BD_IN, "C": SC_IN}
    g["DRVX"], g["DRVY"], g["DRVW"], g["DRVH"] = DRVX, DRVY, DRVW, DRVH
    g["DISX"], g["DISY"] = DISX, DISY
    return g


def lane_windows(g):
    """Column window in which BOTH the send- and receive-binding name the lane."""
    out, inc = g["attach_out"], g["attach_in"]

    def near(table, x):
        return min(table, key=lambda k: (abs(table[k] - x), table[k]))

    win = {}
    for lane in ("S", "B", "C", "D", "I"):
        cols = []
        for x in range(g["IXLO"], g["IXHI"] + 1):
            ok_s = lane not in out or near(out, x) == lane
            ok_r = lane not in inc or near(inc, x) == lane
            if lane in out and lane in inc:
                good = ok_s and ok_r
            elif lane in out:
                good = ok_s
            else:
                good = ok_r
            if good:
                cols.append(x)
        # longest contiguous run
        best = cur = []
        for x in cols:
            cur = cur + [x] if cur and x == cur[-1] + 1 else [x]
            if len(cur) > len(best):
                best = cur
        win[lane] = (best[0], best[-1])
    return win


# ──────────────────────────────────────────────────────────────────────────
# emitter
# ──────────────────────────────────────────────────────────────────────────
class Emit:
    """Serpentine instruction emitter with lane-constrained pipe ops.

    Tokens: a bare instruction char, ``"#<digits>"`` for a backtick literal, or
    ``"<op>:<lane>"`` for a pipe op that has to land inside ``lane``'s window.
    """

    def __init__(self, L, g, win, forbidden):
        self.L, self.g, self.win = L, g, win
        self.forbidden = set(forbidden)
        self.xlo, self.xhi = g["IXLO"], g["IXHI"]
        self.x = self.y = 0
        self.d = "E"
        self.ops = []                     # (x, y, ch, lane) for binding checks

    # -- cursor ------------------------------------------------------------
    def at(self, x, y, d="E"):
        self.x, self.y, self.d = x, y, d
        return self

    def _step(self):
        self.x += 1 if self.d == "E" else (-1 if self.d == "W" else 0)
        self.y += 1 if self.d == "S" else (-1 if self.d == "N" else 0)

    def raw(self, ch):
        self.L.put(self.x, self.y, ch)
        self._step()

    def wrap(self):
        """Turn down onto the next row, reversing direction."""
        x = self.x
        if self.d == "E":
            while x <= self.g["IXHI"] and (x in self.forbidden
                                           or self.L.get(x, self.y) != " "
                                           or self.L.get(x, self.y + 1) != " "):
                x += 1
            assert x <= self.g["IXHI"], "no room to wrap east at row %d" % self.y
        else:
            while x >= self.g["IXLO"] and (x in self.forbidden
                                           or self.L.get(x, self.y) != " "
                                           or self.L.get(x, self.y + 1) != " "):
                x -= 1
            assert x >= self.g["IXLO"], "no room to wrap west at row %d" % self.y
        self.L.put(x, self.y, "v")
        nd = "W" if self.d == "E" else "E"
        self.L.put(x, self.y + 1, "<" if nd == "W" else ">")
        self.y += 1
        self.d = nd
        self.x = x + (-1 if nd == "W" else 1)
        self.rows_used = max(getattr(self, "rows_used", self.y), self.y)
        return self

    def _ok(self, x):
        return self.xlo <= x <= self.xhi and x not in self.forbidden

    def _advance_to_free(self):
        while True:
            if self.d == "E" and self.x > self.xhi:
                self.wrap()
                continue
            if self.d == "W" and self.x < self.xlo:
                self.wrap()
                continue
            if self._ok(self.x) and self.L.get(self.x, self.y) == " ":
                return
            self._step()

    def _reach_run(self, n):
        """Park the cursor at the start of n contiguous free cells (a literal)."""
        for _ in range(10):
            step = 1 if self.d == "E" else -1
            x = self.x
            while self.xlo <= x <= self.xhi:
                if all(self._ok(x + step * k) and self.L.get(x + step * k, self.y) == " "
                       for k in range(n)):
                    while self.x != x:
                        self._step()
                    return
                x += step
            self.wrap()
        raise RuntimeError("no room for a %d-cell literal" % n)

    def _reach(self, lane):
        lo, hi = self.win[lane]
        for _ in range(10):
            if self.d == "E":
                xs = [x for x in range(max(self.x, lo), hi + 1)
                      if self._ok(x) and self.L.get(x, self.y) == " "]
            else:
                xs = [x for x in range(min(self.x, hi), lo - 1, -1)
                      if self._ok(x) and self.L.get(x, self.y) == " "]
            if xs:
                while self.x != xs[0]:
                    self._step()
                return
            self.wrap()
        raise RuntimeError("lane %s unreachable" % lane)

    def tok(self, t):
        if t.startswith("#"):
            digits = t[1:]
            if self.d in ("W", "N"):
                digits = digits[::-1]
            body = "`" + digits + "`"
            self._reach_run(len(body))
            for ch in body:
                self.raw(ch)
            return self
        if ":" in t:
            op, lane = t.split(":")
            self._reach(lane)
            self.ops.append((self.x, self.y, op, lane))
            self.raw(op)
            return self
        self._advance_to_free()
        self.raw(t)
        return self

    def seq(self, toks):
        for t in toks:
            self.tok(t)
        return self


# ──────────────────────────────────────────────────────────────────────────
# routing helpers on top of the emitter
# ──────────────────────────────────────────────────────────────────────────
def _blank(L, x, y):
    return L.get(x, y) == " "


def glide(E, col):
    """Glide (leaving blanks) along the current row until the cursor is at col."""
    assert E.d in ("E", "W"), E.d
    while E.x != col:
        assert _blank(E.L, E.x, E.y), ("glide hits %r at %s" % (E.L.get(E.x, E.y), (E.x, E.y)))
        E._step()
    return E


def vjump(E, col, ynew, d="E"):
    """Glide to `col`, drop/rise to row `ynew`, resume heading `d`."""
    glide(E, col)
    y0 = E.y
    step = 1 if ynew > y0 else -1
    E.L.put(col, y0, "v" if step > 0 else "^")
    for y in range(y0 + step, ynew, step):
        assert _blank(E.L, col, y), ("vjump blocked at %s = %r" % ((col, y), E.L.get(col, y)))
    E.L.put(col, ynew, ">" if d == "E" else "<")
    E.x, E.y, E.d = col + (1 if d == "E" else -1), ynew, d
    return E


class Rows:
    def __init__(self, y0):
        self.y = y0

    def take(self, n=1):
        y = self.y
        self.y += n
        return y


FORBID = {7, 13, 14, 15, 16, 21, 22, 23, 24, 25, 29}
HW_TICK, HW_SPAWN, HW_DIR, HW_RET = 14, 15, 16, 25
D_HX, D_HY, D_EAT, D_NOEAT, D_COLL, D_REP = 22, 23, 7, 21, 29, 13


def build(save_to=None, CBOT=66, RING_PAD=0):
    g = geometry(CBOT=CBOT)
    win = lane_windows(g)
    L = Layout()
    p = L.p

    # ---- rooms ----------------------------------------------------------
    p.room(g["CX0"], g["CY0"], g["CW"], CBOT - g["CY0"] + 1)     # controller
    p.room(8, 8, 6, 4)                                           # state relay
    p.room(26, 4, 6, 4)                                          # scratch relay
    p.room(16, 0, 7, 4)                                          # body relay
    p.input_room(2, 11)
    p.room(38, 10, 9, 22)                                        # display driver
    p.display(49, 12, 18, 18)

    for x, y in ((9, 9), (27, 5), (17, 1)):
        L.put(x, y, "@"); L.put(x + 1, y, ">"); L.put(x + 2, y, "R")
        L.put(x + 3, y, "v")
        L.put(x + 1, y + 1, "^"); L.put(x + 2, y + 1, "s"); L.put(x + 3, y + 1, "<")

    # ---- pipes ----------------------------------------------------------
    p.pipe([(3, 14), (3, 15)])                                   # input  -> ctrl
    p.pipe([(9, 15), (9, 12)])                                   # ctrl   -> state
    p.pipe([(11, 12), (11, 15)])                                 # state  -> ctrl
    p.pipe([(27, 15), (27, 8)])                                  # ctrl   -> scratch
    p.pipe([(29, 8), (29, 15)])                                  # scratch-> ctrl
    feed = [(17, 15), (17, 13), (15, 13), (15, 11), (19, 11), (19, 9),
            (15, 9), (15, 7), (19, 7), (19, 5), (17, 5), (17, 4)]
    ret = [(21, 4), (21, 5), (24, 5), (24, 7), (22, 7), (22, 9), (24, 9),
           (24, 11), (22, 11), (22, 13), (24, 13), (24, 14), (21, 14), (21, 15)]
    p.pipe(feed)                                                 # ctrl   -> body
    p.pipe(ret)                                                  # body   -> ctrl
    p.pipe([(33, 15), (33, 14), (37, 14)])                       # ctrl   -> driver
    p.pipe([(47, 11), (48, 11), (48, 10), (52, 10), (52, 11)])   # driver -> ADDR
    p.pipe([(47, 20), (48, 20)])                                 # driver -> DATA
    p.pipe([(41, 32), (41, 33), (57, 33), (57, 30)])             # driver -> SWAP

    from layout import pipelen
    cap = pipelen(feed) + 1 + pipelen(ret)

    # ---- driver man -----------------------------------------------------
    for (x, y, ch) in [
            (43, 29, "@"),                                   # born on the return leg
            (39, 12, ">"), (40, 12, "r"), (42, 12, "v"), (42, 13, "X"),
            (41, 13, "^"), (42, 14, "<"), (41, 14, "^"), (41, 11, ">"),
            (44, 11, "s"), (45, 11, "v"), (45, 19, "r"), (45, 20, "s"),
            (45, 29, "<"), (39, 29, "^"),
            (43, 13, "1"), (44, 13, "v"), (44, 30, "<"), (41, 30, "s"),
            (39, 30, "^")]:
        L.put(x, y, ch)

    # ---- controller -----------------------------------------------------
    E = Emit(L, g, win, FORBID)
    E.xhi = 32
    R = Rows(g["IYLO"])
    blocks = {}

    def block(name, hw=None):
        """Reserve an approach row + first op row; wire the highway turn-off."""
        y_app = rows(); y_ops = R.take()
        if hw is not None:
            L.put(hw, y_app, "<")
        L.put(1, y_app, "v")
        L.put(1, y_ops, ">")
        blocks[name] = (y_app, y_ops, hw)
        E.at(2, y_ops, "E")
        return y_ops

    def endblock():
        R.y = max(R.y, E.y + 2)

    def ret_dispatch():
        goto(HW_RET)

    def branch_row(col_in):
        """Move onto a fresh 3-row group and return (row, entry cursor)."""
        y_prev = R.take(); yb = R.take(); y_next = R.take()
        vjump(E, col_in, yb, "E")
        return y_prev, yb, y_next

    # helpers that need E/R/L in scope -------------------------------------
    def face(col):
        """Leave the cursor heading EAST at a column <= col."""
        for _ in range(6):
            if E.d == "E" and E.x <= col:
                return
            if E.d == "E":
                E.wrap()                       # -> heading west
            else:
                while E.x > col - 1 and E.x > E.xlo and _blank(L, E.x, E.y):
                    E._step()
                E.wrap()                       # -> heading east
        raise RuntimeError("cannot face column %d" % col)

    def goto(col):
        face(col)
        glide(E, col)
        L.put(col, E.y, "v")

    def arm(x, y, col, ch="v"):
        """Turn the branch outcome at (x,y) toward `col` and drop/rise there."""
        step = 1 if col > x else -1
        L.put(x, y, ">" if step > 0 else "<")
        for xx in range(x + step, col, step):
            assert _blank(L, xx, y), "arm blocked at %s" % ((xx, y),)
        L.put(col, y, ch)

    def rows(n=1):
        R.y = max(R.y, E.y + 2)
        return R.take(n)

    def branch(ch, bx=8, arrive=34):
        """Fresh 3-row group; place `ch` at (bx, yb) with the man heading WEST."""
        face(arrive)
        yprev = rows(); yb = R.take(); ynext = R.take()
        vjump(E, arrive, yb, "W")
        glide(E, bx)
        L.put(bx, yb, ch)
        return yprev, yb, ynext


    # ═══ INIT ════════════════════════════════════════════════════════════
    y = R.take()
    L.put(1, y, "@")
    E.at(2, y, "E")
    E.seq(["r:I", "s:C", "s:C", "8", "M", "+", "M", "r:I", "s:C", "*", "M", "r:C", "+",
           "s:C",
           "1", "s:S",                       # dx = 1
           "r:C", "s:S",                     # hx = sx
           "0", "s:S",                       # dy = 0
           "r:C", "s:S",                     # hy = sy
           "1", "s:S",                       # da = 1
           "r:C", "s:S", "s:B", "s:D",       # ha  -> state, body, display addr
           "5", "M", "+", "s:D",                     # green
           "1", "N", "s:S", "s:D",           # fa = -1 ; commit frame
           "1", "s:S"])                      # K = 1
    ret_dispatch()
    endblock()

    # ═══ TICK ════════════════════════════════════════════════════════════
    block("TICK", HW_TICK)
    E.seq(["r:S", "s:S", "M", "r:S", "+", "s:S", "b", "]", "]", "]", "]"])
    _, yb, _ = branch("x")
    arm(8, yb - 1, D_HX)          # out of range -> death
    L.put(8, yb + 1, ">"); E.at(9, yb + 1, "E")          # in range -> carry on

    E.seq(["r:S", "s:S", "M", "r:S", "+", "s:S", "b", "]", "]", "]", "]"])
    _, yb, _ = branch("x")
    arm(8, yb - 1, D_HY)
    L.put(8, yb + 1, ">"); E.at(9, yb + 1, "E")

    E.seq(["r:S", "s:S", "M", "r:S", "+", "s:S", "M", "r:S", "W", "~"])
    _, yb, _ = branch("X")
    arm(8, yb - 1, D_NOEAT)       # A>0  -> no eat
    arm(8, yb + 1, D_NOEAT)                              # A<0  -> no eat (merges)
    L.put(D_EAT, yb, "v")                                # A==0 -> eat
    endblock()

    # ═══ NO EAT: scan the body, then move ════════════════════════════════
    block("NOEAT", D_NOEAT)
    E.seq(["W", "s:S", "~", "M", "r:S", "s:S", "b", "r:B", "s:B", "m"])
    face(18)
    ys = rows(6)
    vjump(E, 18, ys, "E")
    for (x, y, ch) in [(20, ys, "d"), (20, ys + 1, "r"), (20, ys + 2, "s"),
                       (20, ys + 3, "~"), (20, ys + 4, "X"), (19, ys + 4, "m"),
                       (18, ys + 4, "^"), (20, ys + 5, ">")]:
        L.put(x, y, ch)
    E.ops.append((20, ys + 1, "r", "B"))
    E.ops.append((20, ys + 2, "s", "B"))
    arm(20, ys + 5, D_COLL)                              # collision -> repaint
    E.at(21, ys, "E")
    face(34)
    yn = rows()
    vjump(E, 34, yn, "W")
    E.seq(["r:B", "s:D", "0", "s:D", "W", "s:B", "s:D", "5", "M", "+", "s:D",
           "1", "N", "s:D"])
    ret_dispatch()
    endblock()

    # ═══ EAT ═════════════════════════════════════════════════════════════
    block("EAT", D_EAT)
    E.seq(["1", "N", "s:S", "W", "s:C", "1", "M", "r:S", "+", "s:S",
           "r:C", "s:B", "s:D", "5", "M", "+", "s:D", "1", "N", "s:D"])
    ret_dispatch()
    endblock()

    # ═══ deaths ══════════════════════════════════════════════════════════
    block("DHX", D_HX)
    E.seq(["r:S"] * 6 + ["b"])
    goto(D_REP)
    endblock()

    block("DHY", D_HY)
    E.seq(["r:S"] * 4 + ["b"])
    goto(D_REP)
    endblock()

    block("COLL", D_COLL)
    E.seq(["r:S"] * 8 + ["b"])
    goto(D_REP)
    endblock()

    block("REP", D_REP)
    face(18)
    yr = rows(4)
    vjump(E, 18, yr, "E")
    for (x, y, ch) in [(20, yr, "d"), (20, yr + 1, "r"), (20, yr + 2, ">"),
                       (31, yr + 2, "s"), (32, yr + 2, "9"), (33, yr + 2, "s"),
                       (34, yr + 2, "v"), (34, yr + 3, "<"), (19, yr + 3, "m"),
                       (18, yr + 3, "^")]:
        L.put(x, y, ch)
    E.ops.append((20, yr + 1, "r", "B"))
    E.ops.append((31, yr + 2, "s", "D"))
    E.ops.append((33, yr + 2, "s", "D"))
    E.at(21, yr, "E")
    face(30)
    yn = rows()
    vjump(E, 30, yn, "W")
    E.seq(["1", "N", "s:D", "H"])
    endblock()

    # ═══ SPAWN ═══════════════════════════════════════════════════════════
    block("SPAWN", HW_SPAWN)
    E.seq(["r:I", "s:C", "8", "M", "+", "M", "r:I", "*", "M", "r:C", "+", "s:C", "s:C"])
    E.seq(["r:S", "s:S"] * 6)
    E.seq(["r:S", "r:C", "s:S"])
    E.seq(["r:S", "s:S"])
    E.seq(["r:C", "s:D", "9", "s:D", "1", "N", "s:D"])
    ret_dispatch()
    endblock()

    # ═══ DIR ═════════════════════════════════════════════════════════════
    block("DIR", HW_DIR)
    E.seq(["b"])
    _, yb1, _ = branch("x")
    arm_entry = {}
    for bit0, dy in ((1, -1), (0, +1)):                  # cw=N (bit 1), ccw=S
        col = 17 if bit0 else 30
        arm(8, yb1 + dy, col)
        yq = rows(3) + 1                               # middle of a 3-row group
        L.put(col, yq, ">")
        L.put(col + 1, yq, "]")
        L.put(col + 2, yq, "x")
        arm_entry[(bit0, 1)] = (col + 2, yq + 1)         # heading E: cw -> S
        arm_entry[(bit0, 0)] = (col + 2, yq - 1)         # heading E: ccw -> N
    ROT = 24
    DIRVEC = {(1, 0): (0, -1, -16),                      # op 2  up
              (0, 1): (1, 0, 1),                         # op 3  right
              (1, 1): (0, 1, 16),                        # op 4  down
              (0, 0): (-1, 0, -1)}                       # op 5  left
    ARMCOL = {(1, 1): 21, (0, 1): 22, (1, 0): 23, (0, 0): 29}
    for key, (dx, dy, da) in DIRVEC.items():
        ax, ay = arm_entry[key]
        acol = ARMCOL[key]
        arm(ax, ay, acol)
        y_app = rows(); y_ops = R.take()
        L.put(acol, y_app, "<"); L.put(1, y_app, "v"); L.put(1, y_ops, ">")
        E.at(2, y_ops, "E")
        toks = []
        for v in (dx, dy, da):
            mag = ["8", "M", "+"] if abs(v) == 16 else [str(abs(v))]
            toks += mag + (["N"] if v < 0 else []) + ["s:C"]
        E.seq(toks)
        goto(ROT)
        endblock()

    block("ROT", ROT)
    E.seq(["r:S", "r:C", "s:S", "r:S", "s:S",
           "r:S", "r:C", "s:S", "r:S", "s:S",
           "r:S", "r:C", "s:S", "r:S", "s:S",
           "r:S", "s:S", "r:S", "s:S"])
    ret_dispatch()
    endblock()

    # ═══ DISPATCH (last: every return travels DOWN to it) ════════════════
    block("DISP", HW_RET)
    E.seq(["1", "M", "r:I", "-"])
    _, yb, _ = branch("X")
    yextra = rows()
    arm(8, yb + 1, HW_TICK, "^")   # op 0 -> tick
    arm(8, yb - 1, HW_DIR, "^")    # op>1 -> direction
    L.put(7, yb, "v")                                    # op 1 -> spawn
    assert _blank(L, 7, yb + 1)
    arm(7, yextra, HW_SPAWN, "^")
    endblock()

    # ---- verification ---------------------------------------------------
    _assert_bindings(L, g, E.ops)
    assert R.y <= g["IYHI"] + 1, "controller overflow: needs %d rows, has %d" % (
        R.y - g["IYLO"], g["IYHI"] - g["IYLO"] + 1)

    if save_to:
        p.save(save_to)
    return p, cap, R.y


def _assert_bindings(L, g, ops):
    """Re-derive every s/r binding from the finished grid."""
    out, inc = g["attach_out"], g["attach_in"]
    att = g["ATT"]
    for (x, y, ch, lane) in ops:
        table = out if ch == "s" else inc
        got = min(table, key=lambda k: (abs(table[k] - x) + abs(att - y), att, table[k]))
        assert got == lane, "%s at %s binds %s, wanted %s" % (ch, (x, y), got, lane)


if __name__ == "__main__":
    import json
    path = os.path.join(HERE, "micro.man")
    prog, cap, rows = build(save_to=path)
    print("saved", path)
    print("footprint", prog.footprint(), "body-ring capacity", cap, "ctrl rows", rows)

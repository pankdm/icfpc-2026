#!/usr/bin/env python3
"""snake micro-design: a small, O(1)-state Snake solver.

ARCHITECTURE

  STATE RING   a FIFO ring holding 8 scalars in a fixed canonical order

                   [dy, hy, dx, hx, da, ha, fa, K]

               dy,dx  direction step in board coords      (-1/0/1)
               da     direction step in DISPLAY ADDRESS   (-16/-1/+1/+16)
               hy,hx  head row/column                     (0..15)
               ha     head display address = 16*hy + hx   (0..255)
               fa     fruit display address, or -1        (-1..255)
               K      snake length
               Every round pops the 8 values in order and pushes them back in
               the same order, so the ring is a rotating register file.  A
               value can also be PARKED in the ring past K (SPAWN does that
               with the fruit's x) and recovered by one extra lap -- which is
               why this build needs NO scratch ring at all.  See BINDING for
               why deleting that one ring is worth so much.

  BODY RING    a FIFO ring holding the K body cells as display addresses,
               oldest (tail) first.  Sized for the worst case: at most 100
               rounds per case => at most 49 growths => K <= 50.

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

BINDING -- why the state ring is the only ring.
`s`/`r` pick the nearest attached pipe (Manhattan to the pipe's first/last
cell, ties in reading order).  Every controller pipe attaches to the TOP wall,
so the y term is identical for all of them and the binding is decided by the
column alone: the interior splits into vertical LANES and a pipe op may only be
emitted inside its lane's window.

That window WIDTH sets the program's height, because a token that cannot reach
its lane on the current row forces the serpentine to WRAP -- a whole row, and
(via the dispatch highways, which then have to run further) ticks as well.
With four in-pipes and four out-pipes on a 34-wide room the state lane was five
columns and one `r:S s:S` pair cost half a row.  Deleting the scratch ring
leaves three of each, so the state lane is fifteen columns and seven pairs fit
on one row.  The canonical ring order, the SPAWN parking trick and the inline
DIR arms below all exist only to make that deletion possible.

`_assert_bindings()` re-derives every binding from the finished grid and checks
it against what the emitter intended.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm                      # noqa: E402,F401
from layout import Layout, pipelen          # noqa: E402

GRID = 16
COLOUR = {"snake": 10, "dead": 9, "fruit": 9, "empty": 0}
# round op code -> (dy, dx, da) that the direction change installs
DIRSTEP = {2: (-1, 0, -GRID),    # up
           3: (0, 1, 1),         # right
           4: (1, 0, GRID),      # down
           5: (0, -1, -1)}       # left


# ──────────────────────────────────────────────────────────────────────────
# geometry knobs (integers -- autotune can sweep them)
# ──────────────────────────────────────────────────────────────────────────
def geometry(CX0=0, CY0=16, CW=40, CBOT=100,
             BD_OUT=44, BD_IN=50, ST_OUT=22, ST_IN=24, IN_IN=56, DRV_OUT=58):
    g = dict(CX0=CX0, CY0=CY0, CW=CW, CBOT=CBOT)
    g["CX1"] = CX0 + CW - 1                       # controller right wall
    g["IXLO"], g["IXHI"] = CX0 + 1, CX0 + CW - 2  # interior columns
    g["IYLO"], g["IYHI"] = CY0 + 1, CBOT - 1      # interior rows
    g["ATT"] = CY0 - 1                            # pipe attach row
    g["attach_out"] = {"B": BD_OUT, "S": ST_OUT, "D": DRV_OUT}
    g["attach_in"] = {"B": BD_IN, "S": ST_IN, "I": IN_IN}
    return g


def lane_windows(g):
    """Window for each (op, lane): the columns where that op binds that lane.

    `s` consults only the OUTGOING table and `r` only the INCOMING one, so the
    two are independent -- a receive window may overlap the send window of a
    DIFFERENT lane.  Keeping them separate (rather than intersecting per lane)
    is what lets `r:B` sit right next to `s:D`.
    """
    win = {}
    for op, table in (("s", g["attach_out"]), ("r", g["attach_in"])):
        for lane in table:
            cols = [x for x in range(g["IXLO"], g["IXHI"] + 1)
                    if min(table, key=lambda k: (abs(table[k] - x), table[k])) == lane]
            best = cur = []
            for x in cols:
                cur = cur + [x] if cur and x == cur[-1] + 1 else [x]
                if len(cur) > len(best):
                    best = cur
            win[(op, lane)] = (best[0], best[-1])
    return win



# ──────────────────────────────────────────────────────────────────────────
# emitter
# ──────────────────────────────────────────────────────────────────────────
class Emit:
    """Serpentine instruction emitter with lane-constrained pipe ops.

    Tokens: a bare instruction char, ``"#<digits>"`` for a backtick literal, or
    ``"<op>:<lane>"`` for a pipe op that has to land inside ``lane``'s window.
    """

    def __init__(self, L, g, win, forbidden, wrapcols=()):
        self.L, self.g, self.win = L, g, win
        self.forbidden = set(forbidden)
        self.wrapcols = set(wrapcols)          # reserved landing spots for wrap()
        self.xlo, self.xhi = g["IXLO"], g["IXHI"]
        self.x = self.y = 0
        self.d = "E"
        self.ops = []                     # (x, y, ch, lane) for binding checks
        self.wraps = 0

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
        self.wraps += 1
        bad = self.forbidden - self.wrapcols
        if self.d == "E":
            x = min(self.x, self.g["IXHI"])
            while x <= self.g["IXHI"] and (x in bad
                                           or self.L.get(x, self.y) != " "
                                           or self.L.get(x, self.y + 1) != " "):
                x += 1
            assert x <= self.g["IXHI"], "no room to wrap east at row %d" % self.y
        else:
            x = max(self.x, self.g["IXLO"])
            while x >= self.g["IXLO"] and (x in bad
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

    def _reach(self, op, lane):
        lo, hi = self.win[(op, lane)]
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
            self._reach(op, lane)
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


# Dispatch/branch highway columns: one vertical wire per destination.  They are
# deliberately kept OUT of the state lane (10..26) -- see BINDING above.
# The state lane owns the whole left half (1..19/22) and the BODY and DISPLAY
# lanes sit side by side on the right (20..32 / 32..38).  Every frame alternates
# body-ring and display ops -- with those two lanes at opposite ends of the room
# that alternation walked ~20 blank cells four times per frame, which was the
# single largest tick item in the profile.
# Every column right of RIGID slides with the room's right wall, so the whole
# right half of the controller can be squeezed by lowering CW: the box is
# max(w,h)^2 and w = CW + 31, so five columns off CW is five off the box side.
RIGID = 30                           # columns <= RIGID never move
MIN_CAP = 55                         # >= 50 + slack: the worst snake a case can reach
_RIGHT = dict(HW_RET=57, HW_TICK=47, HW_SPAWN=45, HW_DIR=42,
              D_EAT=39, D_NOEAT=40, WRAP_E=58,
              LOOPX=49, LOOPM=48, LOOPR=46, DEC1=48, DEC2=53, REPD=52,
              BD_OUT=44, BD_IN=50, IN_IN=56, DRV_OUT=58)
D_REP, D_COLL, D_HX, D_HY = 8, 6, 4, 2
WRAP_W = 1                           # reserved: wrap() must always find a landing


def right_cols(CW):
    """The right-half column assignment for a controller CW wide (60 = the original)."""
    return {k: v + (CW - 60) for k, v in _RIGHT.items()}


def _lit(v):
    """Tokens that leave the constant v in A.

    NO backtick literals: the oracle pairs backticks per row AND per column, so
    two unrelated `16` literals that happen to line up vertically make the whole
    program a loaderror ("expected a digit or a space between backticks").  The
    Rust engine does not reproduce that, so it graded 5/5 while the oracle
    refused to load.  |16| is built as 8 M + instead, which costs B -- harmless
    everywhere _lit is used.
    """
    if v == 0:
        return ["0"]
    if abs(v) < 10:
        return [str(abs(v))] + (["N"] if v < 0 else [])
    assert abs(v) == 16, v
    return ["8", "M", "+"] + (["N"] if v < 0 else [])


def build(save_to=None, CY0=8, CBOT=None, CW=60,
          ST_OUT=22, ST_IN=24, ST_X0=24, ST_W=7, BD_X0=33, BD_W=None,
          FEED_E=None, FEED_W=31, FEED_W2=None, RET_E=None,
          DRVX=None, DISX=None, **over):
    R_ = right_cols(CW)
    R_.update(over)
    HW_RET, HW_TICK, HW_SPAWN = R_["HW_RET"], R_["HW_TICK"], R_["HW_SPAWN"]
    HW_DIR, D_EAT, D_NOEAT, WRAP_E = R_["HW_DIR"], R_["D_EAT"], R_["D_NOEAT"], R_["WRAP_E"]
    LOOPX, LOOPM, LOOPR = R_["LOOPX"], R_["LOOPM"], R_["LOOPR"]
    DEC1, DEC2, REPD = R_["DEC1"], R_["DEC2"], R_["REPD"]
    BD_OUT, BD_IN, IN_IN, DRV_OUT = R_["BD_OUT"], R_["BD_IN"], R_["IN_IN"], R_["DRV_OUT"]
    ARMCOL = {2: D_HY, 3: D_HX, 4: D_COLL, 5: D_REP}
    FORBID = {HW_RET, HW_TICK, HW_SPAWN, HW_DIR, D_EAT, D_NOEAT,
              D_REP, D_COLL, D_HX, D_HY, WRAP_W, WRAP_E}
    FEED_E = BD_IN - 1 if FEED_E is None else FEED_E
    FEED_W2 = FEED_W if FEED_W2 is None else FEED_W2
    RET_E = IN_IN - 2 if RET_E is None else RET_E
    BD_W = BD_IN - 1 - BD_X0 if BD_W is None else BD_W   # room right wall = BD_IN-1
    # The TOP BAND is rows 0..ATT.  Rows 0..3 hold the two relay rooms and the
    # input room; rows 4..ATT-1 are the horizontal pipe highways and row ATT
    # carries every controller-side pipe terminal (that is what makes the s/r
    # binding a function of the column alone -- see BINDING above).
    #
    # HEIGHT = CY0 + 78, so every row saved in this band is a row off the box.
    # The band used to be 16 rows deep because the body ring was folded into a
    # 9-column serpentine there; routing that ring along the FULL WIDTH of the
    # band instead gets the same 56 cells of capacity out of three rows.
    CBOT = CY0 + 77 if CBOT is None else CBOT
    DRVX = CW + 2 if DRVX is None else DRVX
    DISX = DRVX + 11 if DISX is None else DISX
    g = geometry(CY0=CY0, CW=CW, CBOT=CBOT, BD_OUT=BD_OUT, BD_IN=BD_IN,
                 ST_OUT=ST_OUT, ST_IN=ST_IN, IN_IN=IN_IN, DRV_OUT=DRV_OUT)
    win = lane_windows(g)
    ATT = g["ATT"]
    L = Layout()
    p = L.p

    # ---- rooms ----------------------------------------------------------
    p.room(g["CX0"], CY0, CW, CBOT - CY0 + 1)          # controller
    p.room(BD_X0, 0, BD_W, 4)                          # body relay
    p.room(ST_X0, 0, ST_W, 4)                          # state relay
    p.input_room(IN_IN - 1, 0)
    p.room(DRVX, 10, 9, 22)                            # display driver
    p.display(DISX, 12, 18, 18)

    for x, y in ((BD_X0 + 1, 1), (ST_X0 + 1, 1)):
        L.put(x, y, "@"); L.put(x + 1, y, ">"); L.put(x + 2, y, "R")
        L.put(x + 3, y, "v")
        L.put(x + 1, y + 1, "^"); L.put(x + 2, y + 1, "s"); L.put(x + 3, y + 1, "<")

    # ---- pipes ----------------------------------------------------------
    p.pipe([(IN_IN, 3), (IN_IN, ATT)])                              # input -> ctrl
    p.pipe([(ST_OUT, ATT), (ST_OUT, 4), (ST_X0 + 1, 4)],            # ctrl  -> state
           end_direction="N")
    p.pipe([(ST_X0 + ST_W - 2, 4), (ST_X0 + ST_W - 2, 5),           # state -> ctrl
            (ST_IN, 5), (ST_IN, ATT)])
    # The body ring: one BOUSTROPHEDON lap of the band's free rows 4..ATT-1.  It
    # has to dodge the state pipes (which chop rows 4/5 between ST_OUT and
    # ST_X0+ST_W-2) and the input pipe (column IN_IN, rows 3..ATT), so the pocket
    # it snakes through is rows 4..ATT-1 x FEED_W..FEED_E, and the return leaves
    # the body room's RIGHT wall and comes back down column BD_IN.
    #
    # CAPACITY, not shape, is what this pipe is for: the ring has to hold the
    # whole snake, so every row the band loses has to be paid back in width.
    # Rows ATT-1 and ATT-2 clear the state pipes entirely and may run all the way
    # to FEED_W2; rows 5 and 4 must stop at FEED_W.
    lanes = [(r, FEED_E if (r - 6) % 2 == 0 else FEED_W2)
             for r in range(ATT - 1, 5, -1)]
    lanes += [(5, FEED_W), (4, BD_X0 + BD_W - 5)]
    feed = [(BD_OUT, ATT), (BD_OUT, lanes[0][0])]
    for i, (row, xe) in enumerate(lanes):
        feed.append((xe, row))
        if i + 1 < len(lanes):
            feed.append((xe, lanes[i + 1][0]))
    ret = [(BD_X0 + BD_W, 1), (RET_E, 1), (RET_E, 3), (BD_IN, 3), (BD_IN, ATT)]
    p.pipe(feed, end_direction="N")                                 # ctrl  -> body
    p.pipe(ret)                                                     # body  -> ctrl
    cap = pipelen(feed) + 1 + pipelen(ret)
    # >= 50 covers the worst case a 100-round case can reach (each growth costs a
    # spawn round plus a tick round).  A bigger ring is pure safety margin but it
    # costs ticks: at snake length 1 a pushed cell has to travel cap-1 cells
    # before it can be popped again.  65 measured 90.7M against 89.6M at 55.
    assert cap >= MIN_CAP, "body ring capacity %d too small" % cap
    p.pipe([(DRV_OUT, ATT), (DRV_OUT, 4), (DRVX - 1, 4), (DRVX - 1, 12)],
           end_direction="E")                                       # ctrl -> driver

    # ---- driver man -----------------------------------------------------
    off = DRVX - 38                                    # driver block was built at x=38
    for (x, y, ch) in [
            (43, 29, "@"),                             # born on the return leg
            (39, 12, ">"), (40, 12, "r"), (42, 12, "v"), (42, 13, "X"),
            (41, 13, "^"), (42, 14, "<"), (41, 14, "^"), (41, 11, ">"),
            (44, 11, "s"), (45, 11, "v"), (45, 19, "r"), (45, 20, "s"),
            (45, 29, "<"), (39, 29, "^"),
            (43, 13, "1"), (44, 13, "v"), (44, 30, "<"), (41, 30, "s"),
            (39, 30, "^")]:
        L.put(x + off, y, ch)
    p.pipe([(47 + off, 11), (48 + off, 11), (48 + off, 10),
            (DISX + 3, 10), (DISX + 3, 11)])                        # -> ADDR
    p.pipe([(47 + off, 20), (DISX - 1, 20)])                        # -> DATA
    p.pipe([(41 + off, 32), (41 + off, 33), (DISX + 4, 33), (DISX + 4, 30)])  # -> SWAP

    # ---- controller -----------------------------------------------------
    E = Emit(L, g, win, FORBID, wrapcols=(WRAP_W, WRAP_E))
    R = Rows(g["IYLO"])

    def block(hw):
        """Enter a block straight off the highway: the turn-off IS the first op row.

        Turn TOWARDS the state lane, so the first `r:S` lands on this very row
        instead of costing a wrap."""
        y_ops = R.take()
        if hw < win[("r", "S")][1]:
            L.put(hw, y_ops, ">")
            E.at(hw + 1, y_ops, "E")
        else:
            L.put(hw, y_ops, "<")
            E.at(hw - 1, y_ops, "W")
        return y_ops

    def endblock():
        R.y = max(R.y, E.y + 1)

    def face(col, d="E"):
        """Leave the cursor heading `d` with `col` still reachable ahead of it."""
        for _ in range(8):
            if d == "E" and E.d == "E" and E.x <= col:
                return
            if d == "W" and E.d == "W" and E.x >= col:
                return
            if E.d == "E":
                while E.x < E.xhi and E.x < col + 1 and _blank(L, E.x, E.y):
                    E._step()
            else:
                while E.x > E.xlo and E.x > col - 1 and _blank(L, E.x, E.y):
                    E._step()
            E.wrap()
        raise RuntimeError("cannot face column %d heading %s" % (col, d))

    def goto(col, ch="v"):
        ahead = (E.d == "E" and E.x <= col) or (E.d == "W" and E.x >= col)
        step = 1 if E.d == "E" else -1
        if ahead and all(_blank(L, x, E.y)
                         for x in range(E.x, col + step, step)):
            glide(E, col)                  # already pointing at it: no wrap
        else:
            face(col, "E")
            glide(E, col)
        L.put(col, E.y, ch)

    def ret_dispatch():
        goto(HW_RET, "^")                      # the dispatcher sits ABOVE every block

    def arm(x, y, col, ch="v"):
        """Turn the branch outcome at (x,y) toward `col` and drop/rise there."""
        step = 1 if col > x else -1
        L.put(x, y, ">" if step > 0 else "<")
        for xx in range(x + step, col, step):
            assert _blank(L, xx, y), "arm blocked at %s" % ((xx, y),)
        L.put(col, y, ch)

    def rows(n=1):
        R.y = max(R.y, E.y + 1)
        return R.take(n)

    def branch(ch, head="W", up_to=None):
        """Drop onto a branch row right where the cursor is; return (yb, bx).

        The branch column is chosen NEXT TO THE CURSOR rather than fixed.  A
        fixed column costs a full-width glide out to it and back on every
        execution, and TICK runs three branches on every tick round -- that glide
        was ~100 of the ~270 blank cells the controller walked per round.

        A branch needs three rows (arm, branch, arm).  When the arm that goes UP
        can be drawn on the block's own last OP row -- its columns are usually
        free there, because ops cluster in the state lane while the arms run out
        to the highways -- the group costs only ONE new row instead of three.
        """
        off = 1 if head == "E" else -1
        for _ in range(4):
            step = 1 if E.d == "E" else -1
            col = E.x
            while (E.xlo <= col <= E.xhi
                   and not (E._ok(col) and _blank(L, col, E.y) and E._ok(col + off))):
                col += step
            if E.xlo <= col <= E.xhi:
                break
            E.wrap()
        else:
            raise RuntimeError("no drop column for a branch")
        bx = col + off
        y_ops = E.y
        lo, hi = (min(bx, up_to), max(bx, up_to)) if up_to is not None else (0, -1)
        # The tight group draws the UP arm on the block's own op row, which the
        # man WALKS.  That is only safe when the arm runs off the far side of the
        # drop column: he turns down at `col` before he can reach the arm's turn
        # glyph.  If the arm would lie between where he entered the row and
        # `col` -- which happens whenever the branch had to wrap first -- he
        # walks straight into it and the branch never executes.  This silently
        # sent every tick round down the hx-death highway at CW=53.
        beyond = up_to is not None and ((up_to > col) if E.d == "E" else (up_to < col))
        tight = (beyond and R.y <= y_ops + 1
                 and all(_blank(L, x, y_ops) for x in range(lo, hi + 1)))
        if tight:
            yb = y_ops + 1
            R.y = max(R.y, yb + 2)
        else:
            rows(); yb = R.take(); R.take()
        vjump(E, col, yb, head)
        glide(E, bx)
        L.put(bx, yb, ch)
        return yb, bx

    def resume(bx, y, prefer_west=None):
        """Send a branch outcome that landed on (bx, y) back along the row."""
        mid = (win[("s", "S")][0] + win[("s", "S")][1]) // 2
        west = (bx >= mid) if prefer_west is None else prefer_west
        L.put(bx, y, "<" if west else ">")
        E.at(bx - 1 if west else bx + 1, y, "W" if west else "E")

    # Block ORDER is a tick lever, not cosmetics: every round walks DISP -> block
    # -> back up the return highway, so the cost is 2 * (block row - DISP row).
    # Ticks are 79% of rounds in the public data, so TICK/NOEAT come first and
    # the once-per-case INIT and repaint code sink to the bottom.  The DIR arms
    # reuse the death highways (see ARMCOL), which is why deaths must stay ABOVE
    # DIR.
    # ═══ DISPATCH (first: every block returns UP to it) ══════════════════
    block(HW_RET)
    E.seq(["r:I", "M", "1", "W", "-"])
    yb, bx = branch("X", "W", up_to=HW_DIR)
    yextra = rows()
    arm(bx, yb + 1, HW_TICK)       # A<0  (op 0)  -> tick
    arm(bx, yb - 1, HW_DIR)        # A>0  (op>1)  -> direction
    drop = bx - 1                  # A==0 (op 1)  -> spawn: straight on, heading west
    while not (E._ok(drop) and _blank(L, drop, yb) and _blank(L, drop, yextra)):
        drop -= 1
    L.put(drop, yb, "v")
    arm(drop, yextra, HW_SPAWN)
    endblock()

    # ═══ TICK ════════════════════════════════════════════════════════════
    block(HW_TICK)
    E.seq(["r:S", "s:S", "M", "r:S", "+", "s:S", "b", "]", "]", "]", "]"])
    yb, bx = branch("x", "W", up_to=D_HY)
    arm(bx, yb - 1, D_HY)                                     # out of range -> death
    resume(bx, yb + 1)                                        # in range -> carry on

    E.seq(["r:S", "s:S", "M", "r:S", "+", "s:S", "b", "]", "]", "]", "]"])
    yb, bx = branch("x", "W", up_to=D_HX)
    arm(bx, yb - 1, D_HX)
    resume(bx, yb + 1)

    E.seq(["r:S", "s:S", "M", "r:S", "+", "s:S", "M", "r:S", "W", "~"])
    yb, bx = branch("X", "E", up_to=D_NOEAT)
    arm(bx, yb - 1, D_NOEAT)       # A>0  -> no eat
    arm(bx, yb + 1, D_NOEAT)       # A<0  -> no eat (merges)
    for xx in range(bx + 1, D_EAT):
        assert _blank(L, xx, yb)
    L.put(D_EAT, yb, "v")          # A==0 -> eat (straight on, heading east)
    endblock()

    # ═══ NO EAT: scan the body, then move ════════════════════════════════
    block(D_NOEAT)
    E.seq(["W", "s:S", "~", "M", "r:S", "s:S", "b", "r:B", "s:B", "m"])
    face(LOOPR, "E")
    ys = rows(6)
    vjump(E, LOOPR, ys, "E")
    for (x, y, ch) in [(LOOPX, ys, "d"), (LOOPX, ys + 1, "r"), (LOOPX, ys + 2, "s"),
                       (LOOPX, ys + 3, "~"), (LOOPX, ys + 4, "X"),
                       (LOOPM, ys + 4, "m"), (LOOPR, ys + 4, "^")]:
        L.put(x, y, ch)
    E.ops.append((LOOPX, ys + 1, "r", "B"))
    E.ops.append((LOOPX, ys + 2, "s", "B"))
    arm(LOOPX, ys + 5, D_COLL)                               # collision -> repaint
    E.at(LOOPX + 1, ys, "E")
    yn = rows()
    vjump(E, LOOPX + 2, yn, "W")
    E.seq(["r:B", "s:D", "0", "s:D", "W", "s:B", "s:D", "5", "M", "+", "s:D",
           "1", "N", "s:D"])
    ret_dispatch()
    endblock()

    # ═══ EAT ═════════════════════════════════════════════════════════════
    block(D_EAT)
    E.seq(["W", "s:B", "s:D",              # A = ha' : grow, and draw the new head
           "r:S", "M", "1", "+", "M",      # B = K+1
           "1", "N", "s:S",                # fa = -1
           "W", "s:S",                     # K = K+1
           "5", "M", "+", "s:D",           # green
           "1", "N", "s:D"])               # commit
    ret_dispatch()
    endblock()

    # ═══ deaths ══════════════════════════════════════════════════════════
    # how deep K sits in the ring when each test fires: hy 6, hx 4, collision 8
    for hw, pops in ((D_HY, 6), (D_HX, 4), (D_COLL, 8)):
        block(hw)
        E.seq(["r:S"] * pops + ["b"])
        goto(D_REP)
        endblock()

    block(D_REP)
    face(LOOPR, "E")
    yr = rows(4)
    vjump(E, LOOPR, yr, "E")
    for (x, y, ch) in [(LOOPX, yr, "d"), (LOOPX, yr + 1, "r"), (LOOPX, yr + 2, ">"),
                       (REPD, yr + 2, "s"), (REPD + 1, yr + 2, "9"),
                       (REPD + 2, yr + 2, "s"), (REPD + 3, yr + 2, "v"),
                       (REPD + 3, yr + 3, "<"),
                       (LOOPM, yr + 3, "m"), (LOOPR, yr + 3, "^")]:
        L.put(x, y, ch)
    E.ops.append((LOOPX, yr + 1, "r", "B"))
    E.ops.append((REPD, yr + 2, "s", "D"))
    E.ops.append((REPD + 2, yr + 2, "s", "D"))
    E.at(LOOPX + 1, yr, "E")
    yn = rows()
    vjump(E, LOOPX + 2, yn, "W")
    E.seq(["1", "N", "s:D", "H"])
    endblock()

    # ═══ DIR ═════════════════════════════════════════════════════════════
    block(HW_DIR)
    E.seq(["b"])                                     # BP = op-1 (1..4)
    yb1, bx1 = branch("x", "W", up_to=DEC1)
    arm_entry = {}
    for bit0, dy in ((1, -1), (0, +1)):              # bit set -> N, clear -> S
        col = DEC1 if bit0 else DEC2
        arm(bx1, yb1 + dy, col)
        yq = rows(3) + 1                             # middle of a 3-row group
        L.put(col, yq, ">")
        L.put(col + 1, yq, "]")
        L.put(col + 2, yq, "x")
        arm_entry[(bit0, 1)] = (col + 2, yq + 1)     # heading E: bit set -> S
        arm_entry[(bit0, 0)] = (col + 2, yq - 1)     # heading E: bit clear -> N
    # (low bit of op-1, low bit of (op-1)>>1) -> round op code
    OPKEY = {(1, 0): 2, (0, 1): 3, (1, 1): 4, (0, 0): 5}
    for key, op in OPKEY.items():
        ax, ay = arm_entry[key]
        acol = ARMCOL[op]
        arm(ax, ay, acol)
        y_ops = rows()
        L.put(acol, y_ops, ">")
        E.at(acol + 1, y_ops, "E")
        sdy, sdx, sda = DIRSTEP[op]
        E.seq(["r:S"] + _lit(sdy) + ["s:S", "r:S", "s:S"]     # dy, hy
              + ["r:S"] + _lit(sdx) + ["s:S", "r:S", "s:S"]   # dx, hx
              + ["r:S"] + _lit(sda) + ["s:S", "r:S", "s:S",   # da, ha
                                       "r:S", "s:S",          # fa
                                       "r:S", "s:S"])         # K
        ret_dispatch()
        endblock()

    # ═══ SPAWN ═══════════════════════════════════════════════════════════
    block(HW_SPAWN)
    E.seq(["4", "M",
           "r:I", "s:S",                   # park fx past K
           "r:I", "{", "M"]                # B = 16*fy
          + ["r:S", "s:S"] * 8             # one lap: fx comes back to the front
          + ["r:S", "+", "M"]              # B = fa = fx + 16*fy
          + ["r:S", "s:S"] * 6             # rotate up to the old fa
          + ["r:S", "W", "s:S", "s:D",     # drop the old fa, push the new one, draw
             "r:S", "s:S",                 # K
             "9", "s:D", "1", "N", "s:D"])
    ret_dispatch()
    endblock()

    # ═══ INIT ════════════════════════════════════════════════════════════
    y0 = R.take()
    L.put(3, y0, "@")
    E.at(4, y0, "E")
    E.seq(["4", "M",                       # B = 4  (the shift count for *16)
           "r:I", "s:S",                   # park sx
           "r:I", "s:S",                   # park sy   (A = sy)
           "{", "M",                       # B = 16*sy
           "r:S", "s:S",                   # A = sx, re-park it
           "+", "s:S",                     # A = ha = sx + 16*sy, park it
           "0", "s:S",                     # dy = 0
           "r:S", "s:S",                   # hy = sy
           "1", "s:S",                     # dx = 1
           "r:S", "s:S",                   # hx = sx
           "1", "s:S",                     # da = 1
           "r:S", "s:S", "s:B", "s:D",     # ha -> state, body ring, display addr
           "5", "M", "+", "s:D",           # green
           "1", "N", "s:S", "s:D",         # fa = -1 ; commit the frame
           "1", "s:S"])                    # K = 1
    ret_dispatch()
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
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "micro4.man")
    prog, cap, nrows = build(save_to=path)
    print("saved", path)
    print("footprint", prog.footprint(), "body-ring capacity", cap, "ctrl rows", nrows)

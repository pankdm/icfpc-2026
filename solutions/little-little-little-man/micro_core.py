#!/usr/bin/env python3
"""micro_core.py -- floorplan, rooms, pipes, driver and the lane emitter for the
LLLM micro build.  See build_micro.py for the design contract.

Eight controller pipes, ALL attached to the controller's TOP wall, so the
Manhattan y-term is the same for every one of them and `s`/`r` binding is a
function of the COLUMN alone:

    outgoing   S (state ring)  P (prog ring)  T (scratch ring)  D (driver)
    incoming   S              P              T                 I (input)

The interior therefore splits into vertical LANES; a pipe op may only be emitted
inside its lane's window, and a token that cannot reach its lane on the current
row forces a WRAP (a whole row).  `lane_windows()` re-derives the windows the way
the oracle does; `assert_bindings()` re-derives every emitted binding from the
FINISHED grid and compares it with what the emitter intended.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm                      # noqa: E402
from layout import Layout, pipelen          # noqa: E402


# ──────────────────────────────────────────────────────────────────────────
# geometry
# ──────────────────────────────────────────────────────────────────────────
def geometry(CW=104, CY0=20, CBOT=300):
    """All the integers autotune may sweep.

    Every controller port sits on the TOP wall at row ATT = CY0-1, so `s`/`r`
    binding is a function of the COLUMN alone.  The three relay rooms sit at
    DIFFERENT band rows so each ring's capacity can be dialled independently:
    SCRATCH must be SHORT (a push/pop round trip is on the critical path), the
    PROG ring must hold 32 words, the STATE ring 11.
    """
    S_OUT, P_OUT, T_OUT = 13, 39, 65
    D_OUT, I_IN = CW - 3, CW - 7
    ATT = CY0 - 1
    g = dict(CX0=0, CY0=CY0, CW=CW, CBOT=CBOT, ATT=ATT)
    g["CX1"] = CW - 1
    g["IXLO"], g["IXHI"] = 1, CW - 2
    g["IYLO"], g["IYHI"] = CY0 + 1, CBOT - 1
    g["attach_out"] = {"S": S_OUT, "P": P_OUT, "T": T_OUT, "D": D_OUT}
    g["attach_in"] = {"S": S_OUT + 2, "P": P_OUT + 2, "T": T_OUT + 2, "I": I_IN}
    g["relay_row"] = {"P": 0, "S": ATT - 10, "T": ATT - 6}   # room top row
    g["DX"] = CW + 2
    g["DY"] = 6
    g["DISX"] = g["DX"] + 14
    g["DISY"] = g["DY"] + 4
    g["W"] = g["DISX"] + 18
    return g


def lane_windows(g):
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


def assert_bindings(g, ops):
    out, inc = g["attach_out"], g["attach_in"]
    att = g["ATT"]
    for (x, y, ch, lane) in ops:
        table = out if ch in "sS" else inc
        got = min(table, key=lambda k: (abs(table[k] - x) + abs(att - y), table[k]))
        assert got == lane, "%s at %s binds %s, wanted %s" % (ch, (x, y), got, lane)


# ──────────────────────────────────────────────────────────────────────────
# rooms, rings, driver, display
# ──────────────────────────────────────────────────────────────────────────
def relay_block(L, x, y):
    """6-tick relay cycle: > R v / ^ s <  -- receive on any incoming, resend."""
    L.put(x, y, "@"); L.put(x + 1, y, ">"); L.put(x + 2, y, "R")
    L.put(x + 3, y, "v")
    L.put(x + 1, y + 1, "^"); L.put(x + 2, y + 1, "s"); L.put(x + 3, y + 1, "<")


def _ring(p, g, lane, L):
    """Relay room + the two pipes of one ring.  Returns the ring capacity.

    Both pipes attach to the relay's BOTTOM wall, four columns apart, and the
    turn row is the row just under the room -- so the capacity is set purely by
    how far above the controller the room sits.
    """
    ATT = g["ATT"]
    OX = g["attach_out"][lane]
    IX = g["attach_in"][lane]
    ry = g["relay_row"][lane]
    turn = ry + 4
    p.room(OX - 5, ry, 9, 4)
    relay_block(L, OX - 4, ry + 1)
    fwd = [(OX, ATT), (OX, turn), (OX - 3, turn)]
    bwd = [(IX, turn), (IX, ATT)]
    p.pipe(fwd, end_direction="N")
    p.pipe(bwd)
    return pipelen(fwd) + 1 + pipelen(bwd)


def build_shell(g):
    """Rooms + pipes + relay men + driver + display.  Returns (Layout, caps)."""
    L = Layout()
    p = L.p
    CW, CY0, CBOT, ATT = g["CW"], g["CY0"], g["CBOT"], g["ATT"]
    DX, DY, DISX, DISY = g["DX"], g["DY"], g["DISX"], g["DISY"]
    o, i = g["attach_out"], g["attach_in"]

    p.room(0, CY0, CW, CBOT - CY0 + 1)                  # controller
    caps = {lane: _ring(p, g, lane, L) for lane in ("P", "S", "T")}

    # ---- input: room sits between the I and D ports so neither pipe crosses --
    p.input_room(i["I"] - 1, 0)
    p.pipe([(i["I"], 3), (i["I"], ATT)])

    # ---- driver + display ------------------------------------------------
    p.room(DX, DY, 11, 24)
    p.display(DISX, DISY, 18, 18)
    p.pipe([(o["D"], ATT), (o["D"], 2), (DX + 1, 2), (DX + 1, DY - 1)],
           end_direction="S")
    p.pipe([(DX + 11, DY + 2), (DISX + 3, DY + 2), (DISX + 3, DISY - 1)],
           end_direction="S")                            # ADDR (display top)
    p.pipe([(DX + 11, DY + 12), (DISX - 1, DY + 12)], end_direction="E")   # DATA
    # SWAP must LEAVE the driver's bottom wall going SOUTH: a first segment
    # heading east would put its backward neighbour off the room, the pipe would
    # not count as the driver's, and every `s` in the swap arm silently binds
    # DATA instead (frames then never commit).
    p.pipe([(DX + 2, DY + 24), (DX + 2, DY + 25), (DISX + 4, DY + 25),
            (DISX + 4, DISY + 18)], end_direction="N")   # SWAP

    # ---- driver man ------------------------------------------------------
    #   v >= 0 -> DATA v      v == -1 -> SWAP 0      v <= -2 -> ADDR -v-2
    for (x, y, ch) in [
            (DX + 1, DY + 22, "@"), (DX + 3, DY + 22, "^"),
            (DX + 3, DY + 12, ">"),
            (DX + 4, DY + 12, "r"), (DX + 5, DY + 12, "M"),
            (DX + 6, DY + 12, "1"), (DX + 7, DY + 12, "+"),
            (DX + 8, DY + 12, "X"),
            (DX + 8, DY + 13, "W"), (DX + 8, DY + 14, "s"),
            (DX + 8, DY + 15, "<"), (DX + 3, DY + 15, "^"),
            (DX + 9, DY + 12, "v"), (DX + 9, DY + 19, "<"),
            (DX + 2, DY + 19, "s"), (DX + 1, DY + 19, "v"),
            (DX + 1, DY + 21, ">"), (DX + 3, DY + 21, "^"),
            (DX + 8, DY + 11, "N"), (DX + 8, DY + 10, "M"),
            (DX + 8, DY + 9, "1"), (DX + 8, DY + 8, "W"),
            (DX + 8, DY + 7, "-"), (DX + 8, DY + 3, "<"),
            (DX + 2, DY + 3, "s"), (DX + 1, DY + 3, "v")]:
        L.put(x, y, ch)
    return L, caps


# ──────────────────────────────────────────────────────────────────────────
# emitter (lane-constrained boustrophedon, after solutions/snake/build_micro.py)
# ──────────────────────────────────────────────────────────────────────────
class Emit:
    def __init__(self, L, g, win, forbidden, wrapcols=()):
        self.L, self.g, self.win = L, g, win
        self.forbidden = set(forbidden)
        self.wrapcols = set(wrapcols)
        self.xlo, self.xhi = g["IXLO"], g["IXHI"]
        self.x = self.y = 0
        self.d = "E"
        self.ops = []
        self.wraps = 0
        self.tickcols = set()          # columns already holding a backtick

    def at(self, x, y, d="E"):
        self.x, self.y, self.d = x, y, d
        return self

    def _step(self):
        self.x += 1 if self.d == "E" else (-1 if self.d == "W" else 0)

    def raw(self, ch):
        self.L.put(self.x, self.y, ch)
        self._step()

    def wrap(self):
        self.wraps += 1
        bad = self.forbidden - self.wrapcols
        if self.d == "E":
            x = min(self.x, self.xhi)
            while x <= self.xhi and (x in bad
                                     or self.L.get(x, self.y) != " "
                                     or self.L.get(x, self.y + 1) != " "):
                x += 1
            assert x <= self.xhi, "no room to wrap east at row %d" % self.y
        else:
            x = max(self.x, self.xlo)
            while x >= self.xlo and (x in bad
                                     or self.L.get(x, self.y) != " "
                                     or self.L.get(x, self.y + 1) != " "):
                x -= 1
            assert x >= self.xlo, "no room to wrap west at row %d" % self.y
        self.L.put(x, self.y, "v")
        nd = "W" if self.d == "E" else "E"
        self.L.put(x, self.y + 1, "<" if nd == "W" else ">")
        self.y += 1
        self.d = nd
        self.x = x + (-1 if nd == "W" else 1)
        return self

    def _ok(self, x):
        return self.xlo <= x <= self.xhi and x not in self.forbidden

    def _free(self, x):
        return self._ok(x) and self.L.get(x, self.y) == " "

    def _advance_to_free(self):
        while True:
            if self.d == "E" and self.x > self.xhi:
                self.wrap(); continue
            if self.d == "W" and self.x < self.xlo:
                self.wrap(); continue
            if self._free(self.x):
                return
            self._step()

    def _reach_run(self, n, tick=False):
        for _ in range(12):
            step = 1 if self.d == "E" else -1
            x = self.x
            while self.xlo <= x <= self.xhi:
                cols = [x + step * k for k in range(n)]
                if (all(self._free(c) for c in cols)
                        and (not tick or all(c not in self.tickcols
                                             for c in (cols[0], cols[-1])))):
                    while self.x != x:
                        self._step()
                    return
                x += step
            self.wrap()
        raise RuntimeError("no room for a %d-cell run" % n)

    def _reach(self, op, lane):
        lo, hi = self.win[(op, lane)]
        for _ in range(12):
            rng = (range(max(self.x, lo), hi + 1) if self.d == "E"
                   else range(min(self.x, hi), lo - 1, -1))
            xs = [x for x in rng if self._free(x)]
            if xs:
                while self.x != xs[0]:
                    self._step()
                return
            self.wrap()
        raise RuntimeError("lane %s unreachable" % lane)

    def tok(self, t):
        if t.startswith("#"):                       # backtick literal
            digits = t[1:]
            neg = digits.startswith("-")
            if neg:
                digits = digits[1:]
            # The man reads the digits IN HIS WALK ORDER, and raw() writes in
            # that same order, so the string is emitted unreversed either way --
            # westward it simply lands mirrored in the grid.
            body = "`" + digits + "`"
            self._reach_run(len(body) + (1 if neg else 0), tick=True)
            x0 = self.x
            for ch in body:
                self.raw(ch)
            self.tickcols.add(x0)
            self.tickcols.add(self.x - (1 if self.d == "E" else -1))
            if neg:
                self.raw("N")
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
        for t in toks.split() if isinstance(toks, str) else toks:
            self.tok(t)
        return self

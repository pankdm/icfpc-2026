#!/usr/bin/env python3
"""Plan B builder: fused/re-ordered op-stream (dsl2) folded to the gate grid.

Same physical machine as plotter_build2.py (gate + FIFO belt + driver/display),
but the op-stream comes from dsl2 (belt read-modify-write FUSION + access-locality
ring re-order + backtick `63` sign()). Semantically identical (verified frame-exact
by scratchpad/pick_verify.py), just far fewer belt rotations -> shorter op-stream
-> smaller box AND fewer walked cells -> fewer ticks.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import littleman as lm
import dsl2
from proto_driver import build_driver

# ---- chosen ring order (index0 = home). Set via env RING or default. ----
ORDERS = {
    "boxeq": ['sx','cx','x0','addr','sy32','y0','x1','err','y1','t2','t','e2','dy','dx','cy'],
    "body6": ['cy','dy','x0','cx','addr','sy32','y0','err','x1','y1','sx','t2','e2','t','dx'],
    "body3": ['x0','cx','addr','sy32','err','y0','x1','sx','y1','t2','e2','t','dx','cy','dy'],
}
RING = os.environ.get("RING", "body3")
dsl2.set_layout(ORDERS[RING])
dsl2.USE_BACKTICK_SIGN = True

# ---------------- gate column geometry (south-wall column discipline) ----------
ROUND_RAIL = 1
BODY_RAIL = 2
CINP = 3
INP_R = 5
BL, BR = 8, int(os.environ.get("BR", "33"))
BIN = BL
BOUT = BR
CMD_S = BR + 2
CCMD = BR + 3
GL = 1
GR = CCMD + 0


def put(p, x, y, ch):
    assert p.get(x, y) == " ", f"overlap at {(x,y)}: {p.get(x,y)!r} vs {ch!r}"
    p.put(x, y, ch)


def hput(p, x, y, ch):
    cur = p.get(x, y)
    assert cur in (" ", ch), f"overlap at {(x,y)}: {cur!r} vs {ch!r}"
    p.put(x, y, ch)


# ---------------- token translation (dsl2 op list -> turtle tokens) -----------
# Literals: bare digits 0-9 (1 cell); #15 -> 3M5* ; setB(32)*-> M5W{ (shift) ;
# #63 (sign) -> real backtick `63` (4 cells) -- kills the M9W}x7 despine.
def translate(ops):
    out = []
    i = 0
    n = len(ops)
    while i < n:
        o = ops[i]
        if (i + 3 < n and o == 'M' and ops[i+1] == ('#', 32)
                and ops[i+2] == 'W' and ops[i+3] == '*'):
            out += [("op", "M"), ("op", "5"), ("op", "W"), ("op", "{")]
            i += 4
        elif o == ('#', 15):
            out += [("op", "3"), ("op", "M"), ("op", "5"), ("op", "*")]
            i += 1
        elif (i + 3 < n and o == 'M' and ops[i+1] == ('#', 63)
                and ops[i+2] == 'W' and ops[i+3] == '}'):
            if os.environ.get("NOBACKTICK"):
                out += [("op", "M"), ("op", "9"), ("op", "W"), ("op", "}")] * 7
            else:
                out += [("op", "M"), ("lit", 63), ("op", "W"), ("op", "}")]
            i += 4
        elif o == ('#', 63):
            out.append(("lit", 63))
            i += 1
        elif isinstance(o, tuple):
            assert 0 <= o[1] <= 9, f"unexpected literal {o}"
            out.append(("op", str(o[1])))
            i += 1
        elif o == 'ri':
            out.append(("ri",))
            i += 1
        elif o == 'PA':
            out += [("op", "M"), ("op", "1"), ("op", "+"), ("cmd",)]
            i += 1
        elif o == 'PD':
            out.append(("cmd",))
            i += 1
        else:
            out.append(("op", o))
            i += 1
    return out


class Turtle:
    def __init__(self, p, y):
        self.p = p
        self.x = BL
        self.y = y
        self._start_row(y)

    def _start_row(self, y):
        self.y = y
        self.x = BL
        hput(self.p, BL - 1, y, ">")

    def _newline(self):
        p = self.p; cx = self.x; y = self.y
        put(p, cx, y, "v")
        put(p, cx, y + 1, "<")
        put(p, BL - 1, y + 1, "v")
        self._start_row(y + 2)

    def _wrap_if(self, w):
        if self.x + w - 1 > BR:
            self._newline()

    def op(self, ch):
        self._wrap_if(1)
        put(self.p, self.x, self.y, ch)
        self.x += 1

    def lit(self, k):
        s = "`" + str(k) + "`"
        self._wrap_if(len(s))
        for ch in s:
            put(self.p, self.x, self.y, ch)
            self.x += 1

    def cmd_send(self):
        p = self.p; cx = self.x; y = self.y
        put(p, cx, y, "v")
        put(p, cx, y + 1, ">")
        put(p, CMD_S, y + 1, "s")
        put(p, CMD_S + 1, y + 1, "v")
        put(p, CMD_S + 1, y + 2, "<")
        put(p, BL - 1, y + 2, "v")
        self._start_row(y + 3)

    def input_read(self):
        p = self.p; cx = self.x; y = self.y
        put(p, cx, y, "v")
        put(p, cx, y + 1, "<")
        put(p, INP_R, y + 1, "r")
        put(p, INP_R - 1, y + 1, "v")
        put(p, INP_R - 1, y + 2, ">")
        self._start_row(y + 2)

    def emit(self, tokens):
        for t in tokens:
            k = t[0]
            if k == "op":
                self.op(t[1])
            elif k == "lit":
                self.lit(t[1])
            elif k == "cmd":
                self.cmd_send()
            elif k == "ri":
                self.input_read()

    def force_newline(self):
        self._newline()
        return self.y


JC = BL - 1          # junction column (E-row entry '>')
RT = BR + 1          # right turn lane


class BTurtle:
    """Boustrophedon typewriter: ops fill BOTH east and west rows (no wasted
    return-glide rows) -> ~halves gate height AND kills the return-glide ticks.
    op() places tokens in stream order regardless of travel direction, so the man
    reads each op/literal correctly on east and west rows alike. Backtick `63`
    literals are kept column-isolated via '.'-padding (lit()) to avoid vertical
    backtick-pairing load errors. Block boundaries and excursions flush to a fresh
    east-row start so rails/excursions stay east-oriented."""
    def __init__(self, p, y):
        self.p = p
        self.y = y
        self.x = BL
        self.dir = 'E'
        self.bt_cols = set()               # columns already holding a backtick
        put(p, JC, y, ">")

    def op(self, ch):
        if self.dir == 'E':
            if self.x > BR:
                self._wrap()
        else:
            if self.x < BL:
                self._wrap()
        put(self.p, self.x, self.y, ch)
        self.x += 1 if self.dir == 'E' else -1

    def lit(self, k):
        # op() places tokens in stream order regardless of E/W direction, so the
        # man reads the literal correctly either way -- no digit reversal needed.
        s = "`" + str(k) + "`"
        w = len(s)
        while True:
            # never let a literal wrap across a row boundary (splits backtick pair)
            if self.dir == 'E' and self.x + w - 1 > BR:
                self._wrap()
            elif self.dir == 'W' and self.x - (w - 1) < BL:
                self._wrap()
            # backtick columns for this placement
            if self.dir == 'E':
                c1, c2 = self.x, self.x + w - 1
            else:
                c1, c2 = self.x, self.x - (w - 1)
            # guarantee NO two backticks ever share a column (kills vertical pairing
            # load errors) by padding with '.' nops until both columns are free.
            if c1 not in self.bt_cols and c2 not in self.bt_cols:
                break
            self.op(".")
        self.bt_cols.add(c1); self.bt_cols.add(c2)
        for ch in s:
            self.op(ch)

    def _wrap(self):
        p = self.p; y = self.y
        if self.dir == 'E':                # x == BR+1 == RT
            put(p, RT, y, "v")
            put(p, RT, y + 1, "<")
            self.y = y + 1; self.dir = 'W'; self.x = BR
        else:                              # x == BL-1 == JC
            put(p, JC, y, "v")
            put(p, JC, y + 1, ">")
            self.y = y + 1; self.dir = 'E'; self.x = BL

    def _flush_estart(self):
        p = self.p; x = self.x; y = self.y
        if self.dir == 'E':
            # man heading east at x (next free cell). Turn down here.
            put(p, x, y, "v")
            put(p, x, y + 1, "<")
            if x != JC:
                put(p, JC, y + 1, "v")
            put(p, JC, y + 2, ">")
            self.y = y + 2
        else:
            # heading west at x (next free cell, x in [JC..BR-1])
            put(p, x, y, "v")
            put(p, x, y + 1, ">") if x == JC else None
            if x != JC:
                # glide west to JC on y+1
                put(p, x, y + 1, "<")
                put(p, JC, y + 1, "v")
                put(p, JC, y + 2, ">")
                self.y = y + 2
            else:
                put(p, JC, y + 2, ">")   # x==JC: v at (JC,y), then need (JC,y+1) pass
                put(p, JC, y + 1, "v")
                self.y = y + 2
        self.x = BL; self.dir = 'E'
        return self.y

    def cmd_send(self):
        self._flush_estart()
        p = self.p; y = self.y
        # at fresh E row (JC='>'); go east a step then down to cmd lane
        put(p, BL, y, "v")
        put(p, BL, y + 1, ">")
        put(p, CMD_S, y + 1, "s")
        put(p, CMD_S + 1, y + 1, "v")
        put(p, CMD_S + 1, y + 2, "<")
        put(p, JC, y + 2, "v")
        put(p, JC, y + 3, ">")
        self.y = y + 3; self.x = BL; self.dir = 'E'

    def input_read(self):
        self._flush_estart()
        p = self.p; y = self.y
        put(p, BL, y, "v")
        put(p, BL, y + 1, "<")
        put(p, INP_R, y + 1, "r")
        put(p, INP_R - 1, y + 1, "v")
        put(p, INP_R - 1, y + 2, ">")
        put(p, JC, y + 2, ">") if INP_R - 1 < JC else None
        self.y = y + 2; self.x = BL; self.dir = 'E'

    def emit(self, tokens):
        for t in tokens:
            k = t[0]
            if k == "op":
                self.op(t[1])
            elif k == "lit":
                self.lit(t[1])
            elif k == "cmd":
                self.cmd_send()
            elif k == "ri":
                self.input_read()

    def force_newline(self):
        return self._flush_estart()


def build():
    p = lm.Program()
    T = 4

    put(p, BL - 2, T, "@")
    t = Turtle(p, T) if os.environ.get("MODE") == "alleast" else BTurtle(p, T)

    t.emit(translate(dsl2.build_init()))
    setup_y = t.force_newline()
    t.emit(translate(dsl2.build_setup()))
    body_y = t.force_newline()
    t.emit(translate(dsl2.build_body()))
    tail_y = t.force_newline()

    # ---- control tail: m ; d ; rails ; PS ----
    put(p, BL, tail_y, "v")
    put(p, BL, tail_y + 1, "m")
    put(p, BL, tail_y + 2, "d")
    put(p, BODY_RAIL, tail_y + 2, "^")
    put(p, BODY_RAIL, body_y, ">")
    put(p, BL, tail_y + 3, "1")
    put(p, BL, tail_y + 4, "N")
    put(p, BL, tail_y + 5, ">")
    put(p, CMD_S, tail_y + 5, "s")
    put(p, CMD_S + 1, tail_y + 5, "v")
    put(p, CMD_S + 1, tail_y + 6, "<")
    put(p, ROUND_RAIL, tail_y + 6, "^")
    put(p, ROUND_RAIL, setup_y, ">")

    GB = tail_y + 7
    p.room(GL - 1, T - 1, (GR - GL + 1) + 2, (GB - T + 1) + 2)

    south = GB + 1
    if os.environ.get("BELT") == "selfloop":
        # single self-loop U-pipe (no relay man): gate sends at BOUT, reads at BIN;
        # values flow through the pipe at 1 cell/tick (no relay throughput cap).
        D = int(os.environ.get("BELTD", "3"))
        p.pipe([(BOUT, south + 1), (BOUT, south + D), (BIN, south + D), (BIN, south + 1)])
        GBOT = south + D
    elif os.environ.get("RELAY", "tight") == "tight":
        # 6-cell relay loop (vs 8): >rv / ^s<  -> 1 value / 6 ticks (was /8).
        rly_y = GB + int(os.environ.get("RLYGAP", "8"))
        RLY = p.room(BIN - 2, rly_y, BOUT - BIN + 1, 4)
        ix, iy = RLY.ix0, RLY.iy0
        rc = ix + 2                                  # r column
        sc = ix + 1                                  # belt-in (send) column
        put(p, ix, iy, "@")
        put(p, ix + 1, iy, ">")
        put(p, ix + 2, iy, "r")
        put(p, ix + 3, iy, "v")
        put(p, ix + 1, iy + 1, "^")
        put(p, ix + 2, iy + 1, "s")
        put(p, ix + 3, iy + 1, "<")
        if os.environ.get("TWORELAY"):
            put(p, ix, iy + 1, "@")        # 2nd man trails 1 cell -> 2x belt throughput
        tHi = south + 2
        tLo = rly_y - 2
        # belt-out: gate BOUT -> serpentine down -> relay TOP wall above r (col rc)
        p.pipe([(BOUT, south + 1), (BOUT, tLo), (rc + 1, tLo), (rc + 1, tHi),
                (rc, tHi), (rc, rly_y - 1)])
        # belt-in: relay TOP wall above sc -> up -> gate BIN
        p.pipe([(sc, rly_y - 1), (sc, tHi), (BIN, tHi), (BIN, south + 1)])
    else:
        rly_y = GB + int(os.environ.get("RLYGAP", "8"))
        RLY = p.room(BIN - 2, rly_y, BOUT - BIN + 1, 4)
        rlx, rly = RLY.ix0, RLY.iy0
        put(p, rlx, rly, "@")
        put(p, rlx + 1, rly, ">")
        put(p, rlx + 2, rly, "r")
        put(p, rlx + 3, rly, "s")
        put(p, rlx + 4, rly, "v")
        put(p, rlx + 4, rly + 1, "<")
        put(p, rlx + 1, rly + 1, "^")
        s_col = rlx + 3
        tHi = south + 2
        tLo = rly_y - 2
        p.pipe([(BOUT, south + 1), (BOUT, tLo), (BOUT - 1, tLo), (BOUT - 1, tHi),
                (BOUT - 2, tHi), (BOUT - 2, tLo), (BOUT - 3, tLo), (BOUT - 3, rly_y - 1)])
        p.pipe([(s_col, rly_y - 1), (s_col, tHi), (s_col - 1, tHi), (s_col - 1, tLo),
                (BIN, tLo), (BIN, south + 1)])

    dvx, dvy = GR + 5, T + 2
    info = build_driver(p, dvx, dvy, None)
    DR = info["DR"]; rENTRY = info["rENTRY"]
    lane = GR + 3
    p.pipe([(CCMD, south + 1), (CCMD, GB + 3), (lane, GB + 3),
            (lane, rENTRY), (DR.x0 - 1, rENTRY)])

    IR = p.input_room(CINP - 1, GB + 6)
    p.pipe([(CINP, IR.y0 - 1), (CINP, south + 1)])
    return p


if __name__ == "__main__":
    import json
    p = build()
    path = os.path.join(os.path.dirname(__file__), "plotter-planB.man")
    p.save(path)
    print("saved", path, "RING=", RING, "footprint", p.footprint())
    print(json.dumps(p.grade("plotter")))

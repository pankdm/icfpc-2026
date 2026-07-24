#!/usr/bin/env python3
"""op-stream -> grid compiler for the plotter (Bresenham) solution.

Two-man design:
  GATE room : the man walks the full verified op-stream (INIT once; per round
              SETUP' with BP=n+1, then BODY looped via a BP counter (m;d), then a
              cmd sentinel).  Persistent state circulates on a FIFO belt
              (gate <-> relay).  The gate emits a single command stream to ...
  DRIVER room: decodes [addr+1,15,...,-1] into ADDR/DATA/SWAP for the display
              (reuses the hardpixel-proven display wiring).

Pipe selection in the gate is pure COLUMN discipline (all pipes on the SOUTH wall,
so vertical distance cancels):  belt-out west-of-centre, belt-in east-of-centre,
cmd far-west, input far-east.  The typewriter op-rows live in a central band where
belt-out/belt-in always win;  cmd sends & input reads are short excursions out to
the far columns where those pipes win instead.  Two west rails carry the BODY loop
back-edge and the per-round back-edge."""
import sys, os
from collections import deque
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import littleman as lm
import dsl
from verify_gate import SETUP1
from proto_driver import build_driver

# ---------------- gate column geometry (south-wall column discipline) ----------
# Driver sits EAST (cmd far-east); input room WEST (input far-west).
BL, BR = 22, 62            # op-band columns
BOUT = 56                  # belt-out attach (outgoing, east-centre)
BIN = 28                   # belt-in  attach (incoming, west-centre)
CCMD = 72                  # cmd attach (outgoing, far EAST)
CINP = 12                  # input attach (incoming, far WEST)
CMD_S = 68                 # column where a cmd send happens (cmd nearest) -- EAST excursion
INP_R = 16                 # column where an input read happens (input nearest) -- WEST excursion
BODY_RAIL = 8              # west rail column for the BODY back-edge
ROUND_RAIL = 5             # west rail column for the per-round back-edge
GL = 3                     # gate interior left col
GR = 74                    # gate interior right col


def put(p, x, y, ch):
    assert p.get(x, y) == " ", f"overlap at {(x,y)}: {p.get(x,y)!r} vs {ch!r}"
    p.put(x, y, ch)


def hput(p, x, y, ch):     # allow re-placing identical glide arrows silently
    cur = p.get(x, y)
    assert cur in (" ", ch), f"overlap at {(x,y)}: {cur!r} vs {ch!r}"
    p.put(x, y, ch)


# ---------------- de-spine: remove ALL multi-digit literals (no backticks) -------
# The loader pairs backticks vertically per column too, so far-apart literals in a
# shared column enclose non-digits -> load error. We avoid backticks entirely:
#   setB(32);*  (= M,#32,W,*)  ->  M,5,W,{     (B=5 ; A<<5 = A*32)
#   sign()      (= M,#63,W,})  ->  (M,9,W,})*7 (A >>a 63 via seven >>9)
#   #15         ->  3,M,5,*                     (A = 15)
#   #d (0..9)   ->  bare digit op
def despine(ops):
    out = []
    i = 0
    n = len(ops)
    while i < n:
        o = ops[i]
        if (i + 3 < n and o == "M" and ops[i+1] == ("#", 63)
                and ops[i+2] == "W" and ops[i+3] == "}"):
            out += ["M", "9", "W", "}"] * 7
            i += 4
        elif (i + 3 < n and o == "M" and ops[i+1] == ("#", 32)
                and ops[i+2] == "W" and ops[i+3] == "*"):
            out += ["M", "5", "W", "{"]
            i += 4
        elif o == ("#", 15):
            out += ["3", "M", "5", "*"]
            i += 1
        elif isinstance(o, tuple):
            assert 0 <= o[1] <= 9, f"undespined literal {o}"
            out.append(str(o[1]))
            i += 1
        else:
            out.append(o)
            i += 1
    return out


# ---------------- token translation (post-despine op list -> turtle tokens) -----
def translate(ops):
    out = []
    for o in despine(ops):
        if o == "ri":
            out.append(("ri",))
        elif o == "PA":
            out += [("op", "M"), ("op", "1"), ("op", "+"), ("cmd",)]
        elif o == "PD":
            out.append(("cmd",))
        else:
            out.append(("op", o))
    return out


class Turtle:
    """Lays tokens as an all-east typewriter in the band, wrapping via a west
    return glide; cmd/input are short excursions.  y only ever increases."""
    def __init__(self, p, y):
        self.p = p
        self.x = BL
        self.y = y
        self._start_row(y)

    def _start_row(self, y):
        self.y = y
        self.x = BL
        hput(self.p, BL - 1, y, ">")          # junction: rails & falls enter here

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

    def cmd_send(self):                       # EAST excursion (cmd is far east)
        p = self.p; cx = self.x; y = self.y
        put(p, cx, y, "v")
        put(p, cx, y + 1, ">")
        put(p, CMD_S, y + 1, "s")
        put(p, CMD_S + 1, y + 1, "v")
        put(p, CMD_S + 1, y + 2, "<")
        put(p, BL - 1, y + 2, "v")
        self._start_row(y + 3)

    def input_read(self):                     # WEST excursion (input is far west)
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
        """Break to a fresh op row at BL; return its y (a rail target)."""
        self._newline()
        return self.y


def build():
    p = lm.Program()
    T = 4                                     # gate first op row

    # spawn -> junction -> INIT
    put(p, BL - 2, T, "@")
    t = Turtle(p, T)

    # ---- INIT (fill belt with 15 zeros) ----
    t.emit(translate(dsl.INIT))
    setup_y = t.force_newline()
    # ---- SETUP' ----
    t.emit(translate(SETUP1))
    body_y = t.force_newline()
    # ---- BODY ----
    t.emit(translate(dsl.BODY))
    tail_y = t.force_newline()

    # ---- control tail: m ; d ; rails ; PS ----
    put(p, BL, tail_y, "v")
    put(p, BL, tail_y + 1, "m")               # BP--
    put(p, BL, tail_y + 2, "d")               # south: BP>0 -> CW=west (loop) ; ==0 -> south (exit)
    # BP>0 : west to BODY_RAIL, up to body_y, east into body junction
    put(p, BODY_RAIL, tail_y + 2, "^")
    put(p, BODY_RAIL, body_y, ">")
    # BP==0 : south, PS (A=-1) cmd send (EAST), then ROUND_RAIL up to setup_y
    put(p, BL, tail_y + 3, "1")
    put(p, BL, tail_y + 4, "N")               # A=-1
    put(p, BL, tail_y + 5, ">")               # east
    put(p, CMD_S, tail_y + 5, "s")            # cmd send -1 (SWAP)
    put(p, CMD_S + 1, tail_y + 5, "v")
    put(p, CMD_S + 1, tail_y + 6, "<")        # west
    put(p, ROUND_RAIL, tail_y + 6, "^")       # up round rail
    put(p, ROUND_RAIL, setup_y, ">")

    GB = tail_y + 10                          # gate interior bottom
    p.room(GL - 1, T - 1, (GR - GL + 1) + 2, (GB - T + 1) + 2)

    # ================= belt (relay) + driver + display + input, all BELOW =========
    south = GB + 1                            # gate south wall row
    # ---- relay room (below the gate; both belt pipes attach its TOP wall) ----
    rly_y = GB + 12                           # belt loop capacity >= 15
    RLY = p.room(26, rly_y, 33, 7)            # interior cols 27..57 spans BIN(28)&BOUT(56)
    rlx, rly = RLY.ix0, RLY.iy0
    put(p, rlx, rly, "@")                     # spawn -> east
    put(p, rlx + 1, rly, ">")                 # junction: north arrivals turn east
    put(p, rlx + 2, rly, "r")                 # read belt-out (only incoming)
    put(p, rlx + 3, rly, "s")                 # send belt-in (only outgoing)
    put(p, rlx + 4, rly, "v")
    put(p, rlx + 4, rly + 1, "<")
    put(p, rlx + 1, rly + 1, "^")             # back up into the junction
    p.pipe([(BOUT, south + 1), (BOUT, RLY.y0 - 1)])   # belt-out down into relay top
    p.pipe([(BIN, RLY.y0 - 1), (BIN, south + 1)])     # belt-in up into gate south

    # ---- driver + display (EAST of gate; cmd enters driver WEST wall) ----
    dvx, dvy = GR + 12, GB + 3
    info = build_driver(p, dvx, dvy, None)
    DR = info["DR"]; rENTRY = info["rENTRY"]
    # cmd: gate south col CCMD -> down -> east -> driver west wall at rENTRY
    p.pipe([(CCMD, south + 1), (CCMD, GB + 3), (DR.x0 - 3, GB + 3),
            (DR.x0 - 3, rENTRY), (DR.x0 - 1, rENTRY)])

    # ---- input room (WEST, below the gate) ----
    IR = p.input_room(CINP - 1, GB + 6)
    p.pipe([(CINP, IR.y0 - 1), (CINP, south + 1)])
    return p


if __name__ == "__main__":
    import json
    p = build()
    path = os.path.join(os.path.dirname(__file__), "plotter-v1.man")
    p.save(path)
    print("saved", path, "footprint", p.footprint())
    print(json.dumps(p.grade("plotter")))

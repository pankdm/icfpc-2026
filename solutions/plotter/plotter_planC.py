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
import planC_ops as pc
from proto_driver import build_driver

# SETUP' : insert inc (M,1,+) before the single 'b' so BP = n+1 (plots n+1 points)
def _setup_prime():
    ops = list(pc.SETUP)
    i = ops.index('b')
    return ops[:i] + ['M', ('#', 1), '+'] + ops[i:]
SETUP1 = _setup_prime()
INIT = pc.INIT
BODY = pc.BODY
NBELT = len(pc.LAYOUT9)   # 9 belt values

# ---------------- gate column geometry (south-wall column discipline) ----------
# COMPRESSED layout: put the two BELT attaches at the band ENDS (BIN=west end,
# BOUT=east end) and the two far pipes (input, cmd) just OUTSIDE the band.  Then
# every band column is nearer its belt pipe than the far pipe, so the whole gate
# width collapses to (band + tiny margins) instead of ~2x the band.  Discipline:
#   read  r : belt-in(BIN)  vs input(CINP)  -> BIN at band-west, CINP just west
#   send  s : belt-out(BOUT) vs cmd(CCMD)   -> BOUT at band-east, CCMD just east
ROUND_RAIL = 1             # west rail column for the per-round back-edge
BODY_RAIL = 2              # west rail column for the BODY back-edge
CINP = 3                   # input attach (incoming) -- just west of the band
INP_R = 5                  # input read excursion col (picks input over belt-in)
BAND_RIGHT = 48            # tunable: op-band right column (narrower band -> taller/thinner gate)

def set_geometry(band_right):
    """Recompute all gate column globals from the band-right column."""
    global BAND_RIGHT, BL, BR, BIN, BOUT, CMD_S, CCMD, GL, GR
    BAND_RIGHT = band_right
    BL, BR = 8, band_right
    BIN = BL
    BOUT = BR
    CMD_S = BR + 2
    CCMD = BR + 3
    GL = 1
    GR = CCMD + 1

BL = BR = BIN = BOUT = CMD_S = CCMD = GL = GR = None
set_geometry(BAND_RIGHT)


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
    """Lays tokens as a TRUE BOUSTROPHEDON in the band (east row, then a west row
    packed with ops too — no blank return glide), so gate height ~= ops/bandwidth
    instead of 2x that, and the man never walks a blank return row (ticks win).
    All ops are single characters (literals despined to digits) so west rows
    execute correctly regardless of direction.  cmd/input are short excursions
    that reset to a fresh east row.  y only ever increases."""
    def __init__(self, p, y):
        self.p = p
        self._start_row(y)

    def _start_row(self, y):                  # fresh EAST row at BL
        self.y = y
        self.x = BL
        self.dir = 1
        hput(self.p, BL - 1, y, ">")          # junction: rails & falls enter here

    def _wrap(self):
        p = self.p
        if self.dir == 1:                     # east row -> drop to a west row
            put(p, BR, self.y, "v")           # turn south at band-east edge
            put(p, BR, self.y + 1, "<")       # head west
            self.y += 1; self.x = BR - 1; self.dir = -1
        else:                                 # west row -> drop to an east row
            put(p, BL - 1, self.y, "v")       # turn south at junction col
            put(p, BL - 1, self.y + 1, ">")   # head east (junction)
            self.y += 1; self.x = BL; self.dir = 1

    def op(self, ch):
        if self.dir == 1 and self.x > BR - 1:
            self._wrap()
        elif self.dir == -1 and self.x < BL:
            self._wrap()
        put(self.p, self.x, self.y, ch)
        self.x += self.dir

    def lit(self, k):                         # unused (despined to digits)
        for ch in ("`" + str(k) + "`"):
            self.op(ch)

    def cmd_send(self):                       # EAST excursion (cmd is far east)
        # Send at CMD_S, then RESUME the boustrophedon as a WEST row from the band
        # east edge (BR-1) instead of gliding ~band-width blank cells back to BL.
        # cmd_send fires twice per pixel (PA,PD) so this glide was a top tick cost.
        p = self.p; cx = self.x; y = self.y
        put(p, cx, y, "v")
        put(p, cx, y + 1, ">")
        put(p, CMD_S, y + 1, "s")
        put(p, CMD_S + 1, y + 1, "v")
        put(p, CMD_S + 1, y + 2, "<")        # head west; glide the few cells into band
        self.y = y + 2; self.x = BR - 1; self.dir = -1

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
        """Break to a fresh EAST op row at BL (rail target); works from any dir.
        self.x (the man's next cell) is in [BL-1, BR]."""
        p = self.p; sx = self.x; y = self.y
        put(p, sx, y, "v")                     # man steps here, turns south
        if sx > BL - 1:
            put(p, sx, y + 1, "<")             # head west to junction col
            put(p, BL - 1, y + 1, "v")
        else:                                  # sx == BL-1: straight down
            put(p, BL - 1, y + 1, "v")
        self._start_row(y + 2)
        return self.y


def build():
    p = lm.Program()
    T = 4                                     # gate first op row

    # spawn -> junction -> INIT
    put(p, BL - 2, T, "@")
    t = Turtle(p, T)

    # ---- INIT (fill belt with 15 zeros) ----
    t.emit(translate(INIT))
    setup_y = t.force_newline()
    # ---- SETUP' ----
    t.emit(translate(SETUP1))
    body_y = t.force_newline()
    # ---- BODY ----
    t.emit(translate(BODY))
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

    GB = tail_y + 7                           # gate interior bottom (last tail row is +6)
    p.room(GL - 1, T - 1, (GR - GL + 1) + 2, (GB - T + 1) + 2)

    # ================= belt (relay) + driver + display + input, all BELOW =========
    south = GB + 1                            # gate south wall row
    # ---- relay room (below the gate; both belt pipes attach its TOP wall) ----
    # SERPENTINE belt (matmul fold pattern): the belt needs ~26 cells of loop
    # capacity to minimise avgTicks (sweep), but a STRAIGHT belt spends ~14 vertical
    # rows to hold it -> relay hangs low, box height-bound.  Fold each belt pipe
    # into a serpentine that packs the same cell-count in ~6 rows, so the relay
    # rides up right under the gate and the box drops to the width-bound floor with
    # NO tick penalty (capacity = cell-count, preserved).  Turns kept >=2 rows off
    # both the gate south wall and the relay top wall (a turn adjacent to a wall
    # spuriously attaches and silently breaks the FIFO).
    rly_y = GB + 8                            # relay top row (was GB+14 straight)
    RLY = p.room(BIN - 2, rly_y, BOUT - BIN + 1, 4)  # top wall spans BIN-1..BOUT-1
    rlx, rly = RLY.ix0, RLY.iy0               # rlx = BIN-1 ; junction '>' at BIN
    RB = RLY.ix1                              # relay interior right col
    put(p, rlx, rly, "@")                     # spawn -> east
    put(p, rlx + 1, rly, ">")                 # junction: north arrivals turn east
    # BATCHED relay: a long row of `r s r s ...` relays ONE value per r;s pair
    # (2 ticks) instead of one value per whole loop (~8 ticks) -> ~4x throughput,
    # which is the belt bottleneck (gate is sole feeder+drainer; xray: 52% stall).
    # Each r reads the only incoming pipe (belt-out), each s sends the only outgoing
    # (belt-in); FIFO order preserved (read v_i then immediately send v_i).
    s_col = rlx + 3                           # first relay 's' column -> belt-in attaches here
    # BOTH interior rows relay (east row r s r s...; west row r s r s... too), so the
    # return glide is eliminated -> throughput ~1 value / 2 ticks.
    cx = rlx + 2
    while cx + 1 <= RB - 1:                    # east row: leave RB for the turn-down col
        put(p, cx, rly, "r")
        put(p, cx + 1, rly, "s")
        cx += 2
    put(p, RB, rly, "v")                      # turn down at east edge
    put(p, RB, rly + 1, "<")                  # head west on the return row
    cx = RB - 1
    while cx - 1 >= rlx + 2:                   # west row: also relaying
        put(p, cx, rly + 1, "r")
        put(p, cx - 1, rly + 1, "s")
        cx -= 2
    put(p, rlx + 1, rly + 1, "^")             # back up into the junction
    tHi = south + 2                           # top turn row (2 below gate wall)
    tLo = rly_y - 2                           # bottom turn row (2 above relay top)
    # belt-out: gate wall (BOUT) -> serpentine down over cols BOUT..BOUT-3 -> relay
    p.pipe([(BOUT, south + 1), (BOUT, tLo), (BOUT - 1, tLo), (BOUT - 1, tHi),
            (BOUT - 2, tHi), (BOUT - 2, tLo), (BOUT - 3, tLo), (BOUT - 3, rly_y - 1)])
    # belt-in: relay ('s' col) -> serpentine up over cols s_col..BIN -> gate wall (BIN)
    p.pipe([(s_col, rly_y - 1), (s_col, tHi), (s_col - 1, tHi), (s_col - 1, tLo),
            (BIN, tLo), (BIN, south + 1)])

    # ---- driver + display (BESIDE the gate, in the empty right-side space; the
    #      gate is narrow-tall so cols >GR / rows <GB are free). This tucks the
    #      whole driver+display+swap block into the gate's vertical envelope
    #      instead of hanging it BELOW -> removes ~55 rows of height. ----
    dvx, dvy = GR + 5, T + 2                   # top-aligned beside gate
    info = build_driver(p, dvx, dvy, None)
    DR = info["DR"]; rENTRY = info["rENTRY"]
    # cmd: gate south col CCMD -> straight down BELOW the gate -> east along a row
    #      clear of the bottom wall -> up a free lane (col GR+3, buffered off both
    #      the gate wall and the driver wall so no spurious attach) -> east into
    #      the driver WEST wall at rENTRY.  Carries only the transient command
    #      stream (persistent state stays on the short belt).
    lane = GR + 3                             # free lane: gate wall(GR+1) | gap | lane | gap gap | driver
    p.pipe([(CCMD, south + 1), (CCMD, GB + 3), (lane, GB + 3),
            (lane, rENTRY), (DR.x0 - 1, rENTRY)])

    # ---- input room (WEST, below the gate) ----
    IR = p.input_room(CINP - 1, GB + 6)
    p.pipe([(CINP, IR.y0 - 1), (CINP, south + 1)])
    return p


if __name__ == "__main__":
    import json
    p = build()
    path = os.path.join(os.path.dirname(__file__), "plotter-planC.man")
    p.save(path)
    print("saved", path, "footprint", p.footprint())
    print(json.dumps(p.grade("plotter")))

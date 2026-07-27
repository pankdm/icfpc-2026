#!/usr/bin/env python3
"""Carousel matmul — the FULL composed P=1 machine.

One CTRL man: seed -> [TOP prologue -> a-fetch -> 16-cell MAC lap xK]*,
ROWMARK=150 in the b-ring drives row emits.  No offset arithmetic (emit is
BP-counted), no H (the man parks on the drained A-ring; single-round proven
sufficient: the live champion halts after one round and passes all privates).

Key structure:
  * multi-feed rings (relay R takes any ready): bf(hot,top) + bf2(seed/marker,
    BOTTOM, perimeter-routed); cf(hot) + cf2(seed) on the bottom wall.
  * A-ring doubles as the M,K stash (S0 pushes M,K ahead of the a-values;
    b-init pops them back first).
  * holder swap is order-free: r(Ar), s(Hf), r(Hr) pops the OLD a.
  * b-ring serp is on the RETURN side: the ROWMARK (pushed via the long bf2)
    still lands at the relay before any next-cycle re-push arrives, because
    re-pushes only resume after a full serp latency.
  * seed and runtime-marker share the `150` literal row, the c-zero loop and
    the W N X exit test (seed B=0 straight to riser; marker B=150 -> CCW south
    into the emit loop).  d at (20,9) splits them earlier (BP=0 vs BP=K).
  * riser col 1 funnels every westbound exit back to TOP at (1,4).

TOP: r(br) A=v; M B=v; r(Kr); s(Kf); b BP=K; `100`; '-' A=100-v; X:
     real v<=99 -> A>0 CW south (row 5); marker 150 -> A=-50 CCW north.
Lap rows 7-9 (16 cells): '>' sb M ra sa * v / rb / d m sc + rc M '<'.
"""
import os
import sys

REPO = os.path.abspath(__file__).split("/solutions/")[0]
sys.path.insert(0, REPO + "/tools")
import littleman as lm  # noqa: E402

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

W, BW = 34, 16          # CTRL room (0,0)-(33,16); interior x 1..32, y 1..15
BOT = BW + 1            # bottom-wall attach row (17)

# top-wall pipe columns
BR, BF, HR, HF, AR, KR, KF = 2, 3, 5, 6, 9, 10, 12
IN, AF = 23, 26
# bottom-wall pipe columns
CF, CR, OUTC, CF2, BF2 = 4, 6, 8, 14, 19


class B:
    def __init__(self):
        self.p = lm.Program()
        self.placed = {}
        self.intent = {}

    def C(self, x, y, ch, bind=None):
        if (x, y) in self.placed and self.placed[(x, y)] != ch:
            raise SystemExit(
                f"CELL COLLISION ({x},{y}): {self.placed[(x,y)]!r} vs {ch!r}")
        self.placed[(x, y)] = ch
        self.p.put(x, y, ch)
        if bind is not None:
            self.intent[(x, y)] = bind

    def run(self, x, y, s):
        for i, ch in enumerate(s):
            self.C(x + i, y, ch)

    def pipeC(self, points, end_direction=None):
        cells = []
        for i in range(len(points) - 1):
            (x0, y0), (x1, y1) = points[i], points[i + 1]
            dx = (x1 > x0) - (x1 < x0)
            dy = (y1 > y0) - (y1 < y0)
            assert dx == 0 or dy == 0, \
                f"diagonal pipe segment {points[i]}->{points[i+1]}"
            for k in range(abs(x1 - x0) + abs(y1 - y0)):
                cells.append((x0 + dx * k, y0 + dy * k, dx, dy))
        lx, ly = points[-1]
        cells.append((lx, ly, cells[-1][2], cells[-1][3]))
        if end_direction:
            dx, dy = lm.DIRS[end_direction]
            cells[-1] = (lx, ly, dx, dy)
        for idx, (x, y, dx, dy) in enumerate(cells):
            bend = idx > 0 and (cells[idx - 1][2], cells[idx - 1][3]) != (dx, dy)
            ch = (lm.VEC2ARROW[(dx, dy)]
                  if (idx == 0 or idx == len(cells) - 1 or bend)
                  else ("-" if dx != 0 else "|"))
            cur = self.p.get(x, y)
            if cur != " " and cur != ch:
                raise SystemExit(
                    f"PIPE COLLISION ({x},{y}): existing {cur!r} vs pipe {ch!r}")
            self.C(x, y, ch)

    def relay(self, x, y):
        self.p.room(x, y, 6, 4)
        self.run(x + 1, y + 1, "@>Rv")
        self.run(x + 2, y + 2, "^s<")


def serp_pts(entry, x_lo, x_hi, y_from, y_to):
    """Boustrophedon from `entry`=(x,y_from) over rows y_from..y_to (inclusive,
    stepping toward y_to), turning at x_lo/x_hi.  Returns waypoint list."""
    pts = [entry]
    at, y = entry[0], y_from
    step = 1 if y_to > y_from else -1
    while True:
        tgt = x_hi if abs(at - x_lo) < abs(at - x_hi) else x_lo
        pts.append((tgt, y))
        at = tgt
        if y == y_to:
            break
        y += step
        pts.append((at, y))
    return pts


def build():
    b = B()
    C = b.C
    b.p.room(0, 0, W, BW + 1)

    # ---------- riser ----------
    for y in range(5, 15):
        C(1, y, "^")

    # ---------- TOP prologue (row 4, east) ----------
    C(1, 4, ">")
    C(2, 4, ".")
    C(3, 4, "r", bind=(BR, -1))
    C(4, 4, "M")
    for x in range(5, 10):
        C(x, 4, ".")
    C(10, 4, "r", bind=(KR, -1))
    C(11, 4, ".")
    C(12, 4, "s", bind=(KF, -1))
    C(13, 4, "b")
    C(14, 4, ".")
    b.run(15, 4, "`100`")
    C(20, 4, "-")
    C(21, 4, "X")

    # ---------- REAL path (row 5, west) + descent ----------
    C(21, 5, "<")
    for x in range(9, 21):
        C(x, 5, ".")
    C(8, 5, "r", bind=(AR, -1))     # A = a_new
    C(7, 5, ".")
    C(6, 5, "s", bind=(HF, -1))     # push a_new (holder=[old,new])
    C(5, 5, "r", bind=(HR, -1))     # pop old a
    C(4, 5, "W")                    # A=v
    C(3, 5, ".")
    C(2, 5, "v")
    C(2, 6, ".")

    # ---------- LAP (rows 7-9) ----------
    C(2, 7, ">")
    C(3, 7, "s", bind=(BF, -1))
    C(4, 7, "M")
    C(5, 7, "r", bind=(HR, -1))
    C(6, 7, "s", bind=(HF, -1))
    C(7, 7, "*")
    C(8, 7, "v")
    C(2, 8, "r", bind=(BR, -1))
    C(8, 8, ".")
    C(2, 9, "d")
    C(3, 9, "m")
    C(4, 9, "s", bind=(CF, BOT))
    C(5, 9, "+")
    C(6, 9, "r", bind=(CR, BOT))
    C(7, 9, "M")
    C(8, 9, "<")

    # ---------- b-init (west rows 1-2), entered from col 9 ----------
    C(9, 1, "<")
    C(8, 1, "r", bind=(AR, -1))     # A=M
    C(7, 1, "M")
    C(6, 1, "v")
    C(6, 2, ">")
    C(7, 2, "s", bind=(HF, -1))     # holder dummy = M
    C(8, 2, "r", bind=(AR, -1))     # A=K
    C(9, 2, ".")
    C(10, 2, "s", bind=(KF, -1))    # K-ring = [K]
    C(11, 2, "W")                   # A=M,B=K
    C(12, 2, "*")                   # A=MK,B=K
    C(13, 2, "b")                   # BP=MK
    # exit east along row 2, then down col 29 to the B-track
    for x in range(14, 29):
        C(x, 2, ".")
    C(29, 2, "v")
    for y in range(3, 10):
        C(29, y, ".")               # (29,8) shared with S0 travel row 8

    # ---------- S0 (row 1 east), exit down col 31 to row 8 ----------
    C(19, 1, "@")
    C(20, 1, ".")
    C(21, 1, "r", bind=(IN, -1))    # N
    C(22, 1, "M")
    C(23, 1, "r", bind=(IN, -1))    # M
    C(24, 1, ".")
    C(25, 1, ".")
    C(26, 1, "s", bind=(AF, -1))    # push M
    C(27, 1, "*")
    C(28, 1, "b")                   # BP=NM
    C(29, 1, "r", bind=(IN, -1))    # K
    C(30, 1, "s", bind=(AF, -1))    # push K
    C(31, 1, "v")
    for y in range(2, 8):
        C(31, y, ".")
    C(31, 8, "<")
    C(30, 8, ".")
    C(28, 8, ".")                   # (29,8) placed above as '.'
    # ---------- seed-A track (cols 26-27, rows 8-12) ----------
    C(27, 8, "v")
    C(27, 9, "r", bind=(IN, -1))
    C(27, 10, "s", bind=(AF, -1))
    C(27, 11, "m")
    C(27, 12, "d")                  # south+CW = west
    C(26, 12, "^")
    for y in range(9, 12):
        C(26, y, ".")
    C(26, 8, ">")
    # A-exit: d straight south -> row 13 west -> col 11 north -> b-init
    C(27, 13, "<")
    for x in range(15, 27):
        C(x, 13, ".")
    # (14,13),(12,13) shared with emit-exit / B-exit below; (13,13) fresh:
    C(13, 13, ".")
    C(11, 13, "^")
    for y in range(6, 13):
        if y == 12:
            continue                # (11,12) shared with emit-exit row
        C(11, y, ".")
    C(11, 3, "<")
    C(10, 3, ".")
    C(9, 3, "^")
    # (11,4) TOP glide, (11,5) real glide, (9,2) b-init '.', (9,1) '<' exist

    # ---------- B-track (cols 28-29, rows 10-14) ----------
    C(29, 10, "v")
    C(29, 11, "r", bind=(IN, -1))
    C(29, 12, "s", bind=(BF2, BOT))
    C(29, 13, "m")
    C(29, 14, "d")                  # south+CW = west
    C(28, 14, "^")
    for y in range(11, 14):
        C(28, y, ".")
    C(28, 10, ">")
    # B-exit: d straight -> row 15 west -> col 12 north -> mark flow
    C(29, 15, "<")
    C(28, 15, "5")
    for x in range(13, 28):
        if x != 20:                 # (20,15) is the marker's '<' turn
            C(x, 15, ".")
    C(12, 15, "X")
    C(11, 15, ".")
    C(10, 15, ".")
    C(9, 15, "^")
    C(12, 14, ".")
    C(12, 13, ".")
    C(12, 11, ".")
    C(12, 9, ".")
    C(12, 8, ">")
    # (12,12),(12,11),(12,10) shared cells placed by other sections below

    # ---------- mark flow (rows 8-9) ----------
    C(22, 8, "<")                   # marker joins heading south
    for x in range(14, 22):
        C(x, 8, ".")
    C(13, 8, "v")
    C(13, 9, ">")
    b.run(14, 9, "`150`")
    C(19, 9, "s", bind=(BF2, BOT))  # push ROWMARK
    C(20, 9, "d")                   # seed BP=0 straight | marker BP=K CW south
    C(21, 9, "W")                   # seed: A=K,B=150
    C(22, 9, "b")                   # BP=K
    C(23, 9, "0")
    C(24, 9, "v")
    # row 10 west -> c-zero loop (seed only; marker dives south at col 20)
    C(24, 10, "<")
    for x in range(21, 24):
        C(x, 10, ".")
    C(20, 10, ".")
    C(19, 10, ".")
    C(18, 10, ".")
    C(17, 10, "<")
    # c-zero loop (cols 16-17, rows 10-12)
    C(16, 10, "a")
    C(16, 11, "s", bind=(CF2, BOT))
    C(16, 12, ">")
    C(17, 12, "^")
    C(17, 11, "m")
    # shared exit test
    C(15, 10, ".")
    C(14, 10, ".")
    C(13, 10, ".")                  # seed 0 straight | marker -150 CCW south
    for x in range(2, 13):
        C(x, 10, ".")
    # runtime marker: d(20,9) CW south -> col 20 -> row 15 west -> emit
    C(20, 11, ".")
    C(20, 12, "0")                  # marker A -> 0 (X(12,15) discriminator)
    C(20, 13, ".")
    C(20, 14, ".")
    C(20, 15, "<")

    # ---------- runtime marker: X -> north -> east -> descend col 22 ----------
    C(21, 3, ">")
    C(22, 3, "v")
    for y in range(4, 8):
        C(22, y, ".")

    # ---------- emit loop (rows 13-14) ----------
    C(9, 13, "<")
    C(8, 13, "r", bind=(CR, BOT))
    C(7, 13, "s", bind=(OUTC, BOT))
    C(6, 13, "0")
    C(5, 13, "s", bind=(CF, BOT))
    C(4, 13, "v")
    C(4, 14, ">")
    C(5, 14, "m")
    for x in range(6, 10):
        C(x, 14, ".")
    C(10, 14, "a")
    C(10, 13, "<")
    # emit exit east -> up col 14 -> west row 12 -> riser
    C(11, 14, ".")
    C(13, 14, ".")
    C(14, 14, "^")
    C(14, 13, ".")
    C(14, 12, "<")
    for x in range(2, 14):
        C(x, 12, ".")

    # ================= EXTERIOR =================
    b.p.input_room(IN - 1, -5)
    b.pipeC([(IN, -2), (IN, -1)], "S")
    b.p.output_room(10, BOT + 2)                         # O room (10,19)
    b.pipeC([(OUTC, BOT), (OUTC, BOT + 1), (11, BOT + 1)], "S")

    # holder relay (3,-6..8,-3)
    b.relay(3, -6)
    b.pipeC([(HF, -1), (HF, -2)], "N")
    b.pipeC([(HR, -2), (HR, -1)], "S")

    # K relay (10,-6..15,-3)
    b.relay(10, -6)
    b.pipeC([(KF, -1), (KF, -2)], "N")
    b.pipeC([(11, -2), (11, -1), (KR, -1)], "S")

    # A relay (8,-12..13,-9); return straight down col 9
    b.relay(8, -12)
    b.pipeC([(AR, -8), (AR, -1)], "S")
    # A feed: climb col 31, serp rows -37..-27 (cols 9..30), tail into west wall
    afp = [(AF, -1), (AF, -2), (45, -2), (45, -14)]
    afp += serp_pts((45, -14), 9, 44, -14, -20)[1:]
    assert afp[-1] == (9, -20), afp[-1]
    afp += [(7, -20), (7, -11)]
    b.pipeC(afp, "E")                                     # -> west wall (8,-11)

    # b relay SOUTH-EAST (24,20..29,23)
    b.relay(24, BOT + 3)
    # hot feed bf@3: up col 2, across row -38 (above the A serp), down col 34,
    # under the room into the relay top (28,20).
    b.pipeC([(BF, -1), (BF, -2), (2, -2), (2, -22), (46, -22), (46, 18),
             (28, 18), (28, 19)], "S")
    # bf2 (seed/marker feed, bottom@19): padded west zigzag (rows 19..33,
    # cols 15..18) so the ROWMARK cannot overtake the hot feed
    # (need len(bf2) > len(bf) - ~45), then into the west wall (24,21).
    bf2p = [(BF2, BOT), (BF2, 18), (22, 18), (22, 29), (44, 29), (44, 27),
            (24, 27), (24, 26), (43, 26), (43, 25), (26, 25), (26, 24)]
    b.pipeC(bf2p, "N")                                    # -> bottom (26,23)
    # b return: exits the relay bottom (27,24), serp rows 34..44 (cols 8..30),
    # tail around the west side up to br@2 on the ctrl top wall.
    brp = [(30, 21), (46, 21), (46, 30)]
    brp += serp_pts((46, 30), 16, 45, 30, 38)[1:]
    assert brp[-1] == (16, 38), brp[-1]
    brp += [(16, 40), (-5, 40), (-5, -1), (BR, -1)]
    b.pipeC(brp, "S")                                     # -> ctrl top (2,0)

    # c relay far SOUTH (1,28..6,31): cf and cr are straight parallel columns
    # (cols 4 and 5) — the ring capacity (K<=16 standing values) lives in them;
    # no pipe runs alongside a room wall (spurious-attach trap).  cf2 enters
    # the relay TOP at (2,27): its end reads before cf's (4,27), so the seed
    # zeros keep priority over the first products.
    b.relay(1, BOT + 11)                                  # rows 28..31
    b.pipeC([(CF, BOT), (CF, BOT + 10)], "S")             # col 4 -> top (4,28)
    b.pipeC([(CF2, BOT), (CF2, BOT + 22), (-1, BOT + 22), (-1, BOT + 10),
             (2, BOT + 10)], "S")                         # -> top (2,28)
    b.pipeC([(5, BOT + 10), (5, BOT), (CR, BOT)], "N")    # col 5 -> ctrl (6,16)

    return b


def verify_bindings(path, intents, origin=(0, 0)):
    import pipecheck
    ox, oy = origin
    intents = {(x - ox, y - oy): (ax - ox, ay - oy)
               for (x, y), (ax, ay) in intents.items()}
    found, topo = pipecheck.bindings(path)
    pipes = topo.get("pipes") or []
    ok = True
    for f in found:
        cell = tuple(f["cell"])
        if cell not in intents:
            if f["n_candidates"] == 1:
                continue            # relay-room op with a single pipe: safe
            print(f"  UNDECLARED {f['op']} at {cell}")
            ok = False
            continue
        pi = f["pipe"]
        if pi is None:
            print(f"  NO PIPE for {f['op']} at {cell}")
            ok = False
            continue
        pc = pipes[pi].get("path") or []
        attach = (tuple(pc[0]["pos"]) if f["op"] == "s" else tuple(pc[-1]["pos"]))
        if attach != intents[cell]:
            print(f"  REBOUND {f['op']} at {cell}: got {attach}, want {intents[cell]}")
            ok = False
    for cell in sorted(set(intents) - {tuple(f["cell"]) for f in found}):
        print(f"  MISSING op at {cell}")
        ok = False
    return ok


if __name__ == "__main__":
    b = build()
    out = os.path.join(OUT_DIR, "matmul-carousel.man")
    open(out, "w").write(b.p.render() + "\n")
    w, h, box = b.p.footprint()
    print(f"wrote {out}  {w}x{h} box {box}")
    if "--verify" in sys.argv:
        minx, miny, _, _ = b.p.bounds()
        ok = verify_bindings(out, b.intent, origin=(minx, miny))
        print("bindings:", "ALL OK" if ok else "FAILED")
        sys.exit(0 if ok else 1)

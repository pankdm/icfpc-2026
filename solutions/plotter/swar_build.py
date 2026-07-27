#!/usr/bin/env python3
"""Plotter, SWAR rebuild.  Generates plotter-swar*.man.

PIPELINE (one man per room, every stage a rectangular ring)

    IN -> RELAY -> ECHO <-> CTRL -> MOD -> ADDRM -> DATAM -> display
                                              \\-> ADDR      \\-> DATA, SWAP

  CTRL   per-round setup (swar_setup.setup) + the ramp ring `s ; m ; d ; +`,
         emitting W_k = P0 + k*Ic and then a 0 sentinel.
  ECHO   CTRL's scratch fifo: a 2-cell-wide ring of `R ; s` pairs.  It also
         relays the four input values, which arrive on a second incoming pipe;
         `R` prefers the pipe whose attach cell comes first in reading order,
         so the RELAY pipe is attached above the CTRL pipe and inputs always win.
  MOD    B = Jc (first value of every round).   `r ; % ; s ; X`
  ADDRM  B = 1024.  `r ; s(->DATAM) ; % ; s(->ADDR)`   -- forwards the RAW P so
         that DATAM still sees a negative value for a pixel and 0 for the
         sentinel; sends ADDR later than it forwards, which is what keeps
         ADDR_k ahead of DATA_k at the display.
  DATAM  B = 15.    `r ; X ; 0 ; + ; s(->DATA)`, sentinel -> `s(->SWAP)`.

TWO OUTGOING PIPES IN ONE ROOM
  `s` picks the nearest outgoing pipe (Manhattan to the pipe's first cell).  In
  CTRL the scratch sends and the ramp sends must split, so both pipes attach on
  the SAME COLUMN -- one above the room, one below.  The |x - cx| term then
  cancels and the room splits cleanly into a top half (scratch) and a bottom
  half (ramp).  `check_pipe_binding` proves it cell by cell.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import littleman as lm                      # noqa: E402
import swar_setup as SS                     # noqa: E402


class CheckedProgram(lm.Program):
    """Program whose put() refuses to overwrite -- pipes silently overwriting a
    room glyph is the failure mode that produces an unreadable load error."""

    def put(self, x, y, ch):
        old = self.cells.get((x, y), " ")
        wall = "+-|=:"
        assert old == " " or old == ch or (old in wall and ch in wall), \
            f"overlap at ({x},{y}): {old!r} vs {ch!r}"
        return super().put(x, y, ch)


class G:
    def __init__(self):
        self.p = CheckedProgram()

    def put(self, x, y, ch):
        self.p.put(x, y, ch)

    def row(self, x, y, s, dx=1):
        for i, ch in enumerate(s):
            self.put(x + i * dx, y, ch)

    def col(self, x, y, s, dy=1):
        for i, ch in enumerate(s):
            self.put(x, y + i * dy, ch)


# ─────────────────────────────────────────────────────────────────────────────
# rings.  A rectangular ring is walked clockwise; `cells` is the cycle starting
# at the top-left corner, so ops can be dropped onto it positionally.
# ─────────────────────────────────────────────────────────────────────────────

def ring_cells(x, y, w, h):
    """Clockwise cycle of a w x h rectangular ring, starting at (x, y)."""
    out = [(x + i, y) for i in range(w - 1)]
    out += [(x + w - 1, y + j) for j in range(h - 1)]
    out += [(x + w - 1 - i, y + h - 1) for i in range(w - 1)]
    out += [(x, y + h - 1 - j) for j in range(h - 1)]
    return out


def ring_cells_ccw(x, y, w, h):
    """Counter-clockwise cycle -- what `X` needs, since it turns CCW on A < 0 and
    every value on the pixel stream is negative (0 is the round sentinel)."""
    out = [(x, y + j) for j in range(h - 1)]
    out += [(x + i, y + h - 1) for i in range(w - 1)]
    out += [(x + w - 1, y + h - 1 - j) for j in range(h - 1)]
    out += [(x + w - 1 - i, y) for i in range(w - 1)]
    return out


def lay_ring_ccw(g, x, y, w, h, glyphs):
    cells = ring_cells_ccw(x, y, w, h)
    assert len(cells) == len(glyphs), (len(cells), len(glyphs))
    for (cx, cy), ch in zip(cells, glyphs):
        g.put(cx, cy, ch)


def lay_ring(g, x, y, w, h, glyphs):
    cells = ring_cells(x, y, w, h)
    assert len(cells) == len(glyphs), (len(cells), len(glyphs))
    for (cx, cy), ch in zip(cells, glyphs):
        g.put(cx, cy, ch)


# ─────────────────────────────────────────────────────────────────────────────
# the build
# ─────────────────────────────────────────────────────────────────────────────

def build(IW=56):
    toks = SS.run(3, 4, 20, 19).toks
    body, tail = toks[:-4], toks[-4:]
    assert [k for _, k in tail] == [SS.OUT, SS.READ, SS.OP, SS.READ], tail
    assert all(len(t) == 1 for t, _ in toks), "multi-cell token in the stream"

    per_row = IW - 3
    R = -(-len(body) // per_row)
    if R % 2 == 0:
        R += 1                                   # last serpentine row heads EAST
    IH = 2 * R - 1                               # forced by the pipe split
    assert R + 8 <= IH, (R, IH)

    g = G()
    # ---------------- top band ----------------
    ECHO_W = 24                                  # interior 22 x 2
    inp = g.p.input_room(0, 0)
    rel = g.p.room(5, 0, 9, 4)                   # interior 7 x 2: four r/s pairs
    ech = g.p.room(0, 6, ECHO_W, 4)

    ex, ey = ech.ix0, ech.iy0
    cells = ring_cells(ex, ey, ECHO_W - 2, 2)
    corners = {(ex, ey): ">", (ex + ECHO_W - 3, ey): "v",
               (ex + ECHO_W - 3, ey + 1): "<", (ex, ey + 1): "^"}
    gl, k = [], 0
    for cx, cy in cells:
        if (cx, cy) in corners:
            gl.append(corners[(cx, cy)])
        elif (cx, cy) == (ex + 1, ey):
            gl.append("@")                       # nop: entered heading east
        elif (cx, cy) == (ex + 2, ey):
            gl.append(".")                       # keeps the R/s parity even
        else:
            gl.append("R" if k % 2 == 0 else "s")
            k += 1
    assert k % 2 == 0
    lay_ring(g, ex, ey, ECHO_W - 2, 2, gl)

    # RELAY forwards FOUR values per lap.  It has to clear all four inputs into
    # ECHO before CTRL's first scratch push can arrive there, or ECHO -- which
    # only prefers the RELAY pipe when that pipe is READY -- interleaves them.
    rx, ry = rel.ix0, rel.iy0
    lay_ring(g, rx, ry, 7, 2,
             [">", "@", ".", "r", "s", "r", "v", "<", "s", "r", "s", "r", "s", "^"])

    # ---------------- CTRL ----------------
    CT = 12
    ctrl = g.p.room(0, CT, IW + 2, IH + 2)
    X0, Y0 = ctrl.ix0, ctrl.iy0

    def C(ix, iy):
        return (X0 + ix, Y0 + iy)

    g.put(*C(0, 0), ">")                         # return-path merge
    g.put(*C(1, 0), "@")
    for j in range(R):
        if j % 2 == 0:
            if j:
                g.put(*C(1, j), ">")
            g.put(*C(IW - 1, j), "v")
        else:
            g.put(*C(IW - 1, j), "<")
            g.put(*C(1, j), "v")
    idx = 0
    for j in range(R):
        cols = range(2, IW - 1) if j % 2 == 0 else range(IW - 2, 1, -1)
        for c in cols:
            g.put(*C(c, j), body[idx][0] if idx < len(body) else ".")
            idx += 1

    g.put(*C(IW - 1, R), "<")                    # tail: s(Jc) r M r
    g.row(*C(IW - 2, R), "".join(t[0] for t in tail), -1)
    g.put(*C(IW - 6, R), "v")
    g.put(*C(IW - 6, R + 1), ">")
    g.put(*C(IW - 5, R + 1), "v")
    rrx, rry = IW - 5, R + 2
    lay_ring(g, *C(rrx, rry), 3, 3, [">", "s", "v", "m", "d", "+", "^", "."])
    g.put(*C(rrx + 2, rry + 3), "0")             # ramp exit -> sentinel -> home
    g.put(*C(rrx + 2, rry + 4), "s")
    g.put(*C(rrx + 2, rry + 5), "<")
    for c in range(1, rrx + 2):
        g.put(*C(c, rry + 5), ".")
    g.put(*C(0, rry + 5), "^")
    for j in range(1, rry + 5):
        g.put(*C(0, j), ".")

    # ---------------- display + plot chain -------------------------------
    # The chain sits LEFT of the display.  Routing is planar only if ADDR leaves
    # ADDRM upward on a column that clears MOD (col 9, MOD is only 7 wide) while
    # CTRL -> MOD runs west one row higher and drops into MOD's TOP wall.
    DY = CT + IH + 6
    mod = g.p.room(0, DY, 7, 8)
    adr = g.p.room(0, DY + 10, 12, 6)
    dat = g.p.room(0, DY + 19, 12, 7)
    disp = g.p.display(14, DY, 34, 26)

    mx, my = mod.ix0, mod.iy0                    # MOD: r(Jc) M ; ring r % s X
    g.row(mx, my, ">@rMv")
    for j in range(1, 5):
        g.put(mx + 4, my + j, ".")
    g.put(mx + 4, my + 5, "<")
    for c in range(3, 0, -1):
        g.put(mx + c, my + 5, ".")
    g.put(mx, my + 5, "^")
    g.put(mx, my + 4, ".")
    g.put(mx, my + 3, ">")                       # ring entry, heading east
    lay_ring_ccw(g, mx + 1, my + 2, 3, 3, ["X", "v", ">", "r", "^", "%", "<", "s"])
    g.put(mx, my + 2, "^")                       # sentinel: X falls through west
    g.put(mx, my + 1, ".")

    ax, ay = adr.ix0, adr.iy0                    # ADDRM: B = 1024 = 1<<5<<5
    g.row(ax, ay, "@5M1{{Mv")
    lay_ring_ccw(g, ax + 7, ay + 1, 3, 3, ["v", "r", ">", "s", "^", "%", "<", "s"])

    dx, dy = dat.ix0, dat.iy0                    # DATAM: B = 15 = 6 + 9
    g.row(dx, dy, "@9M6+M...v")
    g.put(dx + 9, dy + 1, "<")
    g.put(dx + 8, dy + 1, "v")                   # ring entry / merge
    g.row(dx + 4, dy + 1, ">...")
    lay_ring_ccw(g, dx + 6, dy + 2, 3, 3, ["X", "0", ">", "+", "^", "s", "<", "r"])
    g.put(dx + 5, dy + 2, "s")                   # sentinel -> SWAP
    g.put(dx + 4, dy + 2, "^")

    # ---------------- pipes ----------------
    P = g.p.pipe
    CX = X0 + 4                                  # shared column of CTRL's two outs
    P([(inp.x1 + 1, inp.y0 + 1), (rel.x0 - 1, inp.y0 + 1)])          # IN -> RELAY
    P([(rx + 3, rel.y1 + 1), (rx + 3, ech.y0 - 1)])                  # RELAY -> ECHO
    P([(CX, ctrl.y0 - 1), (CX, ech.y1 + 1), (18, ech.y1 + 1)],
      end_direction="N")                                             # CTRL -> ECHO
    P([(20, ech.y1 + 1), (20, ech.y1 + 2), (30, ech.y1 + 2)],
      end_direction="S")                                             # ECHO -> CTRL
    P([(CX, DY - 4), (CX, DY - 3), (3, DY - 3), (3, DY - 1)])         # CTRL -> MOD
    P([(mx + 2, mod.y1 + 1), (mx + 2, adr.y0 - 1)])                   # MOD -> ADDRM
    # ADDR and DATA are two branches of the same pixel; the display consumes
    # ADDR before DATA only if they ARRIVE in that order, so the two pipe lengths
    # have to be balanced against the 4-tick head start ADDR gets in ADDRM's ring
    # and the 8-tick pixel cadence.  ADDR = 19 cells, DATA = 17.
    P([(ax + 8, adr.y0 - 1), (ax + 8, DY - 2), (disp.x0 + 1, DY - 2),
       (disp.x0 + 1, DY - 1)])                                       # ADDR
    # ADDRM -> DATAM is deliberately 18 cells long.  The display sees ADDR_k,
    # DATA_k, ADDR_{k+1} in that order only if
    #     LA - 2 <= LX + LD < LA + cadence - 2
    # (LA/LD = ADDR/DATA pipe lengths, LX = this pipe, cadence = 8), so the cheap
    # place to add the missing delay is here, upstream of the split.
    P([(ax + 8, adr.y1 + 1), (ax + 8, adr.y1 + 2), (ax, adr.y1 + 2),
       (ax, adr.y1 + 3), (ax + 7, adr.y1 + 3)], end_direction="S")
    P([(dat.x1 + 1, dy + 3), (disp.x0 - 1, dy + 3)])                  # DATA
    P([(dx + 5, dat.y1 + 1), (dx + 5, disp.y1 + 2), (30, disp.y1 + 2),
       (30, disp.y1 + 1)])                                            # SWAP
    return g.p, dict(IW=IW, IH=IH, R=R, ops=len(toks))


if __name__ == "__main__":
    p, info = build(*(int(a) for a in sys.argv[1:2]))
    out = os.path.join(HERE, "plotter-swar1.man")
    p.save(out)
    print(info, p.footprint())
    print(subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "tools",
                                                       "grade_fast.py"), "plotter", out],
                         capture_output=True, text=True).stdout[-2000:])

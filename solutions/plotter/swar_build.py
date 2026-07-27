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

BASE_TICKS = 505      # measured: fixed overhead + 8 ticks x 18 pixels a round


def geometry(npre, ntail):
    """Pick (L, k, IW): L = last serpentine row, k = the branch row (must head
    EAST, so even), IW = interior width.  The pipe split forces IH ~ 2L, so rows
    are twice as expensive as columns and the search is worth doing."""
    best = None
    for L in range(7, 24):
        # The 4x4 ramp ring puts the `0 ; s` sentinel in the column BESIDE it, so
        # the machinery under the serpentine is 7 rows, not 8 -- which is what
        # lets L be even (last row heads west, tail row starts on the left).
        IH = max(2 * L + 1, L + 8)
        if IH > 2 * L + 2:
            continue
        for k in range(0, L - 1):
            prows, trows = k + 1, L - k - 1
            if trows < 1:
                continue
            T = max(-(-npre // prows), -(-ntail // trows))
            IW = T + 3
            # PADDING IS TICKS: a '.' in an unfilled serpentine slot is walked
            # every round.  Minimising the box alone picks a wide, mostly-empty
            # serpentine and loses more in ticks than it gains in area.
            pad = prows * T - npre + trows * T - ntail
            w, h = IW + 18, IH + 39
            cand = (max(w, h) ** 2 * (BASE_TICKS + pad), L, k, IW, IH)
            if best is None or cand < best:
                best = cand
    return best[1:]


def build(geom=None):
    pre, px, py, tail = SS.segments()
    tail_body, tail_fin = tail[:-4], tail[-4:]
    assert [k for _, k in tail_fin] == [SS.OUT, SS.READ, SS.OP, SS.READ]
    assert all(len(t) == 1 for t, _ in pre + px + py + tail)
    L, k, IW, IH = geom or geometry(len(pre), len(tail_body))
    BX = IW                                      # branch column
    MC = BX + max(len(px), len(py)) + 1           # merge column

    g = G()
    # ---------------- top band ----------------
    ECHO_W = 24                                  # interior 22 x 2
    ech = g.p.room(0, 0, ECHO_W, 4)
    rel = g.p.room(ECHO_W + 2, 0, 9, 4)          # interior 7 x 2: four r/s pairs
    inp = g.p.input_room(ECHO_W + 13, 0)

    ex, ey = ech.ix0, ech.iy0
    cells = ring_cells(ex, ey, ECHO_W - 2, 2)
    corners = {(ex, ey): ">", (ex + ECHO_W - 3, ey): "v",
               (ex + ECHO_W - 3, ey + 1): "<", (ex, ey + 1): "^"}
    gl, kk = [], 0
    for cx, cy in cells:
        if (cx, cy) in corners:
            gl.append(corners[(cx, cy)])
        elif (cx, cy) == (ex + 1, ey):
            gl.append("@")                       # nop: entered heading east
        elif (cx, cy) == (ex + 2, ey):
            gl.append(".")                       # keeps the R/s parity even
        else:
            gl.append("R" if kk % 2 == 0 else "s")
            kk += 1
    assert kk % 2 == 0
    lay_ring(g, ex, ey, ECHO_W - 2, 2, gl)

    rx, ry = rel.ix0, rel.iy0
    lay_ring(g, rx, ry, 7, 2,
             [">", "@", ".", "r", "s", "r", "v", "<", "s", "r", "s", "r", "s", "^"])

    # ---------------- CTRL ----------------
    CT = 6
    ctrl = g.p.room(0, CT, MC + 3, IH + 2)
    X0, Y0 = ctrl.ix0, ctrl.iy0
    east = (k % 2 == 0)
    off = 0 if east else MC - IW + 1            # left-hand block: shift right

    def C(ix, iy):
        return (X0 + off + ix, Y0 + iy)

    # Row k+1 is skipped (the branch block sits beside it), so the rows after it
    # take the direction row k+1 would have had.
    dirs = {j: ("E" if j % 2 == 0 else "W") for j in range(k + 1)}
    dirs.update({j: ("E" if j % 2 == 1 else "W") for j in range(k + 2, L + 1)})
    assert (dirs[k] == "E") == east

    g.put(*C(0, 0), ">")                         # return-path merge
    idx_pre = idx_tail = 0
    for j, d in sorted(dirs.items()):
        src = pre if j <= k else tail_body
        if d == "E":
            if not (j == k + 2 and not east):    # k+2 is entered from the block
                g.put(*C(1, j), "@" if j == 0 else ">")
            cols = range(2, IW - 1)
            g.put(*C(IW - 1, j), "." if (j == k and east) else "v")
        else:
            cols = range(IW - 2, 1, -1)
            if not (j == k + 2 and east):
                g.put(*C(IW - 1, j), "<")
            g.put(*C(1, j), "." if (j == k and not east) else "v")
        for c in cols:
            if j <= k:
                ch = pre[idx_pre][0] if idx_pre < len(pre) else "."
                idx_pre += 1
            else:
                ch = tail_body[idx_tail][0] if idx_tail < len(tail_body) else "."
                idx_tail += 1
            g.put(*C(c, j), ch)
    assert idx_pre >= len(pre) and idx_tail >= len(tail_body)

    # ---------------- the octant branch ----------------
    # `X` turns CW on A > 0 and CCW on A < 0, and the test is odd so it never
    # falls through.  y-major goes south, x-major north; both rows are free east
    # of the serpentine, so the block costs columns, not rows.
    # `X` turns CW on A > 0 and CCW on A < 0, so the two octants leave the branch
    # cell on opposite sides -- north/south of an EASTWARD row k, and (mirrored)
    # south/north of a WESTWARD one.  Letting k be odd is what balances the PRE
    # and TAIL row counts; the block just moves to the other side, costing the
    # same 16 columns and no rows.
    step = 1 if east else -1
    bx0 = BX if east else -1
    mce = bx0 + step * (max(len(px), len(py)) + 1)
    up, dn = (px, py) if east else (py, px)      # row k-1 gets `up`
    g.put(*C(bx0, k), "X")
    for row, seg in ((k - 1, up), (k + 1, dn)):
        g.put(*C(bx0, row), ">" if east else "<")
        for i, t in enumerate(seg):
            g.put(*C(bx0 + step * (1 + i), row), t[0])
        for c in range(len(seg) + 1, max(len(px), len(py)) + 1):
            g.put(*C(bx0 + step * c, row), ".")
    g.put(*C(mce, k - 1), "v")
    g.put(*C(mce, k), ".")
    g.put(*C(mce, k + 1), "v")                   # merge
    g.put(*C(mce, k + 2), "<" if east else ">")
    lo, hi = (IW - 1, mce) if east else (mce + 1, 2)
    for c in range(lo, hi):
        if g.p.get(*C(c, k + 2)) == " ":
            g.put(*C(c, k + 2), ".")

    # ---------------- tail row, ramp ring, return ----------------
    R = L + 1
    # The ramp ring follows the tail row to whichever side it ends on -- padding
    # the tail row across the serpentine to reach a fixed ring column cost 30
    # ticks a round, more than the row it saved.
    fin = "".join(t[0] for t in tail_fin)
    if dirs[L] == "E":
        g.put(*C(IW - 1, R), "<")
        g.row(*C(IW - 2, R), fin, -1)
        rrx = IW - 2 - len(fin) - 1
    else:                                        # last row headed west
        g.put(*C(1, R), ">")
        g.row(*C(2, R), fin)
        rrx = 2 + len(fin)
    # Ramp ring: 4x4, TWO pixels per lap.  A pixel needs three edge cells
    # (s, m, +) and one turning test (`d`), and a rectangle has four corners, so
    # two `d`s fit -- 12 cells / 2 pixels = 6 ticks/pixel instead of 8.  Both
    # `d`s exit when BP hits 0, one east and one west, so the two exits merge on
    # the row below before the `0 ; s` sentinel.
    g.put(*C(rrx, R), "v")
    g.put(*C(rrx, R + 1), ".")
    rry = R + 2
    lay_ring(g, *C(rrx, rry), 4, 4,
             [">", "s", "m", "d", "+", ".", "<", "s", "m", "d", "+", "."])
    ret = rry + 4
    g.put(*C(rrx + 4, rry), "v")                 # east exit
    for j in range(rry + 1, ret):
        g.put(*C(rrx + 4, j), ".")
    g.put(*C(rrx + 4, ret), "<")
    for c in range(rrx, rrx + 4):
        g.put(*C(c, ret), ".")
    g.put(*C(rrx - 1, rry + 3), "v")             # west exit
    g.put(*C(rrx - 1, ret), "<")                 # merge
    g.put(*C(rrx - 2, ret), "0")
    g.put(*C(rrx - 3, ret), "s")
    for c in range(1, rrx - 3):
        g.put(*C(c, ret), ".")
    g.put(*C(0, ret), "^")
    for j in range(1, ret):
        g.put(*C(0, j), ".")

    # ---------------- display + plot chain -------------------------------
    # The chain sits LEFT of the display.  Routing is planar only if ADDR leaves
    # ADDRM upward on a column that clears MOD (col 9, MOD is only 7 wide) while
    # CTRL -> MOD runs west one row higher and drops into MOD's TOP wall.
    DY = CT + IH + 5
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
    P([(inp.x0 - 1, inp.y0 + 1), (rel.x1 + 1, inp.y0 + 1)])          # IN -> RELAY
    P([(rel.x0 - 1, ry + 1), (ech.x1 + 1, ry + 1)])                  # RELAY -> ECHO
    # The scratch loop's LATENCY equals its CAPACITY: a value CTRL pushes only
    # comes back after traversing every pipe cell.  CTRL's fifo is at most 10
    # deep and it pushes about every 2.5 ops, so a loop longer than ~25 cells
    # stalls almost every fetch.  Keep it just above the fifo depth: 5 + 1 + 6.
    P([(CX, ctrl.y0 - 1), (CX, ech.y1 + 1), (CX + 3, ech.y1 + 1)],
      end_direction="N")                                             # CTRL -> ECHO
    P([(CX + 6, ech.y1 + 1), (CX + 6, ech.y1 + 2), (CX + 10, ech.y1 + 2)],
      end_direction="S")                                             # ECHO -> CTRL
    P([(CX, DY - 3), (CX, DY - 2), (3, DY - 2), (3, DY - 1)])         # CTRL -> MOD
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
    # SWAP only has to arrive no EARLIER than the last DATA, so it is the one
    # pipe worth shortening: every cell of it is a tick of per-round drain.
    P([(dx + 5, dat.y1 + 1), (dx + 5, disp.y1 + 2), (disp.x0 + 3, disp.y1 + 2),
       (disp.x0 + 3, disp.y1 + 1)])                                   # SWAP
    return g.p, dict(L=L, k=k, IW=IW, IH=IH,
                     ops=len(pre) + len(px) + len(tail),
                     cells=len(pre) + len(px) + len(py) + len(tail))


if __name__ == "__main__":
    p, info = build()
    out = os.path.join(HERE, "plotter-swar3.man")
    p.save(out)
    print(info, p.footprint())
    print(subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "tools",
                                                       "grade_fast.py"), "plotter", out],
                         capture_output=True, text=True).stdout[-2000:])

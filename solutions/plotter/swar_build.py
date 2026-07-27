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

LOOP = 2              # scratch-loop horizontal legs; capacity must exceed the fifo
SWCOL = 1             # SWAP entry column, offset into the display's bottom wall
ZIG = 7               # ADDRM->DATAM zigzag width; pipe is 2*ZIG+2 cells
BASE_TICKS = 505      # measured: fixed overhead + 8 ticks x 18 pixels a round

# Fixed vertical overhead, split so the two compressible parts are knobs:
#   6 (top band) + IH + 2 (CTRL walls) + GAP + 26 (display) + SWAP_ROWS
# GAP    rows between CTRL's bottom wall and the MOD/display top walls.  It
#        carries CTRL->MOD (cols 3..5) and the ADDR riser (col 9, then east to
#        col 15) -- disjoint column ranges, so they fit on ONE row.
# SWAP_ROWS  rows below the display for the SWAP return.  DATAM's bottom wall is
#        flush with the display's, so a single row reaches the bottom wall if the
#        loader tolerates pipe cells running under it.
GAP = 3               # FLOOR: at 2 the ADDR riser's bend sits directly under
                      # CTRL's wall, and an arrow whose backward cell is a wall is
                      # read as a pipe SOURCE.  (Both floors measured by sweep.)
SWAP_ROWS = 2         # FLOOR: the display's side test reads the entry
                      # direction off the last TWO path cells, so a bottom-wall
                      # attach needs a vertical approach, i.e. two rows.
# Blank rows between CTRL's tail row and the top of the 4x4 ramp ring.  Pure
# walking cells: the man leaves the tail row heading south and the ring's `>`
# turns him east whether he lands on it after 1 nop or 0.
SPACER = 0      # 0 is the champion (plotter-swar7.man); 1 reproduces swar5


def vfixed():
    return 34 + GAP + SWAP_ROWS


def ih_of(L):
    """CTRL interior height actually consumed: L+1 serpentine rows, the tail
    row, SPACER, the 4-row ramp ring and the return row."""
    return L + 7 + SPACER


def geometry(npre, ntail, bw):
    """Pick (L, k, W).  The branch block occupies columns 1..bw but only on the
    three rows around the branch, so every OTHER serpentine row reclaims them:
    rows are wide (W-3 tokens) except rows 1..k, which must clear the block.
    That hole was 29x6 of unused floor before this."""
    best = None
    for L in range(5, 20):
        IH = ih_of(L)
        if IH > 2 * L + 2:
            continue
        for k in range(1, L - 1):
            trows = L - k - 1
            if trows < 1:
                continue
            for W in range(bw + 8, 90):
                pre_cap = (W - 3) + (k - 1) * (W - bw - 3) + (W - bw - 2)
                tail_cap = trows * (W - 3)
                if pre_cap < npre or tail_cap < ntail:
                    continue
                pad = pre_cap - npre + (0 if trows < 2 else (tail_cap - ntail) % 2)
                w, h = W + 2, IH + vfixed()
                cand = (max(w, h) ** 2 * (BASE_TICKS + pad), L, k, W, IH)
                if best is None or cand < best:
                    best = cand
                break
    return best[1:]


def build(geom=None):
    pre, px, py, tail_body, tail_fin = SS.segments()
    assert not any(k == SS.SCRATCH for _, k in tail_fin)
    assert all(len(t) == 1 for t, _ in pre + px + py + tail_body + tail_fin)
    BW = max(len(px), len(py)) + 2               # X column + ops + merge column
    L, k, W, IH = geom or geometry(len(pre), len(tail_body), BW)
    assert k % 2 == 1, "branch row heads west, so the block sits on the left"

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
    ctrl = g.p.room(0, CT, W + 2, IH + 2)
    X0, Y0 = ctrl.ix0, ctrl.iy0

    def C(ix, iy):
        return (X0 + ix, Y0 + iy)

    dirs = {j: ("E" if j % 2 == 0 else "W") for j in range(k + 1)}
    dirs.update({j: ("E" if j % 2 == 1 else "W") for j in range(k + 2, L + 1)})
    assert dirs[k] == "W" and dirs[k + 2] == "E"

    # left bound of each row: rows 1..k must clear the branch block
    # Rows 1..k-1 share a left bound (a westward row exits where the eastward
    # row under it enters), so raising it absorbs PRE slack two cells at a time
    # -- slack left as trailing '.' would be walked every round.  The divisor is
    # the ROW COUNT k-1, not 2*(k-1): the pairing constrains which rows may move
    # together, but each of those rows still gives up `bump` cells of its own.
    pre_min = (W - 3) + (k - 1) * (W - BW - 3) + (W - BW - 2)
    bump = max(0, (pre_min - len(pre)) // max(1, k - 1))
    lb = {0: 1}
    for j in range(1, k + 1):
        lb[j] = BW + 1 + (bump if j < k else 0)
    trows = L - k - 1
    slack = trows * (W - 3) - len(tail_body)
    x = 1 + (slack // 2 if trows > 1 else 0)     # shorten the last pair evenly
    for j in range(k + 2, L + 1):
        lb[j] = 1 if j == k + 2 else x

    g.put(*C(0, 0), ">")                         # return-path merge
    idx_pre = idx_tail = 0
    for j in range(L + 1):
        if j == k + 1:
            continue
        d = dirs[j]
        src, idx = (pre, "p") if j <= k else (tail_body, "t")
        if d == "E":
            g.put(*C(lb[j], j), "@" if j == 0 else ">")
            cols = list(range(lb[j] + 1, W - 1))
            g.put(*C(W - 1, j), "v")
        else:
            g.put(*C(W - 1, j), "<")
            end = BW if j == k else lb[j]        # row k walks on into the X
            cols = list(range(W - 2, end, -1))
            if j != k:
                g.put(*C(lb[j], j), "v")
        for c in cols:
            if idx == "p":
                ch = pre[idx_pre][0] if idx_pre < len(pre) else "."
                idx_pre += 1
            else:
                ch = tail_body[idx_tail][0] if idx_tail < len(tail_body) else "."
                idx_tail += 1
            g.put(*C(c, j), ch)
    assert idx_pre >= len(pre) and idx_tail >= len(tail_body), (idx_pre, idx_tail)

    # ---------------- the octant branch ----------------
    # Row k heads WEST into `X` at column BW; `X` turns CW on A > 0 (y-major,
    # north) and CCW on A < 0 (x-major, south), and the test is odd so it never
    # falls through.  Both paths run west and rejoin at column 1, which is where
    # row k+2 starts -- so the block costs three rows of columns 1..BW and every
    # other row uses them for tokens.
    g.put(*C(BW, k), "X")
    for row, seg in ((k - 1, py), (k + 1, px)):
        g.put(*C(BW, row), "<")
        for i, t in enumerate(seg):
            g.put(*C(BW - 1 - i, row), t[0])
        for c in range(2, BW - len(seg)):
            g.put(*C(c, row), ".")
    g.put(*C(1, k - 1), "v")
    g.put(*C(1, k), ".")
    g.put(*C(1, k + 1), "v")                     # merge
    g.put(*C(1, k + 2), ">")

    # ---------------- tail row, ramp ring, return ------------------------
    R = L + 1
    fin = "".join(t[0] for t in tail_fin)
    if dirs[L] == "E":
        g.put(*C(W - 1, R), "<")
        g.row(*C(W - 2, R), fin, -1)
        rrx = W - 2 - len(fin) - 1
    else:
        g.put(*C(lb[L], R), ">")
        g.row(*C(lb[L] + 1, R), fin)
        rrx = lb[L] + 1 + len(fin)
    # Ramp ring: 4x4, TWO pixels per lap (three edge cells s/m/+ and one turning
    # test `d` each, and a rectangle has four corners).  Both `d`s exit when BP
    # hits 0, one east and one west, so the exits merge on the row below before
    # the `0 ; s` sentinel -- which is what keeps this to 7 rows, not 8.
    g.put(*C(rrx, R), "v")
    for j in range(1, SPACER + 1):
        g.put(*C(rrx, R + j), ".")
    rry = R + 1 + SPACER
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
    DY = CT + IH + 2 + GAP
    mod = g.p.room(0, DY, 7, 8)
    adr = g.p.room(0, DY + 10, 12, 6)
    dat = g.p.room(0, DY + 19, 12, 7)
    disp = g.p.display(14, DY, 34, 26)

    # MOD: r(mind) M ; then r(4096*maxL) N + M forms Jc while walking down the
    # descent column it was gliding through anyway.  Ring: r % s X.
    mx, my = mod.ix0, mod.iy0
    g.row(mx, my, ">@rMv")
    for c, ch in zip(range(1, 5), "rN+M"):
        g.put(mx + 4, my + c, ch)
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
    P([(CX, ctrl.y0 - 1), (CX, ech.y1 + 1), (CX + LOOP, ech.y1 + 1)],
      end_direction="N")                                             # CTRL -> ECHO
    P([(CX + LOOP + 3, ech.y1 + 1), (CX + LOOP + 3, ech.y1 + 2),
       (CX + 2 * LOOP + 4, ech.y1 + 2)], end_direction="S")          # ECHO -> CTRL
    # CTRL -> MOD.  Head west on the FIRST gap row (cols 3..5), then drop col 3
    # into MOD's top wall.  The ADDR riser turns on its own row at col 9+, so the
    # two never share a cell however thin the gap gets.
    # MEASURED: exactly ONE pipe cell may touch CTRL's bottom wall.  Running the
    # westward leg on the first gap row puts cols 3,4,5 against that wall, the
    # loader then attaches the pipe at col 3, the |x-cx| term in `s`'s nearest
    # -pipe test stops cancelling, and CTRL's scratch/ramp split collapses
    # (grades 0/6, display-addr).  So drop one row first, THEN head west.
    gm = [(CX, DY - GAP), (CX, DY - GAP + 1), (3, DY - GAP + 1)]
    if GAP > 2:
        gm.append((3, DY - 1))
        P(gm)
    else:                       # last leg runs west ON the row above MOD's wall
        P(gm, end_direction="S")
    P([(mx + 2, mod.y1 + 1), (mx + 2, adr.y0 - 1)])                   # MOD -> ADDRM
    # ADDR and DATA are two branches of the same pixel; the display consumes
    # ADDR before DATA only if they ARRIVE in that order, so the two pipe lengths
    # have to be balanced against the 4-tick head start ADDR gets in ADDRM's ring
    # and the 8-tick pixel cadence.  ADDR = 19 cells, DATA = 17.
    AT = DY - min(GAP, 2)                     # ADDR's turn row (keeps LA at 19)
    ap = [(ax + 8, adr.y0 - 1), (ax + 8, AT), (disp.x0 + 1, AT)]
    if AT != DY - 1:
        ap.append((disp.x0 + 1, DY - 1))
    P(ap)                                                            # ADDR

    # ADDRM -> DATAM is deliberately 18 cells long.  The display sees ADDR_k,
    # DATA_k, ADDR_{k+1} in that order only if
    #     LA - 2 <= LX + LD < LA + cadence - 2
    # (LA/LD = ADDR/DATA pipe lengths, LX = this pipe, cadence = 8), so the cheap
    # place to add the missing delay is here, upstream of the split.
    z = ZIG
    if z:
        P([(ax + 8, adr.y1 + 1), (ax + 8, adr.y1 + 2), (ax + 8 - z, adr.y1 + 2),
           (ax + 8 - z, adr.y1 + 3), (ax + 7, adr.y1 + 3)], end_direction="S")
    else:
        P([(ax + 8, adr.y1 + 1), (ax + 8, adr.y1 + 2)])
    P([(dat.x1 + 1, dy + 3), (disp.x0 - 1, dy + 3)])                  # DATA
    # SWAP only has to arrive no EARLIER than the last DATA, so it is the one
    # pipe worth shortening: every cell of it is a tick of per-round drain.
    if SWAP_ROWS > 1:
        P([(dx + 5, dat.y1 + 1), (dx + 5, disp.y1 + SWAP_ROWS),
           (disp.x0 + SWCOL, disp.y1 + SWAP_ROWS),
           (disp.x0 + SWCOL, disp.y1 + 1)])
    else:                       # single row: run east under the display's floor
        P([(dx + 5, dat.y1 + 1), (disp.x0 + SWCOL, disp.y1 + 1)],
          end_direction="N")                                          # SWAP
    return g.p, dict(L=L, k=k, W=W, IH=IH,
                     ops=len(pre) + len(px) + len(tail_body) + len(tail_fin),
                     cells=len(pre) + len(px) + len(py) + len(tail_body) + len(tail_fin))


if __name__ == "__main__":
    import argparse
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--gap", type=int, default=GAP)
    ap_.add_argument("--swap-rows", type=int, default=SWAP_ROWS)
    ap_.add_argument("--spacer", type=int, default=SPACER)
    ap_.add_argument("--out", default="plotter-swar3.man")
    a_ = ap_.parse_args()
    GAP, SWAP_ROWS, SPACER = a_.gap, a_.swap_rows, a_.spacer
    p, info = build()
    out = os.path.join(HERE, a_.out)
    p.save(out)
    print(info, p.footprint())
    print(subprocess.run([sys.executable, os.path.join(HERE, "..", "..", "tools",
                                                       "grade_fast.py"), "plotter", out],
                         capture_output=True, text=True).stdout[-2000:])

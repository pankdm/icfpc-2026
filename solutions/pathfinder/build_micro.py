#!/usr/bin/env python3
"""WORK IN PROGRESS -- DOES NOT BUILD YET.

pathfinder micro-design: an O(1)-RAM solver, ported from snake's architecture.

The champion spends 67.8% of its ticks in the BFS at 4,852 ticks per cell popped
-- 12.24 scalar-RAM reads each.  This build DELETES that RAM.  All 256 board
cells live in ONE memory device (MEM16, oracle-proven standalone as
scratchpad/pf_gadgets/build_mem16.py):

  MEM16   16 little men, one 64-bit word each, 16 four-bit slots per word.
          Slot value 0 = free & unvisited, 1/2/3 = (dist mod 3)+1, 4 = wall.
          Bit 3 of every slot is always 0, so every mask (7<<sh, sh<=60) and
          every payload (t<<sh, t<=4) stays POSITIVE and the word man can
          dispatch on the SIGN of one incoming value with a single `X`.
          Transaction = three sends (q, mask, payload) and one receive
          (field<<sh).  A payload of 0 makes the word man's `| M` a no-op, so
          a read needs no second branch and cannot deadlock waiting for a value
          that never comes.  Per-round reset is ONE negative value: the hub
          broadcasts -K with `S` and every word ANDs itself with
          K = 0x4444444444444444, keeping the wall bits and clearing the tags.
          No walls plane, no copy-back, no acknowledgement handshake.

  Two tag bits suffice because the grid is bipartite: adjacent path cells differ
  in distance by exactly one, so a neighbour is at dist-1 or dist+1 and those
  differ by 2 -- non-zero mod 3.  pf_model.simulate_bitplane proves this on all
  387 public frames and on 291 random mazes.

  STATE RING   up to four scalars in a canonical order, one full lap per
               direction block, so every access is O(1) amortised (finding 2).
               BFS lap [cur, t, robot, flag]; walk lap [robot, want, flag].
               Every popped value is pushed back before any branch (finding 7).
  NB RING      a 3-deep scratch.  The neighbour address has to survive the q/sh
               arithmetic (which eats A and B) and the memory round trip, and
               MOVE needs three values reordered into the ring's canonical slot
               order, which a FIFO cannot do in place.
  FRONTIER     FIFO of (cell, tag) pairs.  Worst measured queue depth is 30
               pairs (400 random mazes + a 1500-step adversarial hill climb).
  DRIVER       snake's display driver verbatim: addr (>=0) then colour writes
               one pixel, -1 commits the frame.  Three display pipes, one lane.

BINDING.  `s` picks the nearest OUTGOING pipe and `r` the nearest INCOMING one,
Manhattan to the attached segment, reading-order ties.  Pipes here do NOT all
live on one wall (the driver hangs off the bottom), so the emitter evaluates the true 2-D binding at each candidate cell instead of using fixed column lanes.

The walk tie-break -16, +1, +16, -1 is SERVER-PROVEN; reordering it was measured
to break 4 frames.  The BFS probe order is free.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

from layout import Layout                                  # noqa: E402

GRID = 16
COLOUR = {"path": 0, "wall": 7, "flag": 9, "robot": 10}
WALK_DELTAS = (-GRID, 1, GRID, -1)      # server-proven -- DO NOT REORDER
BFS_DELTAS = (-GRID, 1, GRID, -1)
K_MASK = 0x4444444444444444


# ═══════════════════════════════════════════════════════════ MEM16 device ══
def mem16(
    L, X0, Y0, NW=16, WROW=6, WY0=6, HUBW=30, WW=14, T=8, RC=20,
    centered=False, eager_payload=False,
):
    p = L.p
    WX = X0 + HUBW + 4
    CX = WX + WW + 2

    def lrow(i):
        return Y0 + WY0 + WROW * i + 2

    def orow(i):
        return Y0 + WY0 + WROW * i + 3
    hub_h = WY0 + WROW * NW + 4
    p.room(X0, Y0, HUBW, hub_h)
    rows = [lrow(i) for i in range(NW)]

    def node_row(level, j):
        span = NW >> level
        blk = rows[j * span:(j + 1) * span]
        return (blk[0] + blk[-1]) // 2
    root = node_row(0, 0)

    def h(dx, dy, ch):
        L.put(X0 + dx, Y0 + dy, ch)
    lit = "`%d`" % K_MASK
    if centered:
        ry = root - Y0
        center_rc = HUBW - 2
        for dx, ch in enumerate(">@rX", start=1):
            h(dx, ry, ch)
        # Negative reset arm immediately above the decoder root.
        h(4, ry - 1, ">")
        for k, ch in enumerate(lit):
            h(5 + k, ry - 1, ch)
        xr = 5 + len(lit)
        h(xr, ry - 1, "N")
        h(xr + 1, ry - 1, "S")
        h(xr + 2, ry - 1, "v")
        h(xr + 2, ry + 2, "<")
        # Positive transaction arm dips below the entry and rejoins the
        # decode tree at x=7 on the root row.
        h(4, ry + 1, ">")
        h(5, ry + 1, ">")
        h(6, ry + 1, "b")
        h(7, ry + 1, "^")
        # Upper and lower leaves need distinct one-way return columns. They
        # merge into the entry from rows two cells above/below the root.
        for y in range(Y0 + 5, root - 2):
            L.put(X0 + RC, y, "v")
        h(RC, ry - 2, "<")
        h(1, ry - 2, "v")
        for y in range(root + 3, Y0 + hub_h - 1):
            L.put(X0 + center_rc, y, "^")
        h(center_rc, ry + 2, "<")
        h(1, ry + 2, "^")
    else:
        for dx, ch in enumerate(">@rX", start=1):
            h(dx, 2, ch)
        h(1, 4, "^")
        h(5, 2, "v")
        h(4, 1, ">")
        for k, ch in enumerate(lit):
            h(5 + k, 1, ch)
        xr = 5 + len(lit)
        h(xr, 1, "N")
        h(xr + 1, 1, "S")
        h(xr + 2, 1, "v")
        h(xr + 2, 4, "<")
        h(4, 3, ">")
        h(5, 3, ">")
        h(6, 3, "b")
        h(7, 3, "v")
    L.put(X0 + 7, root, ">")
    L.put(X0 + T, root, "x")
    for level in range(1, 4):
        for j in range(1 << level):
            r = node_row(level, j)
            L.put(X0 + T + 2 * (level - 1), r, ">")
            L.put(X0 + T + 2 * (level - 1) + 1, r, "]")
            L.put(X0 + T + 2 * level, r, "x")
    for i in range(NW):
        y = rows[i]
        for k, ch in enumerate(">rsrs"):
            L.put(X0 + T + 6 + k, y, ch)
    if not centered:
        for y in range(Y0 + 5, Y0 + hub_h - 1):
            L.put(X0 + RC, y, "^")
        L.put(X0 + RC, Y0 + 4, "<")

    for i in range(NW):
        top = Y0 + WY0 + WROW * i
        p.room(WX, top, WW, WROW)

        def w(dx, dy, ch, top=top):
            L.put(WX + dx, top + dy, ch)
        for dx, ch in enumerate(">@rX", start=1):
            w(dx, 2, ch)
        w(1, 4, "^")
        for dx, ch in enumerate(">N&M", start=4):
            w(dx, 1, ch)
        if eager_payload:
            # Join reset and both transaction arms only on row 5; none of
            # their horizontal walks crosses another arm's receive site.
            w(8, 1, "v")
            w(8, 2, ">")
            for dy in range(2, 5):
                w(12, dy, "v")
            w(12, 5, "<")
            w(1, 5, "^")
        else:
            w(12, 1, "v")
            w(12, 4, "<")
        if eager_payload:
            assert WROW >= 7
            # The controller has already queued the intended payload.  Branch
            # on the field locally: a non-zero field consumes and ignores it;
            # a zero field consumes and applies it before replying.
            for dx, ch in enumerate(">&sX", start=4):
                w(dx, 3, ch)
            for dx, ch in enumerate(">rv", start=7):
                w(dx, 4, ch)
            w(9, 5, "<")
            for dx, ch in enumerate("r|Mv", start=8):
                w(dx, 3, ch)
            w(11, 4, "v")
            w(11, 5, "<")
        else:
            for dx, ch in enumerate(">&sr|M", start=4):
                w(dx, 3, ch)
            w(10, 3, "v")
            w(10, 4, "<")
        p.pipe([(X0 + HUBW, lrow(i)), (WX - 1, lrow(i))])
        p.pipe([(WX + WW, orow(i)), (CX - 1, orow(i))])

    p.room(CX, Y0 + WY0, 7, WROW * NW)
    cy = orow(NW // 2)
    for dx, ch in enumerate(">@Rsv", start=1):
        L.put(CX + dx, cy, ch)
    L.put(CX + 5, cy + 1, "<")
    L.put(CX + 1, cy + 1, "^")
    return dict(hub_top=(X0 + 3, Y0), coll_top=(CX + 3, Y0 + WY0),
                right=CX + 6, bottom=Y0 + hub_h - 1)


# ═══════════════════════════════════════════════════════════════ emitter ═══
class Emit:
    def __init__(self, L, bind, xlo, xhi, forbidden):
        self.L, self.bind = L, bind
        self.xlo, self.xhi = xlo, xhi
        self.forbidden = set(forbidden)
        self.x = self.y = 0
        self.d = "E"
        self.ops = []
        self.wraps = 0

    def at(self, x, y, d="E"):
        self.x, self.y, self.d = x, y, d
        return self

    def _step(self):
        self.x += 1 if self.d == "E" else -1

    def _free(self, x, y):
        return self.L.get(x, y) == " "

    def _ok(self, x):
        return self.xlo <= x <= self.xhi and x not in self.forbidden

    def wrap(self):
        self.wraps += 1
        for x in (list(range(self.x, self.xhi + 1)) + list(range(self.x, self.xlo - 1, -1))
                  if self.d == "E" else
                  list(range(self.x, self.xlo - 1, -1)) + list(range(self.x, self.xhi + 1))):
            if self._ok(x) and self._free(x, self.y) and self._free(x, self.y + 1):
                break
        else:
            raise RuntimeError("no room to wrap on row %d" % self.y)
        self.L.put(x, self.y, "v")
        nd = "W" if self.d == "E" else "E"
        self.L.put(x, self.y + 1, "<" if nd == "W" else ">")
        self.y += 1
        self.d = nd
        self.x = x + (-1 if nd == "W" else 1)
        return self

    def _advance(self):
        while True:
            if (self.d == "E" and self.x > self.xhi) or (self.d == "W" and self.x < self.xlo):
                self.wrap(); continue
            if self._ok(self.x) and self._free(self.x, self.y):
                return
            self._step()

    def _reach(self, op, lane):
        for _ in range(14):
            x = self.x
            while self.xlo <= x <= self.xhi:
                if (self._ok(x) and self._free(x, self.y)
                        and self.bind(op, x, self.y) == lane):
                    while self.x != x:
                        self._step()
                    return
                x += 1 if self.d == "E" else -1
            self.wrap()
        raise RuntimeError("lane %s:%s unreachable from row %d" % (op, lane, self.y))

    def tok(self, t):
        if ":" in t:
            op, lane = t.split(":")
            self._reach(op, lane)
            self.ops.append((self.x, self.y, op, lane))
            self.L.put(self.x, self.y, op)
            self._step()
            return self
        self._advance()
        self.L.put(self.x, self.y, t)
        self._step()
        return self

    def seq(self, toks):
        for t in (toks.split() if isinstance(toks, str) else toks):
            self.tok(t)
        return self


# ────────────────────────────────────────────────────────────── op macros ──
C16 = "8 M + M"                        # A = 16, B = 16 (no backtick literal)
SHIP_Q = "s:H W M 4 * M 7 {"           # (A=q,B=r) -> ship q, B = sh, A = 7<<sh
NEXT_TAG = "M 3 W % M 1 +"             # t = ptag%3+1     1->2 2->3 3->1
PREV_TAG = "M 1 + M 3 W % M 1 +"       # want = (t+1)%3+1 1->3 2->1 3->2


def delta_ops(delta):
    """A = base on entry; leave A = base + delta.  NB ring must be empty."""
    if abs(delta) == 1:
        return ("M 1 N +" if delta < 0 else "M 1 +").split()
    return ["s:N"] + C16.split() + ["r:N", "-" if delta < 0 else "+"]


def txn_ops():
    """NB holds nb.  Ship q and the probe mask; leave B = sh, A = field<<sh."""
    return (C16 + " r:N s:N / " + SHIP_Q + " s:H r:C").split()


# ═══════════════════════════════════════════════════════════════ builder ═══
def build(save_to=None, MEMX=0, MEMY=12, CGAP=3, CW=58, CY0=12, CROWS=70,
          DRV_DY=6, DIS_DX=11, FR_SPAN=46, FR_ROWS=3):
    L = Layout()
    p = L.p
    mem = mem16(L, MEMX, MEMY)

    CX0 = mem["right"] + CGAP
    CX1 = CX0 + CW - 1
    IXLO, IXHI = CX0 + 1, CX1 - 1
    CBOT = CY0 + CROWS - 1
    p.room(CX0, CY0, CW, CROWS)

    # ---- pipe terminals -------------------------------------------------
    ATT = CY0 - 1                                   # top-wall attach row
    out_col = {"H": CX0 + 4, "F": CX0 + 17, "S": CX0 + 30, "N": CX0 + 43}
    in_col = {"C": CX0 + 10, "F": CX0 + 23, "S": CX0 + 36, "N": CX0 + 49,
              "I": CX0 + 54}
    DRVX = CX0 + 2
    DRV_Y = CBOT + DRV_DY
    drv_in = (DRVX - 1, DRV_Y + 2)                  # driver's left wall row
    D_COL = CX0 + 40                                # bottom-wall attach column

    def bind(op, x, y):
        if op == "s":
            cand = {k: abs(v - x) + abs(ATT - y) for k, v in out_col.items()}
            cand["D"] = abs(D_COL - x) + abs(CBOT + 1 - y)
        else:
            cand = {k: abs(v - x) + abs(ATT - y) for k, v in in_col.items()}
        best = min(cand.values())
        ties = sorted(k for k in cand if cand[k] == best)
        if len(ties) > 1:                            # reading order: top row first
            return None
        return ties[0]

    # ---- reserved columns ------------------------------------------------
    NX, HWS, HWR, HWW = IXLO, IXLO + 1, IXLO + 2, IXLO + 3
    HWT, HWM, NXE = IXHI - 2, IXHI - 1, IXHI
    FORBID = {NX, HWS, HWR, HWW, HWT, HWM, NXE}
    E = Emit(L, bind, IXLO + 4, IXHI - 3, FORBID)

    class Rows:
        def __init__(self, y):
            self.y = y

        def take(self, n=1):
            y = self.y
            self.y += n
            return y
    R = Rows(CY0 + 1)

    def block(hw=None):
        R.y = max(R.y, E.y + 1)
        y = R.take()
        if hw is None:
            E.at(E.xlo, y, "E")
        else:
            L.put(hw, y, ">")
            E.at(max(hw + 1, E.xlo), y, "E")
        return y

    def face_east():
        if E.d != "E":
            E.wrap()

    def goto(col, ch):
        """Leave the block: reach `col` on this row and turn onto the highway."""
        for _ in range(6):
            lo, hi = (E.x, col) if E.d == "E" else (col, E.x)
            if ((E.d == "E") == (col >= E.x)
                    and all(L.get(x, E.y) == " " for x in range(lo, hi + 1))):
                while E.x != col:
                    E._step()
                L.put(col, E.y, ch)
                R.y = max(R.y, E.y + 1)
                return
            E.wrap()
        raise RuntimeError("cannot goto %d from row %d" % (col, E.y))

    def branch(ch):
        """Three fresh rows: (arm-up, branch, arm-down).  Returns (bx, ya, yb, yc)."""
        face_east()
        E._advance()
        col = E.x
        while not (E._ok(col) and L.get(col, E.y) == " "
                   and col + 1 <= E.xhi + 3 and L.get(col + 1, E.y) == " "):
            col += 1
            if col > E.xhi:
                E.wrap()
                face_east()
                col = E.x
        R.y = max(R.y, E.y + 1)
        ya, yb, yc = R.take(), R.take(), R.take()
        L.put(col, E.y, "v")
        for y in range(E.y + 1, yb):
            assert L.get(col, y) == " ", "branch drop blocked at %s" % ((col, y),)
        L.put(col, yb, ">")
        bx = col + 1
        L.put(bx, yb, ch)
        E.at(bx + 1, yb, "E")
        return bx, ya, yb, yc

    def arm(bx, y, col, ch):
        step = 1 if col > bx else -1
        L.put(bx, y, ">" if step > 0 else "<")
        for xx in range(bx + step, col, step):
            assert L.get(xx, y) == " ", "arm blocked at %s" % ((xx, y),)
        L.put(col, y, ch)

    def side(bx, y, toks):
        """Emit ops westwards along an arm row, then chain to the next block."""
        L.put(bx, y, "<")
        E.at(bx - 1, y, "W")
        E.seq(toks)
        goto(NX, "v")

    # ═══════════════════════════════════════════════════════════════════
    # UNFINISHED -- see the WIP banner at the top of this file.
    # The block sequences below are DERIVED AND CHECKED BY HAND but not yet
    # emitted; each line is the exact token stream for one block.
    #
    # SETUP (man born here, runs once; branchless -- colour = 7*v and payload
    # = 4*v<<sh, and a payload of 0 is a no-op in the word man):
    #   C16 * b 0 s:S                       BP = 256, ring = [i=0]
    #  loop:
    #   r:S s:S s:D r:I s:N M 7 * s:D       addr = i, colour = 7v
    #   C16 r:S s:S / SHIP_Q s:H r:C        ship q, mask; read+discard field
    #   r:N { M 4 * s:H                     payload = (4v)<<sh   (B = sh)
    #   r:S M 1 + s:S m d                   i++, BP--, loop while BP > 0
    #  tail:
    #   r:I s:N r:I M 4 W { M r:N + s:N     robot = 16*ry + rx, parked in NB
    #   s:D 5 M + s:D 1 N s:D               draw the robot, commit frame 1
    #   r:S r:N s:S                         ring = [robot]
    #
    # ROUND (also the jump target from MOVE when the robot reaches the flag):
    #   r:I s:N r:I M 4 W { M r:N + s:N s:S   flag -> NB and ring [robot, flag]
    #   1 N s:H                               reset the plane (hub broadcasts -K)
    #   C16 r:N s:N / SHIP_Q s:H r:C 1 { s:H  tag[flag] = 1
    #   r:N s:N s:D 9 s:D                     draw the flag (no commit)
    #   r:N s:F 1 s:F                         frontier <- (flag, 1)
    #
    # BFS POP (ring [robot, flag] -> [cur, t, robot, flag]):
    #   r:F s:S r:F NEXT_TAG s:S r:S s:S r:S s:S
    #
    # BFS DIRECTION BLOCK, one per delta, ring lap [cur, t, robot, flag]:
    #   r:S s:S  delta_ops(delta)  s:N  txn_ops()      -> A = field<<sh, B = sh
    #   X   A>0 (busy, clockwise arm):
    #         0 s:H r:S s:S r:S s:S r:S s:S r:N        keep the ring intact
    #       A==0 (free, straight on):
    #         r:S s:S { s:H } M r:N s:F W s:F W M      payload, push (nb, t)
    #         r:S s:S - M r:S s:S W                    A = robot - nb
    #         X  ==0 -> the robot is reached, jump to WALK; else next direction
    #
    # WALK TRANSITION ([cur,t,robot,flag] -> [robot, want, flag]):
    #   r:S  r:S PREV_TAG s:S  r:S s:N  r:S s:S  r:N s:S     (see the notes)
    #
    # WALK PROBE, one per WALK_DELTAS entry, ring lap [robot, want, flag]:
    #   r:S s:S  delta_ops(delta)  s:N  txn_ops()
    #   r:S s:S { M  r:S s:S                       B = want<<sh, ring restored
    #   ~ M 0 s:H W                                A = field^want (payload 0)
    #   X  ==0 -> MATCH (jump to MOVE, nb still parked in NB)
    #      else -> r:N (drop nb) and fall into the next probe
    #
    # MOVE (ring [robot, want, flag], NB = [nb]; NB is used 3-deep here):
    #   r:S s:D 0 s:D                              old cell -> path colour
    #   r:N s:N s:D 5 M + s:D 1 N s:D              new cell -> robot, commit
    #   r:S PREV_TAG s:N   r:S s:N                 want' and flag into NB
    #   r:N M s:S  r:N s:S  r:N s:S                ring = [nb, want', flag]
    #   -                                          A = flag - nb
    #   X  ==0 -> ROUND (the robot stands on the flag) ; else -> next walk step
    #
    # Still to write: the ring relay rooms + pipes (STATE cap>=5, NB cap>=4,
    # FRONTIER cap>=110 values folded into the band), snake's DRIVER block and
    # the 18x18 display, the input room, and the highway wiring.
    raise NotImplementedError("controller blocks not emitted yet")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "micro.man")
    prog = build(save_to=path)
    print("saved", path, prog.footprint())

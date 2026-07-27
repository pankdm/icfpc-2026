#!/usr/bin/env python3
"""subset-sum: streamed meet-in-the-middle "chain field".

Idea (measured alternative to the 2^20 brute-force parallel field, which spends
~200 ticks per enumerated mask because every worker walks a pipe-RAM belt):

  * indices 0..NV-1 have lexicographic bit weight 2^(NV-1-i); the answer is the
    subset with the LARGEST such mask (proof: {0,4} beats {1,3} iff 10001 > 01010).
  * split the mask into a P-bit prefix (indices 0..P-1) and a C-bit suffix
    (indices P..NV-1), C = NV - P.
  * one worker per prefix value w (2^P of them).  Worker w holds  B = t - P_w
    where P_w = sum of the prefix values it selects.  That is its ONLY state.
  * a chain of C stages enumerates every suffix mask in DESCENDING order and
    emits the suffix sum S.  Stage k owns value v_{P+k} and toggles its bit
    every 2^(C-1-k) steps -- a ripple counter made of men.
  * a counter room emits c = suffix_mask + 1 (2^C .. 1, then 0 = terminator).
  * merger interleaves (c, S) and pushes the pair down a daisy chain of the
    workers; each worker forwards the pair to the next, so the whole field sees
    every pair with no fan-out tree at all.
  * worker: r c / forward / b (BP=c) / d (c==0 -> terminator) / r S / forward /
    - / X.  Three ops per mask, B never clobbered.  On a match BP already holds
    c, so the answer mask is recovered for free.
  * winners report msg = w*2^C + c = mask20 + 1; losers report 0.  The reduce
    runs back down the same daisy chain and the highest w with a nonzero msg
    wins, which is exactly the lexicographic rule.
  * the resolver walks mask20 from the top bit, pulls the values out of a delay
    line in index order, pushes the selected ones into a hold pipe, then `q`
    counts them to produce k.  Padded slots hold 0 and are dropped by v>0.

Everything is parameterised by NV/P so a scaled-down machine (NV=6, P=2) can be
exercised on hand-written cases before building the real NV=20 one.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from littleman import Program
from layout import auto_pipe


class Room:
    """Interior-relative cell canvas; emits an absolute room when placed."""

    def __init__(self, name):
        self.name = name
        self.cells = {}
        self.man = None

    def put(self, x, y, ch):
        if self.cells.get((x, y)) == "." and ch != ".":
            del self.cells[(x, y)]
        if (x, y) in self.cells and self.cells[(x, y)] != ch:
            raise ValueError(
                f"{self.name}: cell ({x},{y}) already {self.cells[(x,y)]!r}, want {ch!r}"
            )
        self.cells[(x, y)] = ch

    def run(self, x, y, s, d="E"):
        dx, dy = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}[d]
        for i, ch in enumerate(s):
            if ch != "\0":
                self.put(x + i * dx, y + i * dy, ch)
        return (x + len(s) * dx, y + len(s) * dy)

    def set_man(self, x, y):
        self.man = (x, y)

    def size(self):
        w = max(x for x, _ in self.cells) + 1
        h = max(y for _, y in self.cells) + 1
        return w, h


def lint_room(room):
    """The oracle rejects a backtick pair INSIDE one room whose span is not all
    digits/spaces ("expected a digit or a space between backticks").  The Rust
    engine silently treats such a pair as "not a literal", so this only shows up
    as a submission load error -- check it at build time instead."""
    w, h = room.size()

    def at(x, y):
        return room.cells.get((x, y), " ")

    def scan(cells, label):
        ticks = [i for i, c in enumerate(cells) if c == "`"]
        i = 0
        while i + 1 < len(ticks):
            a, b = ticks[i], ticks[i + 1]
            span = cells[a + 1:b]
            if any(c != " " and not c.isdigit() for c in span):
                raise ValueError("%s: dirty backtick pair %s %d..%d %r"
                                 % (room.name, label, a, b, "".join(span)))
            i += 2

    for x in range(w):
        scan([at(x, y) for y in range(h)], "col %d" % x)
    for y in range(h):
        scan([at(x, y) for x in range(w)], "row %d" % y)


def lit(v, width=None):
    """Backtick literal for a non-negative int, optionally zero-padded."""
    s = str(v)
    if width is not None:
        s = s.rjust(width, "0")
    return "`" + s + "`"


class Machine:
    """Places rooms at absolute positions and wires pipes."""

    def __init__(self):
        self.p = Program()
        self.placed = {}

    def place(self, room, ox, oy):
        lint_room(room)
        w, h = room.size()
        self.p.room(ox, oy, w + 2, h + 2)
        for (x, y), ch in room.cells.items():
            self.p.put(ox + 1 + x, oy + 1 + y, ch)
        if room.man:
            self.p.put(ox + 1 + room.man[0], oy + 1 + room.man[1], "@")
        rect = (ox, oy, ox + w + 1, oy + h + 1)
        self.placed[room.name] = rect
        return rect


# ---------------------------------------------------------------- worker tile

def worker_room(name, w, P, C):
    """One prefix worker.  Fixed shape for every w (variable parts are padded).

    Exactly one incoming pipe (from the previous worker / merger) and one
    outgoing pipe (to the next worker / resolver), so `r` and `s` are never
    ambiguous.  The reduce rides the same chain FORWARD after the terminator:
    each worker emits its own msg if nonzero, else forwards what it got, so the
    value leaving the last worker is the msg of the highest w that matched.
    """
    lit_w = len(str((2 ** P - 1) * (2 ** C)))
    TERMCOL = max(15, lit_w + 6)
    IW = TERMCOL + 6

    r = Room(name)

    # ---- INIT: r s (+M | ..) per prefix bit, then r s - M for t
    seq = []
    for i in range(P):
        sel = (w >> (P - 1 - i)) & 1
        seq += ["r", "s", "+", "M"] if sel else ["r", "s", ".", "."]
    seq += ["r", "s", "-", "M"]
    per_row = IW - 2
    rows = (len(seq) + per_row - 1) // per_row
    seq += ["."] * (rows * per_row - len(seq))

    for j in range(rows):
        chunk = seq[j * per_row:(j + 1) * per_row]
        if j % 2 == 0:                                   # eastbound
            if j == 0:
                r.set_man(0, 0)
                r.put(0, 0, "@")
            else:
                r.put(0, j, ">")
            for i, ch in enumerate(chunk):
                r.put(1 + i, j, ch)
            r.put(IW - 1, j, "v")
        else:                                            # westbound
            r.put(IW - 1, j, "<")
            for i, ch in enumerate(chunk):
                r.put(IW - 2 - i, j, ch)
            r.put(0, j, "v")

    rr = rows                                            # routing row
    if (rows - 1) % 2 == 0:
        r.put(IW - 1, rr, "<")
        for x in range(2, IW - 1):
            r.put(x, rr, ".")
        r.put(1, rr, "v")
    else:
        r.put(0, rr, ">")
        r.put(1, rr, "v")

    h0 = rr + 1
    h1, h2, h3, h4 = h0 + 1, h0 + 2, h0 + 3, h0 + 4
    h5, h6, h7, h8, h9 = h0 + 5, h0 + 6, h0 + 7, h0 + 8, h0 + 9

    # ---- HOT loop: r c / fwd / BP=c / d / r S / fwd / - / X
    r.run(1, h0, ">rsbd")
    for x in range(6, TERMCOL):
        r.put(x, h0, ".")
    r.put(TERMCOL, h0, "v")
    r.put(5, h1, "<"); r.put(4, h1, "r"); r.put(3, h1, "s")
    r.put(2, h1, "-"); r.put(1, h1, "X")
    r.put(0, h1, "v")
    # A<0 return: east along h2, north past h1/h0 into the routing row, west home
    r.put(1, h2, ">")
    for x in range(2, 6):
        r.put(x, h2, ".")
    r.put(6, h2, "^"); r.put(6, h1, "."); r.put(6, h0, ".")
    r.put(6, rr, "<")
    for x in range(2, 6):
        if (x, rr) not in r.cells:
            r.put(x, rr, ".")
    r.put(0, h2, "v")

    # ---- TERM (no match): read+forward S, msg = 0
    r.put(TERMCOL, h1, "r")
    r.put(TERMCOL, h2, "s")
    r.put(TERMCOL, h3, "0")
    r.put(TERMCOL, h4, ".")
    r.put(TERMCOL, h5, ".")

    # ---- DRAIN (matched): keep forwarding pairs until c == 0
    r.run(0, h3, ">rsX")
    r.put(3, h4, "<"); r.put(2, h4, "r"); r.put(1, h4, "s"); r.put(0, h4, "^")
    r.run(4, h3, "rs")

    # ---- EXTRACT: BP (= c) -> A by unary counting
    r.run(6, h3, "1M0")
    r.run(9, h3, ">+md")                                 # loop entry must re-face
    r.put(12, h4, "<"); r.put(11, h4, "."); r.put(10, h4, ".")
    r.put(9, h4, "^")
    r.put(13, h3, "M")
    r.put(14, h3, "v"); r.put(14, h4, "v"); r.put(14, h5, "<")
    for x in range(1, 14):
        r.put(x, h5, ".")
    r.put(0, h5, "v")

    # ---- msg = w*2^C + c
    r.put(0, h6, ">")
    x, _ = r.run(1, h6, lit(w * (2 ** C), lit_w))
    r.put(x, h6, "+")
    for xx in range(x + 1, TERMCOL):
        r.put(xx, h6, ".")
    r.put(TERMCOL, h6, "v")

    # ---- REDUCE (forward): own if nonzero else pass through
    r.put(TERMCOL, h7, ">")
    r.put(TERMCOL + 1, h7, "X")
    r.put(TERMCOL + 1, h8, "s")
    r.put(TERMCOL + 1, h9, "H")
    r.put(TERMCOL + 1, h6, "H")
    r.put(TERMCOL + 2, h7, "r")
    r.put(TERMCOL + 3, h7, "s")
    r.put(TERMCOL + 4, h7, "H")
    r.put(IW - 1, h9, ".")
    return r, dict(IW=IW, IH=h9 + 1, TERMCOL=TERMCOL)


def snake(room, x0, y0, width, seq, man=False):
    """Lay a linear instruction run boustrophedon in cols x0..x0+width-1.

    Items longer than one character are ATOMIC (backtick literals must not be
    split across a row turn); a group that does not fit is pushed to the next
    row and the tail of the current row padded with nops."""
    per = width - 2
    lines, cur = [], []
    for item in seq:
        if len(cur) + len(item) > per:
            cur += ["."] * (per - len(cur))
            lines.append(cur)
            cur = []
        cur += list(item)
    cur += ["."] * (per - len(cur))
    lines.append(cur)
    for j, chunk in enumerate(lines):
        if j % 2 == 0:
            if j == 0 and man:
                room.set_man(x0, y0)
                room.put(x0, y0, "@")
            else:
                room.put(x0, y0 + j, ">")
            for i, ch in enumerate(chunk):
                room.put(x0 + 1 + i, y0 + j, ch)
            room.put(x0 + width - 1, y0 + j, "v")
        else:
            room.put(x0 + width - 1, y0 + j, "<")
            for i, ch in enumerate(chunk):
                room.put(x0 + width - 2 - i, y0 + j, ch)
            room.put(x0, y0 + j, "v")
    exit_col = x0 + width - 1 if (len(lines) - 1) % 2 == 0 else x0
    return exit_col, y0 + len(lines)


def route_to(room, x, y, tx, ty=None):
    """Man lands on (x,y) heading south; walk him to (tx,ty) heading south.

    Uses row y as a horizontal lane and column tx to descend."""
    if x == tx:
        room.put(x, y, "v")
        return
    step = 1 if tx > x else -1
    room.put(x, y, ">" if step > 0 else "<")
    for cx in range(x + step, tx, step):
        room.put(cx, y, ".")
    room.put(tx, y, "v")


# ------------------------------------------------------------- support rooms
# Every room below documents which pipe each `r`/`s` must bind to; check_binds()
# in the assembly step verifies the nearest-pipe choice against those labels.


def dist_room(NV):
    """Read n, then n values (0-padded to NV), then t; `S` each to all consumers.

    pipes: in = INPUT.  out = {source, counter, valstore} (S -> no ambiguity).
    """
    r = Room("dist")
    r.set_man(0, 0)
    r.put(0, 0, "@"); r.put(1, 0, "r"); r.put(2, 0, "b"); r.put(3, 0, "v")
    r.put(3, 1, "<"); r.put(2, 1, "."); r.put(1, 1, "."); r.put(0, 1, "v")
    y = 2
    for i in range(NV):
        if i < 10:                                   # n >= 10, always present
            r.put(0, y, ">"); r.put(1, y, "r"); r.put(2, y, "m")
            r.put(3, y, "S"); r.put(4, y, "v")
            r.put(4, y + 1, "<")
            for x in (3, 2, 1):
                r.put(x, y + 1, ".")
            r.put(0, y + 1, "v")
            y += 2
        else:                                        # d: BP>0 -> read, else 0
            r.put(0, y, ">"); r.put(1, y, "d")
            r.put(2, y, "0"); r.put(3, y, "."); r.put(4, y, "v")
            r.put(1, y + 1, ">"); r.put(2, y + 1, "r"); r.put(3, y + 1, "m")
            r.put(4, y + 1, "v")
            r.put(4, y + 2, "S")
            r.put(4, y + 3, "<")
            for x in (3, 2, 1):
                r.put(x, y + 3, ".")
            r.put(0, y + 3, "v")
            y += 4
    r.put(0, y, ">"); r.put(1, y, "r"); r.put(2, y, "S"); r.put(3, y, "H")
    return r


def counter_room(P, NV, C):
    """Forward v_0..v_(P-1) and t to the merger, then emit 2^C..1 then 0.

    pipes: in = dist.  out = merger.
    """
    r = Room("counter")
    seq = []
    for _ in range(P):
        seq += ["r", "s"]
    seq += ["r"] * (NV - P)
    seq += ["r", "s"]                                # t
    seq += ["1", "M", lit(2 ** C)]
    col, ny = snake(r, 0, 0, 16, seq, man=True)
    route_to(r, col, ny, 0, 0)
    y = ny + 1
    r.put(0, y, ">"); r.put(1, y, "s"); r.put(2, y, "-"); r.put(3, y, "X")
    r.put(3, y + 1, "<"); r.put(2, y + 1, "."); r.put(1, y + 1, ".")
    r.put(0, y + 1, "^")
    r.put(4, y, "s"); r.put(5, y, "H")
    return r


def source_room(P, NV):
    """Drop the prefix values, forward the C chain values, drop t, emit 0s.

    pipes: in = dist.  out = stage0.
    """
    r = Room("source")
    seq = ["r"] * P
    for _ in range(NV - P):
        seq += ["r", "s"]
    seq += ["r"]                                     # t
    col, ny = snake(r, 0, 0, 16, seq, man=True)
    route_to(r, col, ny, 0, 0)
    y = ny + 1
    r.put(0, y, ">"); r.put(1, y, "0"); r.put(2, y, "s"); r.put(3, y, "v")
    r.put(3, y + 1, "<"); r.put(2, y + 1, "."); r.put(1, y + 1, ".")
    r.put(0, y + 1, "^")
    return r


def stage_room(k, C):
    """Chain stage k: B = v_(P+k); its bit is on for 2^(C-1-k) steps, then off.

    Three literals (init / ON->OFF reload / OFF->ON reload) live in disjoint
    column ranges so no in-room vertical backtick pair is ever dirty.
    pipes: in = previous stage (or source).  out = next stage (or merger).
    """
    p = 2 ** (C - 1 - k)
    LP = lit(p)
    L = len(LP)
    DOWN = 8 + L                                     # ON->OFF descent column
    FR = 10 + L                                      # OFF->ON ascent column
    IC = FR + 2                                      # init literal column
    W = IC + L + 3

    r = Room("stage%d" % k)
    seq = ["r", "M"] + ["r", "s"] * (C - 1 - k)
    col, ny = snake(r, 0, 0, W, seq, man=True)
    route_to(r, col, ny, FR + 1)
    ir = ny + 1                                      # init row
    up = ir + 1
    m0 = up + 1
    o0 = m0 + 3

    # init: BP = p, then fall into the shared west lane -> ON entry
    r.put(FR + 1, ir, ">")
    x = FR + 2
    for ch in LP:
        r.put(x, ir, ch); x += 1
    r.put(x, ir, "b"); r.put(x + 1, ir, "v")
    lane_end = x + 1
    r.put(lane_end, up, "<")
    r.put(FR, up, "<")
    for cx in range(lane_end - 1, 1, -1):
        if (cx, up) not in r.cells:
            r.put(cx, up, ".")
    r.put(1, up, "v")

    # ON loop
    r.put(1, m0, ">"); r.put(2, m0, "r"); r.put(3, m0, "+")
    r.put(4, m0, "s"); r.put(5, m0, "m"); r.put(6, m0, "d")
    r.put(6, m0 + 1, "<")
    for cx in (5, 4, 3, 2):
        r.put(cx, m0 + 1, ".")
    r.put(1, m0 + 1, "^")
    x = 7
    for ch in LP:
        r.put(x, m0, ch); x += 1
    r.put(x, m0, "b"); r.put(DOWN, m0, "v")
    r.put(DOWN, m0 + 1, "v"); r.put(DOWN, m0 + 2, "<")
    for cx in range(DOWN - 1, 1, -1):
        r.put(cx, m0 + 2, ".")
    r.put(1, m0 + 2, "v")

    # OFF loop
    r.put(1, o0, ">"); r.put(2, o0, "r"); r.put(3, o0, "s")
    r.put(4, o0, "m"); r.put(5, o0, "d")
    r.put(5, o0 + 1, "<")
    for cx in (4, 3, 2):
        r.put(cx, o0 + 1, ".")
    r.put(1, o0 + 1, "^")
    x = 6
    for ch in LP:
        r.put(x, o0, ch); x += 1
    r.put(x, o0, "b"); x += 1
    for cx in range(x, FR):
        r.put(cx, o0, ".")
    r.put(FR, o0, "^")
    r.put(FR, o0 - 1, "."); r.put(FR, o0 - 2, "."); r.put(FR, o0 - 3, ".")
    return r


def merger_room(P):
    """Forward P+1 init values from the counter, then interleave (c, S) pairs.

    pipes: in = counter (TOP wall, col 1), chain (BOTTOM wall, col 2).
           out = worker 0.
    """
    r = Room("merger")
    seq = ["r", "s"] * (P + 1)
    col, ny = snake(r, 0, 0, 14, seq, man=True)
    route_to(r, col, ny, 0, 0)
    L = ny + 1
    r.put(0, L, ">"); r.put(1, L, "r"); r.put(2, L, "s"); r.put(3, L, "X")
    r.put(3, L + 1, "v")
    r.put(3, L + 2, "<"); r.put(2, L + 2, "r"); r.put(1, L + 2, "s")
    r.put(0, L + 2, "^"); r.put(0, L + 1, "^")
    r.put(4, L, "r"); r.put(5, L, "s")
    r.put(6, L, "0"); r.put(7, L, "s"); r.put(8, L, "H")
    return r


def valstore_room(NV):
    """Wait for the winner msg, forward it, then forward the NV stored values.

    pipes: in = worker-last (TOP wall, col 1), dist (BOTTOM wall, col 1).
           out = resolver.
    """
    r = Room("valstore")
    r.set_man(0, 0)
    r.put(0, 0, "@"); r.put(1, 0, "r"); r.put(2, 0, "s")
    x = 3
    for ch in lit(NV):
        r.put(x, 0, ch); x += 1
    r.put(x, 0, "b"); r.put(x + 1, 0, "v")
    r.put(x + 1, 1, "<")
    for cx in range(x, 0, -1):
        r.put(cx, 1, ".")
    r.put(0, 1, "v"); r.put(0, 2, "v"); r.put(0, 3, "v")
    r.put(0, 4, ">"); r.put(1, 4, "r"); r.put(2, 4, "s")
    r.put(3, 4, "m"); r.put(4, 4, "d"); r.put(5, 4, "H")
    r.put(4, 5, "<"); r.put(3, 5, "."); r.put(2, 5, "."); r.put(1, 5, ".")
    r.put(0, 5, "^")
    return r


def cnt_room(NV):
    """Count nonzero picks, forward them, then emit k down the second pipe.

    pipes: in = resolver.  out = vals (TOP wall, col 3), k (BOTTOM wall, col 7).
    """
    r = Room("cnt")
    seq = ["0", "M", lit(NV), "b"]
    col, ny = snake(r, 0, 0, 12, seq, man=True)
    route_to(r, col, ny, 0, 0)
    L = ny + 1
    r.put(0, L, ">"); r.put(1, L, "r"); r.put(2, L, "X")
    for cx in range(3, 7):
        r.put(cx, L, ".")
    r.put(7, L, "v")
    r.put(2, L + 1, ">"); r.put(3, L + 1, "s"); r.put(4, L + 1, "1")
    r.put(5, L + 1, "+"); r.put(6, L + 1, "M"); r.put(7, L + 1, "v")
    r.put(7, L + 2, "m"); r.put(7, L + 3, "d")
    for cx in range(6, 0, -1):
        r.put(cx, L + 3, ".")
    r.put(0, L + 3, "^"); r.put(0, L + 2, "^"); r.put(0, L + 1, "^")
    r.put(7, L + 4, "W"); r.put(7, L + 5, "s"); r.put(7, L + 6, "H")
    return r


def hold_room():
    """Emit k, then drain exactly k held values into the output room.

    pipes: in = k (TOP wall, col 1), vals (BOTTOM wall, col 2).  out = OUTPUT.
    """
    r = Room("hold")
    r.set_man(0, 0)
    r.put(0, 0, "@"); r.put(1, 0, "r"); r.put(2, 0, "b"); r.put(3, 0, "s")
    r.put(4, 0, "v")
    r.put(4, 1, "<"); r.put(3, 1, "."); r.put(2, 1, "."); r.put(1, 1, ".")
    r.put(0, 1, "v"); r.put(0, 2, "v"); r.put(0, 3, "v")
    r.put(0, 4, ">"); r.put(1, 4, "d"); r.put(2, 4, "H")
    r.put(1, 5, ">"); r.put(2, 5, "r"); r.put(3, 5, "s"); r.put(4, 5, "m")
    r.put(5, 5, "v")
    r.put(5, 6, "<"); r.put(4, 6, "."); r.put(3, 6, "."); r.put(2, 6, ".")
    r.put(1, 6, "."); r.put(0, 6, "^"); r.put(0, 5, "^")
    return r


def sink_room(P):
    """Swallow the broadcast stream leaving the last worker; forward only the
    final reduce value.  pipes: in = last worker.  out = valstore."""
    r = Room("sink")
    col, ny = snake(r, 0, 0, 12, ["r"] * (P + 1), man=True)
    route_to(r, col, ny, 0, 0)
    L = ny + 1
    r.put(0, L, ">"); r.put(1, L, "r"); r.put(2, L, "X")
    r.put(2, L + 1, "<"); r.put(1, L + 1, "r"); r.put(0, L + 1, "^")
    r.put(3, L, "r"); r.put(4, L, "r"); r.put(5, L, "s"); r.put(6, L, "H")
    return r


def resolver_room(NV):
    """msg -> mask20, then walk the top bit down, pairing each bit with the
    matching value pulled from the delay line, and emit v (picked) or 0.

    pipes: in = valstore.  out = cnt.
    """
    r = Room("resolver")
    # prologue: A = msg; msg>0 -> A = msg-1, msg==0 -> A stays 0
    r.set_man(0, 0)
    r.put(0, 0, "@"); r.put(1, 0, "r"); r.put(2, 0, "X")
    for x in range(3, 8):
        r.put(x, 0, ".")
    r.put(8, 0, "v"); r.put(8, 1, "v"); r.put(8, 2, "v"); r.put(8, 3, "<")
    r.put(2, 1, "v")
    r.put(2, 2, ">"); r.put(3, 2, "M"); r.put(4, 2, "1"); r.put(5, 2, "W")
    r.put(6, 2, "-"); r.put(7, 2, "v")
    r.put(7, 3, "<")
    for x in range(6, 0, -1):
        r.put(x, 3, ".")
    r.put(0, 3, "v")

    for i in range(NV):
        y0, y1, y2, y3 = 4 + 4 * i, 5 + 4 * i, 6 + 4 * i, 7 + 4 * i
        L = lit(2 ** (NV - 1 - i))
        cx = len(L) + 4
        r.put(0, y0, "v")
        r.put(0, y1, ">"); r.put(1, y1, "M")
        for j, ch in enumerate(L):
            r.put(2 + j, y1, ch)
        r.put(2 + len(L), y1, "W"); r.put(3 + len(L), y1, "-")
        r.put(cx, y1, "X")
        r.put(cx + 1, y1, "v")
        # bit = 0  (rem < L): restore, drop the value, emit 0
        r.run(cx, y0, ">+Mr0sWv")
        # bit = 1  (rem >= L): keep rem-L, emit the value
        r.run(cx, y2, ">>MrsW")
        r.put(cx + 6, y2, ".")
        r.put(cx + 7, y2, "v")
        r.put(cx + 7, y1, ".")
        # join lane
        r.put(cx + 7, y3, "<")
        for x in range(cx + 6, 0, -1):
            r.put(x, y3, ".")
        r.put(0, y3, "H" if i == NV - 1 else "v")
    # the 20 literals stack in the same columns; blank the nop filler so every
    # in-room vertical backtick pair spans spaces only (an empty literal)
    for k, v in list(r.cells.items()):
        if v == ".":
            r.cells[k] = " "
    return r


# ------------------------------------------------------------------- assembly

def build(NV=20, P=8, G=None):
    """Two strips flanking the worker field, so no long pipe has to cross another.

      LEFT strip : input, dist, counter, merger, stage(C-1)..stage0, source
      FIELD      : the 2^P workers, boustrophedon, daisy-chained
      RIGHT strip: valstore, resolver, cnt, hold, output
    """
    C = NV - P
    NW = 2 ** P
    m = Machine()
    p = m.p

    rooms = {"dist": dist_room(NV), "counter": counter_room(P, NV, C),
             "merger": merger_room(P), "source": source_room(P, NV),
             "valstore": valstore_room(NV), "resolver": resolver_room(NV),
             "cnt": cnt_room(NV), "hold": hold_room(), "sink": sink_room(P)}
    for k in range(C):
        rooms["stage%d" % k] = stage_room(k, C)

    def outer(n):
        w, h = rooms[n].size()
        return w + 2, h + 2

    # worker grid: rows must be ODD so the last worker sits at the RIGHT end
    w0, _ = worker_room("w0", 0, P, C)
    WW, WH = w0.size()[0] + 2, w0.size()[1] + 2
    CW, CH = WW + 4, WH + 4
    if G is None:
        best, G = None, 1
        for g in range(1, NW + 1):
            rr = -(-NW // g)
            cost = max(g * CW, rr * CH) * (g * CW + rr * CH)
            if best is None or cost < best:
                best, G = cost, g
    Rr = -(-NW // G)

    STRIP_X = 14
    GAP = 4
    left = ["dist", "counter", "merger"] + ["stage%d" % k for k in range(C - 1, -1, -1)] + ["source"]
    right = ["sink", "valstore", "resolver", "cnt", "hold"]

    pos = {}
    y = 14
    lw = 0
    inp = p.input_room(STRIP_X, 8)
    for n in left:
        w, h = outer(n)
        pos[n] = (STRIP_X, y)
        m.place(rooms[n], STRIP_X, y)
        lw = max(lw, w)
        y += h + GAP

    FIELD_X = STRIP_X + lw + 14
    FIELD_Y = 12

    def wpos(i):
        col, row = divmod(i, Rr)
        if col % 2:
            row = Rr - 1 - row
        return FIELD_X + col * CW, FIELD_Y + row * CH

    for i in range(NW):
        wr, _ = worker_room("w%d" % i, i, P, C)
        x, yy = wpos(i)
        pos["w%d" % i] = (x, yy)
        m.place(wr, x, yy)

    RX = FIELD_X + G * CW + 12
    y = 12
    rw = 0
    for n in right:
        w, h = outer(n)
        pos[n] = (RX, y)
        m.place(rooms[n], RX, y)
        rw = max(rw, w)
        y += h + GAP
    out_x = RX + outer("hold")[0] + 5
    outp = p.output_room(out_x, pos["hold"][1])

    def R(n):
        x0, y0 = pos[n]
        w, h = outer(n)
        return x0, y0, x0 + w - 1, y0 + h - 1

    def straight(pts):
        p.pipe(pts)

    def down(a, b, col):
        straight([(col, R(a)[3] + 1), (col, R(b)[1] - 1)])

    def up(a, b, col):
        straight([(col, R(a)[1] - 1), (col, R(b)[3] + 1)])

    dx0, dy0, dx1, dy1 = R("dist")
    sx0, sy0, sx1, sy1 = R("source")
    vx0, vy0, vx1, vy1 = R("valstore")
    rx0, ry0, rx1, ry1 = R("resolver")
    cx0, cy0, cx1, cy1 = R("cnt")
    hx0, hy0, hx1, hy1 = R("hold")
    mx0, my0, mx1, my1 = R("merger")
    fx, fy = wpos(0)
    lx, ly = wpos(NW - 1)

    # ---- left strip
    straight([(STRIP_X + 1, 11), (STRIP_X + 1, dy0 - 1)])
    down("dist", "counter", dx0 + 1)
    down("counter", "merger", mx0 + 2)
    up("source", "stage0", sx0 + 2)
    for k in range(C - 1):
        up("stage%d" % k, "stage%d" % (k + 1), R("stage%d" % k)[0] + 2)
    up("stage%d" % (C - 1), "merger", mx0 + 3)
    straight([(dx0 - 1, dy0 + 4), (6, dy0 + 4), (6, sy0 + 4), (sx0 - 1, sy0 + 4)])

    # ---- right strip
    down("valstore", "resolver", vx0 + 1)
    down("resolver", "cnt", rx0 + 2)
    straight([(cx0 + 8, cy1 + 1), (cx0 + 8, cy1 + 2), (hx0 + 2, cy1 + 2),
              (hx0 + 2, hy0 - 1)])                                # k
    straight([(cx0 + 4, cy0 - 1), (cx0 + 4, cy0 - 3), (RX + rw + 8, cy0 - 3),
              (RX + rw + 8, hy1 + 3), (hx0 + 3, hy1 + 3),
              (hx0 + 3, hy1 + 1)])                                # values
    straight([(hx1 + 1, hy0 + 1), (out_x - 1, hy0 + 1)])

    # ---- crossings
    # dist -> valstore: out west, up over everything on row 2, down the far right
    straight([(dx0 - 1, dy0 + 2), (2, dy0 + 2), (2, 2), (RX + rw + 4, 2),
              (RX + rw + 4, vy1 + 2), (vx0 + 2, vy1 + 2), (vx0 + 2, vy1 + 1)])
    # merger -> worker 0 (top-left of the field)
    straight([(mx1 + 1, my0 + 2), (FIELD_X - 6, my0 + 2), (FIELD_X - 6, fy + 3),
              (fx - 1, fy + 3)])
    # last worker (bottom-right) -> sink -> valstore top
    kx0, ky0, kx1, ky1 = R("sink")
    straight([(lx + WW, ly + 5), (RX - 5, ly + 5), (RX - 5, ky0 + 2),
              (kx0 - 1, ky0 + 2)])
    straight([(kx0 + 6, ky1 + 1), (kx0 + 6, ky1 + 2), (vx0 + 2, ky1 + 2),
              (vx0 + 2, vy0 - 1)])

    # ---- worker daisy chain (column-major serpentine)
    for i in range(NW - 1):
        x, yy = wpos(i)
        nx, ny = wpos(i + 1)
        if nx == x:
            if ny > yy:
                straight([(x + 3, yy + WH), (x + 3, ny - 1)])
            else:
                straight([(x + 3, yy - 1), (x + 3, ny + WH)])
        else:
            straight([(x + WW, yy + 3), (nx - 1, yy + 3)])
    return m


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--nv", type=int, default=20)
    ap.add_argument("--p", type=int, default=8)
    ap.add_argument("--g", type=int, default=None)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    m = build(a.nv, a.p, a.g)
    txt = m.p.render()
    fp = m.p.footprint()
    path = a.out or os.path.join(HERE, "chainfield.man")
    open(path, "w").write(txt + "\n")
    print(path, fp)


if __name__ == "__main__":
    main()

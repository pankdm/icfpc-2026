"""Reusable littleman helpers discovered while building the `memory` solution.

Proposed for promotion into tools/littleman.py (PATTERNS section):

  * Cur           - a walking cursor that places instructions along a heading and
                    emits turn glyphs, for laying out a man's linear/branching path.
  * build_memory  - the full 100-cell addressable-memory machine (circulating belt).

KEY REUSABLE FACTS pinned against the oracle while building this:
  * Blank interior cells are NO-OPs ('.'/space => "continue straight"), so a man
    glides through empty room space; you only place instructions + turn arrows.
  * s/r pick the nearest same-direction pipe by Manhattan distance; the vertical
    component cancels, so **pipe selection depends only on the instruction's COLUMN**
    relative to the pipes' attach columns. This lets you write a normal 2D program
    with just "column discipline" instead of routing the man adjacent to each pipe.
  * `X` turns CW if A>0, CCW if A<0, STRAIGHT only if A==0 (A<0 is a turn, not straight).
  * Self-loop pipes are illegal ("must connect two different rooms"); a circulating
    storage belt therefore needs a Gate room + a Relay room + two pipes.
  * A storage "belt" (FIFO pipe loop) that the gate pumps one value at a time is a
    workable RAM substitute: gate r's a value, optionally rewrites it, s's it back.
    Values only move when the gate pumps them, so ordering is fully deterministic.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import littleman as lm

ARROW = {"E": ">", "W": "<", "N": "^", "S": "v"}
DXY = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}


class Cur:
    """A walking cursor over a Program: emit() lays instructions along the heading,
    turn() drops the arrow for a new heading and steps into it. Space = nop glide."""
    def __init__(self, p, x, y, d):
        self.p, self.x, self.y, self.d = p, x, y, d

    def emit(self, s):
        for ch in s:
            self.p.put(self.x, self.y, ch)
            dx, dy = DXY[self.d]; self.x += dx; self.y += dy
        return self

    def turn(self, nd):
        self.p.put(self.x, self.y, ARROW[nd]); self.d = nd
        dx, dy = DXY[nd]; self.x += dx; self.y += dy
        return self

    def goto(self, x, y, d):
        self.x, self.y, self.d = x, y, d; return self


def build_memory(N=100, XH=34):
    """100-cell addressable memory (problem 'memory'), footprint-tick score ~40.5M local.

    Storage = a circulating FIFO "belt" holding [c0..c(N-1), SENTINEL(-1)] between a
    Gate room (the controller/man) and a Relay room, via two pipes. Each stored cell =
    value + OFFSET(2_000_000) so real values stay positive and the -1 sentinel is
    distinguishable by sign (X) without clobbering registers.

    Per op the gate reads op(+addr[+value]), then does one belt revolution: SEEK
    (count down BP=addr to find the target cell), service it (READ emits value-OFFSET,
    WRITE stores value+OFFSET), then DRAIN the remaining cells until the sentinel
    reappears (which re-syncs alignment for the next op). Column-only pipe selection:
    input@2 belt-in@6 belt-out@10 output@14.
    """
    p = lm.Program()
    R = 25; SR = R + 1
    p.room(0, 0, 30, SR + 1)
    # ---- SEED: send N*OFFSET then sentinel(-1) into the belt ----
    p.text(1, 1, '@'); p.text(2, 1, '`' + str(N) + '`')
    c = 2 + len(str(N)) + 2
    p.put(c, 1, 'b'); p.text(c + 1, 1, '`2000000`')
    tc = c + 10
    p.put(tc, 1, 'v'); p.put(tc, 3, '<')
    p.put(9, 2, '>'); p.put(10, 2, 's'); p.put(11, 2, 'm'); p.put(12, 2, 'v'); p.put(12, 3, '<')
    p.put(9, 3, 'd'); p.put(1, 3, 'v')
    p.put(1, 4, '>'); p.put(2, 4, '1'); p.put(3, 4, 'N'); p.put(10, 4, 's')
    p.put(11, 4, 'v'); p.put(11, 5, '<'); p.put(2, 5, 'v')
    # ---- MAIN: read op (->B), addr (->BP) ----
    p.put(2, 6, 'r'); p.put(2, 7, 'M'); p.put(2, 8, 'r'); p.put(2, 9, 'b')
    p.put(2, 10, '>'); p.put(6, 10, 'v')
    # ---- SEEK: r(belt); d BP>0 -> NOTTGT(resend,dec,loop) ; BP==0 -> TGT ----
    p.put(6, 11, 'r'); p.put(6, 12, 'd')
    p.put(5, 12, 's'); p.put(4, 12, 'm'); p.put(3, 12, '^'); p.put(3, 10, '>')
    # ---- TGT: W (A=op,B=cell); X op>0 -> WRITE ; op==0 -> READ ----
    p.put(6, 13, 'W'); p.put(6, 14, 'X')
    # READ: resend cell, emit cell-OFFSET
    p.put(6, 15, '>')
    p.put(7, 15, 'W'); p.put(8, 15, 's'); p.put(9, 15, 'M')
    p.text(10, 15, '`2000000`'); p.put(19, 15, '-'); p.put(20, 15, 'N'); p.put(21, 15, 's'); p.put(22, 15, 'v')
    p.put(22, 16, '<'); p.put(7, 16, 'v')
    # WRITE: read value, store value+OFFSET (discard old)
    p.put(5, 14, 'v'); p.put(5, 16, '<'); p.put(2, 16, 'v')
    p.put(2, 17, 'r'); p.put(2, 18, 'M'); p.put(2, 19, '>')
    p.text(3, 19, '`2000000`'); p.put(12, 19, '+')
    p.put(13, 19, 'v'); p.put(13, 20, '<'); p.put(9, 20, 's'); p.put(7, 20, 'v')
    # ---- DRAIN: r(belt); s(belt); X A>0 -> loop ; A<0(sentinel) -> MAIN ----
    p.put(7, 21, 'v')
    p.put(7, 22, 'r'); p.put(7, 23, 's'); p.put(7, 24, 'X')
    p.put(6, 24, '^'); p.put(6, 21, '>')
    p.put(24, 24, '^'); p.put(24, 5, '<')
    # ---- belt + IO frame ----
    p.input_room(1, SR + 5);  p.pipe([(2, SR + 4), (2, SR + 1)])
    p.output_room(13, SR + 5); p.pipe([(14, SR + 1), (14, SR + 4)])
    XL = 16; base = SR + 8; width = XH - XL
    nrows = max(2, (N + 4 + width - 1) // width)      # belt capacity >= N+4
    wp = [(10, SR + 1), (10, base), (XL, base)]
    y = base; goright = True; lastx = XL
    for _ in range(nrows):
        nx = XH if goright else XL
        wp.append((nx, y)); y += 1; wp.append((nx, y))
        lastx = nx; goright = not goright
    ey = y
    if lastx != XH:
        wp.append((XH, ey)); lastx = XH
    wp.append((XH + 1, ey)); p.pipe(wp)
    rx = XH + 2
    p.room(rx, ey - 2, 6, 6)
    p.put(rx + 1, ey, '>'); p.put(rx + 2, ey, '@'); p.put(rx + 3, ey, 'r'); p.put(rx + 4, ey, 'v')
    p.put(rx + 4, ey + 1, '<'); p.put(rx + 3, ey + 1, 's'); p.put(rx + 2, ey + 1, '.'); p.put(rx + 1, ey + 1, '^')
    p.pipe([(rx - 1, ey + 1), (6, ey + 1), (6, SR + 1)])
    return p


if __name__ == "__main__":
    import json
    p = build_memory(100)
    print(p.render())
    print("footprint:", p.footprint())
    print("grade:", json.dumps(p.grade("memory")))

#!/usr/bin/env python3
"""Phase-1 fork/pipeline gadget rig.

Three variants of the SAME workload:
  N transactions against a mock "RAM" room sitting behind a deliberately long
  (PIPE_LEN-cell) request pipe and an equally long reply pipe, so each request
  costs a big round-trip latency -- the same shape as LLM's controller stalling
  on `r` for ~51 ticks per transaction.

  serial : ONE man.  7 -> s(req) -> r(reply) -> + -> M -> m -> d
  fork   : TWO men via Y.  A: 7 -> s(req) -> m -> d       (requester, runs ahead)
                            B: r(reply) -> + -> M -> m -> d (consumer)
  dep    : TWO men via Y, but B must hand A the next address every iteration
           through a RELAY room -- i.e. a fully dependent chain, no prefetch.

Workload result: acc = 7*N, emitted once at the end.
Input:  one integer N.   Output: one integer 7*N.

Geometry is hand-placed; nearest-pipe distances are asserted below.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tools.littleman import Program

PIPE_LEN = 42          # cells each way -> ~2*PIPE_LEN tick round trip

# ---------------------------------------------------------------- geometry
MX0, MY0, MW, MH = 40, 0, 18, 8          # MAIN room
MXW, MXE = MX0, MX0 + MW - 1             # west wall 40, east wall 57
MYN, MYS = MY0, MY0 + MH - 1             # north 0, south 7
RAMX = MXE + 1 + PIPE_LEN                # RAM west wall

# pipe cells adjacent to MAIN (these are what `nearest` measures against)
P_IN = (MXW - 1, 1)          # (39,1)  input  -> MAIN
P_OUT = (MXW - 1, 6)         # (39,6)  MAIN   -> output
P_REQ = (MXE + 1, 2)         # (58,2)  MAIN   -> RAM
P_REP = (MXE + 1, 3)         # (58,3)  RAM    -> MAIN
P_H1 = (45, MYS + 1)         # (45,8)  MAIN   -> RELAY   (B hands off)
P_H2 = (51, MYS + 1)         # (51,8)  RELAY  -> MAIN    (A picks up)
ALL_OUT = [P_OUT, P_REQ, P_H1]
ALL_IN = [P_IN, P_REP, P_H2]


def shell(p, relay=False):
    """Rooms + pipes shared by every variant. Returns nothing."""
    p.room(MX0, MY0, MW, MH)
    # --- input room + 2-cell pipe into MAIN west wall y=1
    p.input_room(35, 0)
    p.pipe([(38, 1), (39, 1)])
    # --- output room + 2-cell pipe out of MAIN west wall y=6
    p.output_room(35, 5)
    p.pipe([(39, 6), (38, 6)])
    # --- mock RAM: 6x4 room, 8-tick service ring
    p.room(RAMX, 1, 6, 4)
    ax = RAMX + 1
    p.text(ax, 2, ">@rv")          # (ax..ax+3, y=2)
    p.text(ax, 3, "^ s<")          # (ax..ax+3, y=3)
    # request pipe MAIN(east,y=2) -> RAM(west,y=2)
    p.pipe([(MXE + 1, 2), (RAMX - 1, 2)])
    # reply pipe RAM(west,y=3) -> MAIN(east,y=3)
    p.pipe([(RAMX - 1, 3), (MXE + 1, 3)])
    if relay:
        # RELAY room south of MAIN; 2-cell pipes each way (cheap handoff)
        p.room(44, 10, 9, 4)           # x44..52, y10..13; interior x45..51,y11..12
        p.text(45, 11, ">@rv")
        p.text(45, 12, "^ s<")
        p.pipe([(45, 8), (45, 9)])     # MAIN south wall -> RELAY top wall
        p.pipe([(51, 9), (51, 8)])     # RELAY top wall -> MAIN south wall


def man_dist(cell, pipe):
    return abs(cell[0] - pipe[0]) + abs(cell[1] - pipe[1])


def check(cell, want, others, label):
    dw = man_dist(cell, want)
    for o in others:
        do = man_dist(cell, o)
        assert do > dw, f"{label}: {cell} d(want)={dw} but d({o})={do}"
    return dw


# ---------------------------------------------------------------- serial
def build_serial():
    p = Program()
    shell(p)
    # setup on row 1 (west): @ nop, r reads N, b sets BP=N
    p.text(41, 1, "@rb")
    check((42, 1), P_IN, [P_REP], "serial setup r")
    p.put(49, 1, "v")
    p.put(49, 2, ">")
    # hot ring rows 2-3, x51..56 (12 ticks)
    p.text(51, 2, ">7  sv")        # 51 > | 52 7 | 53 . | 54 . | 55 s | 56 v
    p.text(51, 3, "dmM+r<")        # 51 d | 52 m | 53 M | 54 + | 55 r | 56 <
    check((55, 2), P_REQ, [P_OUT], "serial s")
    check((55, 3), P_REP, [P_IN], "serial r")
    # exit lane: d falls through west along row 3 -> down -> output
    p.put(43, 3, "v")
    p.put(43, 6, "<")
    p.put(42, 6, "s")
    p.put(41, 6, "H")
    check((42, 6), P_OUT, [P_REQ], "serial out s")
    return p


# ---------------------------------------------------------------- fork
def build_fork():
    p = Program()
    shell(p)
    p.text(41, 1, "@rb")
    check((42, 1), P_IN, [P_REP], "fork setup r")
    p.put(49, 1, "v")
    p.put(49, 3, ">")              # (49,2) blank, glide south
    p.put(50, 3, "Y")              # copies born at (50,2) N-facing, (50,4) S-facing
    p.put(50, 2, ">")              # steer north copy east  -> A ring
    p.put(50, 4, ">")              # steer south copy east  -> B ring
    # --- man A: requester ring rows 2-3, x52..56 (10 ticks)
    p.text(52, 2, ">7 sv")         # 52 > | 53 7 | 54 . | 55 s | 56 v
    p.text(52, 3, "d m <")         # 52 d | 53 . | 54 m | 55 . | 56 <
    check((55, 2), P_REQ, [P_OUT], "fork A s")
    p.put(51, 3, "H")              # A exits west and halts
    # --- man B: consumer ring rows 4-5, x52..56 (10 ticks)
    p.text(52, 4, ">  rv")         # 52 > | 55 r | 56 v
    p.text(52, 5, "dmM+<")         # 52 d | 53 m | 54 M | 55 + | 56 <
    check((55, 4), P_REP, [P_IN], "fork B r")
    # B exits west along row 5 -> down -> output
    p.put(43, 5, "v")
    p.put(43, 6, "<")
    p.put(42, 6, "s")
    p.put(41, 6, "H")
    check((42, 6), P_OUT, [P_REQ], "fork B out s")
    return p


# ---------------------------------------------------------------- dep
def build_dep():
    """Fully dependent chain: A's request N+1 carries B's token from reply N,
    handed over through the RELAY room -- i.e. zero prefetch, pure handoff cost.
      A (rows 5-6, near h2): r(h2) -> s(req) -> m -> d
      B (rows 2-3, near rep): r(rep) -> + -> M -> m -> 7 -> s(h1) -> d
    Setup primes the relay with the first token so A has something to forward."""
    p = Program()
    shell(p, relay=True)
    # ---- setup row 1: read N, BP=N, prime the relay with the first token
    p.text(41, 1, "@rb7s")         # 41 @ | 42 r | 43 b | 44 7 | 45 s(h1)
    check((42, 1), P_IN, [P_REP, P_H2], "dep setup r")
    check((45, 1), P_H1, [P_REQ, P_OUT], "dep setup s(h1)")
    p.put(49, 1, "v")              # descend col 49 through B-ring blanks (49,2),(49,3)
    p.put(49, 4, "<")              # ... then west along the empty row 4 to the Y
    p.put(44, 4, "Y")              # copies: (44,3) heading N, (44,5) heading S
    p.put(44, 3, "^")
    p.put(44, 2, ">")              # north copy -> east into B's ring at (46,2)
    p.put(44, 5, ">")              # south copy -> east into A's ring at (51,5)
    # ---- man A: ring rows 5-6, x51..56  (12 ticks)
    p.text(51, 5, ">r  sv")        # 51 > | 52 r(h2) | 55 s(req) | 56 v
    p.text(51, 6, "d   m<")        # 51 d | 55 m | 56 <
    check((52, 5), P_H2, [P_REP, P_IN], "dep A r(h2)")
    check((55, 5), P_REQ, [P_H1, P_OUT], "dep A s(req)")
    p.put(50, 6, "H")              # A's fall-through halt
    # ---- man B: ring rows 2-3, x46..56  (22 ticks)
    p.text(46, 2, ">        rv")   # 46 > | 55 r(rep) | 56 v
    p.text(46, 3, "ds7  m M+<")    # 46 d | 47 s(h1) | 48 7 | 51 m | 53 M | 54 + | 55 <
    # rewrite row 3 explicitly (west-bound execution order 55 -> 46)
    for x in range(47, 56):
        p.put(x, 3, " ")
    p.put(55, 3, "+")
    p.put(54, 3, "M")
    p.put(53, 3, "m")
    p.put(48, 3, "7")
    p.put(47, 3, "s")
    p.put(46, 3, "d")
    p.put(56, 3, "<")
    check((55, 2), P_REP, [P_IN, P_H2], "dep B r(rep)")
    check((47, 3), P_H1, [P_REQ, P_OUT], "dep B s(h1)")
    # B exits west from d -> south -> west -> W restores acc -> output
    p.put(45, 3, "v")
    p.put(45, 6, "<")
    p.put(44, 6, "W")              # A=7,B=acc  ->  A=acc
    p.put(42, 6, "s")
    p.put(41, 6, "H")
    check((42, 6), P_OUT, [P_REQ, P_H1], "dep B out s")
    return p


if __name__ == "__main__":
    out = os.path.dirname(os.path.abspath(__file__))
    for name, fn in [("serial", build_serial), ("fork", build_fork)]:
        p = fn()
        path = os.path.join(out, f"{name}.man")
        p.save(path)
        print(name, p.footprint(), path)

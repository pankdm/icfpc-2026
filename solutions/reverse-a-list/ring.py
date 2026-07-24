"""Compact FIFO-ring reverse-a-list builders (ring-vN). Tightening v3's O(n^2) ring.

Key idea vs v3: free the TOP by putting BOTH the input (I, incoming) and the FEED
(outgoing) on the *bottom* wall (an in/out pair may share a wall). That removes the
~5-row input stack that sat above CTRL in v3. RETURN enters the left wall, O exits
the right wall. PUMP sits below-left; the ring is folded compactly.

Pole layout of CTRL:
    top    : free
    left   : RETURN (in)   -> dequeue `r`
    right  : O      (out)  -> output  `s`
    bottom : I (in) right-ish, FEED (out) left-ish
             -> value/count `r` near bottom-right, enqueue `s` near bottom-left
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm


def build(WI=9, HI=8):
    """Compact ring. WI/HI = CTRL interior width/height."""
    p = lm.Program()
    # CTRL room: outer top-left (0,0); interior cols 1..WI rows 1..HI; walls 0 and WI+1/HI+1.
    W = WI + 2
    H = HI + 2
    p.room(0, 0, W, H)  # CTRL
    P = p.put

    # ---- pole columns/rows ----
    IcolB = WI          # I on bottom wall at interior col WI (right)
    FcolB = 2           # FEED on bottom wall at interior col 2 (left)
    RrowL = 3           # RETURN on left wall at interior row 3
    OrowR = HI - 2      # O on right wall

    # ---- satellites ----
    # I room below-right, pipe up into CTRL bottom at col IcolB
    # bottom wall is row H-1 = HI+1. pipe cells go downward from (IcolB, HI+2), (IcolB, HI+3)
    Irow = HI + 4       # I room top row (below CTRL)
    p.input_room(IcolB - 1, Irow)               # 3x3, I at (IcolB, Irow+1)
    p.pipe([(IcolB, Irow - 1), (IcolB, HI + 2)])  # I -> up into CTRL bottom

    # O room right, pipe from CTRL right wall
    Ocol = W + 2
    p.output_room(Ocol, OrowR)                  # 3x3 ; O at (Ocol+1, OrowR+1)
    p.pipe([(W, OrowR + 1), (Ocol - 1, OrowR + 1)])  # CTRL right -> O

    # PUMP room below-left; FEED down into it, RETURN back up to CTRL left wall
    Prow = HI + 4
    Pw = 8
    p.room(-1, Prow, Pw, 4)                      # PUMP interior rows Prow+1..Prow+2
    p.pipe([(FcolB, HI + 2), (FcolB, Prow - 1)])  # FEED CTRL bottom -> PUMP top? need col in pump range
    # FEED enters PUMP top: FcolB=2 must be within pump interior cols 0..Pw-2=6 -> ok
    # RETURN: PUMP -> CTRL left wall (row RrowL). Route up the far-left.
    ret = [(-1 + Pw - 2, Prow + 2)]  # will be overwritten below with explicit route
    # explicit RETURN route folded on the left of CTRL
    r_start = (-1 + 1, Prow + 1)     # from inside pump left area going out its... use its top-left
    # Build RETURN from PUMP top-left up-left column to CTRL left wall row RrowL
    ret = [(1, Prow - 1), (-3, Prow - 1), (-3, RrowL), (0, RrowL)]
    p.pipe(ret)
    # pump forwarder man: R ; s
    pr1, pr2 = Prow + 1, Prow + 2
    P(-1 + 1, pr1, ">"); P(-1 + 2, pr1, "@"); P(-1 + 3, pr1, "R"); P(-1 + 4, pr1, "s")
    P(-1 + Pw - 2, pr1, "v"); P(-1 + Pw - 2, pr2, "<"); P(-1 + 1, pr2, "^")

    # ============ CTRL MAN PROGRAM ============
    # SETUP: read count near bottom-right (I), M, b.
    # start @ top-left, go east then down the right side to read count.
    P(1, 1, "@")                    # start face E
    P(WI, 1, "v")                   # east to right col, turn S
    # down right col to count-r
    P(WI, 2, "r")                   # count read (near I bottom? check nearest) -> A=n
    P(WI, 3, "M")                   # B=n  (but this col also near O? O is right wall OrowR)
    P(WI, 4, "b")                   # BP=n
    P(WI, 5, "<")                   # turn west (enter read loop area)
    # ... to be continued; placeholder
    return p


if __name__ == "__main__":
    p = build()
    print(p.render())
    print("FP", p.footprint())

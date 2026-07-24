"""TCP / Packet Reassembly solution builder.

One control man + two FIFO storage rings:
  * DATA ring:  a sliding window [s0..s15] + sentinel(-1) at the tail.  s_i holds
    the value for seq (w+i), or 0 if that packet hasn't arrived.  head=s0=seq w.
  * W ring:  a 1-value ring holding the awaited seq w (absolute).

Per packet: read w (rW), seq (rIN); d=seq-w; resend w; branch:
  d==0  DRAIN : output val, output consecutive present slots, shift window by k,
                append k empties, w+=k.
  d>0   INSERT: seek slot d; if the sentinel is reached first (d>=16) -> ABORT
                (output -1, halt); else write val at slot d.

Column discipline (nearest pipe = nearest column):
  incoming top:    cIN=4(input) cRET=12(data) cRETW=22(w)
  outgoing bottom: cOUT=4       cFEED=12       cFEEDW=22
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

DXY = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
ARROW = {"E": ">", "W": "<", "N": "^", "S": "v"}


def build():
    p = lm.Program()
    placed = {}

    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION at {(x,y)}: {placed[(x,y)]!r} vs {ch!r}")
        placed[(x, y)] = ch
        p.put(x, y, ch)

    def mpath(pts):
        """Route the man through orthogonal waypoints; place a turn arrow at each
        segment start. Straights stay spaces (glide). Final point NOT written."""
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            dx = (x1 > x0) - (x1 < x0)
            dy = (y1 > y0) - (y1 < y0)
            d = 'E' if dx > 0 else 'W' if dx < 0 else 'S' if dy > 0 else 'N'
            C(x0, y0, ARROW[d])

    def feeder(y):
        C(1, y, '>')

    # ------------- geometry (FOLDED: every pipe endpoint on the TOP wall) ----------
    # The man code (below) is BYTE-IDENTICAL to tcp-v1.  In v1 the readable pipes
    # (returns + IN) sat on the TOP wall and the sendable pipes (feeds + OUT) on the
    # BOTTOM wall (wall = read/send discriminator, column = ring discriminator), which
    # forced each ring loop to span the whole 66-row room -> ~130-cell pipes -> huge
    # latency and a tall footprint.  Here ALL endpoints move to the TOP wall with the
    # relays directly above (matmul fold).  Now nearest-pipe is PURE column discipline
    # (row-independent, since every attach shares y=0): op-type picks read vs send,
    # column picks the ring.  Ring loops shrink to ~20 cells (cap>=17 for DATA) -> far
    # less latency (fewer ticks) and the below-room relays / tall risers vanish.
    CX, CY, CW, CH = 0, 0, 32, 66
    top, bot = CY, CY + CH - 1
    p.room(CX, CY, CW, CH)
    # readables (man r-ops resolve here by nearest column):
    cIN, cRET, cRETW = 4, 12, 23
    # sendables (man s-ops resolve here by nearest column):
    cOUT, cFEED, cFEEDW = 1, 11, 22

    # IN / OUT rooms above the top wall
    p.input_room(cIN - 1, top - 5);  p.pipe([(cIN,  top - 2), (cIN,  top - 1)])
    p.output_room(cOUT - 1, top - 5); p.pipe([(cOUT, top - 1), (cOUT, top - 2)])

    def relay_above(feed_col, ret_col, RY):
        """FIFO relay ABOVE the CTRL: feed rises from the CTRL top wall into the
        relay bottom wall, the relay man recirculates, the return descends back into
        the CTRL top wall.  Loop capacity ~= 2*(-1-(RY+4))+buffer.  ret_col==feed_col+1."""
        rx = feed_col - 1
        p.room(rx, RY, 6, 4)
        C(rx + 1, RY + 1, '@'); C(rx + 2, RY + 1, '>'); C(rx + 3, RY + 1, 'R'); C(rx + 4, RY + 1, 'v')
        C(rx + 2, RY + 2, '^'); C(rx + 3, RY + 2, 's'); C(rx + 4, RY + 2, '<')
        p.pipe([(feed_col, -1), (feed_col, RY + 4)])   # feed   CTRL -> relay (up)
        p.pipe([(ret_col,  RY + 4), (ret_col,  -1)])   # return relay -> CTRL (down)

    relay_above(cFEED, cRET, -12)    # DATA ring: window(16)+sentinel => cap must be >=17; -12 gives cap 18 (floor; -11 deadlocks)
    relay_above(cFEEDW, cRETW, -8)   # W ring: 1 live value => small cap ~8

    # =============================================================
    # CONTROL MAN
    # =============================================================
    # ---- PREAMBLE: seed data ring [0*16,-1], w ring [0] ----
    p.man(2, 1); C(2, 1, '@')
    C(4, 1, 'r')                                        # read n (discard)
    C(6, 1, '`'); C(7, 1, '1'); C(8, 1, '6'); C(9, 1, '`')  # A=16
    C(10, 1, 'b')                                       # BP=16
    mpath([(11, 1), (11, 2), (1, 2), (1, 3)]); feeder(3)
    C(2, 3, '0'); C(12, 3, 's'); C(13, 3, 'm'); C(14, 3, 'd')   # SEED loop
    mpath([(14, 4), (1, 4), (1, 3)])                    # loop while BP>0
    # exit BP==0: w-seed@22, then sentinel@12 on row4 glide, then MAIN via row5
    C(22, 3, 's')                                       # sW seed w=0 (A=0)
    mpath([(23, 3), (23, 7), (1, 7), (1, 6)])           # down, W row7, up to MAIN
    C(16, 7, '1'); C(15, 7, 'N'); C(12, 7, 's')         # A=-1 ; sB@12 sentinel

    # ---- MAIN: read w,seq ; d=seq-w ; resend w ; branch ----
    feeder(6)
    C(4, 6, 'r'); C(5, 6, 'M')                          # A=seq ; B=seq
    C(21, 6, 'r'); C(22, 6, 's')                        # A=w ; sW resend w
    C(23, 6, 'W'); C(24, 6, '-')                        # A=seq,B=w ; A=d,B=w
    C(25, 6, 'X')     # E: d>0->CW(S)=INSERT ; d==0->straight(E)=DRAIN
    # INSERT edge: CW(S) -> down col28 -> INSERT-A feeder(1,42)
    mpath([(25, 7), (25, 10), (28, 10), (28, 41), (1, 41), (1, 42)])
    # DRAIN edge: straight(E) -> down col26 -> DRAIN-A feeder(1,10)
    mpath([(26, 6), (26, 9), (1, 9), (1, 10)])

    # ---- DRAIN-A: output val ; k=1 ; drop s0 ----
    feeder(10)
    C(4, 10, 'r')                                       # rIN A=val
    mpath([(5, 10), (5, 11), (4, 11)]); C(4, 11, 's')   # sOUT val
    mpath([(3, 11), (3, 12), (4, 12)])
    C(4, 12, '1'); C(5, 12, 'M')                        # A=1 ; B=1 (k=1)
    C(12, 12, 'r')                                      # rB drop s0 (A=s0)
    mpath([(13, 12), (16, 12), (16, 13), (1, 13), (1, 14)])

    # ---- DROPLOOP: rB ; present/absent/sentinel (enter X heading S) ----
    feeder(14)
    C(12, 14, 'r'); C(13, 14, 'v'); C(13, 15, 'X')
    #  S: present(A>0)->CW(W) ; absent(0)->straight(S) ; sentinel(<0)->CCW(E)
    # present -> DPRES(output v, k++) -> loopback to feeder(1,14)
    mpath([(12, 15), (4, 15)]); C(4, 15, 's')           # sOUT v
    mpath([(3, 15), (3, 16), (4, 16)])
    C(4, 16, '1'); C(5, 16, '+'); C(6, 16, 'M')         # k=k+1
    mpath([(7, 16), (7, 13), (1, 13)])                  # loopback -> feeder
    # absent -> DKEEP feeder(1,18)
    mpath([(13, 16), (14, 16), (14, 17), (1, 17), (1, 18)])
    # sentinel -> DWUP feeder(1,30)
    mpath([(14, 15), (26, 15), (26, 29), (1, 29), (1, 30)])

    # ---- DKEEP: enqueue 0 as new head -> KEEPLOOP ----
    feeder(18)
    C(12, 18, 's')                                      # sB enqueue 0 (A=0)
    mpath([(13, 18), (24, 18), (24, 25), (1, 25), (1, 26)])

    # ---- KEEPLOOP: rB ; re-enqueue rest until sentinel (enter X heading S) ----
    #  loopback approaches feeder from the SOUTH via col1 (rows 27,28) so it never
    #  places a turn on the code row (row26).
    feeder(26)
    C(12, 26, 'r'); C(13, 26, 'v'); C(13, 27, 'X')
    #  S: present CW(W) ; empty straight(S) ; sentinel CCW(E)
    C(12, 27, 's'); C(1, 27, '^')                       # present: sB then glide row27 W -> up
    C(13, 28, '<'); C(12, 28, 's'); C(1, 28, '^')       # empty:  sB then glide row28 W -> up
    mpath([(14, 27), (24, 27), (24, 29), (1, 29), (1, 30)])  # sentinel(E) -> DWUP

    # ---- DWUP: w += k ; BP=k ----
    feeder(30)
    C(20, 30, 'r')                                      # rW A=w (B=k)
    C(21, 30, '+')                                      # A=w+k
    C(22, 30, 's')                                      # sW send w+k
    C(23, 30, 'W'); C(24, 30, 'b')                      # A=k,B=w+k ; BP=k
    mpath([(25, 30), (25, 33), (1, 33), (1, 34)])       # -> APPEND feeder

    # ---- APPEND: append k zeros then sentinel ----
    feeder(34)
    C(2, 34, 'd')          # E: BP>0->CW(S)=AZ ; BP==0->straight(E)=AFIN
    # AZ: turn E ; A=0 ; sB@12 ; m ; loopback
    C(2, 35, '>'); C(3, 35, '0')          # CW(S)->(2,35) turn E ; A=0
    C(12, 35, 's'); C(13, 35, 'm')
    mpath([(14, 35), (14, 33), (1, 33), (1, 34)])       # loopback to feeder
    # AFIN: A=-1 ; sB@12 sentinel -> MAIN
    C(3, 34, '1'); C(4, 34, 'N')                        # A=-1
    C(12, 34, 's')                                      # sB sentinel
    mpath([(13, 34), (30, 34), (30, 5), (1, 5), (1, 6)])  # -> MAIN via return lane row5

    # ---- INSERT-A: BP=d ; read val ; SEEK ----
    feeder(42)
    C(2, 42, 'b')                                       # BP=d  (A=d on entry)
    C(4, 42, 'r')                                       # rIN A=val
    C(5, 42, 'M')                                       # B=val
    mpath([(6, 42), (6, 43), (1, 43), (1, 46)])         # -> SEEK feeder(1,46) via col1?
    # (approach SEEK feeder from north (1,45))
    # NB re-route: go to (1,45)->(1,46)
    # ---- SEEK: rB ; sentinel->ABORT ; else seek to slot d ; WRITE ----
    feeder(46)
    C(12, 46, 'r'); C(13, 46, 'v'); C(13, 47, 'X')
    #  S: sentinel(A<0)->CCW(E)=ABORT ; A>0->CW(W) ; A==0->straight(S) ; merge>=0 -> BPCHECK
    C(12, 47, 'v'); C(12, 48, '>'); C(13, 48, 'v')      # merge W+S -> S at (13,49)
    C(13, 49, 'd')         # S: BP>0->CW(W)=SKIP ; BP==0->straight(S)=WRITE
    # SKIP: re-enqueue A ; m ; loopback
    C(12, 49, 's'); C(11, 49, 'm')
    mpath([(10, 49), (10, 45), (1, 45), (1, 46)])       # loopback to SEEK feeder
    # WRITE: A=slot,B=val -> write val
    C(13, 50, 'W')                                      # A=val,B=slot
    mpath([(13, 51), (12, 51)]); C(12, 51, 's')         # sB write val
    mpath([(11, 51), (11, 53), (1, 53), (1, 54)])       # -> DRAINREST feeder
    # ABORT: sentinel CCW(E) at (14,47), A=-1 -> output -1 ; halt
    mpath([(14, 47), (28, 47), (28, 62), (4, 62)])
    C(4, 62, 's'); C(3, 62, 'H')                        # sOUT(-1) ; halt

    # ---- DRAINREST: re-enqueue rest until sentinel (enter X heading S) ----
    feeder(54)
    C(12, 54, 'r'); C(13, 54, 'v'); C(13, 55, 'X')
    #  S: present CW(W) ; empty straight(S) ; sentinel CCW(E)
    C(12, 55, 's'); C(1, 55, '^')                       # present: sB -> glide row55 W -> up
    C(13, 56, '<'); C(12, 56, 's'); C(1, 56, '^')       # empty:  sB -> glide row56 W -> up
    # sentinel CCW(E): re-enqueue sentinel, then -> MAIN via col29/row5
    mpath([(14, 55), (16, 55), (16, 57), (12, 57)]); C(12, 57, 's')  # sB sentinel
    mpath([(11, 57), (11, 59), (29, 59), (29, 5), (1, 5), (1, 6)])   # -> MAIN

    return p, placed, dict(CX=CX, CY=CY, CW=CW, CH=CH)


def compact_rows(p, y_lo, y_hi, keep=()):
    """Delete every interior-empty row in [y_lo,y_hi] (cols 1..30 all spaces) and
    shift everything below up.  Semantically a no-op for the man (its path only loses
    empty glide cells -> identical route, fewer ticks) provided no collision results.
    Rows in `keep` are never deleted.  Rows <=0 (pipes/relays/IO/top wall) untouched."""
    def interior_empty(y):
        return all(p.get(x, y) == ' ' for x in range(1, 31))
    delete = sorted(y for y in range(y_lo, y_hi + 1)
                    if y not in keep and interior_empty(y))
    dset = set(delete)
    new = {}
    for (x, y), ch in p.cells.items():
        if y in dset:
            continue
        ny = y - sum(1 for d in delete if d < y) if y > y_lo else y
        new[(x, y if y <= 0 else ny)] = ch
    p.cells = new
    return delete


if __name__ == "__main__":
    import sys
    p, placed, g = build()
    delete = compact_rows(p, 1, 64)
    print("deleted rows:", delete, file=sys.stderr)
    out = p.render() + "\n"
    open(os.path.join(os.path.dirname(__file__), "tcp-folded.man"), "w").write(out)
    print("footprint:", p.footprint(), file=sys.stderr)

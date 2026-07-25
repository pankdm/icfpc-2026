"""tcp sweep design builder — 3-man SWEEP (reader + serpentine sweeper + checker).

MONOTONIC positioner: lane[slot] lives at column CB+slot (spacing-1, adjacent),
so the serpentine sweeper can walk adjacent columns in seq order.

emit_montree: man enters heading S at (CB,y0) with B=seq preloaded. Per level l
(l=0..3, MSB-first) the gadget `W & b a` tests bit (3-l) of seq (W=2^(3-l)):
A=W; A=W&seq (=W if bit set else 0); BP=A; `a` turns CCW(=east) iff bit set.
Bit set -> glide east W, drop to child; clear -> straight south. Leaf col = CB+slot.
(A is clobbered by the digit each level, so val is read at the LEAF, not carried.)

Stage 1 (build_test): reader inserts val into lane[seq&15]; serpentine sweeper
drains lanes in seq order straight to output. Validates drain ordering.
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout

def emit_montree(L, cb, y0, leaf_fn):
    """Monotonic tree. Returns {slot: leaf_col=cb+slot}. Man enters (cb,y0) S, B=seq."""
    Wd = [8, 4, 2, 1]                    # weight per level = 2^(3-level)
    leaves = {}
    def node(level, col, row):
        w = Wd[level]
        L.put(col, row,     str(w))      # A = w
        L.put(col, row + 1, '&')         # A = w & seq
        L.put(col, row + 2, 'b')         # BP = A
        L.put(col, row + 3, 'a')         # CCW(east) iff bit set
        # set-child: glide east w on row+3, drop south at col+w
        for k in range(1, w):
            L.put(col + k, row + 3, '-') if False else None   # leave blank glide
        L.put(col + w, row + 3, 'v')     # turn S at the set-child column
        crow = row + 4
        if level < 3:
            node(level + 1, col,     crow)   # clear child (straight S)
            node(level + 1, col + w, crow)   # set child
        else:
            leaf_fn(L, col,     crow, 'clear')  # handled by caller: slot known by col
    node(0, cb, y0)
    # leaves at row y0+16, cols cb..cb+15
    for s in range(16):
        leaves[s] = cb + s
    return leaves


def build_test():
    L = Layout()
    CB = 15                              # leftmost lane column
    yr = 2
    y0 = yr + 1                          # tree top row
    LEAFROW = y0 + 16                    # 19
    # ---- READER ----
    L.put(1, yr, '@'); L.put(2, yr, 'r')          # discard n (once)
    L.put(3, yr, '>')                              # loop entry
    L.put(4, yr, 'r')                              # seq -> A
    L.put(5, yr, 'M')                              # B = seq
    L.put(CB, yr, 'v')                             # glide E to CB, turn S into tree
    # place tree gadgets (leaf_fn is a no-op; we add leaf ops after)
    leaves = emit_montree(L, CB, y0, lambda *a: None)
    # leaf ops: read val + insert into lane, then return
    for s in range(16):
        c = leaves[s]
        L.put(c, LEAFROW, 'r')                     # read val (only incoming = input)
        L.put(c, LEAFROW + 1, 's')                 # send val into lane[s]
        L.put(c, LEAFROW + 2, '<')                 # return rail
    L.put(3, LEAFROW + 2, '^')                     # up col3 to loop entry
    RWALL = LEAFROW + 3                            # reader south wall
    L.room(0, 0, CB + 18, RWALL + 1)
    L.input_room(3, -5); L.pipe([(4, -2), (4, -1)])

    # ---- LANES ----
    TW = RWALL + 4                                 # sweeper top wall
    for s in range(16):
        c = leaves[s]
        L.pipe([(c, RWALL + 1), (c, TW - 1)])

    # ---- SWEEPER (spacing-1 serpentine, sweep EAST lane0..15) ----
    R0, R1, R2, R3, Rw = TW + 1, TW + 2, TW + 3, TW + 4, TW + 5
    BW = TW + 6
    for i in range(16):
        c = CB + i
        if i % 2 == 0:                             # DOWN-col
            L.put(c, R0, 'v')                      # entry (arrive E -> S)
            L.put(c, R1, 'r')                      # read lane i
            L.put(c, R2, 's')                      # drain
            if i != 15:
                L.put(c, R3, '>')                  # exit E
        else:                                      # UP-col
            L.put(c, R3, '^')                      # entry (arrive E -> N)
            L.put(c, R2, 'r')                      # read lane i
            L.put(c, R1, 's')                      # drain
            if i != 15:
                L.put(c, R0, '>')                  # exit E
    # lane15 (col CB+15) wraps back to lane0 (col CB)
    c15 = CB + 15
    # lane15 is odd index -> up-col, exits at R0
    L.put(c15, R0, '>')                            # to east wrap col
    ec = CB + 16                                   # east wrap col
    wc = CB - 1                                    # west wrap col
    L.put(ec, R0, 'v'); L.put(ec, Rw, '<')         # down east col, turn W onto rail
    L.put(wc, Rw, '^'); L.put(wc, R0, '>')         # up west col, turn E to lane0
    # spawn: west of wc, heading E into lane0
    L.put(wc - 1, R0, '@')
    L.room(0, TW, CB + 18, BW - TW + 1)

    # ---- OUTPUT ----
    oc = CB + 8
    L.output_room(oc - 1, BW + 3)
    L.pipe([(oc, BW + 1), (oc, BW + 2)])
    return L


def emit_checker(L, cx, cy):
    """Checker room top-left (cx,cy), 17 wide x 10 tall. Owns Wt=B (init 0).
    seq-pipe -> WEST wall; drain-pipe -> EAST wall; output-pipe -> SOUTH wall.

    row0: top rail (CI-seq==0 -> DP re-poll)
    row1: main E flow: @ >merge r - b ]]]] d(ovf) > >DPmerge q(drain) d(fwd) v
    col10: overflow emit-1 (down)
    col13: FWD (r,s,Wt++) down
    row7: FWD loopback W -> col11 up -> DPmerge
    col14: DP-empty riser down -> row8
    row8: CI bottom rail W -> q(seq) d
    col2:  CI-seq>0 riser up -> TOPmerge
    col1:  CI-seq==0 riser up -> row0 -> DPmerge
    """
    x = lambda i: cx + i
    y = lambda j: cy + 1 + j          # y(0) = first INTERIOR row (row cy is the north wall)
    # main row1
    L.put(x(1), y(1), '@')
    L.put(x(2), y(1), '>')                 # TOP merge
    L.put(x(3), y(1), 'r')                 # seq
    L.put(x(4), y(1), '-')                 # off = seq-Wt
    L.put(x(5), y(1), 'b')
    L.put(x(6), y(1), ']'); L.put(x(7), y(1), ']'); L.put(x(8), y(1), ']'); L.put(x(9), y(1), ']')
    L.put(x(10), y(1), 'd')                # overflow CW->S
    L.put(x(11), y(1), '>')                # DP merge (also col11 riser top)
    L.put(x(12), y(1), 'q')                # count drain
    L.put(x(13), y(1), 'd')                # drain>0 CW->S = FWD
    L.put(x(14), y(1), 'v')                # DP-empty -> S
    # overflow emit -1
    L.put(x(10), y(2), '1'); L.put(x(10), y(3), 'N'); L.put(x(10), y(4), 's'); L.put(x(10), y(5), 'H')
    # FWD col13
    L.put(x(13), y(2), 'r'); L.put(x(13), y(3), 's')
    L.put(x(13), y(4), '1'); L.put(x(13), y(5), '+'); L.put(x(13), y(6), 'M')
    L.put(x(13), y(7), '<')                # loopback rail W
    L.put(x(11), y(7), '^')                # up to DP merge (11,1)
    # DP-empty riser col14 down to row8
    L.put(x(14), y(8), '<')                # bottom rail W
    # CI on bottom rail
    L.put(x(4), y(8), 'q')                 # count seq (WEST nearest)
    L.put(x(3), y(8), 'd')                 # seq>0 CW(W->N)=up col3 ; else straight W
    # CI seq>0 -> up col3 -> divert W into TOP merge
    L.put(x(3), y(2), '<')                 # top of col3 riser: turn W
    L.put(x(2), y(2), '^')                 # turn N -> TOP merge (2,1)
    # CI seq==0 -> straight W -> col1 riser up -> row0 -> DP merge
    L.put(x(1), y(8), '^')                 # up col1 (through @) to row0
    L.put(x(1), y(0), '>')                 # row0 E
    L.put(x(11), y(0), 'v')                # down to DP merge (11,1)
    L.room(cx, cy, 17, 11)            # rows cy..cy+10 ; interior y(0)..y(8) = cy+1..cy+9
    # seq -> WEST wall; drain -> NORTH wall; output -> SOUTH wall (outside cy+10).
    return {'seqW': (cx - 1, y(4)), 'drainN': (x(12), cy - 1), 'outS': (x(8), cy + 11)}


def build_full():
    L = Layout()
    CB = 15
    yr = 2
    y0 = yr + 1
    LEAFROW = y0 + 16
    # ---- READER ----
    L.put(1, yr, '@'); L.put(2, yr, 'r')          # discard n
    L.put(3, yr, '>')                              # loop entry
    L.put(4, yr, 'r')                              # seq -> A
    L.put(5, yr, 'M')                              # B = seq
    L.put(6, yr, 's')                              # forward seq -> checker (seq-pipe nearest at top)
    L.put(CB, yr, 'v')                             # glide E to CB, into tree
    leaves = emit_montree(L, CB, y0, lambda *a: None)
    for s in range(16):
        c = leaves[s]
        L.put(c, LEAFROW, 'r')                     # read val (only reader-incoming = input)
        L.put(c, LEAFROW + 1, 's')                 # insert into lane[s]
        L.put(c, LEAFROW + 2, '<')                 # return rail
    L.put(3, LEAFROW + 2, '^')
    RWALL = LEAFROW + 3
    L.room(0, 0, CB + 18, RWALL + 1)
    L.input_room(1, -5); L.pipe([(2, -2), (2, -1)])  # input -> reader top col2 (near r@col4/leaf via only-incoming)

    # seq-pipe: reader top (col7) -> checker.  Route later once checker placed.
    # ---- LANES ----
    TW = RWALL + 4
    for s in range(16):
        c = leaves[s]
        L.pipe([(c, RWALL + 1), (c, TW - 1)])
    # ---- SWEEPER ----
    R0, R1, R2, R3, Rw = TW + 1, TW + 2, TW + 3, TW + 4, TW + 5
    BW = TW + 6
    for i in range(16):
        c = CB + i
        if i % 2 == 0:
            L.put(c, R0, 'v'); L.put(c, R1, 'r'); L.put(c, R2, 's')
            if i != 15: L.put(c, R3, '>')
        else:
            L.put(c, R3, '^'); L.put(c, R2, 'r'); L.put(c, R1, 's')
            if i != 15: L.put(c, R0, '>')
    c15 = CB + 15
    L.put(c15, R0, '>')
    ec = CB + 16; wc = CB - 1
    L.put(ec, R0, 'v'); L.put(ec, Rw, '<')
    L.put(wc, Rw, '^'); L.put(wc, R0, '>')
    L.put(wc - 1, R0, '@')
    L.room(0, TW, CB + 18, BW - TW + 1)
    sc = CB + 8                       # sweeper drain outgoing column

    # ---- CHECKER ---- (below the sweeper; drain drops straight down; drain-col = sc)
    cx, cy = sc - 12, BW + 4         # so checker drainN col (cx+12) == sc
    hints = emit_checker(L, cx, cy)

    # ---- PIPES ----
    # seq-pipe: reader s(seq)@(6,yr). Source (-1,yr) must have its BACKWARD neighbour on
    # the reader border -> first move WEST so backward = (0,yr) = reader west wall.
    seqW = hints['seqW']             # (cx-1, y(4)) = (10, cy+5)
    sy = seqW[1]
    L.pipe([(-1, yr), (-2, yr), (-2, sy), (seqW[0], sy)])
    # drain-pipe: sweeper bottom (sc,BW+1) straight down into checker NORTH wall.
    drN = hints['drainN']            # (sc, cy-1)
    L.pipe([(sc, BW + 1), (sc, drN[1])])
    # output-pipe: checker south -> O.
    outS = hints['outS']
    L.output_room(outS[0] - 1, outS[1] + 2)
    L.pipe([(outS[0], outS[1]), (outS[0], outS[1] + 1)])
    return L


if __name__ == '__main__':
    import sys
    if '--full' in sys.argv:
        L = build_full()
        print('FOOT', L.footprint())
        print(L.render())
    else:
        L = build_test()
        print('FOOT', L.footprint())
        L.save('/Users/visenbaev/icfpc26/solutions/tcp/tcp-sweep-test.man')
        print('saved')

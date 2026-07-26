import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys, os
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# Subset-sum machine. Belt ring [CNT,T,v_{n-1..0},SENT].
# Pipe geometry (validated): I-read col34(top); O-send col45(right);
# FEED (enqueue) & RETURN (dequeue) BOTH on CTRL left wall so left-column belt
# ops are unambiguous at every row. Left cols -> belt, right/top -> I/O.

STAGE = os.environ.get('SS_STAGE', 'C')  # A=load+dump ; B=search+w-dump ; C=full

def build():
    p = lm.Program(); placed = {}
    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]} vs {ch}")
        placed[(x, y)] = ch; p.put(x, y, ch)

    # ---- rooms & pipes ----
    p.room(10, 0, 42, 92)                    # CTRL cols10..51 rows0..91 interior 11..50 x1..90
    p.input_room(33, -5); p.pipe([(34, -2), (34, -1)])       # I top col34
    p.output_room(54, 5); p.pipe([(52, 6), (53, 6)])         # O right wall row6
    # Compact belt ring (~41 cells) in the left margin -> low pipe latency.
    p.room(2, 40, 7, 5)                       # RELAY cols2..8 rows40..44 interior 3..7 x41..43
    p.pipe([(9, 30), (5, 30), (5, 39)])       # FEED CTRL left row30 -> RELAY top col5
    p.pipe([(4, 39), (4, 20), (9, 20)])       # RETURN RELAY top col4 -> CTRL left row20
    C(3, 41, '>'); C(4, 41, '@'); C(5, 41, 'R'); C(6, 41, 's'); C(7, 41, 'v')
    C(7, 42, '<'); C(3, 42, '^')

    # ================= INIT =================
    p.man(12, 2); C(13, 2, '>')
    C(34, 2, 'r')     # A=n
    C(35, 2, 'b')     # BP=n  (outer counter)
    C(36, 2, 'M')     # B=n
    C(37, 2, '1')     # A=1
    C(38, 2, '{')     # A=2^n
    C(39, 2, 'M')     # B=2^n (CNT_init stash)
    C(40, 2, '1')     # A=1
    C(41, 2, 'N')     # A=-1 (SENT)
    C(42, 2, 'v'); C(42, 3, '<')
    C(15, 3, 's')     # enqueue SENT
    C(12, 3, 'v'); C(12, 6, '>')

    # ================= LOADLOOP READ =================
    C(34, 6, 'r')     # A=value
    C(35, 6, 'v'); C(35, 7, '<')
    C(15, 7, 's')     # enqueue value
    C(14, 7, 'v'); C(14, 8, 'v')

    # ================= ROTATE (r;s;X) =================
    C(14, 9, 'r'); C(14, 10, 's'); C(14, 11, 'X')   # S: A>0 loop(W), A<0 exit(E)
    C(13, 11, '^'); C(13, 8, '>')                    # loop up col13
    C(15, 11, 'v'); C(15, 12, 'm'); C(15, 13, 'd')   # exit -> DEC
    C(14, 13, '<'); C(12, 13, '^')                   # BP>0 loop-read up col12

    # ================= APPEND =================
    C(15, 15, '>'); C(34, 15, 'r')   # A=t (B=2^n)
    C(35, 15, 'W')                    # A=2^n,B=t
    C(36, 15, 'v'); C(36, 16, '<')
    C(15, 16, 's')                    # enqueue CNT
    C(14, 16, 'W'); C(13, 16, 's')    # A=t ; enqueue T
    C(12, 16, 'v'); C(12, 18, '>'); C(13, 18, 'v'); C(13, 19, '>'); C(14, 19, 'v')

    # ================= ROTATE2 =================
    C(14, 20, 'r'); C(14, 21, 's'); C(14, 22, 'X')  # S: A>0 loop(W), A<0(SENT) exit(E)
    C(13, 22, '^'); C(13, 19, '>')                   # loop up col13
    C(15, 22, 'M')                                   # B=-1 ; belt=[CNT,T,v..,SENT] front=CNT

    if STAGE == 'A':
        C(16, 22, 'v'); C(16, 23, '<'); C(13, 23, 'v'); C(13, 24, '>')
        C(14, 24, 'r'); C(45, 24, 's'); C(46, 24, 'X')
        C(46, 25, '<'); C(13, 25, '^'); C(46, 23, 'H')
        return p, placed

    # ================= SEARCH =================
    # Blank cells are glide no-ops; only turns/instructions are placed. Corridors
    # are blank so perpendicular crossings are free.
    # connector: ROTATE2 M(15,22) -> down col16 -> (16,25)< -> west -> REV entry.
    # END loopback merges into connector at (16,24)v.
    C(16, 22, 'v'); C(16, 24, 'v'); C(16, 25, '<'); C(12, 25, 'v'); C(12, 26, '>')

    # ---- REV (row26 eastbound) ----
    C(14, 26, 'r')     # A=CNT
    C(15, 26, 'X')     # E: A>0->CW(S)=continue ; A==0->straight(E)=OUTPUT0
    C(15, 27, 'b')     # BP=cnt (mask)
    C(15, 28, '+')     # A=cnt-1
    C(15, 29, 's')     # enqueue cnt-1
    C(15, 30, 'r')     # A=T
    C(15, 31, 's')     # resend T
    C(15, 32, 'M')     # B=T (remaining)
    C(15, 33, '<'); C(14, 33, 'v')            # -> VLOOP entry (col14 south)

    # ---- VLOOP (r-row 38) ----
    C(14, 34, 'v')     # EXCLUDE re-entry
    C(14, 35, 'v')     # INCLUDE re-entry
    C(14, 38, 'r')     # A=item
    C(14, 39, 's')     # resend
    C(14, 40, 'X')     # S: A>0(value)->CW(W)=VALUE ; A<0(END)->CCW(E)=END
    # VALUE (W)
    C(13, 40, 'x')     # W: bit1->CW(N)=INCLUDE ; bit0->CCW(S)=EXCLUDE
    # INCLUDE (N col13)
    C(13, 39, 'W'); C(13, 38, '-'); C(13, 37, 'M'); C(13, 36, ']'); C(13, 35, '>')
    # EXCLUDE (S col13 -> up col12 -> re-enter col14 at row34)
    C(13, 41, ']'); C(13, 42, '<'); C(12, 42, '^'); C(12, 34, '>')

    # ---- END (E from X(14,40)) ----
    C(15, 40, 'W')     # A=remaining, B=-1
    C(16, 40, 'X')     # E: ==0->MATCH(straight E) ; >0->CW(S) ; <0->CCW(N) -> REV
    C(16, 41, '>'); C(24, 41, '^')            # REV branch S -> col24 rail
    C(16, 39, '>'); C(24, 39, '^')            # REV branch N -> col24 rail
    C(24, 24, '<')                            # rail top -> west -> (16,24)v

    if STAGE == 'B':
        # ---- MATCH: recompute w=cnt, output via col19 rail (STAGE B) ----
        C(17, 40, 'r'); C(18, 40, '-')
        C(19, 40, '^'); C(19, 10, '>')
        C(45, 10, 's'); C(46, 10, 'H')
        C(16, 26, '0'); C(19, 26, '^')        # OUTPUT0 join col19 rail
        return p, placed

    # ================= OUTPUT (STAGE C) =================
    # MATCH: END X(16,40) straight E -> route to Pass K entry (14,46) south.
    C(17, 40, '>'); C(20, 40, 'v'); C(20, 45, '<'); C(14, 45, 'v')

    # ---- Pass K: popcount(w) -> emit k, store w on belt, keep k in B, restore belt ----
    C(14, 46, 'r')     # A=cnt-1
    C(14, 47, '-')     # A=w  (B=-1)
    C(14, 48, 'b')     # BP=w
    C(14, 49, 's')     # enqueue w -> belt=[T,v..,SENT,w]
    C(14, 50, '1'); C(14, 51, 'M'); C(14, 52, '0')   # A=0(k), B=1
    C(14, 53, '>')                            # -> popcount loop (right area)
    # popcount loop
    C(26, 53, 'd')     # E: BP>0->CW(S)=loop ; ==0->straight(E)=DONE
    C(26, 54, 'x')     # S: bit1->CW(W)=INC ; bit0->CCW(E)=SKIP
    C(25, 54, '+'); C(24, 54, 'v')            # INC: A+=1 -> down
    C(27, 54, 'v')                            # SKIP -> down
    C(24, 55, '>'); C(26, 55, 'v'); C(27, 55, '<')   # merge at (26,55)v
    C(26, 56, ']')     # BP>>=1
    C(26, 57, '<'); C(23, 57, '^'); C(23, 53, '>')   # loopback up col23 -> d
    # DONE: M(B=k), emit k, drain to restore belt front=w
    C(27, 53, 'M')     # B=k
    C(45, 53, 's')     # send k to O
    C(46, 53, 'v'); C(46, 58, '<'); C(14, 58, 'v')   # return below popcount -> drain
    # drain: r;s until SENT resent -> belt=[w,T,v..,SENT]
    C(14, 59, 'r'); C(14, 60, 's'); C(14, 61, 'X')   # A>0->loop(W) ; A<0(SENT)->PASSF(E)
    C(13, 61, '^'); C(13, 58, '>')            # loop up col13 -> (14,58)v
    C(15, 61, 'v'); C(15, 62, '<'); C(14, 62, 'v')   # PASSF exit -> Pass F entry

    # ---- Pass F: filter selected (belt=[w,T,v..,SENT], B=k) -> [sel_decreasing] ----
    C(14, 63, 'r')     # A=w
    C(14, 64, 'b')     # BP=w
    C(14, 65, 'r')     # A=T (discard)
    C(14, 66, 'v')     # NOTSEL/setup re-entry
    C(14, 67, 'v')     # SELECTED re-entry
    C(14, 69, 'r')     # A=item
    C(14, 70, 'X')     # S: A>0(value)->CW(W)=FVAL ; A<0(SENT)->CCW(E)=FDONE
    C(13, 70, 'x')     # W: bit1->CW(N)=SELECTED ; bit0->CCW(S)=NOTSEL
    C(13, 69, 's'); C(13, 68, ']'); C(13, 67, '>')   # SELECTED: enqueue, shift -> (14,67)
    C(13, 71, ']'); C(13, 72, '<'); C(12, 72, '^'); C(12, 66, '>')  # NOTSEL: shift -> (14,66)
    C(15, 70, 'v'); C(15, 74, '<'); C(14, 74, 'v')   # FDONE -> Pass RE entry

    # ---- Pass RE: reverse-emit k selected values to O in increasing index order ----
    C(14, 75, 'W')     # A=size (=k)
    C(14, 76, 'X')     # S: A>0->CW(W)=DOROT ; A==0->straight(S)=DONE
    C(14, 77, 'H')     # DONE halt
    C(13, 76, 'v'); C(13, 77, 'b'); C(13, 78, 'M'); C(13, 79, '1')
    C(13, 80, 'W'); C(13, 81, '-'); C(13, 82, 'M')   # BP=m, B=m-1
    C(13, 83, 'v')     # DEQ entry
    C(13, 84, 'r'); C(13, 85, 'm'); C(13, 86, 'a')   # BP>0->CCW(E)=ENQ ; ==0->straight(S)=OUT
    C(14, 86, 's'); C(15, 86, '^'); C(15, 83, '<')   # ENQ: re-enqueue -> loop (13,83)
    C(13, 87, '>'); C(45, 87, 's')            # OUT: send element to O
    C(46, 87, '^'); C(46, 74, '<')            # loop back -> (14,74)v -> OUTER

    # ---- OUTPUT0 (STAGE C): emit single 0, halt ----
    C(16, 26, '0'); C(17, 26, 'v'); C(17, 30, '>'); C(45, 30, 's'); C(46, 30, 'H')

    return p, placed

if __name__ == '__main__':
    p, _ = build()
    print(p.render())
    print('footprint', p.footprint())
    p.save(_REPO + '/solutions/subset-sum/ss.man')

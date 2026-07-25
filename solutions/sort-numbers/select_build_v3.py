"""Streaming selection sort v3 — COMPACT re-embed of v2's proven op-graph.

Same algorithm/semantics as select-v2 (single FIFO ring, bias +10001, sentinel -1,
per-pass min extraction).  Compressed controller: scan core hugs the right wall,
LOAD/EMIT glides pulled tight, ring folds as two tall NON-adjacent legs.

Key layout trick: the LOAD init reads its bias literal HORIZONTALLY on row1 and the
init-return lives on the LEFT (v2's row2/row4 merge discipline) so it never crosses
the right-side load loop.  (A vertical bias literal reads as 0 on the oracle -> avoid.)

Registers: A scratch ; B = bias(LOAD)/min(SCAN) ; BP = count(LOAD).
Mouths:  LEFT wall  INPUT(in,row3)  OUTPUT(out,row6)
         RIGHT wall RET(in,row7)     FEED(out,row9)
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout, place_pipe, relay_man, DIRS

OUT = 'solutions/sort-numbers/select-v3.man'
DX = 2   # scan core shifted +2 vs the col8 version (gives a 9-wide left region)


def build_controller(L):
    put = L.put
    L.room(0, 0, 17, 21)      # interior cols 1..15 rows 1..19 ; right wall col16

    # ============ SCAN CORE (v2 shape, hugging right wall; rows 8..16) ==============
    put(11, 8, '>')           # MREV merge
    put(12, 8, 'r')           # read first token (RET)
    put(13, 8, 'X')           # E: real->S, sentinel->N
    put(13, 9, 'M')           # B := min
    put(13, 10, 'v')          # MSCAN merge
    put(13, 11, 'r')          # read token (RET)
    put(13, 12, 'X')          # S: real->W, sentinel->E
    put(12, 12, '-')          # A = token - min
    put(11, 12, 'X')          # W: keep(>0)->N, newmin(<0)->S, equal(0)->W
    put(11, 11, '+'); put(11, 10, '>'); put(12, 10, 's')   # KEEP: token -> FEED -> MSCAN
    put(10, 12, '^'); put(10, 11, '+'); put(10, 10, '>')   # EQUAL -> (11,10) -> (12,10)s
    put(11, 13, '+'); put(11, 14, 'W'); put(11, 15, 's')   # NEWMIN: old min -> FEED
    put(11, 16, '>'); put(15, 16, '^'); put(15, 10, '<')   # climb col15 -> (14,10) -> MSCAN

    put(1, 8, '>')            # MREV approach highway (row8 glide -> (11,8))

    # EMPTY: REV sentinel first token -> N at (13,7); W row7, up clear col11, W row2 -> ML.
    put(13, 7, '<'); put(11, 7, '^'); put(11, 2, '<'); put(2, 2, '^')   # -> (2,1) ML merge

    # ============ LOAD (v2 discipline: horiz bias row1, init-return LEFT) ============
    put(1, 1, '@'); put(2, 1, '>')         # ML merge (spawn + EMPTY re-entry)
    put(3, 1, 'r'); put(4, 1, 'b')         # A=n ; BP=n
    for i, ch in enumerate('`10001`'):
        put(5 + i, 1, ch)     # horizontal bias cols 5..11 -> A=10001 at (11,1)
    put(12, 1, 'M')           # B := bias
    put(13, 1, 'v'); put(13, 4, '<'); put(2, 4, '^')       # init return: col13 down, row4 W, MLL
    # LOAD LOOP row3
    put(2, 3, '>')            # MLL merge
    put(3, 3, 'r'); put(4, 3, '+')         # A=v ; A=v+bias
    put(14, 3, 's')           # send FEED (glide 5..13)
    put(15, 3, 'v'); put(15, 4, 'm'); put(15, 5, 'd')      # bp-- ; S: bp>0->W loop, bp==0->S exit
    put(14, 5, '<'); put(2, 5, '^')        # loopback row5 -> col2 up -> MLL
    # exit (bp==0): sentinel -> FEED ; W row6 -> col1 rail -> highway
    put(15, 6, '<'); put(14, 6, '1'); put(13, 6, 'N'); put(12, 6, 's')   # A=-1 -> FEED
    put(1, 6, 'v')            # glide W to col1 -> down to (1,8) highway

    # ============ EMIT (sentinel MSCAN-X(13,12)->E to (14,12)) =====================
    put(14, 12, 'v')          # descend col14
    put(14, 13, '1'); put(14, 14, 'N'); put(14, 15, 's')   # fresh sentinel -> FEED
    put(14, 17, '<')          # (14,16) glide: emit descends S, NEWMIN glides E ; row17 west
    for i, ch in enumerate('`10001`'):
        put(13 - i, 17, ch)   # bias literal cols 13..7 read W -> A=10001 at (7,17)
    put(6, 17, 'N')           # A = -10001
    put(5, 17, '+')           # A = -10001 + min = minval
    put(4, 17, 'v'); put(4, 18, 's')       # -> OUTPUT (left)
    put(4, 19, '<'); put(1, 19, '^')       # loop: col1 rail up -> (1,8) highway
    return L


def build():
    L = Layout()
    build_controller(L)
    # ---- I/O rooms tucked off the LEFT to kill the width extension ----
    # INPUT: room top-right (ring's free upper area); mouth on right wall (16,2).
    #        LOAD reads at col3 still pick INPUT (nearer than RET even from the left).
    L.input_room(19, 1)       # I at (20,2) ; left border col19
    place_pipe(L, [(18, 2), (17, 2)], DIRS['W'])        # I -> ctrl right wall (16,2)
    # OUTPUT: room below; mouth on bottom wall (4,20).  EMIT sends at (4,18).
    # OUTPUT room bottom (rows21..23 -> height 24); L-pipe from ctrl bottom (4,20).
    L.output_room(9, 21)      # O at (10,22) ; left border col9
    place_pipe(L, [(4, 21), (4, 22), (5, 22), (6, 22), (7, 22), (8, 22)], DIRS['E'])  # ->O(9,22)
    # ---- ring: relay bottom-right ; FEED top(col19), RET top(col21) ; gap col20 ----
    L.room(18, 16, 6, 4)      # relay room cols18..23 rows16..19
    relay_man(L, 19, 17)
    place_pipe(L, [(17, 9), (18, 9), (19, 9), (19, 10), (19, 11), (19, 12),
                   (19, 13), (19, 14), (19, 15)], DIRS['S'])      # FEED ctrl(16,9)->relay top(19,16)
    place_pipe(L, [(21, 15), (21, 14), (21, 13), (21, 12), (21, 11), (21, 10),
                   (21, 9), (21, 8), (21, 7), (20, 7), (19, 7), (18, 7), (17, 7)],
               DIRS['W'])                                        # RET relay top(21,16)->ctrl(16,7)
    return L


if __name__ == '__main__':
    L = build()
    print('footprint:', L.footprint())
    L.save(OUT)
    print(L.render())

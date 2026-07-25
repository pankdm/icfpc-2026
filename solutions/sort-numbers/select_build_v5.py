"""Streaming selection sort v5 — HAND-CRAFTED TIGHT SCAN CELL, compact frame.

Same proven algorithm (single FIFO ring, bias +10001, sentinel -1, per-pass min
extraction).  Two levers combined:
  1. TIGHT NEWMIN: v4's newmin branch returned via a ~20-cell detour; here it runs
     +,W east along row12 and climbs the ADJACENT col11 back to the merge in ~7
     cells (EMIT crosses col11 at the blank glide (11,11) at 90 deg).
  2. SMALL BOX: core at cols8-13 so the ctrl room is 15 wide; the ring is tucked in
     a narrow strip beside/below it; OUTPUT below-left.

Registers: A scratch ; B = bias(LOAD)/min(SCAN) ; BP = count(LOAD).
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout, place_pipe, relay_man, DIRS

OUT = 'solutions/sort-numbers/select-v5.man'


def build_controller(L):
    put = L.put
    L.room(0, 0, 15, 18)      # interior cols 1..13 rows 1..16 ; right wall col14

    # ============ TIGHT SCAN CORE (cols 7..13, rows 6..12) =======================
    put(8, 7, '>')            # first-token merge (LOAD exit + per-pass highway land here)
    put(9, 7, 'r')            # read first token (RET)
    put(10, 7, 'X')           # E: real->S (start), sentinel->N (round done)
    put(10, 8, 'M')           # B := min
    put(10, 9, 'v')           # MSCAN MERGE (heading S)
    put(10, 10, 'r')          # READ token
    put(10, 11, 'X')          # S: real->W (compare), sentinel->E (EMIT)
    put(9, 11, '-')           # A = token - min
    put(8, 11, 'X')           # W: keep(>0)->N, newmin(<0)->S, equal(0)->W

    # KEEP: restore token, send FEED, back to MERGE
    put(8, 10, '+'); put(8, 9, '>'); put(9, 9, 's')        # +token -> FEED -> (10,9)

    # EQUAL: restore token (min unchanged) -> reuse KEEP send
    put(7, 11, '^'); put(7, 10, '+'); put(7, 9, '>')       # -> (8,9)> -> (9,9)s

    # NEWMIN (tight): +token, swap(B:=token ; A:=old min), climb col11, send, merge
    put(8, 12, '>')           # turn E on row12
    put(9, 12, '+')           # A = token
    put(10, 12, 'W')          # swap: B := token (new min), A := old min
    put(11, 12, '^')          # turn N up col11
    #    (11,11) BLANK glide — crossing with EMIT (EMIT E, NEWMIN N)
    put(11, 10, 's')          # send old min -> FEED (heading N)
    put(11, 9, '<')           # -> W -> (10,9) MERGE

    # EMPTY (sentinel as first token -> round done): (10,7)X sentinel->N; glide up col10
    put(10, 2, '<'); put(2, 2, '^')        # (10,6..3 glide) -> row2 W -> (2,1) ML merge

    # ============ LOAD (horiz bias row1, init-return LEFT) =======================
    put(1, 1, '@'); put(2, 1, '>')         # ML merge (spawn + EMPTY re-entry)
    put(3, 1, 'r'); put(4, 1, 'b')         # A=n ; BP=n
    for i, ch in enumerate('`10001`'):
        put(5 + i, 1, ch)     # horizontal bias cols 5..11 -> A=10001 at (11,1)
    put(12, 1, 'M')           # B := bias
    put(13, 1, 'v'); put(13, 4, '<'); put(2, 4, '^')       # init return: col13 down, row4 W, MLL
    put(2, 3, '>')            # MLL merge
    put(3, 3, 'r'); put(4, 3, '+')         # A=v ; A=v+bias
    put(5, 3, 's')            # send FEED
    put(6, 3, 'm'); put(7, 3, 'd')         # bp-- ; E: bp>0->S loop, bp==0->E exit
    put(7, 4, '<')                         # loopback (bp>0): row4 W back to (2,4)^ MLL
    put(8, 3, 'v')                         # exit (bp==0): turn S
    put(8, 4, '1'); put(8, 5, 'N'); put(8, 6, 's')         # A=1 -> -1 -> send sentinel FEED
    #    (8,6)s -> S -> (8,7)'>' first-token merge

    # per-pass return highway (row7 -> first token (8,7))
    put(1, 7, '>')

    # ============ EMIT (sentinel MSCAN-X(10,11)->E; glide E via (11,11),(12,11) to col13)
    # descent on col13 + bias cols6..12 so EMIT backticks (6,12) DON'T column-align with
    # LOAD backticks (5,11) -> no spurious vertical backtick literal over the core glyphs.
    put(13, 11, 'v')          # descend col13 (entered E through blank (11,11),(12,11))
    put(13, 12, '1'); put(13, 13, 'N'); put(13, 14, 's')   # fresh sentinel -> FEED
    put(13, 15, '<')          # turn W on row15
    for i, ch in enumerate('`10001`'):
        put(12 - i, 15, ch)   # bias cols 12..6 read W -> A=10001 at (5,15); palindrome
    put(5, 15, 'N')           # A = -10001
    put(4, 15, '+')           # A = -10001 + min = minval
    put(3, 15, 's')           # -> OUTPUT (heading W, no wall fault)
    put(1, 15, '^')           # loop: col1 rail up -> (1,7) highway
    return L


def build():
    L = Layout()
    build_controller(L)
    # ---- INPUT room top-right ----
    L.input_room(17, 0)       # I at (18,1) ; left border col17
    place_pipe(L, [(16, 1), (15, 1)], DIRS['W'])        # I -> ctrl right wall (14,1)
    # ---- OUTPUT room below-left ; EMIT sends at (2,15) -> attach ctrl bottom (2,17) ----
    L.output_room(6, 18)      # O at (7,19) ; left border col6
    place_pipe(L, [(3, 18), (3, 19), (4, 19), (5, 19)], DIRS['E'])  # (3,17 wall)->O(6,19)
    # ---- ring: relay bottom-right ; FEED col16, gap col17, RET col18 ; cap 9+1+13=23 ----
    L.room(15, 16, 6, 4)      # relay room cols15..20 rows16..19
    relay_man(L, 16, 17)      # @(16,17)>Rv ; ^(17,18)s< ; FEED top(16,16), RET top(18,16)
    place_pipe(L, [(15, 8), (16, 8), (16, 9), (16, 10), (16, 11), (16, 12), (16, 13),
                   (16, 14), (16, 15)], DIRS['S'])      # FEED ctrl(14,8)->relay top(16,16)
    place_pipe(L, [(18, 15), (18, 14), (18, 13), (18, 12), (18, 11), (18, 10), (18, 9),
                   (18, 8), (18, 7), (18, 6), (17, 6), (16, 6), (15, 6)],
               DIRS['W'])                               # RET relay top(18,16)->ctrl(14,6)
    return L


if __name__ == '__main__':
    L = build()
    print('footprint:', L.footprint())
    L.save(OUT)
    print(L.render())

"""Streaming selection sort v2 — folded layout, tight 8-cell inner scan loop.
Same algorithm as v1 (single FIFO ring, bias +10001, sentinel -1).

Horizontal plan (scan core hugs the RIGHT wall so FEED/RET are the nearest pipes):
  RIGHT wall: FEED(23,12) out, RET(23,14) in   <- scan/rev reads, recirc sends
  LEFT  wall: INPUT(0,3) in, OUTPUT(0,20) out   <- load reads, emit output
Registers: A scratch; B=bias(LOAD)/min(SCAN); bp=count.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout, place_pipe, relay_man, DIRS, pipelen, ring_capacity

OUT = 'solutions/sort-numbers/select-v2.man'
RW = 23   # right wall col


def build_controller(L):
    put = L.put
    L.room(0, 0, 24, 26)      # interior cols 1..22 rows 1..24 ; right wall col23

    # ============ REV + SCAN CORE (tight 8-cell KEEP loop), right side ============
    put(15, 8, '>')           # MREV merge (E)
    put(16, 8, 'r')           # read first token (RET)
    put(17, 8, 'X')           # E: real(>0)->S, sentinel(<0)->N
    put(17, 9, 'M')           # B := min
    put(17, 10, 'v')          # MSCAN merge
    put(17, 11, 'r')          # read token (RET)
    put(17, 12, 'X')          # S: real->W, sentinel->E
    put(16, 12, '-')          # A = token - min
    put(15, 12, 'X')          # W: keep(>0)->N, newmin(<0)->S, equal(0)->W
    # KEEP
    put(15, 11, '+'); put(15, 10, '>'); put(16, 10, 's')   # send token FEED -> merge
    # EQUAL
    put(14, 12, '^'); put(14, 11, '+'); put(14, 10, '>')   # -> (15,10) -> (16,10)s -> merge
    # NEWMIN
    put(15, 13, '+'); put(15, 14, 'W'); put(15, 15, 's')   # old min FEED
    put(15, 16, '>'); put(19, 16, '^'); put(19, 10, '<')   # climb col19 -> (18,10) -> merge

    # MREV approach highway: (1,8)'>' -> glide row8 E -> (15,8) MREV merge.
    put(1, 8, '>')

    # EMPTY: REV sent -> N at (17,7). Up col17 to row2, W row2 to (2,2), up to ML(2,1).
    put(17, 7, '^'); put(17, 2, '<')            # up col17 to row2, W
    put(2, 2, '^')                              # W glide row2 ; up -> (2,1) ML merge

    # ============ EMIT ============
    # sentinel X1(17,12) -> E ; glide to col22 ; descend ; sentinel->FEED ;
    # row20 read bias westward ; output min-bias -> OUTPUT(left) ; loop to MREV highway.
    put(22, 12, 'v')          # (18..21,12) glide E ; descend col22
    put(22, 13, '1'); put(22, 14, 'N'); put(22, 15, 's')   # sentinel -> FEED
    put(22, 20, '<')          # glide down ; turn W on row20
    for i, ch in enumerate('`10001`'):
        put(13 - i, 20, ch)   # bias literal cols 13..7 read W -> A=10001 at (7,20)
    put(6, 20, '-')           # A = 10001 - min
    put(5, 20, 'N')           # A = min - 10001
    put(4, 20, 'v')           # turn S
    put(4, 21, 's')           # -> OUTPUT (left)
    put(4, 22, '<'); put(1, 22, '^')            # loop: W row22, climb col1 to (1,8) highway

    # ============ LOAD ============
    put(1, 1, '@'); put(2, 1, '>')      # ML merge
    put(3, 1, 'r'); put(4, 1, 'b')      # A=n ; bp=n
    for i, ch in enumerate('`10001`'):
        put(5 + i, 1, ch)     # horizontal bias cols5..11 -> A=10001
    put(12, 1, 'M')           # B := bias
    put(13, 1, 'v'); put(13, 4, '<'); put(2, 4, '^')       # init return -> (2,3) MLL merge
    # LOAD LOOP row3
    put(2, 3, '>')            # MLL merge
    put(3, 3, 'r'); put(4, 3, '+')      # A=v ; A=v+bias
    put(20, 3, 's')           # send FEED (glide 5..19)
    put(21, 3, 'v'); put(21, 4, 'm'); put(21, 5, 'd')      # bp-- ; S: bp>0->W loop, bp==0->S exit
    put(20, 5, '<'); put(2, 5, '^')     # loopback row5 -> col2 up -> merge
    # exit (bp==0): sentinel -> FEED ; route to MREV highway
    put(21, 6, '1'); put(21, 7, 'N'); put(21, 8, 's')      # sentinel -> FEED
    put(21, 9, 'v'); put(21, 18, '<')   # descend col21 ; row18 W
    put(1, 18, '^')           # climb col1 to (1,8) highway (shared with emit-loop)
    return L


def build():
    L = Layout()
    build_controller(L)
    put = L.put
    # ---- I/O rooms (left) ----
    L.input_room(-5, 2)       # I at (-4,3) ; right border col-3
    place_pipe(L, [(-2, 3), (-1, 3)], DIRS['E'])       # I -> ctrl (0,3)
    L.output_room(-5, 19)     # O at (-4,20)
    place_pipe(L, [(-1, 20), (-2, 20)], DIRS['W'])     # ctrl (0,20) -> O
    # ---- ring: relay (right) + NON-ADJACENT folded FEED/RET (no parallel legs) ----
    # FEED vertical leg col25, RET vertical leg col27 (gap col26) so no two pipe legs
    # are orthogonally adjacent -> full effective capacity, short latency (~9 + ~13).
    L.room(25, 16, 6, 6)      # relay room cols25..30 rows16..21
    relay_man(L, 26, 17)      # @>Rv / ^s< at (26,17)
    place_pipe(L, [(24, 8), (25, 8), (25, 9), (25, 10), (25, 11),
                   (25, 12), (25, 13), (25, 14), (25, 15)], DIRS['S'])          # FEED -> relay (25,16)
    place_pipe(L, [(27, 15), (27, 14), (27, 13), (27, 12), (27, 11), (27, 10),
                   (27, 9), (27, 8), (27, 7), (27, 6), (26, 6), (25, 6), (24, 6)], DIRS['W'])  # RET -> ctrl (23,6)
    return L


if __name__ == '__main__':
    L = build()
    print('footprint:', L.footprint())
    L.save(OUT)
    print(L.render())

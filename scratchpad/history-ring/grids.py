#!/usr/bin/env python3
"""Room content grids for the ring build (content only, no borders).

Coordinates: row 0 = top interior row.  See design notes in builder.
"""

# D1 classifier, interior 19 wide x 5 tall.
# Pipes: IN west wall row1; OUT east wall? -> single in/out so any wall.
# Tags: 0 -> -1 | 1..16 -> v | ESC(29),k -> k | 17..91 -> -(v+32)
D1 = [
    #0123456789012345678
    "v<<<<<<<<<<<<<<<<<<",   # row0 return corridor (westbound), v at col0
    ">`17`M  r X `1`Ns^ ",   # row1 main east: r@8, X1@10; year lane 12-16, ^17
    "  >WM`32`v-        ",   # row2 recover east: >2 W3 M4 lit5-8 v9; -10 (shared)
    " vX~`92`M+X+s^     ",   # row3: X3@2 ~3 lit4-7 M8 +9 X2@10; small +11 s12 ^13
    " >rs  ^  >Ns      ^",   # row4: ESC >1 r2 s3 ^6; plain >9 N10 s11 ^18
]

# L1 ring lookup, interior 23 wide x 6 tall.
# Pipes: IN west wall row1; OUT east wall row1; RING_out east wall row4;
#        RING_in east wall row5.
# Tags: T<0 -> output |T|-1 ; T=g>0 -> ring entry g, ring restored via sentinel -1.
L1 = [
    #01234567890123456678901 2
    "v<<<s-N<               ",  # row0: passthrough westbound: <7 N6 -5 s4; v0
    ">`1`Mr X               ",  # row1 main east: lit1-3 M4 r5 X1@7
    "       b         >sv   ",  # row2: b@7; hit: >17 s18(OUT) v19
    "       v   > md r s^>sv",  # row3: v7; rot1 >11 m13 d14; hit r15 s16 ^17; restore >19 s20 v21
    "       >   ^s r<   ^X<v",  # row4: >7 entry; rot1 ^11 s12 r13 <14; restore ^19 X20? <21 v22
    "^                 <s  <",  # row5: sentinel: <18? s19?...
]
# NOTE: L1 above is a sketch; the authoritative grid is built in build_v1.py
# after simulation-driven fixes.

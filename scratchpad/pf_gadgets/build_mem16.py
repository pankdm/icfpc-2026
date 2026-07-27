#!/usr/bin/env python3
"""PF GADGET 4 -- MEM16: the whole per-cell memory as ONE device.

256 board cells x a 3-bit field packed into 16 nibbles per 64-bit word, one
word per little man.  Field values:  0 free/unvisited, 1/2/3 = (dist mod 3)+1,
4 = wall.  Bit 3 of every nibble is ALWAYS 0, so every mask (7<<sh, sh<=60) and
every payload (t<<sh, t<=4) stays POSITIVE -- that is what lets the word man
dispatch on the sign of the single incoming value with one `X`.

PROTOCOL (controller <-> hub), one value per send:
    send  nb > 0        transaction on cell nb: the hub replies with the
                        3-bit field, then WAITS for one more value
    send  t  (0..4)     0 = leave the cell alone, t>0 = OR t into the field
                        (the word man only consumes it when the field was 0,
                        and the hub only forwards it when t > 0 -- the two
                        conditions coincide because the controller sends t>0
                        exactly when the field it just read was 0)
    send  v < 0         RESET: broadcast -K to all 16 words; each ANDs its word
                        with K = 0x4444444444444444, keeping the wall bits and
                        clearing every tag.  No reply, no follow-up value.

HUB   entry `r X`;  v<0 -> load -K, `S` (S = send to EVERY outgoing pipe, and
      the hub's only outgoing pipes are the 16 word pipes).  v>0 -> compute
      q = nb>>4 into BP and sh = 4*(nb&15) into B, mask = 7<<sh into A, then
      walk a 4-level `x`/`]` decode tree to leaf p.  Leaf p serves word
      q = bitrev4(p) -- the tree consumes BP LSB-first while the leaves are laid
      out in row order, and the words are interchangeable, so nothing has to be
      un-reversed.  B survives the tree (`x`,`]` touch only BP), so the leaf can
      still build t<<sh with one `{`.

WORD  `r X`:  A>0 -> `& s X` (field to the collector) then free: `r | M`;
              A<0 -> `N & M` (reset).

usage: build_mem16.py [out.man]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from layout import Layout                                       # noqa: E402

K_MASK = 0x4444444444444444          # 4919131752989213764

# ---------------------------------------------------------------- geometry
NW = 16                              # words
WROW = 6                             # rows per word room
WY0 = 6                              # first word room's top wall row
WX = 24                              # word rooms' left wall
WW = 14                              # word room width  (interior x+1..x+12)
CX = 40                              # collector left wall
CW = 7
T = 8                                # decode tree entry column (hub interior)
RC = 20                              # hub return column
HW = 22                              # hub width (x 0..21)


def leaf_row(i):
    return WY0 + WROW * i + 2        # word room i's interior row 2 (its `r`)


def out_row(i):
    return WY0 + WROW * i + 3        # word room i's interior row 3 (its `s`)


def build(out=None, standalone=True):
    L = Layout()
    p = L.p
    hub_h = leaf_row(NW - 1) + 4
    p.room(0, 0, HW, hub_h)                       # hub: x 0..34, y 0..hub_h-1

    # ---- hub entry / dispatch  (pure router: the controller does the maths)
    for x, ch in enumerate('>@rX', start=1):
        L.put(x, 2, ch)
    L.put(1, 4, '^')                              # return corridor -> entry
    L.put(5, 2, 'v')                              # q == 0 falls through to row 3
    L.put(4, 1, '>')                              # v < 0: broadcast the reset word
    L.put(5, 1, 'S')
    L.put(6, 1, 'v')
    L.put(6, 4, '<')
    L.put(4, 3, '>')                              # v > 0
    L.put(5, 3, '>')                              # q == 0 joins here
    L.put(6, 3, 'b')                              # BP = q
    L.put(7, 3, 'v')

    # ---- decode tree ------------------------------------------------------
    rows = [leaf_row(i) for i in range(NW)]

    def node_row(level, j):
        span = NW >> level
        blk = rows[j * span:(j + 1) * span]
        return (blk[0] + blk[-1]) // 2

    root = node_row(0, 0)
    L.put(7, root, '>')
    L.put(T, root, 'x')
    for level in range(1, 4):
        for j in range(1 << level):
            r = node_row(level, j)
            L.put(T + 2 * (level - 1), r, '>')
            L.put(T + 2 * (level - 1) + 1, r, ']')
            L.put(T + 2 * level, r, 'x')
    # ---- leaves -----------------------------------------------------------
    for i in range(NW):
        y = rows[i]
        L.put(T + 6, y, '>')
        L.put(T + 7, y, 'r')                      # mask from the controller
        L.put(T + 8, y, 's')                      # mask -> word i
        L.put(T + 9, y, 'r')                      # payload from the controller
        L.put(T + 10, y, 's')                     # payload -> word i (0 = no-op)
    for y in range(5, hub_h - 1):                 # the return column
        L.put(RC, y, '^')
    L.put(RC, 4, '<')

    # ---- word rooms -------------------------------------------------------
    for i in range(NW):
        top = WY0 + WROW * i
        p.room(WX, top, WW, WROW)                 # interior x WX+1..WX+12
        def w(dx, dy, ch, top=top):
            L.put(WX + dx, top + dy, ch)
        for dx, ch in enumerate('>@rX', start=1):
            w(dx, 2, ch)
        w(1, 4, '^')
        # RESET arm (A<0 -> north):  A = -K -> word &= K, keeping the wall bits
        for dx, ch in enumerate('>N&M', start=4):
            w(dx, 1, ch)
        w(12, 1, 'v')
        w(12, 4, '<')
        # TXN arm (A>0 -> south): field = word & mask, ship it, then OR the
        # payload in.  The controller sends payload 0 whenever the field was
        # non-zero, and `| M` with 0 is a no-op -- so no second branch is needed
        # and nothing can deadlock waiting for a value that never comes.
        for dx, ch in enumerate('>&sr|M', start=4):
            w(dx, 3, ch)
        w(10, 3, 'v')
        w(10, 4, '<')
        p.pipe([(HW, leaf_row(i)), (WX - 1, leaf_row(i))])          # hub -> word
        p.pipe([(WX + WW, out_row(i)), (CX - 1, out_row(i))])       # word -> coll

    # ---- collector --------------------------------------------------------
    ctop = WY0
    cbot = WY0 + WROW * NW - 1
    p.room(CX, ctop, CW, cbot - ctop + 1)
    cy = out_row(NW // 2)
    for dx, ch in enumerate('>@Rsv', start=1):
        L.put(CX + dx, cy, ch)
    L.put(CX + 5, cy + 1, '<')
    L.put(CX + 1, cy + 1, '^')

    if standalone:
        p.input_room(2, hub_h + 2)
        p.pipe([(3, hub_h + 1), (3, hub_h)])
        p.pipe([(CX + CW, cy), (CX + CW + 1, cy)])
        p.output_room(CX + CW + 2, cy - 1)
    if out:
        p.save(out)
    return p


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'mem16.man')
    prog = build(out=path)
    print('wrote %s  %dx%d box=%d' % ((path,) + prog.footprint()))

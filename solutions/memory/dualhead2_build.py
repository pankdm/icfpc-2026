#!/usr/bin/env python3
"""memory DUAL-HEAD -- one 128-slot belt circulating through TWO engine rooms.

*** CLOSED.  DO NOT BUILD.  Read dualhead2_floor.py's docstring first: it carries
the closure on MEASURED geometry (box 4356 routed-but-crossing / ~5329 fixed,
against the single-engine lineage's live 24x24 = 576 at server 8,290,368 -- 9.3x
worse in box for a 1.36x tick win), the forced oB-x-cmdB crossing proof, and the
two things here that ARE worth reusing:
    * tools/bindsolve.py   -- enumerate pipe attachments instead of deriving
                              midpoints by hand (68 valid assignments for the
                              CONTROL below; ZERO for the two-send variant)
    * the ONE-SEL-SEND trick below -- `b` stashes op into BP the instant `x` has
                              consumed the selector bit, so the shared tail can
                              test it with `a`.  A general register-wall escape.
The rooms in this file are correct and fully binding-checked; it is the floorplan
that cannot be embedded.  Everything below is the design as built.

    ENGINE A --p1--> ENGINE B --p2--> ENGINE A       64 values in each pipe

Each engine taps the value at its OWN incoming dest, so there are two tap points
64 apart and every access rotates to the NEARER head: mean relays/op 35.61 against
48.46 for the single-head belt.  Both HOP rooms disappear (each engine is the
other's relay).  Protocol validated 7/7 public + 20000 fuzz in
scratchpad/dualhead/proto128.py (branch worktree-agent-aff5a0486cce150f2).

Design provenance: solutions/memory/dualhead_build.py @ 23fafa8 carries the full
derivation.  This file BUILDS it, and takes that file's finding (3) -- the ESCAPE:

  MERGE gets a THIRD incoming pipe (SEL) from CONTROL carrying `which`, and reads
  the selected engine explicitly instead of with `R`.  Output ordering then comes
  from CONTROL (which knows the op order), so it no longer depends on belt drift
  and the "belts must be exactly 64 or 65 cells" constraint DISAPPEARS: the belts
  only need >= 64 cells (>= 65 to avoid the both-pipes-full deadlock) and may be
  routed freely.  MERGE exists at all because the output room accepts at most one
  incoming pipe (interpreter/parser.py:350).

WHY THE BELT IS 128 AND NOT 100.  CONTROL needs prev, delta and a divisor live at
once and BP is write-only; with a power-of-two belt the head selector falls out of
BP alone (`b` BP=delta ; `]` x6 ; `x` on the low bit), so B=prev is never touched.
Price of 128 over 100: mean relays 28.24 -> 35.61.

PREV IS NEVER REDUCED (it grows 2..66 per op, so delta goes large and NEGATIVE);
safe because every decode is floored, so rem/a come out non-negative with no branch:
    rem = delta mod 8 ;  a = (delta>>3) mod 8 ;  relays before the tap = 8a+rem+1

CMD STREAM per op, per engine:  [delta, value, op, which]
    which == 0  -> THIS room taps (then `op` picks read vs write)
    which <  0  -> this room does a plain relay
The engines are BYTE-IDENTICAL: room B's head is +64, which does not change delta's
low 6 bits, so rem and a -- the only things the rings consume -- are the same; the
selector is the only asymmetry and CONTROL sends it as a cmd item.

*** ONE SEL SEND, NOT TWO. ***  MERGE must not be told anything on a write (no
engine sends it a value then), but `which` is only known in the leaf, where `op` is
dead.  Fix: each leaf arm stashes op into BP (`b`, right after the `x` branch --
BP's low bit has already been consumed), and the shared tail tests it with `a`, so
the single SEL send happens on READS ONLY.  That is what lets the whole controller
keep 2 leaves instead of 4 and keeps SEL down to one binding region.

PIPE BINDING is solved, not guessed: scratchpad bind-solver brute-forces the three
CONTROL attachments against every send cell (see CTRL_SENDS below); every op is
STRICTLY nearest its intended pipe, never on a midpoint (a tie resolves by reading
order and silently reaches the wrong room -- dualhead_build.py finding (4)).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from littleman import Program                                    # noqa: E402

BELT, HALF = 128, 64

# ── engine geometry ─────────────────────────────────────────────────────────
# All four engine pipes attach to the BOTTOM wall, so binding is decided purely by
# COLUMN (the |y-wall| term cancels):
#     OX x=1      CMD x=3      PIN x=9      POUT x=14
#   CMD/PIN midpoint 6   : `r` at x<=5 reads COMMANDS, at x>=7 reads the BELT
#   OX/POUT midpoint 7.5 : `s` at x>=8 sends to the BELT, never to the merge pipe
# The read tap uses `S` (send to EVERY outgoing pipe = belt + merge) so it needs no
# binding at all.  Moving any of these columns silently re-binds instructions.
X_OX, X_CMD, X_PIN, X_POUT = 1, 3, 9, 14
ENG_W, ENG_H = 17, 23            # interior cols 1..15, rows 1..21

CTRL_W, CTRL_H = 15, 27          # interior cols 1..13, rows 1..25
MERGE_W, MERGE_H = 11, 9         # interior cols 1..9, rows 1..7


# ── the shared vertical relay ring ──────────────────────────────────────────
def vring(P, down, up, top, nrelay):
    """Vertical 2-column ring with a MERGED guard-bypass / ring-exit cell.

    The man arrives WESTBOUND on row `top`.
        (down, top) 'a' guard : BP>0 -> ccw(west->south) into the ring
                                BP==0 -> straight west onto the exit cell
        (up,   top) '<' exit  : ring-exit (from the north) and guard-bypass
                                (from the east) MERGE here, both heading west
    Testing BEFORE entering is what makes rem==0 / a==0 run no lap at all.
    Each column's relay run must be EVEN so it starts on 'r' and ends on its
    matching 's': that adjacency (send time == receive time + 1) is what keeps
    belt ORDER correct.  Returns the bottom row.
    """
    dn = 2 * ((nrelay + 1) // 2)
    upn = 2 * nrelay - dn
    m_on_up = (dn - upn) >= 1
    bot = top + (2 if m_on_up else 3) + dn
    P(down, top, 'a')
    P(down, top + 1, 'v')
    off = top + 2
    if not m_on_up:
        P(down, top + 2, 'm')
        off = top + 3
    for i in range(dn):
        P(down, off + i, 'rs'[i % 2])
    P(down, bot, '<')
    P(up, bot, '^')
    for i in range(upn):
        P(up, bot - 1 - i, 'rs'[i % 2])
    for y in range(top + 2, bot - upn):
        P(up, y, ' ')
    if m_on_up:
        P(up, top + 2, 'm')
    P(up, top + 1, 'd')
    P(up, top, '<')
    return bot


# ── one engine room (both engines are byte-identical) ───────────────────────
def engine(put, ox, oy):
    P = lambda x, y, c: put(ox + x, oy + y, c)

    # init: A=16, BP=16, A=0, then 16 laps x 4 sends of 0 = 64 zeros into the
    # outgoing belt.  4 sends/lap (not 8) keeps every init `s` at x>=9, which is
    # what binds them to the belt rather than the merge pipe (midpoint 7.5).
    for i, c in enumerate("@`16`b0v"):
        P(1 + i, 1, c)
    P(8, 2, '>')
    for i in range(4):
        P(9 + i, 2, 's')
    P(13, 2, 'v'); P(13, 3, '<')
    for x in range(10, 13):
        P(x, 3, ' ')
    P(9, 3, 'm'); P(8, 3, 'd')            # BP>0 -> cw(west->north) = another lap
    for x in range(2, 8):
        P(x, 3, ' ')
    P(1, 3, 'v')                          # BP==0 -> fall into the main loop

    # row 4: decode delta into rem (BP) and a (B)
    #   r:A=delta M:B=delta 8 W /:A=delta>>3,B=rem W:A=rem b:BP=rem
    #   W:A=delta>>3 M 8 W %:A=(delta>>3)%8=a M:B=a
    P(1, 4, '>')
    for i, c in enumerate("rM8W/WbWM8W%M"):
        P(2 + i, 4, c)
    P(15, 4, 'v')

    # row 5: the two rings, flowing WESTWARD
    P(15, 5, '<')
    vring(P, 14, 13, 5, 1)                # remainder ring: rem relays
    P(12, 5, 'W')                         # A = a  (B carried it through)
    P(11, 5, 'b')                         # BP = a
    vring(P, 10, 9, 5, 8)                 # main ring: a laps x 8 relays
    P(8, 5, 'v')

    # the unconditional relay (rings do 8a+rem, the protocol needs 8a+rem+1)
    P(8, 6, 'r'); P(8, 7, 's')            # x=8: PIN over CMD, POUT over OX
    P(8, 8, '<'); P(7, 8, ' '); P(6, 8, ' '); P(5, 8, 'v')

    # read the rest of the command and dispatch
    P(5, 9, 'r')                          # value
    P(5, 10, 'M')                         # B = value
    P(5, 11, 'r')                         # op
    P(5, 12, 'b')                         # BP = op
    P(5, 13, 'r')                         # which
    for y in range(14, 17):
        P(5, y, ' ')
    P(5, 17, 'X')                         # which<0 -> ccw(east) = plain relay
                                          # which==0 -> straight south = tap

    # RELAY arm (which < 0): one plain relay, then descend col 13
    P(6, 17, ' '); P(7, 17, 'r'); P(8, 17, 's')
    for x in range(9, 13):
        P(x, 17, ' ')
    P(13, 17, 'v')
    for y in range(18, 21):
        P(13, y, ' ')
    P(13, 21, '<')

    # TAP path: op decides read vs write
    P(5, 18, 'd')                         # BP=op>0 -> cw(south->west) = write

    # READ arm (op == 0): tap the belt, output AND reinject, atomically
    P(5, 19, '>'); P(6, 19, ' ')
    P(7, 19, 'r')                         # belt value
    P(8, 19, 'S')                         # -> merge pipe AND belt
    for x in range(9, 12):
        P(x, 19, ' ')
    P(12, 19, 'v'); P(12, 20, ' '); P(12, 21, '<')

    # WRITE arm (op == 1): discard the old value, send the new one
    P(4, 18, 'v'); P(4, 19, ' ')
    P(4, 20, '>'); P(5, 20, ' '); P(6, 20, ' ')
    P(7, 20, 'r')                         # old value, discarded
    P(8, 20, 'W')                         # A = value (from B)
    P(9, 20, 's')                         # -> belt
    P(10, 20, 'v'); P(10, 21, '<')

    # return: WEST along row 21, then north up the free col 1 into row 4
    for x in range(2, 10):
        P(x, 21, ' ')
    P(11, 21, '<')
    P(1, 21, '^')
    for y in range(5, 21):
        P(1, y, ' ')


# ── CONTROL ────────────────────────────────────────────────────────────────
# Every send cell, with the pipe it MUST bind to.  The bind-solver consumes this.
CTRL_SENDS = {
    'A': [(5, 5), (2, 7), (5, 9), (5, 13), (2, 15), (5, 17), (5, 21), (4, 23)],
    'B': [(8, 4), (7, 8), (9, 8), (8, 12), (7, 16), (9, 16), (11, 21), (10, 23)],
    'S': [(12, 25)],
}
# Solved attachments (pipe-segment cells, CONTROL-local; brute-forced over every
# wall position, all comparisons STRICT).  cmdA leaves the left wall and cmdB the
# right wall so the controller can sit BETWEEN the two engines.
#   cmdA = left wall row 24 | cmdB = right wall row 23 | SEL = bottom wall col 12
CTRL_ATTACH = {'A': (-1, 24), 'B': (CTRL_W, 23), 'S': (12, CTRL_H)}
# ... i.e. these BORDER (wall) cells, in CONTROL-local coords:
CTRL_BORDER = {'A': (0, 24), 'B': (CTRL_W - 1, 23), 'S': (12, CTRL_H - 1)}


def control(put, cx, cy):
    C = lambda x, y, c: put(cx + x, cy + y, c)

    # row 1: '@' walks east through `1`,`M` (prev := 1) into the main loop; the
    # return path joins westbound at col 13 and turns south at col 5.
    C(1, 1, '@'); C(2, 1, '1'); C(3, 1, 'M'); C(4, 1, ' '); C(5, 1, 'v')
    for x in range(6, 13):
        C(x, 1, ' ')
    C(13, 1, '<')
    C(5, 2, 'r')                          # op
    C(5, 3, 'X')                          # op>0 -> cw(south->west) = WRITE band

    # write entry: west along row 3 to col 1, down the free col 1, east on row 11
    for x in (4, 3, 2):
        C(x, 3, ' ')
    C(1, 3, 'v')
    for y in range(4, 11):
        C(1, y, ' ')
    C(1, 11, '>')
    for x in (2, 3, 4):
        C(x, 11, ' ')
    C(5, 11, 'v')

    for y0, is_write in ((4, False), (12, True)):
        # row y0: addr -> delta, send delta to cmdB, BP = delta, >>1
        C(5, y0, '>'); C(6, y0, 'r'); C(7, y0, '-'); C(8, y0, 's')
        C(9, y0, 'b'); C(10, y0, ']'); C(11, y0, 'v')
        # row y0+1 westward: five more >> (BP = delta>>6), send delta to cmdA,
        # A = delta+prev = addr, B = addr
        C(11, y0 + 1, '<')
        for x in range(6, 11):
            C(x, y0 + 1, ']')
        C(5, y0 + 1, 's'); C(4, y0 + 1, '+'); C(3, y0 + 1, 'M'); C(2, y0 + 1, 'v')
        # value: read it on a write, literal 0 on a read -- the only cell that differs
        C(2, y0 + 2, 'r' if is_write else '0')
        C(2, y0 + 3, 's')                 # -> cmdA (value)
        C(2, y0 + 4, '>')
        for x in range(3, 7):
            C(x, y0 + 4, ' ')
        C(7, y0 + 4, 's')                 # -> cmdB (value)
        C(8, y0 + 4, '1' if is_write else '0')
        C(9, y0 + 4, 's')                 # -> cmdB (op)
        C(10, y0 + 4, 'v')
        C(10, y0 + 5, '<')
        for x in range(6, 10):
            C(x, y0 + 5, ' ')
        C(5, y0 + 5, 's')                 # -> cmdA (op)
        C(4, y0 + 5, ' '); C(3, y0 + 5, 'v')
        C(3, y0 + 6, '>')
        for x in range(4, 12):
            C(x, y0 + 6, ' ')
        C(12, y0 + 6, 'v')                # exit: descend col 12
    # both bands descend the (otherwise empty) col 12 and merge onto row 19
    C(12, 19, '<')
    for x in range(6, 12):
        C(x, 19, ' ')
    C(5, 19, 'v')

    # ── the two leaves (SHARED by both bands).  A = op at entry, B = addr,
    # BP = delta>>6.  Each arm stashes op into BP with `b` the moment the `x`
    # has consumed the selector bit, so the tail can test read-vs-write.
    C(5, 20, 'x')                         # low bit 1 -> cw(west) ; 0 -> ccw(east)

    # EAST arm (bit == 0, room A taps): prev := addr + 2
    C(6, 20, 'b')                         # BP = op
    C(7, 20, '2'); C(8, 20, '+'); C(9, 20, 'M'); C(10, 20, '1'); C(11, 20, 'N')
    C(12, 20, 'v')
    C(12, 21, '<'); C(11, 21, 's')        # cmdB gets -1  (room B does not tap)
    for x in range(7, 11):
        C(x, 21, ' ')
    C(6, 21, '0'); C(5, 21, 's')          # cmdA gets 0   (room A taps)
    for x in (4, 3, 2):
        C(x, 21, ' ')
    C(1, 21, 'v')

    # WEST arm (bit == 1, room B taps): prev := addr + 66
    C(4, 20, 'b')                         # BP = op
    C(3, 20, 'v'); C(3, 21, ' '); C(3, 22, '>')
    for i, c in enumerate('`66`'):
        C(4 + i, 22, c)                   # A = 66
    C(8, 22, '+'); C(9, 22, 'M'); C(10, 22, '0'); C(11, 22, 'v')
    C(11, 23, '<'); C(10, 23, 's')        # cmdB gets 0   (room B taps)
    for x in range(7, 10):
        C(x, 23, ' ')
    C(6, 23, '1'); C(5, 23, 'N'); C(4, 23, 's')   # cmdA gets -1
    C(3, 23, ' '); C(2, 23, ' '); C(1, 23, 'v')

    # shared tail: fall down col 1, east along row 25.  BP still holds op, so `a`
    # sends WRITES up over the SEL send and READS straight through it.
    C(1, 22, ' '); C(1, 24, ' '); C(1, 25, '>')
    for x in range(2, 11):
        C(x, 25, ' ')
    C(11, 25, 'a')                        # BP>0 (write) -> ccw(east->north)
    C(11, 24, '>'); C(12, 24, ' '); C(13, 24, '^')
    C(12, 25, 's')                        # READS ONLY: which -> SEL
    C(13, 25, '^')                        # col 13 rows 2..23 stay empty: the
                                          # return corridor climbs it to (13,1)


# ── MERGE ──────────────────────────────────────────────────────────────────
# 3 incoming (SEL from CONTROL, oA, oB), 1 outgoing (-> output room).  Only ONE
# outgoing pipe, so every `s` binds trivially; the three `r` regions are what the
# geometry has to separate:
#   SEL  = top wall col 5      oA = left wall row 4      oB = right wall row 4
MERGE_ATTACH = {'S': (5, -1), 'A': (-1, 4), 'B': (MERGE_W, 4), 'O': (5, MERGE_H)}
MERGE_READS = {'S': [(5, 2)], 'A': [(3, 6)], 'B': [(7, 5)]}


def merge_room(put, mx, my):
    M = lambda x, y, c: put(mx + x, my + y, c)
    M(9, 1, '<')
    for x in (8, 7, 6):
        M(x, 1, ' ')
    M(5, 1, 'v')
    M(5, 2, 'r')                          # which  (SEL: d=3 vs oA/oB 8)
    M(5, 3, 'X')                          # which<0 -> ccw(east) = room B tapped
    # room A tapped (which == 0): straight south, then west to the oA region
    M(5, 4, ' '); M(5, 5, ' '); M(5, 6, '<'); M(4, 6, ' ')
    M(3, 6, 'r')                          # oA (d=6 vs oB 10, SEL 9)
    M(2, 6, 's')                          # -> output room
    M(1, 6, 'v')
    # room B tapped (which < 0): east to the oB region
    M(6, 3, ' ')
    M(7, 3, 'r')                          # oB (d=5 vs oA 9, SEL 7)
    M(8, 3, 's')
    M(9, 3, '^'); M(9, 2, ' ')
    # loop back: both arms rejoin on row 7 and climb col 9
    M(1, 7, '>')
    for x in range(2, 9):
        M(x, 7, ' ')
    M(9, 7, '^')
    for y in (6, 5, 4):
        M(9, y, ' ')


if __name__ == '__main__':
    print("this module is imported by dualhead2_floor.py", file=sys.stderr)

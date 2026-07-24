"""Merge-sort CONTROLLER — work-in-progress builder + full design.

STATUS (this session):
  * MERGER cell (merger_dsl.place_merger) — VALIDATED end-to-end on the fast Rust
    interp via a clean rig (see build_clean_rig below): [2,5]|[1,3]->1,2,3,5,DELIM ;
    [4,6,8]|[7]->4,6,7,8,DELIM ; then re-primes. ~46 ticks/elem, 26x24 footprint.
  * ROUTER (tools/router.py) — VALIDATED routing the merger's 3 pipes collision-free
    (feeders staggered into disjoint row-bands + different columns to avoid the
    backtick-literal cross-pairing that makes the stock rig loaderror).
  * CONTROLLER INIT + DRAIN plumbing — VALIDATED (build_init_drain below): reads n,
    biases +10001, deposits header [n,DELIM] + n singleton chunks [bias(v),DELIM] into a
    FIFO ring (FEED->relay->RET), then reads the header back to set the counter and
    drains the ring, unbiasing -10001 to OUTPUT. On input "3 3 1 2" it emitted [3,1,2]
    (original order, correctly biased round-trip), ring capacity 37, NO deadlock.
  * split-A delim-loop — PROVEN in isolation (scratchpad/test_splitA.py): INIT(n=2) ->
    merge-setup -> split-A, IN_A routed to an output room. On input "2 5 3" the IN_A
    stream was [10006, 30000] = [bias(5), DELIM] — i.e. it reads chunkA off the ring,
    forwards the biased value, then the 30000 terminator, exactly as the merger expects.
    This validates the delim-loop template that split-B and collect also use.
  * MERGE PHASE — the split-A pattern is proven; REMAINING work is: mirror split-A for
    split-B (forward RIGHT to IN_B@20 — geometry notes below), adapt for collect
    (read MOUT@16 -> forward FEED@8), wrap all three in the count pretest-loop, add the
    FINAL-DRAIN, INTEGRATE the merger room (IN_A/IN_B pipes sized >=16 to avoid the
    alternating-read deadlock; MOUT back to controller), route the 7 controller pipes +
    merger's 3 (spread the rooms — the router failed only when 5 pipes crowded one wall),
    and trace-debug the controller<->merger interleaving. See geometry notes below.

KEY VALIDATED FACTS (pin against interp/src/lib.rs):
  * Grading: score = max(w,h)^2 * avgTicks (avg settleTick over PASSED public cases).
    Input per round = "n v1 .. vn"; rounds joined by " / "; round K+1 released after
    round K's expected output count is emitted. Baseline bubble-ring-v1: 7/7, box 3249,
    avgTicks 27518, local score 89,405,982 (server 131,401,776). Board-best 538,326.
  * Registers A(work) B(const held) BP(counter). '-' does A=A-B leaving B (so the other
    operand is recoverable via '+'); 'X' turns CW if A>0, CCW if A<0, straight if A==0.
    'd' turns CW if BP>0 else straight. Literals load into A only (closing backtick).
  * Pipe select is COLUMN-only (Manhattan vertical cancels). 'r' picks nearest INCOMING,
    's' nearest OUTGOING — separate pools, so incoming/outgoing columns may overlap.
  * Backtick literals cross-pair: two backticks in the same ROW (or COLUMN) form a
    literal spanning between them -> "non-digit in literal" loaderror if any op/arrow
    sits between. Keep every literal's row & column clear of other backticks.
  * DEADLOCK sizing (confirmed by design writeup): the merger reads IN_A and IN_B
    ALTERNATELY while the controller stages chunkA fully then chunkB, so IN_A and IN_B
    pipes must EACH hold a whole chunk (>=16) or the controller blocks on IN_A-full
    while the merger blocks on IN_B-empty. Ring (FEED+relay+RET) must hold all 2n+2
    cells (<=34) or INIT deadlocks mid-deposit.

BIAS=10001 (values ->[1,20001]); DELIM/+INF sentinel=30000 (> any biased value).

================================================================================
CONTROLLER PIPE / COLUMN PLAN (7 pipes on one room; column discipline)
  incoming: INPUT@2, RET@10, MOUT@16     r-bands: <=6 INPUT ; 7-13 RET ; >=14 MOUT
  outgoing: IN_A@4, FEED@8, OUT@13, IN_B@20   s-bands: <=6 IN_A ; 7-10 FEED ; 11-16 OUT ; >=17 IN_B
================================================================================
PHASES (single continuous man, loops back to INIT for the next round):
  INIT  (B:=10001 held):
     r(INPUT)->A=n ; b BP=n ; s(FEED) push n ; load30000 s(FEED) delim ;   [header chunk]
     load10001 M (B=10001)
     do { r(INPUT)->A=v ; '+' bias(B=10001) ; s(FEED) push bias(v) ;
          load30000 s(FEED) delim ; m } while d(BP>0)         [n singleton chunks]
  MERGE-SETUP:
     r(RET)->A=n ; b BP=n ; m (BP=n-1) ; r(RET) discard header delim
  MERGE-LOOP  while d(BP>0):                                   [pre-test: n-1 can be 0]
     load B:=30000
     split-A: do { r(RET); '-'; X : real(A<0)->'+' s(IN_A) loop ;
                                    delim(A==0)->W s(IN_A)=30000, exit }  # forward chunkA + terminator
     load B:=30000 ; split-B: same but s(IN_B)                # forward chunkB + terminator
     load B:=30000 ; collect: do { r(MOUT); '-'; X : real->'+' s(FEED) loop ;
                                    delim->W s(FEED)=30000, exit }  # merged chunk -> ring tail
     m                                                          # merges done ++
  FINAL-DRAIN  (delimiter-terminated; unbias each):            [1 chunk remains = sorted]
     do { r(RET)->A=tok ; M ; load30000 ; '-' ; X :
            real -> load10001 '-' N s(OUT) loop ;               # emit tok-10001
            delim -> DONE, loop to INIT (next round) }
  n=1 special-case is automatic: MERGE-SETUP gives BP=0, MERGE-LOOP skipped, FINAL-DRAIN
  emits the single value chunk. FIFO self-balances -> exactly n-1 merges, no odd-run case.

delim-loop template (vertical, reads pipe@rc heading W, forwards to sc, B=30000 held):
  (spine,y0)   'v'  merge cell (fall-in from above + back-edge from left both leave S)
  (spine,y0+1) '<'  ; glide to (rc,y0+1)'r'=tok ; (rc-1)'-' A=tok-30000,B=30000 ;
  (rc-2,y0+1)  'X'  A<0 REAL (CCW W->S) ; A==0 DELIM (straight W)
  REAL  (rc-2,y0+2)'+' A=tok ; jog to (sc)'s' ; riser UP a side column to row y0 ->
        walk E into (spine,y0) merge cell (back-edge)
  DELIM (rc-3,y0+1)'W' A=30000 ; jog to (sc)'s' (=30000 terminator) ; drop to EXIT (next block)
  ASSEMBLY BLOCKER: the REAL back-edge riser column and the DELIM exit column must not
  collide (they share the rc-3..sc corridor rows); each of the 3 loops needs the riser/
  exit routed on distinct columns, and split-B forwards RIGHT (IN_B) so its branch geometry
  mirrors (approach read heading E). This per-loop collision routing + the controller<->
  merger deadlock interleaving is the remaining, iterative work.

PROVEN split-A coordinates (spine col13, read RET@10, forward IN_A@4; B=30000 preloaded):
  (13,y)  'v'            merge cell (fall-in + back-edge -> S)
  (13,y+1)'<' .. (10,y+1)'r' (9,y+1)'-' (8,y+1)'X'    A<0 REAL(CCW W->S) / A==0 DELIM(straight W)
  REAL : (8,y+2)'+'  (8,y+3)'<' .. (4,y+3)'s'[IN_A]  (3,y+3)'^' riser -> (3,y)'>' -> E into (13,y)
  DELIM: (7,y+1)'W'  (4,y+1)'s'[IN_A=30000]  (2,y+1)'v' -> EXIT down col2
split-B (forward RIGHT to IN_B@20): same spine/read, but REAL sends right:
  REAL : (8,y+2)'+' (8,y+3)'>' .. (20,y+3)'s'[IN_B]  (21,y+3)'^' -> (21,y)'<' -> W into (13,y)
  DELIM: (7,y+1)'W' (6,y+1)'v' (6,y+2)'>' .. (20,y+2)'s'[IN_B]  (22,y+2)'v' EXIT   (avoid col21 riser)
collect (read MOUT@16, forward FEED@8): spine col19, mirror of split-A shifted right:
  (19,y)'v' (19,y+1)'<' (16,y+1)'r' (15,y+1)'-' (14,y+1)'X'
  REAL : (14,y+2)'+' (14,y+3)'<' .. (8,y+3)'s'[FEED] (7,y+3)'^' -> (7,y)'>' -> E into (19,y)
  DELIM: (13,y+1)'W' (8,y+1)'s'[FEED=30000] (6,y+1)'v' EXIT
Each block preloads B:=30000 via a short S-detour through vlit(col,y,30000)+M before entry.
The count pretest wraps split-A/B+collect+m; back-edge (after m) risers UP to the pretest
merge cell; BP==0 falls through to FINAL-DRAIN.

Recommended finish path: place the merger to the side with IN_A/IN_B pipes routed LONG
(>=16 cells) so the alternating-read deadlock can't occur; SPREAD the controller's rooms
(input/relay/merger/output on different sides) so no single wall carries >~3 pipes (the
router only failed when 5 pipes crowded one wall). Optionally wire connective glides with
tools/router.py add_corridor (branches = two corridors from the X/d cell; loop heads = a
shared arrow both fall-in and back-edge enter) to cut hand-routing errors.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
sys.path.insert(0, os.path.dirname(__file__))
import layout as L, router as R, merger_dsl as m


def vlit(P, x, y, val):
    """Vertical backtick literal read heading S; returns the row just past it (A=val)."""
    s = str(val); P.put(x, y, '`')
    for i, ch in enumerate(s):
        P.put(x, y + 1 + i, ch)
    P.put(x, y + 1 + len(s), '`')
    return y + 2 + len(s)


def build_clean_rig(runsA, runsB):
    """VALIDATED merger test rig. Feeders staggered (feeder A far-left rows>=26, feeder B
    far-right rows>=70) so no two backticks share a row/column -> no literal cross-pairing.
    Returns a routed Router (call .render()). Confirms place_merger merges pairs correctly."""
    P = L.Layout()
    m.place_merger(P)                       # room (12,0,26,24); IN_A dst(11,9) IN_B dst(38,9) OUT src(22,24)
    m.feeder(P, 0, 26, runsA, 'A')
    m.feeder(P, 44, 70, runsB, 'B')
    P.output_room(21, 26)
    rooms = [(12, 0, 37, 23), (21, 26, 23, 28)]
    prog = P.p
    def corner(x, y):
        x1 = x + 1
        while prog.get(x1, y) == '-': x1 += 1
        if prog.get(x1, y) != '+': return None
        y1 = y + 1
        while prog.get(x, y1) == '|': y1 += 1
        return (x, y, x1, y1) if prog.get(x, y1) == '+' else None
    for (x, y), c in list(prog.cells.items()):
        if c == '+':
            r = corner(x, y)
            if r and r[1] >= 26 and r[0] in (0, 44) and r not in rooms:
                rooms.append(r)
    rt = R.Router()
    for (x0, y0, x1, y1) in rooms:
        rt.add_room(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    for (x, y), c in list(prog.cells.items()):
        if c == ' ': continue
        for (x0, y0, x1, y1) in rooms:
            if x0 < x < x1 and y0 < y < y1:
                rt.place(x, y, c); break
    fa = [r for r in rooms if r[0] == 0][0]
    fb = [r for r in rooms if r[0] == 44 and r[1] >= 26][0]
    rt.add_pipe_net((fa[0], fa[1] + 1), (12, 9), name='IN_A')
    rt.add_pipe_net((fb[2], fb[1] + 1), (37, 9), name='IN_B')
    rt.add_pipe_net((22, 23), (22, 26), name='OUT')
    assert rt.solve(budget=80) is True
    return rt


def build_init_drain():
    """VALIDATED INIT + count-DRAIN plumbing (no merger). Reads n, biases +10001, deposits
    header+chunks to the ring, drains n chunks unbiasing -10001 to OUTPUT. Output == input
    order (echo) — proves the ring / IO / bias round-trip / do-while loops / column
    discipline all work. Replace the DRAIN with the MERGE PHASE + FINAL-DRAIN to finish."""
    P = L.Layout(); CW, CH = 16, 46
    P.room(0, 0, CW, CH)
    P.put(1, 1, '@'); P.put(2, 1, 'r'); P.put(3, 1, 'b'); P.put(6, 1, 'v'); P.put(6, 2, 's')
    y = vlit(P, 6, 3, 30000); P.put(6, y, 's')
    y = vlit(P, 6, y + 1, 10001); P.put(6, y, 'M')
    S1 = y + 1; P.put(6, S1, 'v'); b = S1 + 1
    P.put(6, b, '<'); P.put(2, b, 'r'); P.put(1, b, 'v'); P.put(1, b + 1, '>'); P.put(2, b + 1, '+')
    P.put(6, b + 1, 'v'); P.put(6, b + 2, 's')
    y2 = vlit(P, 6, b + 3, 30000); P.put(6, y2, 's'); P.put(6, y2 + 1, 'm'); P.put(6, y2 + 2, 'd')
    P.put(5, y2 + 2, '^'); P.put(5, S1, '>'); ex = y2 + 3
    P.put(6, ex, '>'); P.put(10, ex, 'r'); P.put(11, ex, 'b'); P.put(12, ex, 'r')
    P.put(13, ex, 'v'); P.put(13, ex + 1, '<'); P.put(10, ex + 1, 'v'); cds = ex + 2
    P.put(10, cds, 'v'); P.put(10, cds + 1, 'r'); P.put(10, cds + 2, '-'); P.put(10, cds + 3, 's')
    P.put(10, cds + 4, 'r'); P.put(10, cds + 5, 'm'); P.put(10, cds + 6, 'd')
    P.put(9, cds + 6, '^'); P.put(9, cds, '>'); P.put(10, cds + 7, 'H')
    relay = (0, CH + 8, 7, 5); P.room(*relay); L.relay_man(P.p, relay[0] + 1, relay[1] + 1, recv='R')
    P.input_room(0, CH + 2); P.output_room(12, CH + 2)
    rooms = [(0, 0, CW - 1, CH - 1), (relay[0], relay[1], relay[0] + relay[2] - 1, relay[1] + relay[3] - 1),
             (0, CH + 2, 2, CH + 4), (12, CH + 2, 14, CH + 4)]
    rt = R.Router()
    for (x0, y0, x1, y1) in rooms: rt.add_room(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    for (x, yy), c in list(P.p.cells.items()):
        if c == ' ': continue
        for (x0, y0, x1, y1) in rooms:
            if x0 < x < x1 and y0 < yy < y1: rt.place(x, yy, c); break
    rt.add_pipe_net((1, CH + 2), (2, CH - 1), name='INPUT')
    rt.add_pipe_net((10, CH - 1), (13, CH + 2), name='OUT')
    rt.add_pipe_net((6, CH - 1), (relay[0] + 3, relay[1]), name='FEED')
    rt.add_pipe_net((relay[0] + relay[2] - 1, relay[1] + 2), (11, CH - 1), name='RET')
    assert rt.solve(budget=120) is True
    return rt


if __name__ == '__main__':
    rig = build_clean_rig([[2, 5], [4, 6, 8]], [[1, 3], [7]])
    print('clean merger rig footprint', rig.footprint())
    id_ = build_init_drain()
    print('init+drain footprint', id_.footprint())

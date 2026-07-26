import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys, os
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# =====================================================================================
# ss-mitm.man  --  SORTED-MERGE meet-in-the-middle subset-sum (ICFPC 2026)
# =====================================================================================
# SPEC (executable, validated 7/7 public + 4000/4000 fuzz):
#     solutions/subset-sum/ss_mitm_model.py   (study solve(), merge_enumerate(), dedup_maxmask())
#
# This machine must reproduce ss_mitm_model.py PASS-FOR-PASS.  The NAIVE MITM verdict in
# ss_mitm_build.py (2^n match = 35M ticks = timeout) does NOT apply here: the sorted-merge
# + two-pointer match is O(2^(n/2)) (~4k enumerate ops + ~2k match ops ~= well under 15M).
#
# ------------------------------------------------------------------------------------
# ISA CHEAT-SHEET (from interp/src/lib.rs, oracle-parity):
#   r  A := dequeue nearest INCOMING pipe (blocks if empty)     s  enqueue A -> nearest OUTGOING pipe
#   R/U recv from any ready incoming (U also turns away)         S  send A to ALL outgoing
#   q  BP := count of items in nearest incoming pipe            M  B:=A   W  swap A,B
#   + - *  A:=A op B      N A:=-A     /  A:=A/B, B:=A%B (floored)   %  A:=A%B
#   & | ~  bitand/or/xor A,B into A     {  A:=A<<B    }  A:=A>>B (arith)
#   0-9  A:=digit         `123`  literal into A (reads value walking OVER it; reversed if walking W)
#   X  A>0 turn CW, A<0 turn CCW, A==0 straight     (branch on A sign)
#   b  BP:=A    m  BP-=1    ]  BP>>=1    d  BP>0 turn CW   a  BP>0 turn CCW   x  BP&1 ? CW : CCW
#   > < ^ v set dir    H halt    Y fork(hazard)
#   CONSTRAINT (register pressure): r writes ONLY A; NO BP->A/B readback (BP is branch/count only).
#   Pipe = FIFO ring (belt); `s` puts at values[0], `r` takes values[last] (oldest). count via q.
#   Nearest pipe = min Manhattan(man cell -> attach cell), tie = reading order. => COLUMN/ROW
#   DISCIPLINE: place each r/s where the intended belt's attach is nearest.
#
# ------------------------------------------------------------------------------------
# DATA REP:  MULT = 1<<22.  packed entry = sum*MULT + fullpart  (sum in high bits, mask in low).
#   Direct i64 compare == compare by (sum, fullpart).  "add element i" = add delta_i where
#   delta_i = v_i*MULT + bit_i, bit_i = 1<<(n-1-i).  (fullpart|bit == fullpart+bit, disjoint.)
#   Unpack (only at dedup/reconstruct): A=packed,B=MULT,`/` -> A=sum, B=fullpart.
#
# BELT PLAN (rings hung off CTRL; reused across phases):
#   MAIN  (left wall, feed row30 / ret row20)  -- values, then index-order deltas, then S-list
#   BIT   (right wall, feed row30 / ret row20) -- powers of two 2^(n-1)..1 (front=2^(n-1))
#   NN    (small)  -- holds n (re-enqueue after each read)
#   (merge phase adds Q, D belts; CNT belt or `q` for the 2|S| merge counter)
#
# ------------------------------------------------------------------------------------
# PASS-BY-PASS DESIGN (build & COMMIT each as it grades on a dump):
#
# PASS 1  LOAD + DELTA  (this file, being built):
#   1a. read n (input tok0) -> stash on NN; compute bit0 = 2^(n-1) into A by: BP=n-1 counter,
#       A=1, B=1, loop `{`(A<<=1) BP times  -> A=2^(n-1)  (B stays 1 via {-by-1).
#   1b. BIT fill: while A>0: s->BIT ; }->A>>=1 (B=1) ; X(A>0 loop).  => BIT=[2^(n-1)..1].
#   1c. value load: r NN->A=n, re-enqueue, BP=n; loop n: r input->A=v ; s->MAIN.
#       => MAIN=[v_0..v_{n-1}] (front=v_0).
#   1d. read t (input) -> stash (TBELT or NN).
#   1e. TRANSFORM (fuse): r NN->A=n, re-enqueue, BP=n; loop n:
#            `<MULT>`->A=MULT ; M->B=MULT ; r MAIN->A=v ; *->A=v*MULT ; M->B=v*MULT ;
#            r BIT->A=bit ; +->A=delta ; s->MAIN.
#       => MAIN=[delta_0..delta_{n-1}] index order.  (verify vs model deltas)
#       Expected for [3,5,2,6]: [12582920,20971524,8388610,25165825].
#   1f. (split) compute h=n-n//2; append SENTL(-1) after h deltas, SENTH(-1) after all
#       (or drive enumeration halves by counters h,Rn).  MAIN = [d0..d_{h-1}, -1, d_h..d_{n-1}, -1].
#
# PASS 2  ENUMERATE ONE HALF (sorted, iterative merge).  Belts: P (=MAIN half), Q, D.
#   Init S-list P = [0, -1]  (packed 0 = empty subset ; -1 = P's dup-terminator sentinel).
#   For each delta (read from MAIN until SENTL):
#     b_setup: B := delta.  (via r MAIN->A=delta ; M->B=delta ; keep in B across duplicate)
#     DUPLICATE phase (P -> Q and D ; -1 sentinel drives termination, delta in B):
#        loop: r P->A=a ; X(a<0 sentinel? -> a<0 CCW=done, a>=0 real continue) ;
#              real: s->Q (a) ; +->A=a+delta ; s->D (a+delta) ; loop.
#        after: append +inf (e.g. `1<<50`) to Q and to D  (merge refill sentinel, sorts last).
#     MERGE phase (Q,D -> P ; counter BP = 2*|S| ; A=qh, B=dh role-fixed):
#        get 2|S|: (CNT belt holds |S|; r->A=cnt, A=2cnt, b->BP, s->CNT new |S|)  [see note]
#        pre-read: r Q->A=qh ; r D->? -- need dh in B: r D->A=dh ; M->B=dh ; then r Q->A=qh.
#        loop (uniform, refill BEFORE counter test so both +inf sentinels get consumed):
#           `-`->A=qh-dh (B=dh) ; X: A>0 (qh>dh) CW=takeD ; A<=0 CCW/straight=takeQ.
#           takeQ:  `+`->A=qh (restore, B=dh) ; s->P (qh) ; r Q->A=new qh ; m ; d(BP>0 loop) else exit.
#           takeD:  `+`->A=qh ; W->A=dh,B=qh ; s->P (dh) ; r D->A=new dh,B=qh ; W->A=qh,B=new dh ;
#                   m ; d(BP>0 loop) else exit.
#        WHY it terminates clean: |Q|=|D|=|S| reals + 1 sentinel each; pre-read 2, refill every
#        emit -> total reads 2|S|+2 = all items; min is always a real while BP>0 (proof: a belt's
#        head is +inf only after its reals exhausted; other side then holds the real min); both
#        sentinels consumed as final refills -> Q,D empty for next iteration. No leftover.
#        after: append -1 to P (dup-terminator for next iteration).  |S| doubled.
#   => P = sorted-ascending packed subset-sums of this half (with duplicate sums, un-deduped).
#
# PASS 3  loop PASS 2 over all half-deltas (SENTL-driven) -> full sorted L list (1024 entries
#   for n=20).  Then do the H half the same way into a SECOND list belt.
#
# PASS 4  DEDUP (keep max fullpart per sum) + MATCH (two-pointer, forward-only):
#   dedup: one forward pass, keep an entry iff next entry's sum differs (compare packed//MULT).
#   H must be DESCENDING for the two-pointer: either enumerate H taking MAX first (reverse compare)
#   or reverse the H belt.  Two-pointer over Lde asc (i) / Hdesc (j):
#      sL+sH ==t -> cand=fL|fH, best=max(best,cand), i++ ; <t -> i++ ; >t -> j++.
#   Track best_full (running max).  need registers for sL,sH,fL,fH,best,t -> use belts to park.
#
# PASS 5  RECONSTRUCT + OUTPUT (reuse ss.man Pass K/F/RE):  best_full -> popcount k; emit k;
#   then for idx 0..n-1 with bit (n-1-idx) set, emit v_idx in index order; if no match emit single 0.
#
# ------------------------------------------------------------------------------------
# HARNESS: node scratchpad/run_ss.js <file.man> "4 3 5 2 6 8" [cap]  (dump/settle)
#          node tools/grade.js subset-sum <file.man>                 (oracle 7/7)
# STAGE env: DUMPBIT / DUMPMAIN / DUMPDELTA gate an output-drain for verification.
#
# =====================================================================================
# SESSION FINDINGS / STATUS  (read before continuing -- these cost real debugging):
# VERIFIED ON ORACLE (committed): PASS 1a (double 1->2^(n-1) via {-by-1 loop, keeps B=1)
#   and PASS 1b (BIT belt = [2^(n-1)..1]).  DUMPBIT: n=4->[8,4,2,1], n=10->[512..1].
# WIP / UNVERIFIED (below, PASS 1c value-load): the man BLOCKS at the BIT-fill s and
#   value-load never completes -- a routing bug in the PASS1c setup path (it re-enters
#   the fill loop / jams a belt).  Do NOT trust it; likely needs a re-route or rebuild.
#
# *** CRITICAL ARCHITECTURAL LESSON -- ticks are WALK-BOUND ***
#   This "one big 42x92 CTRL room with weaving corridors" layout is NON-VIABLE for the
#   full machine: for n=4, PASS 1a/1b + PASS1c-setup already burned ~6000 ticks purely
#   walking long corridors (col50 down 50 rows, col45 up, etc).  The MERGE phase runs
#   ~2046 iterations (n=20); at even hundreds of walk-ticks each that is millions of
#   ticks -> case 6 (n=20) TIMES OUT (>15M) even if functionally correct = 6/7 = no
#   better than the ss.man floor.  MUST rearchitect: place hot-loop belt attaches
#   ADJACENT (a few cells apart) so the man's per-op route is short, and FOLD to a
#   compact box (see matmul/plotter fold lessons in MEMORY).  The current sprawl trades
#   footprint AND ticks badly.  Recommend: tiny CTRL room with all belt attaches on ONE
#   short wall, ops in a compact inner loop; separate the rare LOAD path from the hot
#   MERGE loop.
#
# ROUTING RULES LEARNED (all cost oracle iterations):
#   * A ring (belt) needs a RELAY ROOM **with a forwarder man** (`>@Rsv` + `<`/`^` loop)
#     to shuttle feed->ret; a bare relay room does NOT move items (belt stays empty).
#   * feed(out) and ret(in) pipes must not CROSS: route the ret's horizontal approach so
#     the feed's vertical leg is outside it (relay placed east/beyond), or wrap ret ABOVE
#     the feed's vertical span (MAIN pattern: ret attaches row20 above feed row30, wraps
#     via row5 top).  Two pipes sharing a cell => LOAD ERR "pipe interrupted".
#   * pipes must not pass through OTHER rooms (O room, other relays) -> reroute.
#   * nearest-pipe = min Manhattan(op cell -> attach path[0]/path[last]); keep belts in
#     separate REGIONS (input=top, MAIN=left, BIT=right, NN=bottom) so r/s are unambiguous.
#   * loop-back into an op-spine must land on a 'v'/'>' REDIRECT cell (not an op cell, or
#     the man re-executes it); after `s`/`r` the man KEEPS its heading (walks into a wall
#     if the next cell is a room border) -> always follow s/r with an arrow before a wall.
#   * `q` for a ring's count is UNRELIABLE (items spread across feed/relay/ret) -> stash
#     scalars (n) on a dedicated 1-item ring (NN) and re-read.
#   * render() trims to bbox: file coords = abs + (-minx,-miny); here (offx=+2, offy=-5).
# =====================================================================================

STAGE = os.environ.get('SS_STAGE', 'DUMPBIT')
POW = 1 << 22     # MULT

def build():
    p = lm.Program(); placed = {}
    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]} vs {ch}")
        placed[(x, y)] = ch; p.put(x, y, ch)
    def T(x, y, s, d='E'):
        dx, dy = lm.DIRS[d]
        for i, ch in enumerate(s):
            C(x + i * dx, y + i * dy, ch)
    def H(x0, x1, y, ch='>'):    # horizontal corridor of arrows (skip occupied cells)
        step = 1 if x1 >= x0 else -1
        for x in range(x0, x1 + step, step):
            if (x, y) not in placed: C(x, y, ch)
    def V(y0, y1, x, ch='v'):    # vertical corridor of arrows (skip occupied cells)
        step = 1 if y1 >= y0 else -1
        for y in range(y0, y1 + step, step):
            if (x, y) not in placed: C(x, y, ch)

    # ---- CTRL room + I/O + rings ----
    p.room(10, 0, 42, 92)                                    # CTRL cols10..51 rows0..91
    p.input_room(33, -5); p.pipe([(34, -2), (34, -1)])       # INPUT top col34
    p.output_room(54, 44); p.pipe([(52, 45), (53, 45)])      # OUTPUT right wall row45

    # Each ring needs a RELAY MAN that shuttles feed->ret (R;s loop), else the belt is dead.
    # MAIN ring (LEFT): relay bottom-left, feed attach left wall row30, ret left wall row20.
    p.room(2, 94, 7, 5)                                      # MAIN relay cols2..8 rows94..98
    p.pipe([(9, 30), (5, 30), (5, 93)])                      # FEED  left row30 -> relay
    p.pipe([(4, 93), (4, 5), (8, 5), (8, 20), (9, 20)])      # RET   relay -> left row20
    C(3, 95, '>'); C(4, 95, '@'); C(5, 95, 'R'); C(6, 95, 's'); C(7, 95, 'v'); C(7, 96, '<'); C(3, 96, '^')
    # BIT ring (RIGHT): relay bottom-right, feed attach right wall row30, ret right wall row40.
    p.room(60, 94, 7, 5)                                     # BIT relay cols60..66 rows94..98
    p.pipe([(52, 30), (64, 30), (64, 93)])                   # FEED right row30 -> relay top(64), east of ret
    p.pipe([(62, 93), (62, 40), (52, 40)])                   # RET relay -> right row40 (no feed crossing)
    C(61, 95, '>'); C(62, 95, '@'); C(63, 95, 'R'); C(64, 95, 's'); C(65, 95, 'v'); C(65, 96, '<'); C(61, 96, '^')
    # NN ring (BOTTOM-CENTER): holds n (1 item).  feed bottom col25, ret bottom col27.
    p.room(23, 96, 7, 5)                                     # NN relay cols23..29 rows96..100
    p.pipe([(25, 92), (25, 95)])                             # FEED bottom col25 -> relay top
    p.pipe([(27, 95), (27, 92)])                             # RET  relay -> bottom col27
    C(24, 97, '>'); C(25, 97, '@'); C(26, 97, 'R'); C(27, 97, 's'); C(28, 97, 'v'); C(28, 98, '<'); C(24, 98, '^')

    # =============================================================================
    # PASS 1a : read n, compute 2^(n-1) into A (B=1).  (n recovered later via q BIT.)
    # =============================================================================
    p.man(12, 2)
    C(12, 2, '@'); H(13, 33, 2, '>'); C(34, 2, 'r')   # walk E to input col34, A=n
    C(35, 2, '>'); C(36, 2, 'v'); V(3, 78, 36, 'v'); C(36, 79, '<'); H(25, 35, 79, '<'); C(24, 79, 'v')  # down col36, W to bottom-center
    # bottom-center strip (col24): stash n, then DOUBLE loop -> A=2^(n-1), B=1
    C(24, 80, 's')                                    # stash n -> NN (nearest NN feed col25)
    C(24, 81, 'b')                                    # BP := n
    C(24, 82, 'm')                                    # BP := n-1
    C(24, 83, '1')                                    # A := 1
    C(24, 84, 'M')                                    # B := 1
    C(24, 85, 'v')                                    # entry / loop-back redirect DOWN
    C(24, 86, '{')                                    # A <<= 1
    C(24, 87, 'm')                                    # BP -= 1
    C(24, 88, 'a')                                    # BP>0 (walking S) CCW=E -> loop ; else straight S
    C(25, 88, '^'); C(25, 87, '^'); C(25, 86, '^'); C(25, 85, '<')  # up col25, W into (24,85)v
    C(24, 89, '>')                                    # BP==0 fall-through E; A=2^(n-1), B=1

    # =============================================================================
    # PASS 1b : BIT fill.  while A>0: s->BIT ; }->A>>=1 ; X(A>0 loop).
    # BIT feed attach = right wall row30 (src (52,30)); do s on the RIGHT.
    # Loop spine col50 rows28..32 ; loop-back col49 rows28..31 ; ENTER at (50,27) heading S.
    # =============================================================================
    H(25, 47, 89, '>'); C(48, 89, '^'); V(28, 88, 48, '^'); C(48, 27, '>'); C(49, 27, '>')  # up col48 to row27
    H(15, 49, 27, '>'); C(50, 27, 'v')                # E along row27 to col50, drop into loop
    C(50, 28, 's')                                    # enqueue A -> BIT (arrives heading S)
    C(50, 29, 'v'); C(50, 30, '}'); C(50, 31, 'X')    # shift ; S:A>0 CW=W loop, A==0 straight done
    C(49, 31, '^'); C(49, 30, '^'); C(49, 29, '^'); C(49, 28, '^')  # up col49 to (49,27)> corridor -> (50,27)v
    C(50, 32, 'v')                                    # A==0 done -> continue down col50

    if STAGE == 'DUMPBIT':
        # drain BIT to OUTPUT.  BIT ret attach = right wall row40 ; OUTPUT = right row45. Both BELOW
        # the fill loop -> clean region, no corridor crossing.  Circuit spine col50 rows39..46.
        V(33, 39, 50, 'v')                               # continue down col50 to (50,39)
        C(50, 40, 'r')                                   # read BIT ret (nearest incoming at (50,40))
        V(41, 44, 50, 'v'); C(50, 45, 's')               # down to (50,45) emit -> OUTPUT
        C(50, 46, '<'); C(49, 46, '^'); V(40, 45, 49, '^'); C(49, 39, '>')  # loop back up col49 to (50,39)
        return p, placed

    # =============================================================================
    # PASS 1c : value load.  BP=n counter (from NN).  loop: r input -> s MAIN.
    # MAIN = [v_0 .. v_{n-1}] (front=v_0).
    # =============================================================================
    # setup: reach NN from west (end heading E), r NN->A=n ; M ; s->NN ; b->BP=n ; up col45 -> row8 -> (13,9)
    V(33, 86, 50, 'v')                               # down col50 to row86
    C(50, 87, '<'); H(15, 49, 87, '<'); C(14, 87, '^'); V(84, 86, 14, '^'); C(14, 83, '>')
    H(15, 25, 83, '>'); C(26, 83, 'r')               # r NN -> A=n (heading E)
    C(27, 83, 'M'); C(28, 83, 's'); C(29, 83, 'b')   # B=n ; re-stash n->NN ; BP=n
    H(30, 44, 83, '>'); C(45, 83, '^'); V(9, 82, 45, '^'); C(45, 8, '<')
    H(14, 44, 8, '<'); C(13, 8, 'v'); C(13, 9, 'v')  # W row8 to col13, down to (13,9) -> top edge (13,10)
    # value-load rectangle: top row10 (read), right col35, bottom row30 (s MAIN), loop-back col12.
    C(13, 10, '>'); H(14, 33, 10, '>'); C(34, 10, 'r')   # read v (nearest incoming = input)
    C(35, 10, 'v'); V(11, 29, 35, 'v'); C(35, 30, '<')   # down right edge
    H(15, 34, 30, '<'); C(14, 30, 's')                   # s -> MAIN (nearest MAIN feed row30)
    C(13, 30, 'm'); C(12, 30, 'd')                       # BP-- ; BP>0 CW=N loop, BP==0 straight W exit
    V(11, 29, 12, '^'); C(12, 10, '>')                   # loop-back up col12 -> (13,10)
    C(11, 30, 'v')                                       # exit (BP==0) -> down to transform / dump

    if STAGE == 'DUMPMAIN':
        # (trace-verify value-load: watch the s->MAIN ops.)  minimal exit + halt to build.
        C(11, 31, 'H')
        return p, placed

    return p, placed


if __name__ == '__main__':
    p, _ = build()
    print('footprint', p.footprint())
    p.save(_REPO + '/scratchpad/ss_mitm2.man')

import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys, os
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# MITM subset-sum. SINGLE belt (one pipe ring). Fixed Rn=6.
# Belt after LOAD = [CTR, T, v_{n-1}..v_0, VSENT(-1), <entries>, TSENT(-2)].
# Values reversed: item0=v_{n-1}=index n-1 <-> BP bit0.
# BP=Rmask scans R-half (low 6 bits); BP=Lmask<<6 scans L-half (one shared value-scan).
# No pruning: sR>t entries never match need<=t, harmless (proven).
#
# ==================== FEASIBILITY VERDICT (2026-07-24) ====================
# STOP: the single-belt MITM CANNOT pass the n=20 case under the real 15M tick cap.
# Verified facts (fetched from oracle this session):
#   * Real spec: tickCap=15_000_000 (NOT 5M), privateTestCount=0, 7 public cases.
#   * Floor ss.man passes 6/7; ONLY failure = "near-total-sum,20 values" (times out).
#   * Output spec: emit k then the k chosen VALUES in increasing original-index order;
#     "0" alone if no subset; lex-smallest chosen-index set on ties. (ss.man matches.)
# Why MITM can't fit (structural, not tuning):
#   MATCH scans the whole 2^R table for EACH of 2^L outer subsets (belt = ring, no
#   random access / no cheap binary search) => 2^L*2^R = 2^n ~= 1.05M entry-compares
#   = ~2.1M belt cell-ops for matching ALONE. Anchor: floor does a 17-cell belt
#   revolution in 283t => ~16.6 t/cell (best case this ISA reaches). 2.1M*16.6 ~= 35M
#   ticks for matching alone (>2.3x cap); full documented design (long pipes, 2-cell
#   entries, no sR-early-exit) ~= 41M (~2.7x). Even halving + 8t/cell ~= 17M, still over.
#   2^L*2^R = 2^n is invariant to the split, so Rn tuning cannot rescue it. The belt
#   destroys MITM's O(2^(n/2)) edge; a sorted-merge would need an O(N log N) belt sort
#   (>>15M itself). => finishing L+MATCH+OUTPUT yields a machine that STILL fails n=20
#   (=> 6/7 like the floor, larger footprint => strictly worse footprint-tick score).
#   DECISION: keep ss.man floor (6/7), submit NOTHING. Do not finish this design.
# ==========================================================================
# ==================== STATUS (this file) ====================
# VERIFIED on the oracle for [3,5,2,6] t=8 (SS_STAGE=R):
#   * LOAD -> belt [63,8,6,2,5,3,-1,-2]  (SS_STAGE=L0 dumps it exactly).
#   * PHASE R builds the full R-table: CTR enumerates 63->0->-1 perfectly (traced),
#     value-scan sums each R-subset (BP=Rmask, accumulate), header decrements CTR
#     in place, pass-through appends each entry before TSENT. Packed values confirmed
#     correct (e.g. Rmask=1->sR=6, Rmask=62->sR=10). The append SPLITS the packed
#     p=Rmask*2^20+sR via `/` (A=p,B=2^20 -> A=Rmask,B=sR) into TWO belt cells
#     (sR, Rmask) in DESCENDING Rmask order -> clean O(1) MATCH compare later.
#   Belt after PHASE R = [-1, T, v.., VSENT, (sR63,Rm63),(sR62,Rm62)..(sR0,Rm0), TSENT].
# The SS_STAGE=R branch below is a table-DUMP for verification only; it currently
# corrupts the belt after PHASE R completes (dump-loop realignment) and is NOT part
# of the real machine -- PHASE R itself is proven correct via the CTR trace.
#
# REMAINING (not built): PHASE L + MATCH + OUTPUT.  Design (de-risked):
#   RESET: on CTR<0 (PHASE R done), one rotate-revolution to set CTR=16383 (=2^14-1;
#     fixed, covers h=n-6<=14 for all n<=20; spurious high Lmask bits map to no value
#     and are auto-excluded -> correct + lex-smallest preserved). Also stash an LST
#     belt slot [CTR,LST,T,...] for Lmask<<6 (needed to form `full` at match time,
#     since the value-scan destroys BP).
#   PHASE L revolution (BP=Lmask<<6): header decrements CTR (reuse PHASE R header
#     pattern), sets BP=Lmask<<6 (A=Lmask; M; `6`; W; {; b), writes LST=Lmask<<6,
#     inits accumulator B=T (read T), value-scan SUBTRACTS included values (reuse
#     build.py VLOOP: INCLUDE = W,-,M,] ; EXCLUDE = ]) -> at VSENT B = need = T-sL.
#     MATCH: with 2-cell entries, hold need in B; per entry r(A=sR); -(A=sR-need,
#     B preserved); X: ==0 -> MATCH (read next cell = Rmask), else resend sR, read
#     Rmask, resend, continue. FIRST hit (descending) wins. On match: full = LST|Rmask;
#     route to OUTPUT. No match after CTR<0 -> emit single 0.
#   OUTPUT: drain the table (r;s until only [.., T, v.., VSENT] with BP=full), then
#     reuse ss.man's Pass K (popcount->k, emit k), Pass F (filter selected), Pass RE
#     (reverse-emit selected values in index order).  See build.py lines 125-172.
# HARNESS: scratchpad/run_ss.js (run to settle), scratchpad/tr.js (trace; build coord
#   = trace + (2,-5) offset), scratchpad/probe.js (opcode probe). SS_STAGE=L0/R/C.
# FLOOR: solutions/subset-sum/ss.man is the working 12/20 brute force -- DO NOT run
#   build.py with SS_STAGE=A/B (it overwrites ss.man); default STAGE=C regenerates it.
# ============================================================
STAGE = os.environ.get('SS_STAGE', 'C')
POW = 1 << 20     # packing multiplier (> max sR = 6*99999)

def build():
    p = lm.Program(); placed = {}
    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]} vs {ch}")
        placed[(x, y)] = ch; p.put(x, y, ch)
    def T(x, y, s, d='E'):
        dx,dy = lm.DIRS[d]
        for i,ch in enumerate(s): C(x+i*dx, y+i*dy, ch)

    # ---- rooms & pipes (belt ring; enlarge later for table capacity) ----
    p.room(10, 0, 42, 92)
    p.input_room(33, -5); p.pipe([(34, -2), (34, -1)])       # I top col34
    p.output_room(54, 5); p.pipe([(52, 6), (53, 6)])         # O right wall row6
    p.room(2, 94, 7, 5)                                       # RELAY (bottom strip)
    # FEED long (capacity): CTRL(9,30) down col9 to relay top; RETURN up col4 to CTRL(9,20)
    p.pipe([(9, 30), (5, 30), (5, 93)])                       # FEED west then down col5 -> relay
    # RETURN lengthened (capacity ~175 for 2-cell table, belt up to 152)
    p.pipe([(4, 93), (4, 5), (8, 5), (8, 20), (9, 20)])       # relay top col4 -> CTRL(9,20)
    C(3, 95, '>'); C(4, 95, '@'); C(5, 95, 'R'); C(6, 95, 's'); C(7, 95, 'v')
    C(7, 96, '<'); C(3, 96, '^')

    # ================= INIT =================  (belt: enqueue VSENT first)
    p.man(12, 2); C(13, 2, '>')
    C(34, 2, 'r')                       # A=n
    C(35, 2, 'b')                       # BP=n  (load counter)
    T(36, 2, '`63`')                    # A=63  (CTR init)  cols36..39
    C(40, 2, 'M')                       # B=63  (CTR stash)
    C(41, 2, '1'); C(42, 2, 'N')        # A=-1  (VSENT)
    C(43, 2, 'v'); C(43, 3, '<')
    C(15, 3, 's')                       # enqueue VSENT
    C(12, 3, 'v'); C(12, 6, '>')

    # ================= LOADLOOP READ =================
    C(34, 6, 'r')                       # A=value
    C(35, 6, 'v'); C(35, 7, '<')
    C(15, 7, 's')                       # enqueue value
    C(14, 7, 'v'); C(14, 8, 'v')
    # ROTATE (r;s;X) rotate until VSENT back to front
    C(14, 9, 'r'); C(14, 10, 's'); C(14, 11, 'X')
    C(13, 11, '^'); C(13, 8, '>')
    C(15, 11, 'v'); C(15, 12, 'm'); C(15, 13, 'd')   # DEC BP; BP>0 loop
    C(14, 13, '<'); C(12, 13, '^')

    # ================= APPEND CTR,T ================= (belt=[v..,VSENT], B=63)
    C(15, 15, '>'); C(34, 15, 'r')      # A=t   (B=63)
    C(35, 15, 'W')                      # A=63, B=t
    C(36, 15, 'v'); C(36, 16, '<')
    C(15, 16, 's')                      # enqueue CTR(63)
    C(14, 16, 'W'); C(13, 16, 's')      # A=t ; enqueue T
    C(12, 16, 'v'); C(12, 18, '>'); C(13, 18, 'v'); C(13, 19, '>'); C(14, 19, 'v')
    # ROTATE2 (r;s;X) until VSENT back to front -> belt=[CTR,T,v..,VSENT] front=CTR
    C(14, 20, 'r'); C(14, 21, 's'); C(14, 22, 'X')
    C(13, 22, '^'); C(13, 19, '>')
    C(15, 22, 'M')                      # exit; B=-1

    # append TSENT(-2) at back -> belt=[CTR,T,v..,VSENT,TSENT], front=CTR
    C(16, 22, 'v'); C(16, 23, '>')
    C(17, 23, '2'); C(18, 23, 'N'); C(19, 23, 's')   # A=-2 ; enqueue TSENT
    C(20, 23, 'v'); C(20, 24, '<')

    if STAGE == 'L0':
        # drain belt to O: r; emit; loop (blocks when empty). Verify first 8 outputs.
        C(14, 24, 'v'); C(14, 25, 'r')                # A=front (arrives S, continues S)
        C(14, 26, '>'); C(45, 26, 's')                # turn E, emit to O
        C(46, 26, '^'); C(46, 24, '<')                # up then west back to (14,24)v
        return p, placed

    # route LOAD exit (20,24)< westward to PHASE R header
    for x in range(15, 20): C(x, 24, '<')
    C(14, 24, 'v')

    # ================= PHASE R HEADER =================
    C(14, 25, 'r')                       # A=CTR (Rmask), arrives S continues S
    C(14, 26, 'X')                       # >0 -> W ; ==0 -> S ; <0 -> E=PHASE L/dump
    # A<0 (east) -> PHASE L (or dump in STAGE R)
    C(15, 26, '>')                       # east rail to phaseL, continues at (16,26)
    # A>0 (west) -> merge down at (14,27)
    C(13, 26, 'v'); C(13, 27, '>')       # west branch turns down then east to (14,27)
    # A==0 straight south hits (14,27) too
    C(14, 27, 'v')                       # merge -> south (PROCESS)
    C(14, 28, 'M')                       # B=Rmask
    C(14, 29, '1')                       # A=1
    C(14, 30, '-')                       # A=1-Rmask , B=Rmask
    C(14, 31, 'N')                       # A=Rmask-1
    C(14, 32, 's')                       # enqueue CTR'=Rmask-1 (in place)
    C(14, 33, 'W')                       # A=Rmask , B=Rmask-1
    C(14, 34, 'b')                       # BP=Rmask (scan mask)
    C(14, 35, 'M')                       # B=Rmask
    C(14, 36, '>')                       # turn E for POW literal
    T(15, 36, '`1048576`')               # A=2^20  cols15..24
    C(25, 36, '*')                       # A=2^20*Rmask , B=Rmask
    C(26, 36, 'M')                       # B=p_init=2^20*Rmask (accumulator)
    C(27, 36, 'v'); C(27, 37, '<')       # turn down then west back toward spine
    for x in range(15, 27): C(x, 37, '<')
    C(14, 37, 'v')                       # -> south to T-skip
    # skip T (r;s pass-through, no accumulate)
    C(14, 38, 'r')                       # A=T
    C(14, 39, 's')                       # re-enqueue T
    # value-scan loop entry
    C(14, 40, 'v')                       # EXCLUDE re-entry merge
    C(14, 41, 'v')                       # INCLUDE re-entry merge
    C(14, 43, 'r')                       # A=item
    C(14, 44, 's')                       # re-enqueue item
    C(14, 45, 'X')                       # A>0 -> W=VALUE ; A<0 -> E=VSENT
    C(13, 45, 'x')                       # W: bit1->N=INCLUDE ; bit0->S=EXCLUDE
    # INCLUDE (N up col13): accumulate
    C(13, 44, '+')                       # A=item+B
    C(13, 43, 'M')                       # B=accum'
    C(13, 42, ']')                       # BP>>1
    C(13, 41, '>')                       # -> re-entry (14,41)v
    # EXCLUDE (S down col13)
    C(13, 46, ']')                       # BP>>1
    C(13, 47, '<'); C(12, 47, '^'); C(12, 40, '>')   # up col12 -> re-entry (14,40)v
    # VSENT (E from X): B=p. route east to pass-through at col20
    C(15, 45, '>')
    for x in range(16, 20): C(x, 45, '>')
    C(20, 45, 'v')                       # down into pass-through
    # ================= PASS-THROUGH (skip entries, append p at TSENT) =============
    C(20, 46, 'v')                       # merge (entry re-loop + VSENT entry)
    C(20, 47, 'r')                       # A=item (entry>0 or TSENT<0), arrives S continues S
    C(20, 48, 'X')                       # A>0 -> W=entry ; A==0 -> S=entry ; A<0 -> E=TSENT
    # entry (A>0 -> W col19): resend, loop back up col18 to (18,46)>-> (20,46)v
    C(19, 48, 's')                       # resend (going W)
    C(18, 48, '^')                       # turn N up col18
    C(18, 47, '^'); C(18, 46, '>'); C(19, 46, '>')   # up then east to (20,46)v
    # entry (A==0 -> S col20): resend, loop up col17 into the same loopback
    C(20, 49, 's')                       # resend (going S)
    C(20, 50, '<'); C(17, 50, '^')       # west then up col17
    C(17, 47, '>')                       # east into (18,47)^ -> up -> (18,46)> loopback
    # TSENT (A<0 -> E col21): split packed p -> append (sR, Rmask), resend TSENT
    C(21, 48, 'v')                       # A=-2 (TSENT), B=p ; turn down
    for y in range(49, 54): C(21, y, 'v')
    C(21, 54, '>')                       # turn east (below loopback region)
    T(22, 54, '`1048576`')               # A=2^20  cols22..30
    C(31, 54, 'W')                       # A=p , B=2^20
    C(32, 54, '/')                       # A=Rmask , B=sR
    C(33, 54, 'W')                       # A=sR , B=Rmask
    C(34, 54, 's')                       # enqueue sR
    C(35, 54, 'W')                       # A=Rmask , B=sR
    C(36, 54, 's')                       # enqueue Rmask
    C(37, 54, '2'); C(38, 54, 'N')       # A=-2
    C(39, 54, 's')                       # enqueue TSENT
    # loopback to header: up col40 to row24, west to (14,24)
    C(40, 54, '^')
    for y in range(25, 54): C(40, y, '^')
    C(40, 24, '<')
    for x in range(15, 40):
        if (x, 24) not in placed: C(x, 24, '<')

    if STAGE == 'R':
        # PHASE-L branch (A<0 header) east from (15,26)> -> drain belt to O
        C(16, 26, 'v'); C(16, 27, 'r')   # dequeue belt (arrives S continues S)
        C(16, 28, '>'); C(45, 28, 's')   # emit to O
        C(46, 28, '^')                   # up
        for y in range(26, 28): C(46, y, '^')
        C(46, 25, '<')
        for x in range(17, 46):
            if (x, 25) not in placed: C(x, 25, '<')
        C(16, 25, 'v')                   # -> (16,26)v loop
        return p, placed

    return p, placed

if __name__ == '__main__':
    p, _ = build()
    print('footprint', p.footprint())
    p.save(_REPO + '/scratchpad/ss_mitm.man')

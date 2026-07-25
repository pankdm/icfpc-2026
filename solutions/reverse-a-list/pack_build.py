"""Register-packing reverse-a-list. Staged build.

Pipes on CTRL bottom wall (attach row ar). Cols: I@2(in) FEED@8(out) RETURN@14(in) MID@18(out).
  r : col<=7 -> I ; col>=9 -> RETURN.      (value-read@6,n-read@4 -> I ; deq@13 -> RETURN)
  s : col<=12 -> FEED ; col>=14 -> MID.    (enqueue@8 -> FEED ; output/field@16 -> MID)
Fold prefix is 13 wide (cols4..16). Vertical channels:
  col3 = round-loop up (reserved clear) ; col17 = fold dip ; col18 = close channel ; col19 = pack loop-back up.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + "/tools")
import littleman as lm

K = 2097152; OFF = 1048576

def _e(p, x, y, s):
    for ch in s: p.put(x, y, ch); x += 1
    return x

def build(stage='A'):
    p = lm.Program(); P = p.put
    HT = 20 if stage == 'A' else 26
    p.room(0, 0, 22, HT + 2)      # interior cols1..20, rows1..HT ; bottom wall row BOT
    BOT = HT + 1

    # ===== SETUP (row1): read n; BP=n; A=0(reg); drop into slot0 =====
    # (3,1)'>' is the round-loop merge (initial glide + DONE up-channel col3)
    P(1,1,'@'); P(3,1,'>')
    P(4,1,'r'); P(5,1,'b'); P(6,1,'0')
    P(7,1,'v'); P(7,2,'<'); P(1,2,'v')

    # ===== PACK SLOTS =====
    def slot(ey):
        P(1,ey,'>'); P(2,ey,'d'); P(18,ey,'v')          # entry; BP test; close channel col18
        P(2,ey+1,'>'); _e(p,4,ey+1,'M1W{+M`20`W{M')     # fold prefix cols4..16
        P(17,ey+1,'v'); P(17,ey+2,'<')                  # dip col17
        P(6,ey+2,'r'); P(5,ey+2,'+'); P(4,ey+2,'m'); P(1,ey+2,'v')  # read v@6 ; + ; m ; spine
        P(1,ey+3,'>')
    slot(3); slot(6); slot(9)

    # ===== FULLREG (row12): enqueue full reg@FEED, reset, loop to slot0 via col19 up =====
    P(1,12,'>'); P(8,12,'s'); P(9,12,'0')
    P(19,12,'^'); P(19,2,'<')

    # ===== CLOSE (col18 -> row13): reg>0 enqueue reg ; then SENT ; -> next phase =====
    P(18,13,'X')                    # S: A>0 CW(W) enqueue ; A==0 straight(S) skip
    P(8,13,'s'); P(7,13,'v')        # enq-reg branch
    P(18,14,'<'); P(7,14,'v')       # skip branch ; merge (7,14)='v'
    # ENQ_SENT (row15): A=-1 ; s SENT@FEED ; drop to (7,16) -> OUTER entry
    P(7,15,'>'); P(8,15,'1'); P(9,15,'N'); P(10,15,'s')
    P(11,15,'v'); P(11,16,'<'); P(7,16,'v')                # -> (7,17) -> (7,18) OUTER

    if stage == 'A':
        # ===== DRAIN forward raw: r; X real->output raw@MID ; SENT->halt =====
        P(7,17,'>'); P(13,17,'r'); P(14,17,'X')
        P(14,16,'H')                                       # SENT -> halt
        P(14,18,'>'); P(16,18,'s')                         # real: output raw @16[MID]
        P(17,18,'v'); P(17,19,'<'); P(7,19,'^')            # loop back to (7,17)
    else:
        # =====================  STAGE C: sentinel-reverse + unpack  ===================
        # OUTER entry (7,18) fed from north: (7,16)'v' -> (7,17)blank -> (7,18)'>'.
        # -- OUTER (row18): deq r; X real->EXTRACT(S) ; SENT->DONE(N) --
        P(7,18,'>'); P(11,18,'r'); P(12,18,'X')
        #   DONE (SENT->N (12,17)): west row17 -> col3 up-channel -> (3,1)
        P(12,17,'<'); P(3,17,'^')
        #   real (S (12,19)): -> EXTRACT
        # -- EXTRACT (row19): M(B=prev) ; descend col7 to LOOP entry --
        P(12,19,'<'); P(10,19,'M'); P(7,19,'v')            # (7,20)blank -> (7,21)'>'
        # -- LOOP (row21): deq r; X real->ROT(S) ; SENT->EMIT(N) --
        P(7,21,'>'); P(11,21,'r'); P(12,21,'X')
        #   ROT (real->S (12,22)): W ; s(enq prev FEED) ; loop up col5 to LOOP entry (7,21)
        P(12,22,'<'); P(10,22,'W'); P(9,22,'s'); P(5,22,'^'); P(5,21,'>')
        #   EMIT (SENT->N (12,20)): s(enq SENT FEED); W(A=prev); descend col6 to UNPACK
        P(12,20,'<'); P(9,20,'s'); P(8,20,'W'); P(6,20,'v')
        # -- UNPACK setup (row23): B=reg;A=3;BP=3;W -> A=reg,BP=3 --
        P(6,23,'>'); P(7,23,'M'); P(8,23,'3'); P(9,23,'b'); P(10,23,'W'); P(11,23,'v')
        P(11,24,'<'); P(1,24,'v')                          # route to loop entry (1,25)
        # -- UNPACK loop (row25): M K W / W s(field MID) W m d --
        P(1,25,'>'); P(2,25,'M'); _e(p,3,25,'`2097152`')   # `2097152` cols3..11
        P(12,25,'W'); P(13,25,'/'); P(14,25,'W'); P(15,25,'s'); P(16,25,'W'); P(17,25,'m'); P(18,25,'d')
        #   d: BP>0 CW(S) loop ; BP==0 straight(E) exit
        P(18,26,'<'); P(1,26,'^')                          # loop back to (1,25)
        #   exit (E (19,25)): up col19 -> row16 -> west -> (7,16) OUTER re-entry
        P(19,25,'^'); P(19,16,'<')                         # up col19, west row16 -> (7,16)'v'

    # ===== satellites & pipes =====
    ar = BOT + 1
    pumpy = ar + 3                                          # PUMP top row ; belt cap = 3+1+3 = 7
    p.input_room(1, ar+2)
    p.pipe([(2,ar+1),(2,ar)])                              # I -> CTRL@2 (N)
    p.room(6, pumpy, 10, 4)                                # PUMP cols6..15
    P(7, pumpy+1, '>'); P(8, pumpy+1, '@'); P(9, pumpy+1, 'R'); P(10, pumpy+1, 's'); P(11, pumpy+1, 'v')
    P(11, pumpy+2, '<'); P(7, pumpy+2, '^')
    p.pipe([(8,y) for y in range(ar, pumpy)])              # FEED CTRL@8 -> PUMP (S), len pumpy-ar
    p.pipe([(14,y) for y in range(pumpy-1, ar-1, -1)])     # RETURN PUMP -> CTRL@14 (N)
    if stage == 'A':
        p.output_room(17, ar+2)                            # O cols17..19
        p.pipe([(18,ar),(18,ar+1)])                        # MID CTRL@18 -> O (S)
    else:
        # SUBOFF relay adjacent-right, MID short. Build B=2^20 ONCE (`20` M 1 { M), then
        # loop: R ; X(>0 real: - s / ==0 discard). B=2^20 persists (R/-/s don't touch B).
        sfy = pumpy + 5
        p.room(15, sfy, 13, 6)                             # cols15..27 rows sfy..sfy+5 ; interior sfy+1..sfy+4
        # SETUP (row sfy+1): @ `20` M 1 { M  -> B=2^20 ; drop to loop
        P(16,sfy+1,'@'); _e(p,17,sfy+1,'`20`'); P(21,sfy+1,'M'); P(22,sfy+1,'1'); P(23,sfy+1,'{'); P(24,sfy+1,'M')
        P(25,sfy+1,'v'); P(25,sfy+2,'<'); P(16,sfy+2,'v')  # return corridor -> (16,sfy+3)
        # LOOP (row sfy+3): R ; X real->S(-,s) / discard->E(loop up)
        P(16,sfy+3,'>'); P(17,sfy+3,'R'); P(18,sfy+3,'X')
        P(19,sfy+3,'^'); P(19,sfy+2,'<')                   # discard: up, W -> (16,sfy+2) loop
        P(18,sfy+4,'>'); P(19,sfy+4,'-'); P(20,sfy+4,'s'); P(21,sfy+4,'^'); P(21,sfy+2,'<')  # real
        # MID CTRL@18 -> SUBOFF top (short)
        p.pipe([(18,y) for y in range(ar, sfy)])
        # O off SUBOFF right: s@(20,sfy+4) -> O
        p.output_room(30, sfy+3)                           # O cols30..32 ; O@(31,sfy+4)
        p.pipe([(28,sfy+4),(29,sfy+4)])                    # SUBOFF wall(27,sfy+4) -> O wall(30,sfy+4)
    return p, HT, BOT

if __name__ == "__main__":
    p, HT, BOT = build('A')
    print(p.render())
    print("footprint:", p.footprint())

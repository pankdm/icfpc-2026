"""Streaming selection sort, fully hand-placed (blanks glide, only placed glyphs collide).
sentinel=-1, bias=+10001."""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import layout as L
from layout import Layout, place_pipe, DIRS
OUT = 'solutions/sort-numbers/select-v1.man'

def build():
    P = Layout()
    P.room(0, 0, 26, 26)                       # controller interior x1..24 y1..24
    P.input_room(12, -6)                       # I(13,-5), bottom border (13,-4)
    P.room(35, 8, 6, 8)                        # relay x35..40 y8..15 (longer pipes -> capacity ~19)
    P.output_room(9, 28)                       # O(10,29), top border (10,28)
    # relay man: R (recv FEED) ; s (send RET)
    for (x,y,c) in [(36,10,'@'),(37,10,'>'),(38,10,'R'),(39,10,'v'),
                    (37,11,'^'),(38,11,'s'),(39,11,'<')]:
        P.put(x,y,c)
    put = P.put

    # ===== LOAD-INIT (row1) =====
    put(1,1,'@'); put(2,1,'>')                 # ML merge (spawn + EMPTY)
    put(3,1,'r'); put(4,1,'b')                 # A=n ; BP=n
    for i,c in enumerate('`10001`'): put(5+i,1,c)   # (5..11) A=10001
    put(12,1,'M')                              # B=10001
    put(13,1,'v')                              # -> init2loop

    # ===== init2loop connector =====
    put(13,3,'>')                              # MLL merge (13,2 blank glide)

    # ===== LOAD-LOOP (row3) =====
    put(14,3,'r'); put(15,3,'+')               # A=v ; A=v+10001
    put(20,3,'s'); put(21,3,'m'); put(22,3,'d')     # s(FEED) ; BP-- ; d(E-hdg? see)
    # NB: man enters row3 heading E (MLL '>').  d heading E: BP>0 CW=S loop; BP==0 straight E exit.
    put(22,4,'<'); put(13,4,'^')               # loopback row4 -> MLL
    # exit: deposit sentinel -1 to FEED, then -> MREV (row5/6)
    put(23,3,'v'); put(23,5,'<')               # (23,4 blank) down then W row5
    put(22,5,'1'); put(21,5,'N'); put(20,5,'s')     # A=1 ; A=-1 ; s(FEED sentinel)
    put(19,5,'v'); put(19,6,'>')               # -> row6 E -> MREV

    # ===== REV-START =====
    put(22,6,'v')                              # MREV merge
    put(22,7,'r'); put(22,8,'X')               # A=firsttoken ; X(S): >0 W real, <0 E sent
    put(21,8,'M'); put(20,8,'v')               # REV-FIRST B:=min ; drop into MSCAN

    # ===== SCAN (spine col20) =====
    put(20,9,'v')                              # MSCAN merge
    put(20,10,'r'); put(20,11,'X')             # token ; X(S): >0 W real, <0 E sent->EMIT
    put(19,11,'-'); put(18,11,'X')             # A=token-min ; X(W): >0 N keep,<0 S newmin,=0 W keep

    # KEEP (recirc token)
    put(18,10,'^'); put(18,9,'+'); put(18,8,'s')     # merge ; + ; s(FEED)
    put(18,7,'>'); put(19,7,'v'); put(19,9,'>')      # loop -> MSCAN(W)   (19,8 blank)
    put(17,11,'^'); put(17,10,'>')             # equal -> KEEP merge

    # NEWMIN (recirc old min, B:=token)
    put(18,12,'+'); put(18,13,'W'); put(18,14,'s')   # + ; W ; s(FEED)
    put(18,15,'>'); put(22,15,'^'); put(22,9,'<')    # loop: E then up col22 then W -> MSCAN(E)
    #  (19,15)(20,15)(21,15) blank ; (22,14..22,10) blank ; (21,9) blank

    # ===== EMIT (sentinel branch -> row17) =====
    put(21,11,'v'); put(21,17,'<')             # descend col21 (21,12..16 blank) then W row17
    put(20,17,'1'); put(19,17,'N'); put(18,17,'s')   # A=1 ; A=-1 ; s(FEED sentinel)
    for i,c in enumerate('`10001`'): put(8+i,17,c)   # (8..14) read W -> A=10001
    put(7,17,'-'); put(6,17,'N'); put(5,17,'s')      # A=10001-min ; A=min-10001 ; s(OUTPUT)
    # emit2rev loopback
    put(4,17,'<'); put(1,17,'^'); put(1,6,'>'); # (3,17)(2,17) blank; col1 up; row6 E -> MREV
    #  row6 (2,6..21,6) blank -> (22,6) MREV

    # ===== EMPTY (REV sentinel -> next round LOAD) =====
    put(24,8,'v'); put(24,24,'<'); put(2,24,'^')     # (23,8 blank) col24 down; row24 W; col2 up->ML(2,1)

    # ===== pipes =====
    place_pipe(P, [(13,-3),(13,-2),(13,-1)], DIRS['S'])                 # INPUT -> (13,0)
    place_pipe(P, [(26,13),(27,13),(28,13),(29,13),(30,13),(31,13),(32,13),(33,13),(34,13)], DIRS['E'])  # FEED -> relay
    place_pipe(P, [(34,10),(33,10),(32,10),(31,10),(30,10),(29,10),(28,10),(27,10),(26,10)], DIRS['W'])  # RET -> (25,10)
    place_pipe(P, [(10,26),(10,27)], DIRS['S'])                        # OUTPUT -> (10,28)
    return P

if __name__ == '__main__':
    P = build()
    print('footprint:', P.footprint())
    P.save(OUT)
    print(P.render())

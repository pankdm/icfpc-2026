import sys; import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),'tools'))
import littleman as lm

def build():
    p=lm.Program(); placed={}
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]} vs {ch}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    def V(x,y,s):
        for i,c in enumerate(s): C(x,y+i,c)
    # ---- rooms & pipes ----
    p.room(0,5,27,47)             # P interior x1..25 y6..50 ; rightwall x26 ; bottomwall y51
    p.input_room(12,0); p.pipe([(13,3),(13,4)])          # INPUT dst(13,4)
    p.room(35,16,6,10)            # R interior x36..39 y17..24
    p.pipe([(27,22),(34,22)])     # pipe1 P->R
    p.pipe([(34,20),(27,20)])     # pipe2 R->P dst(27,20)
    p.output_room(23,54); p.pipe([(24,52),(24,53)])      # OUTPUT src(24,52)
    p.man(36,21)
    C(37,21,'>');C(38,21,'r');C(39,21,'v')
    C(37,22,'^');C(38,22,'s');C(39,22,'<')
    # ================= FILL =================
    p.man(12,6)
    C(13,6,'r');C(14,6,'b');C(15,6,'v')
    C(15,7,'>');C(16,7,'d')
    C(16,8,'r');C(16,9,'s');C(16,10,'m');C(16,11,'<')
    C(14,11,'^');C(14,7,'>')
    C(22,7,'v')                                # exit E (17..21,7 spaces) -> down col22
    # ================= SETUP (col22) =================
    V(22,8,'`20000`'); C(22,15,'s')
    V(22,16,'`16`');   C(22,20,'b')
    C(22,21,'r');C(22,22,'M');C(22,23,'v')     # -> drop col22 to row48
    # ================= TOK =================
    C(18,16,'v'); C(18,18,'r');C(18,19,'-');C(18,20,'X')
    # LT (d<0 E ; d==0 S)
    C(19,20,'v');C(18,21,'>');C(19,21,'v')
    C(19,22,'+');C(19,23,'s');C(19,24,'v')     # drop col19 to row48
    # GE (d>0 W)
    C(17,20,'W');C(16,20,'s');C(15,20,'+');C(14,20,'M');C(13,20,'v')
    V(13,21,'`20000`'); C(13,28,'-'); C(13,29,'X')
    C(9,29,'v')                                # DATA W (12,11,10 spaces) -> drop col9 to row48
    # LAPEND
    C(13,30,'W');C(13,31,'s');C(13,32,'m');C(13,33,'a')
    # NEXTLAP (E)
    C(21,33,'v');C(21,34,'r');C(21,35,'M');C(21,36,'v')   # (14..20,33 spaces) drop col21 to row48
    # WESTBOUND row48 + up-rail col3 + eastbound row16
    C(22,48,'<');C(21,48,'<');C(19,48,'<');C(9,48,'<')
    C(3,48,'^'); C(3,16,'>')                   # up col3 (spaces) ; turn E
    # eastbound (4..17,16 spaces) -> (18,16)
    # ================= OUTPUT (BP==0 S) =================
    C(13,34,'v');C(13,35,'r');C(13,36,'M')
    V(13,37,'`20000`'); C(13,44,'-'); C(13,45,'X')
    # OUT-DATA (W)
    C(12,45,'W');C(11,45,'s');C(10,45,'^');C(10,34,'>');C(13,34,'v')  # up col10 -> row34 -> (13,34)
    # OUT-MARKER (S) -> round rail
    C(13,46,'<'); C(2,46,'^'); C(2,6,'>')      # (3..12,46 spaces) up col2 (3..11,6 spaces) -> @
    return p,placed

if __name__=='__main__':
    p,placed=build()
    print(p.render()); print('footprint',p.footprint())

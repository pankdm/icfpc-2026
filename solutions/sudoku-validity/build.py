import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys; sys.path.insert(0,_REPO + '/tools'); import littleman as lm
IN,MRF,MRR,S2F,S2R,OUT = 2,5,8,11,14,17
BASE=0
class B:
    def __init__(s): s.p=lm.Program(); s.OW={}
    def put(s,x,y,ch):
        if (x,y) in s.OW and s.OW[(x,y)]!=ch: print(f"!!COLL {(x,y)} '{s.OW[(x,y)]}'->'{ch}'")
        s.OW[(x,y)]=ch; s.p.put(x,y,ch)
b=B(); cur=[2,BASE]; P=b.put; P(1,BASE,'@')
def arith(chars):
    for ch in chars: P(cur[0],cur[1],ch); cur[0]+=1
def dipE(kind,row):
    x=cur[0]; P(x,BASE,'v'); P(x,row,kind); P(x,row+1,'>'); P(x+1,row+1,'^'); P(x+1,BASE,'>'); cur[0]=x+2
def emit(stream):
    for op in stream:
        if isinstance(op,tuple):
            if op[0]=='P': dipE(op[1],op[2])
            elif op[0]=='LIT': arith('`'+op[1]+'`')
        else: arith(op)
compute=[
 ('P','r',IN),'M','1','+',('P','s',S2F),
 'W','M','3','W','/','M','3','*',('P','s',S2F),
 ('P','r',IN),'M',('LIT','10'),'+',('P','s',S2F),
 'W','M','3','W','/','M',
 ('P','r',S2R),('P','s',S2F),('P','r',S2R),'+',
 'M',('LIT','19'),'+','M',
 ('P','r',S2R),('P','s',S2F),'W',('P','s',S2F),
 '0',('P','s',S2F),
 ('P','r',IN),'M','1','{','M',
]
# ===== SEED MR ring (loop) =====
arith('`27`'); arith('b')            # BP=27
arith('`1024`')                      # A=1024 (persists)
SJ=cur[0]
cur=[SJ,0]; dipE('s',MRF)            # (SJ,0)='v' junction; sMR(1024); man (SJ+2,0) E
P(SJ+2,0,'m'); P(SJ+3,0,'d')         # BP-- ; BP>0->S(loop) ; 0->E(exit)
P(SJ+3,1,'<'); P(1,1,'^'); P(1,-4,'>'); P(SJ,-4,'v')   # loop back-edge -> drop SJ
arith2=SJ+4
P(SJ+4,0,'0')                        # exit: A=0
cur=[SJ+5,0]; dipE('s',MRF)          # sMR sentinel(0)
C0=cur[0]
emit(compute)
EX=cur[0]
# ================= PASSLOOP =================
dipE('r',S2R)                 # A=counter ; man (EX+2,0) E
PLX=EX+2
P(PLX,0,'X')                  # zero(marker)->E(DONE) ; pos->CW=S(SWEEPSET)
# ---- DONE (straight E) ----  set A=1, dip sOUT, back-edge row -3 to MAIN(2)
P(PLX+1,0,'1')                # A=1
cur=[PLX+2,0]; dipE('s',OUT)  # sOUT(A=1) ; man (PLX+4,0) E
DX=PLX+4
P(DX,0,'^')                   # rise to clearance -3
P(DX,-3,'<')                  # turn W, glide W on row -3 to MAIN col 2
P(C0,-3,'v')                  # drop into compute-start (bypass seed)
# ---- SWEEPSET (S from PLX) ----  b,m then back-edge row -1 to JT
P(PLX,1,'b'); P(PLX,2,'m'); P(PLX,3,'>')  # E
P(PLX+5,3,'^')                # rise
P(PLX+5,-1,'>')               # turn E on row -1 -> glide to JT drop
# ================= SWEEP =================
SW=PLX+12
P(SW,-1,'v')                  # drop from row -1 into JT
P(SW,0,'v')                   # JT: S -> rMR
P(SW,MRR,'r'); P(SW,MRR+1,'>'); P(SW+1,MRR+1,'^'); P(SW+1,0,'>')  # rMR dip -> (SW+2,0) E
P(SW+2,0,'X')                 # sentinel(0)->E(SENT) ; mask(pos)->CW=S(process)
# ---- SENT (straight E) ---- sMR(0) dip, back-edge row -2 to PASSLOOP(EX)
cur=[SW+3,0]; dipE('s',MRF)   # sMR sends A=0 (re-enqueue sentinel) ; man (SW+5,0) E
SEX=SW+5
P(SEX,0,'^'); P(SEX,-2,'<'); P(EX,-2,'v')   # rise, W on row-2, drop into PASSLOOP(EX,0)
# ---- process: CHECK (S) ----
P(SW+2,1,'d')                 # BP>0->CW=W(SKIP) ; 0->straight S(TARGET)
# ---- SKIP (W) ---- glide W, sMR dip, m, back-edge row -1 to JT
P(SW-6,1,'v')                 # turn S (after gliding W)
P(SW-6,MRF,'s'); P(SW-6,MRF+1,'m')          # sMR(mask); m
P(SW-6,MRF+2,'>'); P(SW-5,MRF+2,'^'); P(SW-5,-1,'>')   # rise to row-1, E to JT drop
# ---- TARGET (straight S) ----
P(SW+2,2,'+')                 # A=mask+bit (continue S)
P(SW+2,MRF,'s')               # sMR(mask+bit) at row5
P(SW+2,MRF+1,'&')             # A=(mask+bit)&bit  (row6)
P(SW+2,MRF+2,'X')             # dup(0)->straight S ; ok(pos)->CW=W
# ---- DUP (S) ---- continue S to sOUT(17), A=0
P(SW+2,OUT,'s')               # sOUT sends A=0
P(SW+2,OUT+1,'H')             # halt
# ---- OK (W) ---- set A=99,b, back-edge row -1 to JT
P(SW+1,MRF+2,'`'); P(SW,MRF+2,'9'); P(SW-1,MRF+2,'9'); P(SW-2,MRF+2,'`')  # A=99 going W
P(SW-3,MRF+2,'b')             # BP=99
P(SW-4,MRF+2,'^'); P(SW-4,-1,'>')          # rise to row-1, E to JT drop
b.EX=EX; b.PLX=PLX; b.SW=SW
# ================= rooms & pipes =================
RW=SW+10; ox=RW+1
b.p.room(0,-5,RW+1,OUT+8)     # room rows -5..OUT+2
b.p.input_room(ox+2,IN-1); b.p.pipe([(ox+1,IN),(ox,IN)])
b.p.output_room(ox+2,OUT-1); b.p.pipe([(ox,OUT),(ox+1,OUT)])
b.p.room(ox+2,S2F-1,7,(S2R+1)-(S2F-1)+1)
b.p.pipe([(ox,S2F),(ox+1,S2F)]); b.p.pipe([(ox+1,S2R),(ox,S2R)])
P(ox+3,S2F,'>'); P(ox+4,S2F,'@'); P(ox+5,S2F,'R'); P(ox+6,S2F,'s'); P(ox+7,S2F,'v'); P(ox+7,S2F+1,'<'); P(ox+3,S2F+1,'^')
mpx=ox+15
b.p.room(mpx,MRF-1,7,(MRR+1)-(MRF-1)+1)
b.p.pipe([(ox,MRF),(mpx-1,MRF)]); b.p.pipe([(mpx-1,MRR),(ox,MRR)])
P(mpx+1,MRF,'>'); P(mpx+2,MRF,'@'); P(mpx+3,MRF,'R'); P(mpx+4,MRF,'s'); P(mpx+5,MRF,'v'); P(mpx+5,MRF+1,'<'); P(mpx+1,MRF+1,'^')
b.p.save(_REPO + '/solutions/sudoku-validity/v2.man')
print("FOOT",b.p.footprint())

"""Assemble the LLLM interpreter as a littleman op-stream (two-belt, C-model state ring).
Compact ring: a shared temp pool P0..P13 for all phase-local temporaries; only truly
persistent values are dedicated slots. Validated frame-exact via lllm_optest.py (VM)."""

POOL=['P%d'%i for i in range(12)]
STATE = (
    ['W','H','Wm1','Hm1','N','mx','my','dcol','drow','AA','BB','hlt','kc']  # persistent
    + ['col','row','op']                                                    # cross-phase dedicated
    + POOL                                                                  # shared temps
    + ['et','kbuild']                                                       # private scratch (EQ/GT0/const)
)

class Asm:
    def __init__(self):
        self.ring=list(STATE); self.ops=[]
    def e(self,*o): self.ops.extend(o)
    def rot(self): self.e('r','s'); self.ring.append(self.ring.pop(0))
    def tf(self,n):
        assert n in self.ring, n
        while self.ring[0]!=n: self.rot()
    def LA(self,n): self.tf(n); self.e('r','s'); self.ring.append(self.ring.pop(0))
    def SA(self,n): self.e('M'); self.tf(n); self.e('r','W','s'); self.ring.append(self.ring.pop(0))
    def _abc(self,k):
        for a in range(2,10):
            for b in range(a,10):
                c=k-a*b
                if 0<=c<=9: return (a,b,c)
        return None
    def K(self,k):
        # emit ops leaving A=k, backtick-free (loader pairs backticks vertically -> unsafe).
        if 0<=k<=9: self.e(('#',k)); return
        for a in range(2,10):
            if k%a==0 and 2<=k//a<=9: self.e(('#',k//a),'M',('#',a),'*'); return
        abc=self._abc(k)
        if abc:
            a,b,c=abc; self.e(('#',c)); self.SA('kbuild')
            self.e(('#',a),'M',('#',b),'*','M'); self.LA('kbuild'); self.e('+'); return
        if k%2==0: self.K(k//2); self.e('M','+'); return
        raise ValueError(f"K {k}")
    def rc(self): self.e('rc')
    def sc(self): self.e('sc')
    def rr(self): self.e('rr')
    def sr(self): self.e('sr')
    def cmd(self): self.e('cmd')
    def ri(self): self.e('ri')
    def binS(self,dst,x,y,opch):
        self.LA(y); self.e('M'); self.LA(x); self.e(opch); self.SA(dst)
    def binK(self,dst,x,k,opch):
        self.K(k); self.e('M'); self.LA(x); self.e(opch); self.SA(dst)
    def mov(self,dst,src): self.LA(src); self.SA(dst)
    def _b63(self): self.e(('#',7),'M',('#',9),'*','M')   # B := 63 (A:=63 too), inline (no belt)
    def GT0(self,dst,src):        # dst = 1 if src>0 else 0  (4 belt accesses)
        self.LA(src); self.e('N'); self.SA('et')          # et = -src
        self._b63(); self.LA('et'); self.e('}','N'); self.SA(dst)
    def EQ(self,dst,x,k):         # dst = 1 if x==k  (4 belt accesses)
        self.K(k); self.e('M'); self.LA(x); self.e('-','M','*'); self.SA('et')  # et = (x-k)^2
        self._b63(); self.LA('et'); self.e('N','}','M',('#',1),'+'); self.SA(dst)
    def EQS(self,dst,x,y):        # dst = 1 if x==y  (5 belt accesses)
        self.LA(y); self.e('M'); self.LA(x); self.e('-','M','*'); self.SA('et')
        self._b63(); self.LA('et'); self.e('N','}','M',('#',1),'+'); self.SA(dst)
    def BPLOOP(self, cnt_slot, bodyfn):
        self.LA(cnt_slot); entry=self.ring[0]
        sub=Asm.__new__(Asm); sub.ring=self.ring; sub.ops=[]
        bodyfn(sub); sub.tf(entry)
        self.ops.append(('BPLOOP', sub.ops))
    def LOOPX(self, bodyfn, testslot):
        succ=STATE[(STATE.index(testslot)+1)%len(STATE)]; self.tf(succ); entry=self.ring[0]
        sub=Asm.__new__(Asm); sub.ring=self.ring; sub.ops=[]
        bodyfn(sub)
        assert self.ring[0]==entry, ("LOOPX not ring-preserving", self.ring[0], entry)
        self.ops.append(('LOOPX', sub.ops))
    def FOREVER(self, bodyfn):
        entry=self.ring[0]
        sub=Asm.__new__(Asm); sub.ring=self.ring; sub.ops=[]
        bodyfn(sub); sub.tf(entry)
        self.ops.append(('FOREVER', sub.ops))


def blend(a, slot, newp):   # slot = active(P10)? newp : slot     (uses P8,P9)
    a.binS('P8','P10',newp,'*')
    a.LA('P10'); a.e('N'); a.SA('P9'); a.binK('P9','P9',1,'+')
    a.binS('P9','P9',slot,'*')
    a.binS(slot,'P8','P9','+')


def emit_decode(a, src, bd, colorout):
    # op(dedicated) & colorout from ascii slot `src`, border flag slot `bd`. temps P0..P3.
    a.K(0); a.SA('op')
    for k,opv in [(43,1),(45,2),(77,3),(88,4),(72,5),(94,6),(62,7),(118,8),(60,9)]:
        a.EQ('P0',src,k); a.binK('P1','P0',opv,'*'); a.binS('op','op','P1','+')
    # digit: isdig = gt0(asc-47)*gt0(58-asc); op += isdig*(asc-38)
    a.binK('P0',src,47,'-'); a.GT0('P0','P0')
    a.binK('P1',src,58,'-'); a.LA('P1'); a.e('N'); a.SA('P1'); a.GT0('P1','P1')
    a.binS('P0','P0','P1','*')                   # P0 = isdig
    a.binK('P1',src,38,'-'); a.binS('P1','P1','P0','*'); a.binS('op','op','P1','+')
    # color from op:  isdigit=gt0(op-9); yellow=gt0(op-3)*(1-isdigit); pm=gt0(op)*(1-gt0(op-2)); isM=eq(op,3)
    a.binK('P2','op',9,'-'); a.GT0('P2','P2')    # P2 = isdigit
    a.binK('P0','op',3,'-'); a.GT0('P0','P0')    # ge4
    a.LA('P2'); a.e('N'); a.SA('P1'); a.binK('P1','P1',1,'+')  # 1-isdigit
    a.binS('P0','P0','P1','*')                   # P0 = yellow
    a.GT0('P1','op')                             # gt0(op)
    a.binK('P3','op',2,'-'); a.GT0('P3','P3'); a.LA('P3'); a.e('N'); a.SA('P3'); a.binK('P3','P3',1,'+')
    a.binS('P1','P1','P3','*')                   # P1 = pm
    a.EQ('P3','op',3)                            # P3 = isM
    a.binK(colorout,'P0',3,'*')
    a.binK('P0','P1',10,'*'); a.binS(colorout,colorout,'P0','+')
    a.binK('P0','P3',12,'*'); a.binS(colorout,colorout,'P0','+')
    a.binK('P0','P2',8,'*'); a.binS(colorout,colorout,'P0','+')
    # border override
    a.LA(bd); a.e('N'); a.SA('P0'); a.binK('P0','P0',1,'+')   # 1-bd
    a.binS('op','op','P0','*')
    a.binS(colorout,colorout,'P0','*')
    a.binK('P0',bd,4,'*'); a.binS(colorout,colorout,'P0','+')


def emit_tick(a):
    # 'op' (dedicated) is set by fetch. active=P10, isd=P11.
    a.LA('hlt'); a.e('N'); a.SA('P10'); a.binK('P10','P10',1,'+')   # active=1-hlt
    a.binK('P11','op',9,'-'); a.GT0('P11','P11')                    # isd
    # ---- heading ----
    a.binK('P0','op',5,'-'); a.GT0('P0','P0')                       # gt0(op-5)
    a.LA('P11'); a.e('N'); a.SA('P1'); a.binK('P1','P1',1,'+')      # 1-isd
    a.binS('P1','P0','P1','*')                                      # isarrow -> P1
    a.EQ('P0','op',7); a.EQ('P2','op',9); a.binS('P0','P0','P2','-')  # avx -> P0
    a.EQ('P2','op',8); a.EQ('P3','op',6); a.binS('P2','P2','P3','-')  # avy -> P2
    a.LA('P1'); a.e('N'); a.SA('P3'); a.binK('P3','P3',1,'+')       # 1-isarrow -> P3
    a.binS('P4','dcol','P3','*'); a.binS('P0','P0','P1','*'); a.binS('P4','P4','P0','+')  # h1c -> P4
    a.binS('P5','drow','P3','*'); a.binS('P2','P2','P1','*'); a.binS('P5','P5','P2','+')  # h1r -> P5
    a.binK('P0','AA',63,'}')
    a.LA('AA'); a.e('N'); a.SA('P2'); a.binK('P2','P2',63,'}')
    a.binS('P0','P0','P2','-')                                      # sA -> P0
    a.EQ('P2','op',4)                                              # isX -> P2
    a.binS('P0','P2','P0','*')                                     # ss -> P0
    a.binS('P1','P0','P0','*')                                     # aX -> P1
    a.LA('P1'); a.e('N'); a.SA('P2'); a.binK('P2','P2',1,'+')      # 1-aX -> P2
    a.binS('P6','P4','P2','*')
    a.binS('P3','P0','P5','*'); a.binS('P3','P3','P1','*'); a.binS('P6','P6','P3','-')  # ndc -> P6
    a.binS('P7','P5','P2','*')
    a.binS('P3','P0','P4','*'); a.binS('P3','P3','P1','*'); a.binS('P7','P7','P3','+')  # ndr -> P7
    blend(a,'dcol','P6'); blend(a,'drow','P7')
    # ---- A/B ----
    a.EQ('P0','op',3); a.EQ('P1','op',1); a.EQ('P2','op',2)         # isM,isplus,isminus
    a.binK('P3','op',10,'-'); a.binS('P4','P11','P3','*')           # isd*digitval -> P4
    a.binS('P3','AA','BB','+'); a.binS('P3','P1','P3','*'); a.binS('P4','P4','P3','+')
    a.binS('P3','AA','BB','-'); a.binS('P3','P2','P3','*'); a.binS('P4','P4','P3','+')
    a.binS('P3','P11','P1','+'); a.binS('P3','P3','P2','+'); a.LA('P3'); a.e('N'); a.SA('P3'); a.binK('P3','P3',1,'+')
    a.binS('P3','P3','AA','*'); a.binS('P4','P4','P3','+')          # nA -> P4
    a.binS('P3','P0','AA','*'); a.LA('P0'); a.e('N'); a.SA('P5'); a.binK('P5','P5',1,'+')
    a.binS('P5','P5','BB','*'); a.binS('P5','P3','P5','+')          # nB -> P5
    blend(a,'AA','P4'); blend(a,'BB','P5')
    # ---- move ----
    a.EQ('P0','op',5)                                              # isH
    a.LA('P0'); a.e('N'); a.SA('P1'); a.binK('P1','P1',1,'+')      # notH -> P1
    a.binS('P2','P1','dcol','*'); a.binS('P2','mx','P2','+')       # nmx -> P2
    a.binS('P3','P1','drow','*'); a.binS('P3','my','P3','+')       # nmy -> P3
    a.EQ('P4','P2',0); a.EQS('P5','P2','Wm1'); a.binS('P4','P4','P5','+')
    a.EQ('P5','P3',0); a.binS('P4','P4','P5','+'); a.EQS('P5','P3','Hm1'); a.binS('P4','P4','P5','+')
    a.GT0('P4','P4')                                              # onwall -> P4
    a.binS('P5','P1','P4','*'); a.binS('P5','P0','P5','+'); a.GT0('P5','P5')  # nHalt -> P5
    blend(a,'mx','P2'); blend(a,'my','P3')
    a.binS('P0','P10','P5','*'); a.binS('hlt','hlt','P0','+')      # hlt += active*nHalt


def emit_render(a):
    # cells belt holds triples [op, addr+1, color] per cell. Scan N triples.
    def body(b):
        b.rc(); b.sc()             # op (recirc, no cmd)
        b.rc(); b.cmd(); b.sc()    # addr+1
        b.rc(); b.cmd(); b.sc()    # color
    a.BPLOOP('N', body)
    a.K(16); a.e('M'); a.LA('my'); a.e('*'); a.SA('P0')
    a.LA('mx'); a.e('M'); a.LA('P0'); a.e('+'); a.SA('P0')
    a.binK('P0','P0',1,'+'); a.LA('P0'); a.cmd()
    a.K(9); a.cmd()
    a.K(1); a.e('N'); a.cmd()   # -1 SWAP


def emit_fetch(a):
    a.LA('W'); a.e('M'); a.LA('my'); a.e('*'); a.SA('P0')
    a.LA('mx'); a.e('M'); a.LA('P0'); a.e('+'); a.SA('P0')         # midx -> P0
    a.binK('P1','P0',3,'*')                                        # 3*midx -> P1
    a.BPLOOP('P1', lambda b:(b.rc(), b.sc()))
    a.rc(); a.SA('op'); a.LA('op'); a.sc()                         # op := front (triple's first) ; recirc
    a.binK('P2','N',3,'*'); a.binS('P2','P2','P1','-'); a.binK('P2','P2',1,'-')  # 3N-3midx-1
    a.BPLOOP('P2', lambda b:(b.rc(), b.sc()))


def emit_fill(a):
    def fillbody(b):
        b.ri(); b.SA('P4')                                        # asc -> P4
        b.EQ('P0','col',0); b.EQS('P1','col','Wm1'); b.binS('P7','P0','P1','+')
        b.EQ('P0','row',0); b.binS('P7','P7','P0','+')
        b.EQS('P1','row','Hm1'); b.binS('P7','P7','P1','+'); b.GT0('P7','P7')   # bd -> P7
        emit_decode(b,'P4','P7','P5')                            # op, color=P5
        b.K(16); b.e('M'); b.LA('row'); b.e('*'); b.SA('P6')
        b.LA('col'); b.e('M'); b.LA('P6'); b.e('+'); b.SA('P6')  # dispp -> P6
        b.LA('op'); b.sc()
        b.binK('P0','P6',1,'+'); b.LA('P0'); b.sc()   # addr+1
        b.LA('P5'); b.sc()                             # color
        b.EQ('P0','P4',64)                                       # mm
        b.binS('P1','col','mx','-'); b.binS('P1','P1','P0','*'); b.binS('mx','mx','P1','+')
        b.binS('P1','row','my','-'); b.binS('P1','P1','P0','*'); b.binS('my','my','P1','+')
        b.binK('col','col',1,'+')
        b.EQS('P0','col','W')                                    # atW
        b.LA('P0'); b.e('N'); b.SA('P1'); b.binK('P1','P1',1,'+')
        b.binS('col','col','P1','*')
        b.binS('row','row','P0','+')
    a.BPLOOP('N', fillbody)


def build():
    a=Asm()
    for _ in STATE:
        a.e(('#',0),'s')
    a.ri(); a.SA('W')
    a.ri(); a.SA('H')
    a.binK('Wm1','W',1,'-'); a.binK('Hm1','H',1,'-')
    a.binS('N','W','H','*')
    for s,v in [('col',0),('row',0),('mx',0),('my',0),('hlt',0),('dcol',1),('drow',0),('AA',0),('BB',0)]:
        a.K(v); a.SA(s)
    emit_fill(a)
    emit_render(a)
    def roundbody(b):
        b.ri(); b.SA('kc')
        def kbody(c):
            emit_fetch(c); emit_tick(c)
            c.binK('kc','kc',1,'-'); c.LA('kc')
        b.LOOPX(kbody,'kc')
        emit_render(b)
    a.FOREVER(roundbody)
    return a.ops


def build_fillonly():
    a=Asm()
    for _ in STATE: a.e(('#',0),'s')
    a.ri(); a.SA('W'); a.ri(); a.SA('H')
    a.binK('Wm1','W',1,'-'); a.binK('Hm1','H',1,'-'); a.binS('N','W','H','*')
    for s,v in [('col',0),('row',0),('mx',0),('my',0),('hlt',0),('dcol',1),('drow',0),('AA',0),('BB',0)]:
        a.K(v); a.SA(s)
    emit_fill(a)
    return a.ops


if __name__=='__main__':
    ops=build()
    def flat(o):
        n=0
        for x in o:
            if isinstance(x,tuple) and x[0] in('BPLOOP','LOOPX','FOREVER'): n+=flat(x[1])
            else: n+=1
        return n
    print("ring", len(STATE), "flat ops", flat(ops))

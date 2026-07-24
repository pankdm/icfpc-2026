"""Faithful single-man sim (A,B,BP + named rings) to develop the CONTROLLER op-stream.
The controller reads r,c,v, computes box, and emits the six bits (rowLo,rowHi,colLo,
colHi,boxLo,boxHi) that get sent to the six storage men. Verified vs the sudoku ref.
"""
import collections
M64=(1<<64)-1
def w64(x):
    x&=M64
    return x-(1<<64) if x>=(1<<63) else x

def run(prog, inp, rings, trace=False):
    A=B=BP=0
    R={n:collections.deque() for n in rings}
    IN=collections.deque(inp)
    OUT={n:[] for n in ('rowLo','rowHi','colLo','colHi','boxLo','boxHi')}
    i=0
    while i<len(prog):
        op=prog[i]; k=op if isinstance(op,str) else op[0]
        if trace: print(i,op,'A',A,'B',B,{n:list(R[n]) for n in R})
        if k=='c': A=op[1]
        elif k=='M': B=A
        elif k=='W': A,B=B,A
        elif k=='+': A=w64(A+B)
        elif k=='-': A=w64(A-B)
        elif k=='*': A=w64(A*B)
        elif k=='&': A=w64(A&B)
        elif k=='|': A=w64(A|B)
        elif k=='{': A=w64(A<<B) if 0<=B<=63 else 0
        elif k=='/':
            if B==0: d=A;A=0;B=d
            else:
                q=A//B; r=A-q*B; A=w64(q); B=w64(r)
        elif k[0]=='s' and k[1:] in R: R[k[1:]].append(A)
        elif k[0]=='r' and k[1:] in R: A=R[k[1:]].popleft()
        elif k=='rIN': A=IN.popleft()
        elif k in OUT: OUT[k].append(A)
        else: raise Exception('badop '+str(op))
        i+=1
    return OUT

# --- reference (matches problem semantics; bit=1<<(v-1) per unit) ---
def ref(r,c,v):
    box=3*(r//3)+(c//3)
    out={}
    for kind,idx in (('row',r),('col',c),('box',box)):
        field=idx%5; rk=idx//5
        base=1<<(9*field+(v-1))
        out[kind+'Lo']=base*(1-rk); out[kind+'Hi']=base*rk
    return out

RINGS=['IDX','VR','T']
# compute bitLo,bitHi for one kind: idx in A (consumed), v peeked from VR, uses T ring.
def emit_kind(kind):
    p=[]
    # A=idx. stash idx copy for rk later, and derive field.
    p+=['sT']                       # T=[idx]
    p+=['M',('c',5),'W','/']        # B=idx;A=5;A=idx,B=5; A=rk(drop),B=field
    # 9*field:
    p+=['W','M',('c',9),'*']        # A=field,B=rk; B=field; A=9; A=9*field  (B=field)
    # + (v-1): shift = 9field + v - 1
    p+=['M']                        # B=9field
    p+=['rVR','sVR']                # A=v (peek VR)
    p+=['+']                        # A=v+9field
    p+=['M',('c',1),'W','-']        # B=v+9field;A=1;A=v+9field,B=1; A=shift
    # base=1<<shift
    p+=['M',('c',1),'{']            # B=shift;A=1;A=1<<shift=base
    # rk from stashed idx
    p+=['sT']                       # T=[idx, base]  (stash base after idx)  -> order idx,base
    # need rk: pop idx
    p+=['rT']                       # A=idx (T=[base])
    p+=['M',('c',5),'W','/']        # A=rk (B=field drop)
    # bitHi = base*rk : base in T
    p+=['M']                        # B=rk
    p+=['rT']                       # A=base (T=[])
    p+=['sT']                       # T=[base] (keep a copy for bitLo)
    p+=['*']                        # A=base*rk=bitHi (B=rk)
    p+=[kind+'Hi']                  # emit bitHi
    # bitLo = base - bitHi
    p+=['M']                        # B=bitHi
    p+=['rT']                       # A=base
    p+=['-']                        # A=base-bitHi=bitLo
    p+=[kind+'Lo']                  # emit bitLo
    return p

def controller():
    p=[]
    # read r,c,v
    p+=['rIN','sIDX']               # IDX=[r]
    p+=['rIN','sIDX']               # IDX=[r,c]
    p+=['rIN','sVR']                # VR=[v]
    # box = 3*(r//3)+(c//3)
    p+=['rIDX','sIDX']              # A=r, push back -> IDX=[c,r]
    p+=['M',('c',3),'W','/']        # A=r//3 (B=r%3)
    p+=['M',('c',3),'*']            # B=r//3;A=3;A=3*(r//3) (B=3)
    p+=['sT']                       # T=[3r3]
    p+=['rIDX','sIDX']              # A=c (IDX was [c,r]->pop c ->[r], push c ->[r,c])
    p+=['M',('c',3),'W','/']        # A=c//3
    p+=['M','rT','+']               # B=c//3; A=3r3; A=3r3+c//3=box (B=c//3)
    p+=['sIDX']                     # IDX=[r,c,box]
    # emit three kinds
    for kind in ('row','col','box'):
        p+=['rIDX']                 # A=idx
        p+=emit_kind(kind)
    return p

if __name__=='__main__':
    fails=0; ex=[]
    for r in range(9):
        for c in range(9):
            for v in range(1,10):
                out=run(controller(),[r,c,v],RINGS)
                got={k:(out[k][0] if out[k] else None) for k in out}
                want=ref(r,c,v)
                if got!=want:
                    fails+=1
                    if len(ex)<4: ex.append((r,c,v,got,want))
    print('fails',fails,'of',9*9*9)
    for e in ex: print('FAIL',e)
    print('controller op-count:',len([o for o in controller()]))

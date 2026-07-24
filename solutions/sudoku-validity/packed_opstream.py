"""Token-level simulator + program builder for a PACKED single-man sudoku validator.
Rings: MASK (6 packed registers: rowLo,rowHi,colLo,colHi,boxLo,boxHi),
CTX (per-cell context), T1, T2 (scratch). Validates op-stream vs the reference.
"""
import json, collections, random

MASK64=(1<<64)-1
def w64(x):
    x&=MASK64
    if x>=(1<<63): x-=(1<<64)
    return x

def run(prog, inputs, maskinit, maxsteps=2_000_000, trace=False):
    A=B=BP=0
    rings={'MASK':collections.deque(maskinit),'CTX':collections.deque(),
           'VR':collections.deque(),'T1':collections.deque(),'T2':collections.deque()}
    IN=collections.deque(inputs); OUT=[]
    labels={}
    for i,op in enumerate(prog):
        if isinstance(op,tuple) and op[0]=='L': labels[op[1]]=i
    pc=0; steps=0
    while pc<len(prog):
        steps+=1
        if steps>maxsteps: raise RuntimeError('maxsteps')
        op=prog[pc]
        k=op[0] if isinstance(op,tuple) else op
        if trace and k!='L':
            print(f"pc{pc} {op} A={A} B={B} BP={BP} MASK={list(rings['MASK'])} CTX={list(rings['CTX'])} T1={list(rings['T1'])} T2={list(rings['T2'])} OUT={OUT}")
        if k=='L': pc+=1; continue
        elif k=='c': A=op[1]
        elif k=='M': B=A
        elif k=='W': A,B=B,A
        elif k=='b': BP=A
        elif k=='m': BP=w64(BP-1)
        elif k=='+': A=w64(A+B)
        elif k=='-': A=w64(A-B)
        elif k=='*': A=w64(A*B)
        elif k=='N': A=w64(-A)
        elif k=='&': A=w64(A&B)
        elif k=='|': A=w64(A|B)
        elif k=='~': A=w64(A^B)
        elif k=='{': A=w64(A<<B) if 0<=B<=63 else 0
        elif k=='}': A=w64(A>>B) if B>=0 else (0 if A>=0 else -1)
        elif k=='/':
            if B==0: d=A; A=0; B=d
            else:
                q=A//B; r=A-q*B; A=w64(q); B=w64(r)
        elif k=='%': A=0 if B==0 else w64(A-(A//B)*B)
        elif k[0]=='s' and k[1:] in rings: rings[k[1:]].append(A)
        elif k[0]=='r' and k[1:] in rings:
            dq=rings[k[1:]]
            if not dq: raise RuntimeError(f'{k} empty (block) at pc{pc}')
            A=dq.popleft()
        elif k=='rIN':
            if not IN: return OUT,'input_exhausted'
            A=IN.popleft()
        elif k=='sOUT': OUT.append(A)
        elif k=='jmp': pc=labels[op[1]]; continue
        elif k=='brA': pc=labels[op[1] if A<0 else op[2] if A==0 else op[3]]; continue
        elif k=='brBP': pc=labels[op[1] if BP>0 else op[2]]; continue
        elif k=='H': return OUT,'halt'
        else: raise RuntimeError('badop '+repr(op))
        pc+=1
    return OUT,'end'

# ---------------- program builder ----------------
_uid=[0]
def U(s):
    _uid[0]+=1; return f"{s}{_uid[0]}"

def SUBK(k): return ['sT1',('c',k),'M','rT1','-']      # A = A-k
def DIVK(k): return ['sT1',('c',k),'M','rT1','/']      # A=A//k, B=A%k
def MULK(k): return ['M',('c',k),'*']                   # A = k*A  (needs A=x -> A=k*x)

def PEEK(i,size):
    ops=[]
    for j in range(size):
        ops.append('rCTX')
        if j==i: ops.append('sT1')
        ops.append('sCTX')
    ops.append('rT1')
    return ops

def build():
    # Fully straight-line: no reconverging branches. Each of the 6 register checks
    # tests (reg & bit); on dup (A>0) it turns off to the shared SINK (out 0, halt);
    # on ok (A==0) it continues straight (inline set + writeback). Only control edges:
    # 6 dup->SINK turn-offs + one loop-back jmp START. bitLo/bitHi arithmetic picks
    # which register of a family's pair holds the value (no LO/HI branch).
    p=[]
    p.append(('L','START'))
    p+=['rIN','sCTX','rIN','sCTX']                     # CTX=[r,c]
    p+=['rIN','sVR']                                   # VR=[v]
    # box = 3*(r//3) + c//3
    p+=PEEK(0,2)                                       # A=r
    p+=DIVK(3); p+=MULK(3); p+=['sT2']                 # T2=[3*(r//3)]
    p+=PEEK(1,2)                                       # A=c
    p+=DIVK(3); p+=['M','rT2','+']                     # A=3r3+c//3=box
    p+=['sCTX']                                        # CTX=[r,c,box]
    for fam in ('ROW','COL','BOX'):
        p+=_family(fam)                                # consumes one CTX (idx), peeks VR (v)
    # all six checks ok -> output 1, clear VR, loop (CTX already drained by families)
    p+=[('c',1),'sOUT']
    p+=['rVR',('jmp','START')]
    # shared sink
    p+=[('L','SINK'),('c',0),'sOUT','H']
    return p

def _family(fam):
    # 5 rings (MASK,CTX,VR,T1,T2). idx consumed destructively from CTX (r,c,box in
    # order); v peeked from the 1-slot VR ring. 9*field kept in B across the v-peek.
    LOK=U(fam+'_lok'); HOK=U(fam+'_hok')
    p=[]
    p+=['rCTX']                 # A=idx  (destructive: r, then c, then box)
    p+=DIVK(5)                  # A=rk(idx//5), B=field(idx%5)
    p+=['sT2']                  # T2=[rk]
    p+=['W']                    # A=field, B=rk
    p+=MULK(9)                  # A=9*field  (B clobbered)
    p+=['M']                    # B=9*field
    p+=['rVR','sVR']            # A=v (peek 1-slot VR; B=9field preserved)
    p+=['+']                    # A=v+9field
    p+=['M',('c',1),'W','-']    # B=v+9field;A=1;A=v+9field,B=1;A=v+9field-1=bitpos
    p+=['M',('c',1),'{']        # A=bit=1<<bitpos
    # bitLo=bit*(1-rk), bitHi=bit*rk :
    p+=['M','rT2','*']          # B=bit; A=rk; A=bitHi=rk*bit  (B=bit)
    p+=['sT2']                  # T2=[bitHi]
    p+=['W','-']                # A=bit,B=bitHi; A=bit-bitHi=bitLo
    # --- Lo check/set --- (A=bitLo)
    p+=['M','rMASK','sT1','&']  # B=bitLo; A=Lo; T1=[Lo]; A=Lo&bitLo
    p+=[('brA','SINK',LOK,'SINK')]       # A>0 dup->SINK ; A==0 ok->straight
    p+=[('L',LOK),'rT1','|','sMASK']     # A=Lo; A=Lo|bitLo; write back
    # --- Hi check/set --- (bitHi in T2)
    p+=['rT2','M','rMASK','sT1','&']     # A=bitHi;B=bitHi;A=Hi;T1=[Hi];A=Hi&bitHi
    p+=[('brA','SINK',HOK,'SINK')]
    p+=[('L',HOK),'rT1','|','sMASK']
    return p

def finalize(prog):
    return prog

def ref(rounds):
    row=[0]*9;col=[0]*9;box=[0]*9;outs=[]
    for r,c,v in rounds:
        b=3*(r//3)+(c//3); bit=1<<v
        if (row[r]&bit) or (col[c]&bit) or (box[b]&bit):
            outs.append(0); break
        row[r]|=bit;col[c]|=bit;box[b]|=bit;outs.append(1)
    return outs

def flat_inputs(rounds):
    out=[]
    for r,c,v in rounds: out+= [r,c,v]
    return out

def test():
    prog=finalize(build())
    J=json.load(open('/Users/visenbaev/icfpc26/tests/sudoku-validity.json'))
    maskinit=[0,0,0,0,0,0]
    npass=0; ntot=0
    for case in J['publicTestData']:
        rounds=[tuple(int(x) for x in rd['in']) for rd in case['rounds']]
        exp=ref(rounds)
        # feed only inputs up to and including the failing round (sim reads greedily)
        ins=flat_inputs(rounds)
        got,why=run(prog,ins,maskinit)
        ntot+=1
        ok = got==exp
        npass+= ok
        print(f"{case['name']:30s} {'OK' if ok else 'FAIL'} got={got} exp={exp} why={why}")
    # random generalization
    rng=random.Random(1); rfail=0
    for t in range(300):
        # build a random partial-valid-then-maybe-dup sequence
        rounds=_rand_case(rng)
        exp=ref(rounds); ins=flat_inputs(rounds)
        got,why=run(prog,ins,maskinit)
        if got!=exp:
            rfail+=1
            if rfail<=3: print("RANDFAIL",rounds,"got",got,"exp",exp)
    print(f"public {npass}/{ntot} ; random fails {rfail}/300")

def _rand_case(rng):
    # random cells, may or may not dup; stop after a dup naturally handled by ref
    cells=[(r,c,rng.randint(1,9)) for r in range(9) for c in range(9)]
    rng.shuffle(cells)
    n=rng.randint(1,81)
    return cells[:n]

if __name__=='__main__':
    test()

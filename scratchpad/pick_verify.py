import sys, os, random, json
sys.path.insert(0,"solutions/plotter"); sys.path.insert(0,"tools")
import dsl2, dsl
import littleman as lm

# ---- correctness sim (layout-independent op interpreter, like verify_gate) ----
MASK=(1<<64)-1
def s64(v):
    v&=MASK; return v-(1<<64) if v&(1<<63) else v
def asr(a,b):
    if b<0: return 0
    if b>63: return -1 if a<0 else 0
    return a>>b

def run(rounds, INIT, SETUP, BODY):
    from collections import deque
    belt=deque(); A=B=BP=0; cmd=deque(); frames=[]; buf=[0]*768; cur=0; inp=deque()
    def ex(ops):
        nonlocal A,B,BP,cur
        for op in ops:
            if op=='ri': A=inp.popleft()
            elif op=='r': A=belt.popleft()
            elif op=='s': belt.append(A)
            elif op=='PA': cmd.append(s64(A+1))
            elif op=='PD': cmd.append(A)
            elif isinstance(op,tuple): A=s64(op[1])
            elif isinstance(op,str) and len(op)==1 and op.isdigit(): A=int(op)
            elif op=='M': B=A
            elif op=='W': A,B=B,A
            elif op=='b': BP=A
            elif op=='m': BP=s64(BP-1)
            elif op=='+': A=s64(A+B)
            elif op=='-': A=s64(A-B)
            elif op=='*': A=s64(A*B)
            elif op=='N': A=s64(-A)
            elif op=='&': A=s64(A&B)
            elif op=='}': A=asr(A,B)
            elif op=='{': A=s64(A<<B) if 0<=B<=63 else 0
            else: raise ValueError("bad op %r"%(op,))
    def drive():
        nonlocal cur,buf
        while cmd:
            v=cmd.popleft()
            if v<0: frames.append(list(buf)); buf=[0]*768; cur=0
            else:
                cur=v-1; c=cmd.popleft()
                if 0<=cur<768: buf[cur]=c%16
                cur+=1
    ex(INIT)
    for r in rounds:
        inp.extend(r); ex(SETUP)
        while True:
            ex(BODY); BP=s64(BP-1)
            if BP>0: continue
            break
        cmd.append(-1); drive()
    return frames

spec=json.load(open(os.path.join(lm.REPO,"tests","plotter.json")))
hexc="0123456789abcdef"
def rows(buf): return ["".join(hexc[buf[y*32+x]] for x in range(32)) for y in range(24)]
def verify():
    ok=True
    for tc in spec["publicTestData"]:
        rnds=[tuple(map(int,r["in"])) for r in tc["rounds"]]
        exp=[r["frames"][0] for r in tc["rounds"]]
        got=[rows(b) for b in run(rnds, dsl2.build_init(), dsl2.build_setup(), dsl2.build_body())]
        k=got==exp; ok&=k
        if not k: print("  FAIL",tc["name"])
    return ok

# candidate orders from optimizer
cands={
 "body6":['cy','dy','x0','cx','addr','sy32','y0','err','x1','y1','sx','t2','e2','t','dx'],
 "body3":['x0','cx','addr','sy32','err','y0','x1','sx','y1','t2','e2','t','dx','cy','dy'],
 "boxeq":['sx','cx','x0','addr','sy32','y0','x1','err','y1','t2','t','e2','dy','dx','cy'],
 "orig":list(dsl.LAYOUT),
}
for name,order in cands.items():
    dsl2.set_layout(order)
    dsl2.USE_BACKTICK_SIGN=True
    I,S,B=dsl2.build_init(),dsl2.build_setup(),dsl2.build_body()
    okbt=verify()
    dsl2.USE_BACKTICK_SIGN=False
    Sd,Bd=dsl2.build_setup(),dsl2.build_body()
    okd=verify()
    print(f"{name:6s} backtick: init{len(I)} setup{len(S)} body{len(B)} total{len(I)+len(S)+len(B)} frames_ok={okbt} | despine: setup{len(Sd)} body{len(Bd)} tot{len(I)+len(Sd)+len(Bd)} ok={okd}")

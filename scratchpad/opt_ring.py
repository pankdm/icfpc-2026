import sys, os, random, itertools
sys.path.insert(0, "solutions/plotter")
sys.path.insert(0, "tools")
import dsl

LAYOUT = dsl.LAYOUT  # current order

# Recorder to extract target-name sequences for setup and body
class RecC:
    def __init__(self): self.ring=list(LAYOUT); self.ops=[]; self.seq=[]
    def e(self,*o): self.ops.extend(o)
    def rot(self): self.e('r','s'); self.ring.append(self.ring.pop(0))
    def tf(self,n):
        while self.ring[0]!=n: self.rot()
        self.seq.append(n)
    def readA(self,n): self.tf(n); self.e('r','s'); self.ring.append(self.ring.pop(0))
    def writeA(self,n): self.e('M'); self.tf(n); self.e('r','W','s'); self.ring.append(self.ring.pop(0))
    def setB(self,k): self.e('M',('#',k),'W')
    def inc(self): self.e('M',('#',1),'+')
    def sign(self): self.setB(63); self.e('}')
    def binop(self,X,Y,o): self.readA(Y); self.e('M'); self.readA(X); self.e(o)

insts=[]
class TrackC(RecC):
    def __init__(self): super().__init__(); insts.append(self)
dsl._C = TrackC
dsl.build_setup(); setup_seq=insts[-1].seq
dsl.build_body();  body_seq=insts[-1].seq

slots=list(LAYOUT)
assert set(setup_seq)|set(body_seq) <= set(slots)

def rot_cost(seq, pos, home):
    # front starts at home (position pos[home]); each target t: cost=(pos[t]-front)%15; front=pos[t]+1
    tot=0; front=pos[home]
    for t in seq:
        c=(pos[t]-front)%15
        tot+=c; front=(pos[t]+1)%15
    return tot

def total_cost(order, wbody, wsetup):
    pos={n:i for i,n in enumerate(order)}
    home=order[0]  # must be addr
    return wbody*rot_cost(body_seq,pos,home)+wsetup*rot_cost(setup_seq,pos,home)

def body_only(order):
    pos={n:i for i,n in enumerate(order)}
    return rot_cost(body_seq,pos,order[0])
def setup_only(order):
    pos={n:i for i,n in enumerate(order)}
    return rot_cost(setup_seq,pos,order[0])

# current
print("current LAYOUT body_rot=",body_only(LAYOUT)," setup_rot=",setup_only(LAYOUT))

def anneal(wbody,wsetup,iters=400000):
    # addr fixed at index 0
    rest=[s for s in slots if s!='addr']
    best=None;bestc=1e18
    for restart in range(8):
        order=['addr']+random.sample(rest,len(rest))
        cur=total_cost(order,wbody,wsetup)
        T=8.0
        for it in range(iters//8):
            i,j=random.sample(range(1,15),2)
            order[i],order[j]=order[j],order[i]
            nc=total_cost(order,wbody,wsetup)
            if nc<=cur or random.random()<pow(2.718,-(nc-cur)/max(T,1e-3)):
                cur=nc
            else:
                order[i],order[j]=order[j],order[i]
            T*=0.99995
            if cur<bestc: bestc=cur; best=list(order)
    return best,bestc

random.seed(1)
for (wb,ws,label) in [(1,1,"box-equal"),(4,1,"body-heavy"),(10,1,"body-dom")]:
    b,c=anneal(wb,ws)
    print(f"\n[{label}] w=({wb},{ws}) cost={c}")
    print("  order:",b)
    print(f"  body_rot={body_only(b)} setup_rot={setup_only(b)}  (total ops delta body {2*(body_only(dsl.LAYOUT)-body_only(b))}, setup {2*(setup_only(dsl.LAYOUT)-setup_only(b))})")

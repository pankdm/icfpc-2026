import sys, os, random
sys.path.insert(0, "solutions/plotter"); sys.path.insert(0, "tools")
import dsl2

# recorder wrapping dsl2._C to capture tf-target sequence
targets={'setup':[], 'body':[]}
def make_rec(bucket):
    class R(dsl2._C):
        def tf(self,n):
            while self.ring[0]!=n: self.rot()
            targets[bucket].append(n)
    return R

# extract with current LAYOUT
dsl2.set_layout(dsl2.LAYOUT)
Rs=make_rec('setup'); dsl2._C=Rs; dsl2.build_setup()
Rb=make_rec('body');  dsl2._C=Rb; dsl2.build_body()
setup_seq=[t for t in targets['setup']]
body_seq=[t for t in targets['body']]
# note: last tf(home) target = LAYOUT[0] name; it's included. Good.
print("fused body accesses:",len(body_seq),"setup:",len(setup_seq))

slots=list(dsl2.LAYOUT)
def rot_cost(seq,order):
    pos={n:i for i,n in enumerate(order)}; home=order[0]
    tot=0; front=0
    for t in seq:
        tot+=(pos[t]-front)%15; front=(pos[t]+1)%15
    return tot
# The last element of each seq is home (tf(LAYOUT[0])). But when we permute order,
# home changes, so the final tf target must track order[0]. Rebuild seq w/o the
# trailing home, and append order[0] dynamically.
def strip_home(seq, home):
    return seq[:-1] if seq and seq[-1]==home else seq
sh=strip_home(setup_seq, slots[0]); bh=strip_home(body_seq, slots[0])
def cost(order,wb,ws):
    return wb*rot_cost(bh+[order[0]],order)+ws*rot_cost(sh+[order[0]],order)
def bo(order): return rot_cost(bh+[order[0]],order)
def so(order): return rot_cost(sh+[order[0]],order)
print("current fused: body_rot",bo(slots),"setup_rot",so(slots))

def anneal(wb,ws,iters=1500000):
    best=None;bc=1e18
    for r in range(12):
        order=random.sample(slots,15)
        cur=cost(order,wb,ws);T=6.0
        for it in range(iters//12):
            i,j=random.sample(range(15),2)
            order[i],order[j]=order[j],order[i]
            nc=cost(order,wb,ws)
            if nc<=cur or random.random()<2.718**(-(nc-cur)/max(T,1e-3)): cur=nc
            else: order[i],order[j]=order[j],order[i]
            T*=0.99998
            if cur<bc: bc=cur;best=list(order)
    return best,bc
random.seed(7)
for wb,ws,lab in [(1,1,"box-equal"),(3,1,"body3"),(6,1,"body6")]:
    b,c=anneal(wb,ws)
    print(f"[{lab}] cost={c} body_rot={bo(b)} setup_rot={so(b)}")
    print("  order=",b)

import sys, random
sys.path.insert(0,"solutions/plotter"); sys.path.insert(0,"tools")
import dsl2
targets={'s':[], 'b':[]}
def mk(bk):
    class R(dsl2._C):
        def tf(self,n):
            while self.ring[0]!=n: self.rot()
            targets[bk].append(n)
    return R
dsl2.set_layout(dsl2.LAYOUT)
dsl2._C=mk('s'); dsl2.build_setup()
dsl2._C=mk('b'); dsl2.build_body()
slots=list(dsl2.LAYOUT)
sh=targets['s'][:-1]; bh=targets['b'][:-1]
def rc(seq,order):
    pos={n:i for i,n in enumerate(order)}; tot=0; front=0
    for t in seq: tot+=(pos[t]-front)%15; front=(pos[t]+1)%15
    return tot
def bo(o): return rc(bh+[o[0]],o)
def so(o): return rc(sh+[o[0]],o)
# collect distinct orders achieving min body_rot, tie-break low setup_rot
random.seed(3); found={}
for _ in range(60):
    o=random.sample(slots,15); cur=bo(o)+so(o)*0.01
    for it in range(60000):
        i,j=random.sample(range(15),2); o[i],o[j]=o[j],o[i]
        nc=bo(o)+so(o)*0.01
        if nc<=cur: cur=nc
        else: o[i],o[j]=o[j],o[i]
    key=(bo(o),so(o))
    found[tuple(o)]=key
best=sorted(found.items(), key=lambda kv:(kv[1][0],kv[1][1]))[:6]
for o,(b,s) in best:
    print(f"body={b} setup={s} {list(o)}")

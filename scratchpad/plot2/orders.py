"""Which cyclic order of pre's surviving fifo minimises the branch-block width?"""
import sys, itertools
sys.path.insert(0,"solutions/plotter")
import swar_setup as SS

VALS=["adx","ady","sx","vy","addr0"]
res=[]
for perm in itertools.permutations(VALS[1:]):
    order=[VALS[0]]+list(perm)          # fix adx first (cyclic canonical)
    costs={}
    ok=True
    for name,mp in (("x",SS.MAP_X),("y",SS.MAP_Y)):
        e=SS.Emit(3,4,20,19)
        e.q=[(n,i+1) for i,n in enumerate(order)]
        e.toks=[]
        try:
            SS.converge(e,mp,SS.TARGET)
        except AssertionError:
            ok=False; break
        costs[name]=len(e.toks)
    if ok:
        res.append((max(costs.values()),costs["x"]+costs["y"],order,costs))
res.sort()
for r in res[:8]:
    print(r)

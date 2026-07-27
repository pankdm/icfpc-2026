import sys, os
from collections import Counter
sys.path.insert(0, "solutions/plotter")
import swar_setup as SS
pre,px,py,tb,tf = SS.segments()
names=["pre","px","py","tail_body","tail_fin"]
tot=0
for n,seg in zip(names,[pre,px,py,tb,tf]):
    print(n, len(seg), "".join(t[0] for t in seg))
    tot+=len(seg)
print("total(one branch)", len(pre)+len(px)+len(tb)+len(tf))
c=Counter(t[0] for t in pre+px+tb+tf)
print(sorted(c.items(), key=lambda kv:-kv[1]))

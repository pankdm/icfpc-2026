"""Ceiling on the return-pipe length for the 5-row main room, ignoring the other
three pipes (they only need 2 cells each)."""
import sys
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive5 as D
c=Counter(); best=0
for mgrid, arole, udir, rooms in D.plans():
    p=S.Plan(rooms); c['plans']+=1
    asg=D.assignments(p,arole,udir,12)
    if not asg: continue
    c['asg']+=1
    hit=False
    for (rs,rsd,os_,osd,rd,rdd,idst,idd) in asg:
        for (rls,rlsd) in p.srcs('relay'):
            if rls in (rs,os_,idst,rd): continue
            b=S.route_long(p,rls,rlsd,rd,rdd,{rs,os_,idst},2,30,budget=150000)
            if b:
                hit=True
                if len(b[0])>best:
                    best=len(b[0]); print('ret',best,rooms,flush=True)
    if hit: c['ret_any']+=1
print(dict(c),'best',best)

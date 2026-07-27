import sys
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive5 as D
c=Counter()
for mgrid, arole, udir, rooms in D.plans():
    p=S.Plan(rooms); c['plans']+=1
    if len(p.free)<21: continue
    c['free']+=1
    # stage a: s-bindings only
    msrc=p.srcs('main'); mdst=p.dsts('main')
    sok=[]
    for (rs,rsd) in msrc:
        for (o,od) in msrc:
            if o==rs: continue
            cd=[('relay',rs),('outp',o)]
            if S.nearer(cd,arole['s_less'])!='relay': continue
            if S.nearer(cd,arole['s_gtr'])!='relay': continue
            if S.nearer(cd,arole['s_exit'])!='outp': continue
            sok.append((rs,rsd,o,od))
    if sok: c['s_ok']+=1
    else: continue
    # stage b: U direction
    ud=[(i,idd) for (i,idd) in mdst if idd==udir]
    if ud: c['udir_ok']+=1
    else: continue
    asg=D.assignments(p,arole,udir,5)
    if asg: c['asg_ok']+=1
    else: continue
    # stage c: main->relay len 2
    got=False
    for (rs,rsd,o,od,rd,rdd,idst,idd) in asg:
        for (rld,rldd) in p.dsts('relay'):
            if rld in (rd,idst,rs,o): continue
            if S.route(p,rs,rsd,rld,rldd,{rd,idst,o},2,2,want=1,budget=8000):
                got=True; break
        if got: break
    if got: c['relay2_ok']+=1
print(dict(c))

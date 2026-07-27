import sys
from collections import Counter
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive5 as D
c=Counter(); bestret=0
for mgrid, arole, udir, rooms in D.plans():
    p=S.Plan(rooms); c['plans']+=1
    asg=D.assignments(p,arole,udir,20)
    if not asg: continue
    c['asg']+=1
    st=0
    for (rs,rsd,os_,osd,rd,rdd,idst,idd) in asg:
        reserved={rd,idst}
        for (rld,rldd) in p.dsts('relay'):
            if rld in reserved or rld in (rs,os_): continue
            for p2 in S.route(p,rs,rsd,rld,rldd,reserved|{os_},2,5,want=2,budget=15000):
                st=max(st,1); u2=set(p2[0])
                for (od,odd) in p.dsts('outp'):
                    if od in u2 or od in reserved or od==os_: continue
                    for p3 in S.route(p,os_,osd,od,odd,u2|reserved,2,10,want=2,budget=20000):
                        st=max(st,2); u3=u2|set(p3[0])
                        for (isr,isd) in p.srcs('inp'):
                            if isr in u3 or isr==rd: continue
                            for p4 in S.route(p,isr,isd,idst,idd,u3|{rd},2,14,want=2,budget=20000):
                                st=max(st,3); u4=u3|set(p4[0])
                                for (rls,rlsd) in p.srcs('relay'):
                                    if rls in u4 or rls==rd: continue
                                    b=S.route_long(p,rls,rlsd,rd,rdd,u4,2,30,budget=80000)
                                    if b:
                                        st=max(st,4)
                                        if len(b[0])>bestret:
                                            bestret=len(b[0]); print('ret',bestret,rooms,flush=True)
    c['stage%d'%st]+=1
print(dict(c),'bestret',bestret)

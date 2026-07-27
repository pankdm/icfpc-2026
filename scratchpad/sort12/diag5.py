import os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath('scratchpad/sort12/x'))
sys.path.insert(0, 'scratchpad/sort12')
import search as S, drive
c = Counter(); seen=set()
for mgrid, arole, rooms in drive.plans():
    k = tuple(sorted(rooms.items()))
    if k in seen: continue
    seen.add(k)
    p = S.Plan(rooms)
    c['plans'] += 1
    c['inp_src>0'] += len(p.srcs('inp')) > 0
    c['outp_dst>0'] += len(p.dsts('outp')) > 0
    c['relay_src>0'] += len(p.srcs('relay')) > 0
    c['relay_dst>0'] += len(p.dsts('relay')) > 0
    c['main_src>0'] += len(p.srcs('main')) > 0
    # can the input pipe reach main at all, ignoring other pipes?
    ok = False
    for (isr, isd) in p.srcs('inp'):
        for (idst, idd) in p.dsts('main'):
            if S.route(p, isr, isd, idst, idd, set(), 2, 22, want=1, budget=30000):
                ok = True; break
        if ok: break
    c['inp_route'] += ok
print(dict(c))

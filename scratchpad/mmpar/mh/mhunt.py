import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
BASE=[l for l in open('scratchpad/brk4/m_col5_1cell.man').read().split('\n')]
def build(moves, path):
    g=[list(l.ljust(20)) for l in BASE]
    for (x,y,ch) in moves: g[y][x]=ch
    open(path,'w').write('\n'.join(''.join(r).rstrip() for r in g).rstrip('\n')+'\n')
def grade(a):
    name,moves=a
    p=f'/tmp/mh_{name}.man'; build(moves,p)
    try:
        r=subprocess.run(['python3','tools/grade_fast.py','brackets',p],capture_output=True,text=True,timeout=200)
        d=json.loads(r.stdout.strip().split('\n')[-1])
    except Exception as e: return name,None,str(e)[:30],p
    return name,(d['score'] if d.get('passed')==d.get('total') else None),f"{d.get('passed')}/{d.get('total')}",p
cands=[('del',[(5,4,' ')])]
# free slots (excluding col 5)
for x in range(1,10):
    if x==5: continue
    for y in range(1,10):
        if BASE[y][x]==' ': cands.append((f'p{x}_{y}',[(5,4,' '),(x,y,'M')]))
# removable ^ cells named by the coordinator
for (x,y) in ((8,3),(8,4),(8,5),(7,4)):
    cands.append((f'c{x}_{y}',[(5,4,' '),(x,y,'M')]))
print(len(cands),'candidates',flush=True)
with ThreadPoolExecutor(max_workers=12) as ex:
    for f in as_completed([ex.submit(grade,c) for c in cands]):
        n,sc,why,p=f.result()
        if sc: print('PASS',n,sc,p,flush=True)

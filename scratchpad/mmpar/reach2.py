"""Sweep build_dense knobs looking for a variant whose IN/OUT ports can escape
the block (needed to reuse the engine as a black box for P=2)."""
import os, sys
from collections import deque
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def check():
    import importlib
    if 'engine' in sys.modules:
        del sys.modules['engine']
    import engine
    g, _, _ = engine.build(ports=True)
    occ = {c for c, ch in g.c.items() if ch != ' '}
    blocked = set(occ)
    for (x, y) in occ:
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            blocked.add((x+dx, y+dy))
    xs=[c[0] for c in occ]; ys=[c[1] for c in occ]
    lo=(min(xs),min(ys),max(xs),max(ys))
    res={}
    for name, port in engine.PORTS.items():
        seen=set(); q=deque()
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            n=(port[0]+dx, port[1]+dy)
            if n not in occ: seen.add(n); q.append(n)
        out=False
        while q:
            c=q.popleft()
            if not (lo[0]<=c[0]<=lo[2] and lo[1]<=c[1]<=lo[3]):
                out=True; break
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                n=(c[0]+dx,c[1]+dy)
                if n in seen or n in blocked: continue
                if not (lo[0]-15<=n[0]<=lo[2]+15 and lo[1]-15<=n[1]<=lo[3]+15): continue
                seen.add(n); q.append(n)
        res[name]=out
    return res, g.footprint()

for dx in (0, 2, 4, 6):
    for dy in (0, 2, 4, 8):
        for ppx, ctlx in ((0,0), (-8,-8), (-16,-16)):
            os.environ.update(DX=str(dx), DY=str(dy), PPX=str(ppx), CTLX=str(ctlx))
            try:
                res, fp = check()
            except Exception as e:
                print(f"DX={dx} DY={dy} PPX={ppx} CTLX={ctlx}: FAIL {str(e)[:60]}")
                continue
            print(f"DX={dx} DY={dy} PPX={ppx} CTLX={ctlx}: {res} fp={fp}")

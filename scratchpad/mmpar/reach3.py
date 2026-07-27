"""Port escape from the dense engine, with the CORRECT clearance rule:
a pipe may hug a foreign ROOM WALL (nearest-pipe compares only terminal cells);
it may only not touch another PIPE (two adjacent pipes parse as one).
"""
import os, sys
from collections import deque
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'tools'))
import engine
import router as RT

MODES = ('no-halo', 'pipe-halo-only', 'full-halo')

def run(mode):
    if 'engine' in sys.modules:
        del sys.modules['engine']
    import engine as E
    g, _, _ = E.build(ports=True)
    occ = {c for c, ch in g.c.items() if ch != ' '}
    # classify: cells the router marked PIPE vs everything else (rooms/ops)
    typ = g.R.grid.typ
    pipes = {c for c in occ if typ.get(c) == RT.PIPE}
    blocked = set(occ)
    if mode != 'no-halo':
        src = pipes if mode == 'pipe-halo-only' else occ
        for (x, y) in src:
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                blocked.add((x+dx, y+dy))
    xs=[c[0] for c in occ]; ys=[c[1] for c in occ]
    lo=(min(xs),min(ys),max(xs),max(ys))
    out={}
    for name, port in E.PORTS.items():
        seen=set(); q=deque()
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            n=(port[0]+dx, port[1]+dy)
            if n not in blocked: seen.add(n); q.append(n)
        esc=False
        while q:
            c=q.popleft()
            if not (lo[0]<=c[0]<=lo[2] and lo[1]<=c[1]<=lo[3]): esc=True; break
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                n=(c[0]+dx,c[1]+dy)
                if n in seen or n in blocked: continue
                if not (lo[0]-20<=n[0]<=lo[2]+20 and lo[1]-20<=n[1]<=lo[3]+20): continue
                seen.add(n); q.append(n)
        out[name]=(esc, len(seen))
    return out

for m in MODES:
    print(m, run(m))

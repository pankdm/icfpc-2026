import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys, heapq
sys.path.insert(0,_REPO + '/tools')
import littleman as lm

DIRV={'E':(1,0),'W':(-1,0),'N':(0,-1),'S':(0,1)}
ARR={'E':'>','W':'<','N':'^','S':'v'}
PERP={'E':['N','S'],'W':['N','S'],'N':['E','W'],'S':['E','W']}

class Grid:
    def __init__(self):
        self.p=lm.Program(); self.g={}       # exclusive glyph/arrow/bend cells
        self.straight=set()                   # cells used as straight corridor (spaces, shareable)
    def put(self,x,y,ch):
        if (x,y) in self.g and self.g[(x,y)]!=ch:
            raise SystemExit(f"COLLISION {(x,y)}: {self.g[(x,y)]!r} vs {ch!r}")
        if (x,y) in self.straight:
            raise SystemExit(f"GLYPH-ON-CORRIDOR {(x,y)} {ch!r}")
        self.g[(x,y)]=ch; self.p.put(x,y,ch)
    def row(self,x,y,s):
        for i,c in enumerate(s): self.put(x+i,y,c)
    def col(self,x,y,s):
        for i,c in enumerate(s): self.put(x,y+i,c)
    def room(self,*a,**k):
        r=self.p.room(*a,**k)
        # register room glyphs as exclusive
        for (xy,ch) in list(self.p.cells.items()):
            if ch!=' ': self.g.setdefault(xy,ch)
        return r
    def commit_program_cells(self):
        for (xy,ch) in list(self.p.cells.items()):
            if ch!=' ': self.g.setdefault(xy,ch)
    # ---- router ----
    def _straight_ok(self,cell,dirn):
        return cell not in self.g
    def _bend_ok(self,cell):
        return cell not in self.g and cell not in self.straight
    def route(self,start,sdir,goal,gdir,bound=None):
        """Man at `start` (glyph placed) heading sdir; make it arrive at `goal`
        moving gdir. Places arrows at bends; leaves straights as spaces.
        bound=(x0,y0,x1,y1) optional bounding box for search."""
        sx,sy=start; gx,gy=goal
        first=(sx+DIRV[sdir][0], sy+DIRV[sdir][1])
        # state: (cell, incoming-dir). Target = ARRIVE AT goal moving gdir (goal keeps its own glyph).
        if bound is None: bound=(-5,-5,120,120)
        x0,y0,x1,y1=bound
        def inb(c): return x0<=c[0]<=x1 and y0<=c[1]<=y1
        start_state=(first, sdir)
        # dijkstra (cost = #bends*10 + len) to prefer few bends
        pq=[(0,start_state,None)]; best={}; parent={}
        target=(goal,gdir)
        found=False
        while pq:
            cost,(cell,dirn),par=heapq.heappop(pq)
            if (cell,dirn) in best and best[(cell,dirn)]<=cost: continue
            best[(cell,dirn)]=cost; parent[(cell,dirn)]=par
            if (cell,dirn)==target: found=True; break
            # options: continue straight, or turn (bend at this cell)
            # straight:
            if self._straight_ok(cell,dirn) and inb(cell):
                nc=(cell[0]+DIRV[dirn][0],cell[1]+DIRV[dirn][1])
                heapq.heappush(pq,(cost+1,(nc,dirn),(cell,dirn)))
            # turns (bend here):
            if self._bend_ok(cell) and inb(cell):
                for nd in PERP[dirn]:
                    nc=(cell[0]+DIRV[nd][0],cell[1]+DIRV[nd][1])
                    heapq.heappush(pq,(cost+3,(nc,nd),(cell,dirn)))
        if not found:
            raise SystemExit(f"ROUTE FAIL {start}{sdir} -> {goal}{gdir}")
        # reconstruct
        path=[]; st=target
        while st is not None:
            path.append(st); st=parent[st]
        path.reverse()
        # path is list of (cell,dir_incoming). materialize (skip goal: keeps its own glyph):
        for i,(cell,dirn) in enumerate(path):
            if cell==goal: continue
            prevdir = path[i-1][1] if i>0 else sdir
            if dirn!=prevdir:
                self.put(cell[0],cell[1],ARR[dirn])   # bend
            else:
                self.straight.add(cell)
        return path

def dump(g):
    print(g.p.render()); print('fp',g.p.footprint())

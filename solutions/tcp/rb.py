"""Ring-buffer TCP builder helpers."""
import sys; sys.path.insert(0,'tools')
import littleman as lm

DIRS={"E":(1,0),"W":(-1,0),"N":(0,-1),"S":(0,1)}
ARROW={"E":">","W":"<","N":"^","S":"v"}

class B:
    def __init__(s):
        s.p=lm.Program(); s.placed={}
    def C(s,x,y,ch,force=False):
        if (x,y) in s.placed and s.placed[(x,y)]!=ch and not force:
            raise SystemExit(f"COLLISION {(x,y)} {s.placed[(x,y)]!r} vs {ch!r}")
        s.placed[(x,y)]=ch; s.p.put(x,y,ch)
    def mpath(s,pts):
        for i in range(len(pts)-1):
            (x0,y0),(x1,y1)=pts[i],pts[i+1]
            if (x0,y0)==(x1,y1): continue
            dx=(x1>x0)-(x1<x0); dy=(y1>y0)-(y1<y0)
            d='E' if dx>0 else 'W' if dx<0 else 'S' if dy>0 else 'N'
            s.C(x0,y0,ARROW[d])

# Serpentine man cursor. E-rows at y=base,base+2,...; return path on odd rows.
class Man:
    def __init__(s,b,x,y): s.b=b; s.x=x; s.y=y; s.hdg='E'
    def _adv(s):
        dx,dy=DIRS[s.hdg]; s.x+=dx; s.y+=dy
    def op(s,ch):
        """place instruction at current cell (glide row), advance E."""
        s.b.C(s.x,s.y,ch); s._adv(); return s
    def newrow(s):
        """turn down, west to col1, down to next E-row, face E (feeder)."""
        y0=s.y
        s.b.mpath([(s.x,y0),(s.x,y0+1),(1,y0+1),(1,y0+2)])
        s.b.C(1,y0+2,'>'); s.x=2; s.y=y0+2; s.hdg='E'; return s
    def at(s,col,ch):
        """place op at absolute column `col` on an E-row; auto-newrow if behind."""
        if col < s.x: s.newrow()
        while s.x<col: s._adv()   # glide (blank) forward
        return s.op(ch)
    def lit(s,digits):
        """load multi-digit literal via backticks at current position."""
        s.op('`')
        for d in str(digits): s.op(d)
        s.op('`'); return s

import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# Serpentine snake reader. Man weaves down/up columns reading 1 value per column;
# BP counts down from n; d/a: turn(=continue snake) if BP>0, straight(=exit) if BP==0.
# even col j (x=2+j, j even): down.  odd col: up.  4 test columns x=2..5.
# rows: y0 exittop '<' | y1 'v'/'d' | y2 'r'/'m' | y3 'm'/'r' | y4 'a'/'^' | y5 exitbot '<'
def build(ncol=4):
    p = lm.Program(); placed={}
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch: raise SystemExit(f"COLL {(x,y)} {placed[(x,y)]} vs {ch}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    base=2
    y0,y1,y2,y3,y4,y5 = 0,1,2,3,4,5
    for j in range(ncol):
        x=base+j
        even = (j%2==0)
        if even:  # down pass
            C(x,y1,'v'); C(x,y2,'r'); C(x,y3,'m'); C(x,y4,'a')
        else:     # up pass
            C(x,y4,'^'); C(x,y3,'r'); C(x,y2,'m'); C(x,y1,'d')
    # exit lanes westward (over the columns), halt one cell further west
    for x in range(base, base+ncol):
        C(x,y0,'<'); C(x,y5,'<')
    C(base-1,y0,'H'); C(base-1,y5,'H')
    # preamble on row y1: (base-3)=@, (base-2)=r(read n), (base-1)=b(BP=n), then (base)=v already
    C(base-3,y1,'@'); C(base-2,y1,'r'); C(base-1,y1,'b')
    # room enclosing everything (cols base-4 .. base+ncol, rows y0-1 .. y5+1)
    x0=base-4; x1=base+ncol+1; ry0=y0-2; ry1=y5+2
    p.room(x0, ry0, x1-x0+1, ry1-ry0+1)
    # input pipe into room top, attach near col reads. Put I above, pipe down to a top-wall col.
    ax = base+1   # attach column (interior)
    p.input_room(ax-1, ry0-5)            # I bottom wall at ry0-3
    p.pipe([(ax, ry0-2), (ax, ry0-1)])   # 2-cell gap; end forward = main top wall ry0
    return p, placed

if __name__=='__main__':
    ncol=int(sys.argv[1]) if len(sys.argv)>1 else 4
    p,_=build(ncol)
    p.save(_REPO + '/scratchpad/snake.man')
    print(p.render())

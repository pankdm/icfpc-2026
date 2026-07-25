import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
import littleman as lm

# Serpentine reader depositing each value into its OWN adjacent (1-col) lane pipe.
# Columns adjacent. Per col (even=down): rT 'v', rA 'r', rB 's', rC 'm', rD 'a'
#                    (odd=up):          rD '^', rC 'r', rB 's', rA 'm', rT 'd'
# Lanes: reader south wall col x -> down into collector room north wall.
def build(ncol=16):
    p = lm.Program(); placed={}
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch: raise SystemExit(f"COLL {(x,y)} {placed[(x,y)]} vs {ch}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    base=3
    # rows
    rT,rA,rB,rC,rD = 2,3,4,5,6
    exN, exS = 1, 7           # north exit lane (row1), south exit lane (row7)
    for j in range(ncol):
        x=base+j
        if j%2==0:
            C(x,rT,'v'); C(x,rA,'r'); C(x,rB,'s'); C(x,rC,'m'); C(x,rD,'a')
        else:
            C(x,rD,'^'); C(x,rC,'r'); C(x,rB,'s'); C(x,rA,'m'); C(x,rT,'d')
    # exit lanes westward to H (just stop after reading, for the (c) probe)
    for x in range(base, base+ncol):
        C(x,exN,'<'); C(x,exS,'<')
    C(base-1,exN,'H'); C(base-1,exS,'H')
    # preamble on rT: @ then r(n) b(BP=n) then col0 'v'
    C(base-3,rT,'@'); C(base-2,rT,'r'); C(base-1,rT,'b')
    # reader room
    x0=base-4; x1=base+ncol; ry0=exN-2; ry1=exS+1
    p.room(x0,ry0,x1-x0+1,ry1-ry0+1)
    # input pipe into reader top
    ax=base+1
    p.input_room(ax-1, ry0-5)
    p.pipe([(ax, ry0-2),(ax, ry0-1)])
    # collector room below; lanes from reader south wall to collector north wall
    cN = ry1 + 3          # collector north wall row
    p.room(x0, cN, x1-x0+1, 4)
    for j in range(ncol):
        x=base+j
        p.pipe([(x, ry1+1),(x, cN-1)])   # 2-cell lane; forward into collector top wall cN
    return p, placed

if __name__=='__main__':
    ncol=int(sys.argv[1]) if len(sys.argv)>1 else 16
    p,_=build(ncol)
    p.save('/Users/visenbaev/icfpc26/scratchpad/snake2.man')
    print(p.render())

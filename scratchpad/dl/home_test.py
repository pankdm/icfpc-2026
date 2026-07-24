import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

# Collector homing test: man receives n via an incoming pipe, sets A=n-1,B=1,
# then a down-staircase advancing (n-1) lanes east. Verify exit column = 2n+2 (lane n-1 col),
# lanes assumed at cols 4+2i.
# Staircase unit: X at (c,r) [heading east] -> A>0 south; below it '>' at (c,r+1); '-' at (c+1,r+1); next X at (c+2,r+1).
# We must generate enough stairs for K up to 15.

def build():
    p = lm.Program(); P = p.put
    H = 40
    W = 60
    p.room(0,0,W,H)
    # input room feeding n
    p.input_room(0,-5); p.pipe([(1,-2),(1,-1)])  # feeds into room top col1
    # man starts at (1,1) heading east; read n. First set B=1 (1 M), then r (A=n), then - (A=n-1)
    # place: @ 1 M r - then start staircase at col 6? We'll route: after '-', man heading east.
    P(1,1,"@"); P(2,1,"1"); P(3,1,"M"); P(4,1,"r"); P(5,1,"-")
    # now heading east at col6 row1. Start staircase with startcol so exit col = 2n+2.
    # staircase advances 2 cols east per stair (K stairs). If first X at col Xc0, exit col = Xc0 + 2K.
    # We want exit col = 2n+2 = 2(K+1)+2 = 2K+4. So Xc0 = 2K+4 - 2K = 4. First X at col4? but man is at col6.
    # Let's just place first X at col 6 and measure; we compute exit=6+2K and map later.
    # Build staircase: X at (6+2j, 1+j) for j=0..; '>' at (col,row+1) under each X; '-' at (col+1,row+1)
    K = 16
    for j in range(K+2):
        xc = 6 + 2*j; xr = 1 + j
        P(xc, xr, "X")
        P(xc, xr+1, ">")
        P(xc+1, xr+1, "-")
    # add a marker H far away so program can end after man walks off staircase (he'll go east then wall)
    return p

if __name__ == "__main__":
    p = build()
    p.save(os.path.join(os.path.dirname(__file__), "home.man"))
    print(p.render())

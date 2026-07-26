import sys, os, json
import os
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','tools'))
import littleman as lm

def put(p,x,y,ch):
    assert p.get(x,y)==' ', f"overlap {(x,y)} {p.get(x,y)!r} vs {ch!r}"
    p.put(x,y,ch)

def build_driver(p, dvx, dvy, cmd_attach_from, dispw=16, disph=16, swap_value=1):
    DX = dvx + 6
    DY = dvy + 30
    D = p.display(DX, DY, dispw+2, disph+2)
    W,H=16,26
    DR = p.room(dvx, dvy, W, H)
    L,T,Rr,B = DR.ix0,DR.iy0,DR.ix1,DR.iy1
    cBr=L+8; rENTRY=T+13; rSWAP=T+2; rRET=T; rPIX=B
    Ca=cBr-1; Cd=L+2; Cswap=cBr+1; railW=L+1; railR=Rr
    put(p,L,rENTRY,"@"); put(p,railW,rENTRY,">")
    put(p,cBr-1,rENTRY,"r"); put(p,cBr,rENTRY,"X")
    put(p,cBr,rENTRY+1,"M"); put(p,cBr,rENTRY+2,"1"); put(p,cBr,rENTRY+3,"-"); put(p,cBr,rENTRY+4,"N")
    put(p,cBr,rPIX,"<"); put(p,Ca,rPIX,"s"); put(p,Ca-1,rPIX,"r"); put(p,Cd,rPIX,"s"); put(p,railW,rPIX,"^")
    put(p,cBr,rENTRY-1,str(swap_value)); put(p,cBr,rSWAP,">"); put(p,Cswap,rSWAP,"s")
    put(p,railR,rSWAP,"^"); put(p,railR,rRET,"<"); put(p,railW,rRET,"v")
    p.pipe([(Ca,DR.y1+1),(Ca,D.y0-1)])
    dRow=D.iy0+4
    p.pipe([(Cd,DR.y1+1),(Cd,dRow),(D.x0-1,dRow)])
    sBcol=DX+ (dispw//2+1)
    p.pipe([(Cswap,DR.y0-1),(Cswap,DR.y0-3),(D.x1+3,DR.y0-3),(D.x1+3,D.y1+5),(sBcol,D.y1+5),(sBcol,D.y1+1)])
    if cmd_attach_from is not None:
        p.pipe([cmd_attach_from,(DR.x0-1,rENTRY)])
    return {"D":D,"DR":DR,"rENTRY":rENTRY}

def build(cmd_values):
    p=lm.Program()
    dvx,dvy=32,4
    rENTRY=(dvy+1)+13
    src=p.room(0,rENTRY-1,28,7)
    sx0,sy0=src.ix0,src.iy0
    put(p,sx0,sy0,"@")
    cur=sx0+1
    for v in cmd_values:
        if v<0:
            put(p,cur,sy0,"1"); cur+=1; put(p,cur,sy0,"N"); cur+=1
        elif v<10:
            put(p,cur,sy0,str(v)); cur+=1
        else:
            for ch in "`%d`"%v: put(p,cur,sy0,ch); cur+=1
        put(p,cur,sy0,"s"); cur+=1
    put(p,cur,sy0,"H")
    build_driver(p,dvx,dvy,(src.x1+1,sy0))
    return p

if __name__=='__main__':
    # target: pixel (col3,row5) red -> dispPos=5*16+3=83 ; cmd stream [84, 9, -1]
    p=build([84,9,-1])
    path='/Users/visenbaev/icfpc26/solutions/little-little-little-man/_drvtest.man'
    p.save(path)
    print("saved",path,"footprint",p.footprint())
    # synthetic case
    HEX="0123456789abcdef"
    frame=[['0']*16 for _ in range(16)]
    frame[5][3]='9'
    frows=[''.join(r) for r in frame]
    tc=[{"name":"onepix","rounds":[{"in":["1"],"frames":[frows]}]}]
    json.dump(tc, open('/Users/visenbaev/icfpc26/solutions/little-little-little-man/_drvcase.json','w'))
    print("wrote case")

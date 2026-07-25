import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
import littleman as lm

# KEEPER LOOP (isolated, input-fed). input: target v0 v1 v2 ...
# remaining=target. per v: read v; if remaining==0 emit 9 (SOLUTION) halt;
# else include if v<=remaining (remaining-=v) else exclude(unchanged); emit newrem.
# "300 120 180 50" -> [180, 0, 9].

def build():
    p=lm.Program(); placed={}
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch: raise SystemExit(f"COL {(x,y)} {placed[(x,y)]!r} vs {ch!r}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    def room(x,y,w,h,g="+-|"):
        p.room(x,y,w,h,g)
        for i in range(w):
            placed[(x+i,y)]=p.get(x+i,y); placed[(x+i,y+h-1)]=p.get(x+i,y+h-1)
        for j in range(h):
            placed[(x,y+j)]=p.get(x,y+j); placed[(x+w-1,y+j)]=p.get(x+w-1,y+j)

    room(0,0,14,13)
    p.man(1,1)
    C(2,1,'r')                       # A=target=remaining
    C(3,1,'v')                       # merge cell -> S into loop
    # LOOP body (down col3)
    C(3,2,'M')                       # B:=remaining
    C(3,3,'r')                       # A=v, B=remaining
    C(3,4,'W')                       # A=remaining, B=v
    C(3,5,'X')                       # >0 -> W(continue); ==0 -> S(solution)
    # SOLUTION: redirect East off col3 immediately, then emit 9
    C(3,6,'>'); C(8,6,'9'); C(9,6,'s'); C(10,6,'H')
    # CONTINUE: (2,5) heading W
    C(2,5,'v')                       # S ; A=remaining,B=v
    C(2,6,'-')                       # A=remaining-v, B=v
    C(2,7,'X')                       # >=0 include (>0->W, ==0->S) ; <0 exclude (->E)
    # include: A>0 -> W(1,7); A==0 -> S(2,8)
    C(1,7,'v'); C(1,8,'>')           # A>0 path down then east into (2,8)
    C(2,8,'v')                       # include merge -> S ; A=remaining-v=newrem
    C(2,9,'s')                       # emit newrem
    C(2,10,'>')                      # -> row10 east to loopback
    # exclude: A<0 -> E(3,7)
    C(3,7,'+')                       # A=remaining=newrem ; heading E
    C(4,7,'v'); C(4,8,'s')           # emit newrem
    C(4,9,'v'); C(4,10,'>')          # -> row10 east to loopback
    # loopback row10 -> up col5 -> row1 -> west to (3,1)
    C(5,10,'^')                      # col5 up
    C(5,1,'<'); C(4,1,'<')           # (5,1)<-(4,1)<-(3,1)v
    # I -> keeper ; keeper -> O
    p.input_room(-5,0); p.pipe([(-2,1),(-1,1)])
    p.output_room(-5,8); p.pipe([(-1,9),(-2,9)])   # O reachable from keeper left border? emits use nearest outgoing = O
    return p

if __name__=='__main__':
    p=build(); p.save('/Users/visenbaev/icfpc26/scratchpad/ss_kloop.man'); print(p.render())

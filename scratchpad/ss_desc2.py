import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
import littleman as lm

# INTEGRATED DESCEND (target hardcoded via literal for this test; loader routing TODO).
# input: v0 v1 v2. Loader -> storages. HEAD walks dips: r v(top), s->H2K, down,
# r cmd(bottom), X: cmd<0 CONTINUE(E) up-channel->next dip ; cmd>0 unused.
# KEEPER: remaining=`300`(literal); loop: r v(H2K); remaining==0 -> emit 8->O halt;
#   else include if v<=remaining (remaining-=v) else exclude; cmd=-1 -> K2H.
# [120,180,50] -> incl120(rem180),incl180(rem0),then remaining==0 -> emit 8.

GAP=6
def build(nvals=3, target_lit="300"):
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

    BASE=4
    cols=[BASE+GAP*i for i in range(nvals)]

    # LOADER
    LX1=cols[-1]+4
    room(0,0,LX1+1,3); p.man(1,1)
    for c in cols:
        C(c,1,'r'); C(c+1,1,'s')
    C(LX1-1,1,'H')

    # STORAGES
    SY=6
    for c in cols:
        room(c-2,SY,5,4)
        C(c-1,SY+1,'@'); C(c,SY+1,'r'); C(c+1,SY+1,'v')
        C(c-1,SY+2,'>'); C(c,SY+2,'s'); C(c+1,SY+2,'<')

    # HEAD (tall)
    HY=12; HH=30; HX1=cols[-1]+6
    room(0,HY,HX1+1,HH); TR=HY+1; BR=HY+HH-2
    p.man(1,TR)
    for c in cols:
        C(c,TR,'r'); C(c+1,TR,'s'); C(c+2,TR,'v')
        C(c+2,BR-1,'r'); C(c+2,BR,'X')
        C(c+3,BR,'^'); C(c+3,TR,'>')
        C(c+1,BR,'H')

    # KEEPER (below head)
    KY=HY+HH+4; KW=30
    room(0,KY,KW,22); b=KY
    p.man(1,b+1)
    # literal target -> A=remaining
    lit='`'+target_lit+'`'
    for i,ch in enumerate(lit):
        C(2+i,b+1,ch)
    sp=2+len(lit)                     # spine col after literal
    C(sp,b+1,'v')                     # down into loop (merge cell)
    C(sp,b+2,'M')                     # B:=remaining
    C(sp,b+3,'r')                     # A=v (H2K)
    C(sp,b+4,'W')                     # A=remaining,B=v
    C(sp,b+5,'X')                     # >0 continue(W) ; ==0 solution(S)
    # SOLUTION straight S: redirect E, emit 8 -> O(right)
    C(sp,b+6,'>')
    C(KW-6,b+6,'8'); C(KW-5,b+6,'s'); C(KW-4,b+6,'H')
    # CONTINUE W -> (sp-1,b+5)
    C(sp-1,b+5,'v')                   # S ; A=remaining,B=v
    C(sp-1,b+6,'-')                   # A=remaining-v
    C(sp-1,b+7,'X')                   # >=0 include(>0 W, ==0 S) ; <0 exclude(E)
    C(sp-2,b+7,'v'); C(sp-2,b+8,'>'); C(sp-1,b+8,'v')   # include merge ; A=newrem -> (sp-1,b+9)
    C(sp,b+7,'+'); C(sp+1,b+7,'v'); C(sp+1,b+8,'v'); C(sp+1,b+9,'<')  # exclude: +,down,down,west
    C(sp-1,b+9,'v')                  # shared merge (include from N, exclude from E) ; A=newrem
    C(sp-1,b+10,'M')                 # B:=newrem
    C(sp-1,b+11,'1'); C(sp-1,b+12,'N')  # A=-1
    C(sp-1,b+13,'s')                 # cmd=-1 -> K2H
    C(sp-1,b+14,'W')                 # A=newrem  (heading S)
    # loopback: turn E, up col (sp+3) to row b+1, west to spine merge (sp,b+1)
    C(sp-1,b+15,'>'); C(sp+3,b+15,'^'); C(sp+3,b+1,'<')
    # (sp+3,b+1)< -> glide west -> (sp+1,b+1)? spine merge is (sp,b+1)=v ; need to reach it heading W
    # (sp+3,b+1)< heading W -> (sp+2,b+1) glide -> (sp+1,b+1) glide -> (sp,b+1)=v turn S. OK.

    # ---- PIPES ----
    p.input_room(-5,0); p.pipe([(-2,1),(-1,1)])
    for c in cols:
        p.pipe([(c,3),(c,SY-1)])
        p.pipe([(c,SY+4),(c,HY-1)])
    # H2K: head bottom border col8 -> keeper top border col8 (free gap col, != dip channels)
    p.pipe([(8,HY+HH),(8,KY-1)])
    # K2H: keeper top border col15 -> head bottom border col15 (well-separated from H2K col8)
    p.pipe([(15,KY-1),(15,HY+HH)])
    # O: keeper solution emit -> O (right). keeper right wall = col KW-1; pipe starts OUTSIDE it.
    p.output_room(KW+2,b+5); p.pipe([(KW,b+6),(KW+1,b+6)])
    return p, dict(cols=cols,sp=sp,b=b,KW=KW,HY=HY,HH=HH)

if __name__=='__main__':
    p,_=build(); p.save('/Users/visenbaev/icfpc26/scratchpad/ss_desc2.man'); print(p.render())

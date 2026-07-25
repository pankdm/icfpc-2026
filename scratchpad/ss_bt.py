import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
import littleman as lm

# BIDIRECTIONAL HEAD (descend + backtrack geometry) + 2-mode KEEPER + STACK-MAN.
# Head travels on TWO rows: RE (descend, moves East), RW (backtrack, moves West),
# both dropping into a shared per-column SHAFT. cmd from keeper: -1 go-right(E),
# +1 go-left(W), 0 done. Come-up-right -> RE col+1 ; come-up-left -> RW col-1.
#
# Value tape: cells 0..n-1 hold v_i; cell n holds SENTINEL (0). target = literal.
# KEEPER 2-mode:
#  DESCEND: recv v; remaining==0 -> emit 8(solution); v==0(sentinel) -> cmd=+1
#    (go-left) switch BACKTRACK; else v<=rem incl(push1,rem-=v)/excl(push0), cmd=-1.
#  BACKTRACK: recv v; pop bit; bit==1 -> rem+=v, push0, cmd=-1 switch DESCEND;
#    bit==0 -> cmd=+1 stay. (leftmost handled by head reaching sentinel-left -> nosol.)
# Test [200,180,120] t=300: needs one backtrack -> finds [180,120] -> emit 8.

GAP=6
def build(target_lit="300"):
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

    NVAL=3
    BASE=6
    cols=[BASE+GAP*i for i in range(NVAL)]     # value columns
    sent=cols[-1]+GAP                          # sentinel column (leaf)
    allcols=cols+[sent]

    # LOADER: load v0..v2 into storages, and 0 into sentinel cell
    LX1=sent+6
    room(0,0,LX1+1,3); p.man(1,1)
    for c in cols:
        C(c,1,'r'); C(c+1,1,'s')
    C(sent,1,'0'); C(sent+1,1,'s')             # sentinel value 0 -> sentinel storage
    C(LX1-1,1,'H')

    # STORAGES (values + sentinel)
    SY=6
    for c in allcols:
        room(c-2,SY,5,4)
        C(c-1,SY+1,'@'); C(c,SY+1,'r'); C(c+1,SY+1,'v')
        C(c-1,SY+2,'>'); C(c,SY+2,'s'); C(c+1,SY+2,'<')

    # HEAD (tall). RE=descend row, RW=backtrack row (RW=RE+1). shaft below.
    HY=12; HH=32; HX1=sent+6
    room(0,HY,HX1+1,HH)
    RE=HY+1; RW=HY+2; SH=HY+3; BR=HY+HH-3   # shaft top SH, cmd read BR-1, X at BR
    # head enters on RE at leftmost, heading E
    p.man(1,RE); C(2,RE,'>')                 # ensure heading E onto RE
    for c in allcols:
        # drops
        C(c,RE,'v'); C(c,RW,'v')             # RE drop -> RW drop -> shaft
        C(c,SH,'r')                          # r v_d (V[c] top nearest)
        C(c,SH+1,'s')                        # send v_d -> H2K
        # glide down shaft c to cmd read
        C(c,BR-1,'r')                        # r cmd (K2H bottom nearest)
        C(c,BR,'X')                          # -1->E(right) ; +1->W(left) ; 0->S(done)
        # come-up-right (E): col c+1 up to RE
        C(c+1,BR,'^'); C(c+1,RE,'>')
        # come-up-left (W): col c-1 up to RW
        C(c-1,BR,'^'); C(c-1,RW,'<')
        # done (S from X): (c,BR+1).. route to a halt (solution already emitted by keeper)
        C(c,BR+1,'H')

    # KEEPER (below head) — reuse descend logic; 2-mode added later. For NOW descend-only
    # (no stack/backtrack) to verify the bidirectional geometry drives descend.
    KY=HY+HH+2; KW=30
    room(0,KY,KW,22); b=KY
    p.man(1,b+1)
    lit='`'+target_lit+'`'
    for i,ch in enumerate(lit): C(2+i,b+1,ch)
    sp=2+len(lit)
    C(sp,b+1,'v')
    C(sp,b+2,'M'); C(sp,b+3,'r'); C(sp,b+4,'W'); C(sp,b+5,'X')
    C(sp,b+6,'>'); C(KW-6,b+6,'8'); C(KW-5,b+6,'s'); C(KW-4,b+6,'H')   # solution -> O
    C(sp-1,b+5,'v'); C(sp-1,b+6,'-'); C(sp-1,b+7,'X')
    C(sp-2,b+7,'v'); C(sp-2,b+8,'>'); C(sp-1,b+8,'v')
    C(sp,b+7,'+'); C(sp+1,b+7,'v'); C(sp+1,b+8,'v'); C(sp+1,b+9,'<')
    C(sp-1,b+9,'v')
    C(sp-1,b+10,'M'); C(sp-1,b+11,'1'); C(sp-1,b+12,'N'); C(sp-1,b+13,'s')
    C(sp-1,b+14,'W'); C(sp-1,b+15,'>'); C(sp+3,b+15,'^'); C(sp+3,b+1,'<')

    # ---- PIPES ----
    p.input_room(-5,0); p.pipe([(-2,1),(-1,1)])
    for c in allcols:
        p.pipe([(c,3),(c,SY-1)])
        p.pipe([(c,SY+4),(c,HY-1)])          # storage -> head TOP border (V[c])
    p.pipe([(8,HY+HH),(8,KY-1)])             # H2K (col8, free gap)
    p.pipe([(10,KY-1),(10,HY+HH)])           # K2H (col10, non-adjacent to H2K, free)
    p.output_room(KW+2,b+5); p.pipe([(KW,b+6),(KW+1,b+6)])
    return p, dict(cols=cols,sent=sent,sp=sp)

if __name__=='__main__':
    p,_=build(); p.save('/Users/visenbaev/icfpc26/scratchpad/ss_bt.man'); print(p.render()[:1600])

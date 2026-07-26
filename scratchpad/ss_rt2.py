import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# FULL round-trip: HEAD reads v (top V pipe), sends to KEEPER (H2K), KEEPER
# replies cmd=v+1 (K2H), HEAD reads cmd (bottom border) and outputs it. Expect [v+1].
# Validates both addressing directions for the roaming head.

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
    c=6
    # loader
    room(0,0,c+4,3); p.man(1,1); C(c,1,'r'); C(c+1,1,'s'); C(c+2,1,'H')
    # storage
    SY=6; room(c-2,SY,5,4)
    C(c-1,SY+1,'@'); C(c,SY+1,'r'); C(c+1,SY+1,'v')
    C(c-1,SY+2,'>'); C(c,SY+2,'s'); C(c+1,SY+2,'<')
    # head (tall). interior rows HY+1..HY+HH-2
    HY=12; HH=28; HX1=c+4
    room(0,HY,HX1+1,HH); TR=HY+1; BR=HY+HH-2
    p.man(1,TR)
    C(c,TR,'r')                    # A=v (top V nearest)
    C(c+1,TR,'s')                  # send v -> H2K (right/bottom, nearest at top)
    C(c+2,TR,'v')                  # go down
    C(c+2,BR,'<')                  # bottom, go west
    C(c,BR,'r')                    # A=cmd (K2H bottom-border nearest here)
    C(2,BR,'s'); C(1,BR,'H')       # send cmd -> O (left border nearest at bottom-left)
    # keeper below
    KY=HY+HH+2; room(0,KY,c+8,3)
    p.man(1,KY+1); C(c,KY+1,'r'); C(c+1,KY+1,'M'); C(c+2,KY+1,'1'); C(c+3,KY+1,'+')
    C(c+4,KY+1,'s'); C(c+5,KY+1,'H')

    # pipes
    p.input_room(-5,0); p.pipe([(-2,1),(-1,1)])
    p.pipe([(c,3),(c,SY-1)])
    p.pipe([(c,SY+4),(c,HY-1)])                 # storage->head TOP
    # H2K: head bottom border col c+1 -> keeper top border
    p.pipe([(c+1,HY+HH),(c+1,KY-1)])
    # K2H: keeper top border col c -> head bottom border col c (flows UP into head)
    #   start below head bottom border, end at keeper top border? K2H flows keeper->head.
    #   keeper is BELOW head. So K2H goes UP: from keeper top border up to head bottom border.
    #   start bk-nb on keeper border (c,KY) -> start (c,KY-1); end fwd-nb on head border (c,HY+HH-1)=(c,39)
    #   end (c,HY+HH)=(c,40). path (c,KY-1)->(c,40): KY-1=41 -> 40, going up.
    p.pipe([(c,KY-1),(c,HY+HH)])                # (c,41)->(c,40) up; bk (c,42)=keeper top? KY=42 border
    # O: head left border bottom -> O
    p.output_room(-5,BR); p.pipe([(-1,BR),(-2,BR)])
    return p

if __name__=='__main__':
    p=build(); p.save(_REPO + '/scratchpad/ss_rt2.man'); print(p.render())
    print('rows: HY',12,'HH',28,'BR',12+28-2,'KY',12+28+2)

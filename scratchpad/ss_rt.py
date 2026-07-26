import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# HEAD -> KEEPER forwarding + addressing test.
# storage(top) -> head(tall) -> keeper(bottom). HEAD reads v (top V pipe), sends
# to KEEPER via its ONLY outgoing (H2K). KEEPER reads v, outputs v. Expect [v].
# Validates head can r the value pipe (top) unambiguously and deliver to a remote
# keeper, i.e. the roaming-head addressing works with tall-room separation.

def C_factory(placed, p):
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch: raise SystemExit(f"COL {(x,y)} {placed[(x,y)]!r} vs {ch!r}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    return C
def room_factory(placed,p):
    def room(x,y,w,h,g="+-|"):
        p.room(x,y,w,h,g)
        for i in range(w):
            placed[(x+i,y)]=p.get(x+i,y); placed[(x+i,y+h-1)]=p.get(x+i,y+h-1)
        for j in range(h):
            placed[(x,y+j)]=p.get(x,y+j); placed[(x+w-1,y+j)]=p.get(x+w-1,y+j)
    return room

def build():
    p=lm.Program(); placed={}; C=C_factory(placed,p); room=room_factory(placed,p)
    c=4
    # loader
    room(0,0,c+4,3); p.man(1,1); C(c,1,'r'); C(c+1,1,'s'); C(c+2,1,'H')
    # storage
    SY=6; room(c-2,SY,5,4)
    C(c-1,SY+1,'@'); C(c,SY+1,'r'); C(c+1,SY+1,'v')
    C(c-1,SY+2,'>'); C(c,SY+2,'s'); C(c+1,SY+2,'<')
    # head (tall)
    HY=12; HH=26; HX1=c+4
    room(0,HY,HX1+1,HH); BR=HY+HH-2
    p.man(1,HY+1)
    C(c,HY+1,'r')                     # A=v (top V pipe nearest)
    C(c+1,HY+1,'s')                   # send v -> H2K (head's ONLY outgoing)
    C(c+2,HY+1,'H')
    # keeper (below head)
    KY=HY+HH+2; room(0,KY,c+6,3)
    p.man(1,KY+1); C(c,KY+1,'r'); C(c+1,KY+1,'s'); C(c+2,KY+1,'H')

    # pipes
    p.input_room(-5,0); p.pipe([(-2,1),(-1,1)])
    p.pipe([(c,3),(c,SY-1)])                       # loader->storage
    p.pipe([(c,SY+4),(c,HY-1)])                    # storage->head TOP border (c,HY)
    # H2K: head bottom border -> keeper top border, at col c+1
    p.pipe([(c+1,HY+HH),(c+1,KY-1)])               # (c+1,38)->(c+1,KY-1); bk (c+1,37) head, fwd (c+1,KY) keeper
    # keeper -> O
    p.output_room(-5,KY); p.pipe([(-1,KY+1),(-2,KY+1)])
    return p

if __name__=='__main__':
    p=build(); p.save(_REPO + '/scratchpad/ss_rt.man'); print(p.render())
    print('HY+HH=',12+26)

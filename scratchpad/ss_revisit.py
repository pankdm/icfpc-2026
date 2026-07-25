import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# Revisit test: 1 storage cell holding v. Head reads it 5 times (looping) and
# outputs each read. Expect [v,v,v,v,v] -> proves storage auto-refills for
# repeated (DFS-style) access.
def build():
    p = lm.Program(); placed={}
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch: raise SystemExit(f"COL {(x,y)}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    def room(x,y,w,h,g="+-|"):
        p.room(x,y,w,h,g)
        for i in range(w):
            placed[(x+i,y)]=p.get(x+i,y); placed[(x+i,y+h-1)]=p.get(x+i,y+h-1)
        for j in range(h):
            placed[(x,y+j)]=p.get(x,y+j); placed[(x+w-1,y+j)]=p.get(x+w-1,y+j)

    c = 4
    # loader: read one value, send down to storage
    room(0,0,c+4,3)
    p.man(1,1)
    C(c,1,'r'); C(c+1,1,'s'); C(c+2,1,'H')
    # storage
    SY=6
    room(c-2,SY,5,4)
    C(c-1,SY+1,'@'); C(c,SY+1,'r'); C(c+1,SY+1,'v')
    C(c-1,SY+2,'>'); C(c,SY+2,'s'); C(c+1,SY+2,'<')
    # head: reads storage 5 times in a loop, sends each to O
    HY=12
    room(0,HY,10,5)
    # head man loops: at (c,HY+1) do r then s, then loop back and repeat
    p.man(1,HY+1)
    C(2,HY+1,'>')                                     # loop re-entry: turn East
    C(c,HY+1,'r'); C(c+1,HY+1,'s'); C(c+2,HY+1,'v')  # read, send, turn down
    C(c+2,HY+2,'<'); C(2,HY+2,'^')                    # west then up to (2,HY+1)='>'
    # loop back: from (1,HY+2) up to (1,HY+1) then east to (c,HY+1) again
    # (1,HY+1) is @ (nop) -> East -> glides to c -> r again. loops forever (5+ reads).
    # I room -> loader
    p.input_room(-5,1); p.pipe([(-2,1),(-1,1)])
    # loader -> storage
    p.pipe([(c,3),(c,SY-1)])
    # storage -> head
    p.pipe([(c,SY+4),(c,HY-1)])
    # head -> O  (head room cols0-9, right wall col9)
    p.output_room(12,HY); p.pipe([(10,HY+1),(11,HY+1)])
    return p,placed

if __name__=='__main__':
    p,_=build(); print(p.render()); p.save(_REPO + '/scratchpad/ss_revisit.man')

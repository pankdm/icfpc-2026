import sys
sys.path.insert(0,'/Users/visenbaev/icfpc26/tools')
import littleman as lm

# stack6: pure LAYOUT fold of stack5. Op-streams BYTE-IDENTICAL to tight{M,R,C};
# only wall rectangles shrunk to hug ops + rooms packed with L-pipes.

def blockM(p, ox, oy):
    W_,H_=8,20                      # was 12,21 : trim empty cols7-11 + row19
    p.room(ox,oy,W_,H_)
    def P(x,y,c):
        k=(ox+x,oy+y); assert k not in p.cells or p.cells.get(k)==c, f'M coll {(x,y)}'
        p.put(ox+x,oy+y,c)
    P(1,1,'@');P(2,1,'1');P(3,1,'M');P(4,1,'v');P(4,2,'v')
    P(4,3,'r');P(4,4,'X')
    P(3,4,'<');P(2,4,'v');P(2,5,'+');P(2,6,'+');P(2,7,'+');P(2,8,'M');P(2,9,'r')
    P(2,10,'<');P(1,10,'^');P(1,2,'>');P(2,2,'>');P(3,2,'>')
    P(5,4,'>');P(6,4,'v');P(6,5,'+');P(6,6,'M');P(6,7,'3');P(6,8,'W');P(6,9,'/')
    P(6,10,'W');P(6,11,'b');P(6,12,'d')
    P(6,13,'W');P(6,14,'b');P(6,15,'d')
    P(5,15,'M');P(4,15,'r');P(3,15,'<');P(2,15,'<');P(1,15,'^')
    P(5,12,'r');P(4,12,'s');P(3,12,'H')
    P(6,16,'r');P(6,17,'s');P(6,18,'H')
    P(4,5,'W');P(4,6,'b');P(4,7,'m');P(4,8,'d')
    P(3,8,'v');P(3,9,'r');P(3,10,'s');P(3,11,'H')
    P(4,9,'0');P(4,10,'s');P(4,11,'H')
    p.man(ox+1,oy+1)

def blockR(p, ox, oy):
    W_,H_=8,11
    p.room(ox,oy,W_,H_)
    def P(x,y,c):
        k=(ox+x,oy+y); assert k not in p.cells or p.cells.get(k)==c, f'R coll {(x,y)}'
        p.put(ox+x,oy+y,c)
    P(1,1,'@');P(2,1,'r');P(3,1,'b');P(4,1,'0');P(5,1,'M');P(6,1,'v')
    P(6,2,'<')
    P(2,2,'v')
    P(2,3,'a')
    P(3,3,'v');P(3,4,'1');P(3,5,'+');P(3,6,'M');P(3,7,'r');P(3,8,'s')
    P(3,9,'>');P(4,9,'^')
    P(4,8,'W');P(4,7,'s');P(4,6,'M');P(4,5,'m')
    P(4,2,'<')
    P(5,2,'<');P(3,2,'<')
    P(2,4,'0');P(2,5,'s');P(2,6,'1');P(2,7,'+');P(2,8,'s');P(2,9,'H')
    p.man(ox+1,oy+1)

def blockC(p, ox, oy):
    W_,H_=7,12                      # was 7,13 : trim empty row11
    p.room(ox,oy,W_,H_)
    def P(x,y,c):
        k=(ox+x,oy+y); assert k not in p.cells or p.cells[k]==c, f'C coll {(x,y)}'
        p.put(ox+x,oy+y,c)
    P(3,1,'@'); P(4,1,'v')
    P(4,2,'r');P(4,3,'b');P(4,4,'M');P(4,5,'5');P(4,6,'W');P(4,7,'}');P(4,8,'x')
    P(5,8,'^');P(5,7,'s');P(5,6,'r');P(5,5,'s')
    P(5,1,'<')
    P(3,8,']');P(2,8,'x')
    P(2,7,'s');P(2,6,'r');P(2,5,'s')
    P(2,1,'>')
    P(2,9,'N');P(2,10,'<');P(1,10,'^');P(1,9,'s');P(1,8,'r');P(1,7,'s')
    P(1,1,'>')
    p.man(ox+3,oy+1)

def build(save):
    p=lm.Program()
    blockM(p,0,0)        # M cols0-7  rows0-19
    blockR(p,10,0)       # R cols10-17 rows0-10
    blockC(p,10,11)      # C cols10-16 rows11-22  (adjacent below R)
    p.input_room(20,0)   # I cols20-22 rows0-2
    p.output_room(0,20)  # O cols0-2 rows20-22
    # I -> R : two cells in gap cols18,19
    p.pipe([(19,1),(18,1)])
    # R -> C : L round the east side (R adjacent above C). down col17 then W into C east wall.
    p.put(17,11,'v'); p.put(17,12,'<')
    # C -> M : two cells in gap cols8,9
    p.pipe([(9,15),(8,15)])
    # M -> O : down col3 (below M) then W into O east wall
    p.put(3,20,'v'); p.put(3,21,'<')
    print('footprint',p.footprint())
    p.save(save)
    return p

build(sys.argv[1] if len(sys.argv)>1 else '/Users/visenbaev/icfpc26/solutions/brackets/stack6.man')

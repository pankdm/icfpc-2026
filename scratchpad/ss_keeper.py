import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
import littleman as lm

# Isolated KEEPER descend micro-program test (the 3-register crux).
# Input tokens: remaining, todoTotal, v_d.
# Emits:  7               if remaining==0            (SOLUTION)
#         8               if remaining>todoTotal     (can't-reach BACKTRACK)
#         2, newremaining if v_d<=remaining          (INCLUDE; newrem=rem-v_d)
#         3, newremaining else                       (EXCLUDE; newrem=rem)
# Uses only A/B (remaining persists in B across reads; reads clobber A only).

def build():
    p = lm.Program(); placed={}
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch: raise SystemExit(f"COL {(x,y)} {placed[(x,y)]!r} vs {ch!r}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    def room(x,y,w,h,g="+-|"):
        p.room(x,y,w,h,g)
        for i in range(w):
            placed[(x+i,y)]=p.get(x+i,y); placed[(x+i,y+h-1)]=p.get(x+i,y+h-1)
        for j in range(h):
            placed[(x,y+j)]=p.get(x,y+j); placed[(x+w-1,y+j)]=p.get(x+w-1,y+j)

    room(0,0,12,20)
    p.man(1,1)                       # @ dir East
    # --- read remaining, test ==0 ---
    C(2,1,'r')                       # A=remaining
    C(3,1,'M')                       # B=remaining
    C(4,1,'X')                       # rem>0 -> S(continue); rem==0 -> E(solution)
    # solution path (East)
    C(5,1,'7'); C(6,1,'s'); C(7,1,'H')
    # --- continue (South from (4,1)) : prune check ---
    C(4,2,'r')                       # A=todoTotal, B=remaining
    C(4,3,'-')                       # A=todo-rem
    C(4,4,'X')                       # <0 -> E(prune); ==0 -> S(cont); >0 -> W(cont)
    # prune path (East)
    C(5,4,'8'); C(6,4,'s'); C(7,4,'H')
    # >0 continue: West to (3,4) -> down -> merge at (4,5)
    C(3,4,'v'); C(3,5,'>')
    C(4,5,'v')                       # merge (from N: ==0 ; from W(via 3,5->east): >0) -> South
    # --- v_d decision --- (A=todo-rem, B=remaining)
    C(4,6,'r')                       # A=v_d, B=remaining
    C(4,7,'-')                       # A=v_d-rem
    C(4,8,'X')                       # <0 -> E(incl); ==0 -> S(incl); >0 -> W(excl)
    # include merge: A<0 East to (5,8)->down->west to (4,9); A==0 South to (4,9)
    C(5,8,'v'); C(5,9,'<')
    C(4,9,'v')                       # include merge -> South
    C(4,10,'N')                      # A = rem - v_d = newrem
    C(4,11,'M')                      # B=newrem
    C(4,12,'2'); C(4,13,'s')         # emit 2
    C(4,14,'W')                      # A=newrem
    C(4,15,'s'); C(4,16,'H')         # emit newrem, halt
    # exclude: West from (4,8) to (3,8)
    C(3,8,'v')                       # turn South
    C(3,9,'W')                       # A=remaining (B was remaining)
    C(3,10,'M')                      # B=remaining
    C(3,11,'3'); C(3,12,'s')         # emit 3
    C(3,13,'W'); C(3,14,'s'); C(3,15,'H')  # emit newrem(=rem), halt

    # I -> keeper (west), O <- keeper
    p.input_room(-5,0); p.pipe([(-2,1),(-1,1)])
    p.output_room(14,0); p.pipe([(12,1),(13,1)])
    return p

if __name__=='__main__':
    p=build(); p.save('/Users/visenbaev/icfpc26/scratchpad/ss_keeper.man'); print(p.render())

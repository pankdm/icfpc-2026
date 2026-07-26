"""Build minimal belt test rigs for ticks-per-rotation measurement on the wasm oracle.
Reuses tools/littleman.py DSL. Writes rigs to scratchpad/belt_floor/rigs/.
Do NOT touch solutions/.

DISCIPLINE (oracle gotcha): a turn-arrow <>^v placed in a cell ORTHOGONALLY
ADJACENT to a room wall (or a pipe attach) is misread as a spurious pipe attach
-> load error / broken FIFO. So all turn-arrows are kept >=1 blank cell off every
wall. r/s/instructions may sit against walls. Pipe endpoints sit one cell OUTSIDE
the destination wall (fwd/bwd neighbour = the wall), matching simple_pipe.py.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import os, sys
REPO = _REPO
sys.path.insert(0, os.path.join(REPO, "tools"))
import littleman as lm

OUT = os.path.join(REPO, "scratchpad", "belt_floor", "rigs")
os.makedirs(OUT, exist_ok=True)

def save(p, name):
    path = os.path.join(OUT, name); p.save(path)
    w,h,_ = p.footprint(); print(f"  {name:34s} {w}x{h}")
    return path

# ===========================================================================
# CONFIG 2 (straight): Input -> main(straight rsrs, then wasted return) -> Output
# ===========================================================================
def pipeline_line(L):
    p = lm.Program()
    p.put(2,2,"@"); p.put(3,2,">")
    x=4
    for _ in range(L): p.put(x,2,"r"); p.put(x+1,2,"s"); x+=2
    endx=x; p.put(endx,2,"v"); p.put(endx,3,"<")
    for xx in range(4,endx): p.put(xx,3,"<")
    p.put(3,3,"^")
    W=endx+2; p.room(0,0,W+1,6); bw=5
    p.input_room(4,9);  p.pipe([(5,bw+3),(5,bw+1)])
    oc=endx-1; p.output_room(oc-1,9); p.pipe([(oc,bw+1),(oc,bw+3)])
    return p

# ===========================================================================
# RECT LOOP: 2-row rectangular belt-loop. Top row works east, bottom row works
# west, 4 corner turns. The man circulates forever. Fill both rows with a
# repeating op-pattern P (e.g. "rs"=bare belt, "rsmd"=per-rotation counter,
# "rsrsmd"=unrolled k=2). Reads from always-ready Input (r), drains to Output (s).
# Isolates the MAIN-man ticks/rotation for pattern P (configs 1,2b,4,5).
# ===========================================================================
def rect_loop(P, reps, name=None):
    p = lm.Program()
    top = (P*reps)
    p.put(2,2,"@"); p.put(3,2,">")
    x=4
    for ch in top: p.put(x,2,ch); x+=1
    endx=x; p.put(endx,2,"v"); p.put(endx,3,"<")
    bot = (P*reps)
    xx=endx-1
    for ch in bot:
        if xx<=3: break
        p.put(xx,3,ch); xx-=1
    p.put(3,3,"^")
    W=endx+2; p.room(0,0,W+1,6); bw=5
    # input up into bottom wall col5; output down at col endx-1
    p.input_room(4,9);  p.pipe([(5,bw+3),(5,bw+1)])
    oc=endx-1; p.output_room(oc-1,9); p.pipe([(oc,bw+1),(oc,bw+3)])
    return p

# ===========================================================================
# RING (config 3): real closed belt.  MAIN --P1--> RELAY --P2--> MAIN.
# MAIN self-primes from an Input pipe (uses R: input during prime, belt after).
# main_P / relay_P are op-patterns for each side's rectangular loop (use R not r
# so a room with two incoming pipes drains whichever is ready).
# ===========================================================================
def _rect_room(p, x0, y0, P, reps, read_op):
    """Draw a 2-row rectangular loop room with top-left corner (x0,y0).
    Returns (right_wall_col, bottom_wall_row)."""
    P = P.replace('r', read_op)
    yA, yB = y0+2, y0+3
    p.put(x0+2,yA,"@"); p.put(x0+3,yA,">")
    x=x0+4
    for ch in (P*reps): p.put(x,yA,ch); x+=1
    endx=x; p.put(endx,yA,"v"); p.put(endx,yB,"<")
    xx=endx-1
    for ch in (P*reps):
        if xx<=x0+3: break
        p.put(xx,yB,ch); xx-=1
    p.put(x0+3,yB,"^")
    rW=endx+2; rB=y0+5
    p.room(x0,y0,rW-x0+1,6)
    return rW,rB

def ring(main_P, relay_P, main_reps, relay_reps, seg=12):
    p = lm.Program()
    # MAIN room top-left (0,0). read with R (belt-return P2 + input prime).
    mW,mB = _rect_room(p,0,0,main_P,main_reps,"R")
    # RELAY room to the right, gap 'seg' for pipe legs.
    relay_left = mW + seg + 3
    rW,rB = _rect_room(p,relay_left,0,relay_P,relay_reps,"R")
    # P1 main->relay along row1 (interior, against top wall; arrows are at rows2/3).
    p.pipe([(mW+1,1),(relay_left-1,1)])
    # P2 relay->main along row4.
    p.pipe([(relay_left-1,4),(mW+1,4)])
    # Input prime pipe up into MAIN bottom wall (y=5) col5.
    p.input_room(4,9); p.pipe([(5,8),(5,6)])
    return p

if __name__=="__main__":
    which = sys.argv[1] if len(sys.argv)>1 else "all"
    if which in("all","line"):
        print("config-2 straight lines:")
        for L in (4,8,16,32,64): save(pipeline_line(L), f"line_L{L}.man")
    if which in("all","rect"):
        print("rect-loop main-side (bare belt 'rs', sweep width):")
        for r in (1,2,4,8,16,32): save(rect_loop("rs",r), f"rect_rs_r{r}.man")
        print("config-4 per-rotation counter 'rsmd':")
        for r in (1,4,16): save(rect_loop("rsmd",r), f"rect_counter_r{r}.man")
        print("config-5 unrolled counter (k rotations then m,d):")
        save(rect_loop("rsrsmd",8),      "rect_unroll_k2.man")   # k=2
        save(rect_loop("rsrsrsrsmd",8),  "rect_unroll_k4.man")   # k=4
        save(rect_loop("rsrsrsrsrsrsrsrsmd",8), "rect_unroll_k8.man") # k=8
    if which in("all","ring"):
        print("config-1 naive tight ring (main rs w1, relay rs w1):")
        save(ring("rs","rs",1,1), "ring_tight.man")
        print("config-3 pipelined main + relay variants:")
        save(ring("rs","rs",8,1),  "ring_mainwide_relaytight.man")
        save(ring("rs","rs",8,8),  "ring_both_wide.man")
        save(ring("rs","rs",16,16),"ring_both_w16.man")

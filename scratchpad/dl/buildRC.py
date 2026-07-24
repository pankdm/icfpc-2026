import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

def build(n=16):
    """Reverse-collector: reader distributes v_i to short lane i (left->right),
    collector man walks RIGHT->LEFT reading lanes in reverse via blocking r,
    forwarding each to O. O(n) ticks, minimal (len-2) lanes. Single round."""
    p = lm.Program(); P = p.put
    lastS = 4 + 2*(n-1)          # last send col
    Wr = lastS + 4
    # reader room rows 0..2, interior row1, south wall row2
    p.room(0,0,Wr,3)
    P(1,1,"@"); P(2,1,"r")       # count discard
    for i in range(n):
        P(3+2*i,1,"r"); P(4+2*i,1,"s")
    P(lastS+2,1,"H")
    # input -> reader top col1
    p.input_room(0,-5); p.pipe([(1,-2),(1,-1)])
    # lanes: vertical, reader south wall (col,2) -> down -> merger north wall
    # merger room rows 5..7, interior row6, north wall row5
    p.room(0,5,Wr,3)
    for i in range(n):
        c = 4+2*i
        p.pipe([(c,3),(c,4)])    # len-2 lane into merger north wall row5
    # merger man: spawn (lastS+1,6), face west, read cols lastS..4 (r), send at odd cols
    sp = lastS+1
    P(sp,6,"@"); P(sp+1,6,"<")   # reorient west
    for i in range(n):
        c = 4+2*i
        P(c,6,"r"); P(c-1,6,"s")
    P(2,6,"H")                   # safe halt at far west
    # output room below merger, pipe from merger south wall
    # attach O pipe at merger south wall col 5 (near last outputs)
    p.output_room(0,10)
    p.pipe([(1,8),(1,9)])        # merger south wall (1,7) -> down -> O top (1,10)? O rows10..12
    return p

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv)>1 else 16
    p = build(n)
    print(p.render())
    print("footprint:", p.footprint())
    p.save(os.path.join(os.path.dirname(__file__), "rc.man"))

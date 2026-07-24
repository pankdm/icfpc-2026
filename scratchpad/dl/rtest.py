import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

# Reader fills lanes 0..n-1 (left-align, v_i -> lane i). Lanes are vertical pipes at
# cols 4+2i, dropping into a collector room whose north wall is STAGGERED so lane i
# attaches at row (BASE - i): higher-index lane => topmost attach => read first by R.
# Collector man sits and does: r (barrier: wait for reader's "go" on count-pipe), then loop R,s.

def build(n=3):
    p = lm.Program(); P = p.put
    lastS = 4 + 2*(n-1)
    Wr = lastS + 4
    # reader room rows 0..2
    p.room(0,0,Wr,3)
    P(1,1,"@"); P(2,1,"r")            # discard count
    for i in range(n):
        P(3+2*i,1,"r"); P(4+2*i,1,"s")
    P(lastS+2,1,"H")
    p.input_room(0,-5); p.pipe([(1,-2),(1,-1)])
    # collector room far below; staggered north wall.
    # place each lane i as a vertical pipe from reader south wall (col c, row2->3...) down to
    # collector attach at row RA_i. Collector interior below.
    # We'll make attach rows: lane i attaches at row (TOP + (n-1-i))  => lane n-1 topmost.
    TOP = 8
    # collector room spans rows TOP.. ; but staggered wall is unusual. Simpler: give collector a
    # flat north wall at row Wcol, and vary lane pipe LENGTHS won't change attach row.
    # To stagger ATTACH ROW we must vary where pipe meets the room. Put collector room with a
    # flat wall, and route each lane to a distinct attach COLUMN but we need distinct ROWS.
    # Instead: attach all lanes on the LEFT wall of collector at distinct rows (top-to-bottom
    # = lane n-1 .. lane 0). Route lane i horizontally then into left wall at row.
    return p

print("placeholder")

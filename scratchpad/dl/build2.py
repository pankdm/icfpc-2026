import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

# ---- Design 2 ----
# Lanes: vertical pipes at cols L_i = LB + 3*i, i=0..15, from reader south wall to collector north wall.
# Reader (Man-B): descending EAST staircase. Reads count n -> BP. Per stair writes v_i -> lane i,
#   decrements BP, exits when BP==0. Then resets to count-read.
# Collector (Man-A): FLAT west scan from lane 15. q-skip empties, read+send filled lanes to O.
#   Fixed west stop after lane 0. Resets.

NLANE = 16
LB = 6            # col of lane 0
def lane_col(i): return LB + 3*i

def build():
    p = lm.Program(); P = p.put
    lastlane = lane_col(NLANE-1)   # col of lane 15

    # ---------- READER ROOM ----------
    # Reader occupies top. Count-read at top-left, then staircase descending east.
    # Stair i decision D_i at (dc0 + 3*i, dr0 + 2*i). Work: a,r,s,v,m.
    # s writes lane i => lane i col must equal (dc+2). Set dc0+2 = lane_col(0)=LB => dc0 = LB-2.
    dc0 = LB - 2
    dr0 = 3          # first decision row (interior)
    # reader room bounds: cols 0.. (lastlane+4), rows 0.. bottom
    reader_bottom = dr0 + 2*NLANE + 3
    RW = lastlane + 5
    p.room(0, 0, RW, reader_bottom+1)
    # input room + pipe into reader top at col 2
    p.input_room(-4, 0); p.pipe([(-2,1),(-1,1),(0,1)])  # I at (-3,1)->into room left wall row1? adjust
    # Actually place input room to the left feeding col 2 row 1. Simpler: input room above col2.
    return p, dc0, dr0

if __name__ == "__main__":
    p, dc0, dr0 = build()
    print(p.render())

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm

# 3-lane staggered delay-line reverser, SINGLE round, NO count.
# Feed input as "v0 v1 v2" ; expect "v2 v1 v0".
p = lm.Program()

# Reader room: interior row 1, cols 1..8. south wall row 2.
RX, RY = 0, 0
p.room(RX, RY, 10, 3)              # cols0..9 rows0..2, interior row1 cols1..8
# man walks east: @ r s r s r s
P = p.put
P(1,1,"@")
P(2,1,"r"); P(3,1,"s")   # v0 -> lane0 (mouth below col3)
P(4,1,"r"); P(5,1,"s")   # v1 -> lane1 (mouth below col5)
P(6,1,"r"); P(7,1,"s")   # v2 -> lane2 (mouth below col7)
P(8,1,"H")               # safe halt (wall fault would be fatal & kill merger)

# Input room feeding reader. Put I to the LEFT, pipe into reader west? Reader needs
# incoming pipe nearest to r cells. Place I above-left, pipe into reader TOP wall col1.
p.input_room(0, -5)                # I room rows -5..-3 cols0..2, I at (1,-4)
p.pipe([(1,-2),(1,-1)])            # down into reader top wall at col1 (interior (1,1) below)

# Merger: vertical room on right. west wall col MX=20. interior cols 21..24 rows 5..15.
MX = 20
p.room(MX, 5, 6, 11)               # cols20..25 rows5..15
# lane entry rows on merger west wall (interior-adjacent): r0=12,r1=10,r2=8
r0,r1,r2 = 12,10,8
# Lanes: down from mouth (col, row3) to (col, ri), then east to (MX-1, ri) i.e col19.
def lane(col, ri):
    pts = [(col,3),(col,ri),(MX-1,ri)]
    p.pipe(pts)
lane(3, r0)   # lane0 longest
lane(5, r1)
lane(7, r2)   # lane2 shortest

# Merger man: loops R ; s. interior cols21..24. Put man racetrack:
# @ at (21,6): R at (22,6), then v to (24,6)? need s to send to output (east wall).
# Output room to the right of merger, incoming pipe on merger east wall.
p.output_room(MX+8, 9)             # O room cols28..30 rows9..11, O at (29,10)
p.pipe([(26,10),(27,10)])          # merger east wall col25 -> pipe cols26,27 -> O west (28)
# merger man racetrack rows 6-7 cols21..24 (closed 8-cell loop)
P(21,6,">"); P(22,6,"@"); P(23,6,"R"); P(24,6,"v")
P(24,7,"<"); P(23,7,"s"); P(22,7,"<"); P(21,7,"^")

print(p.render())
print("footprint:", p.footprint())
p.save(os.path.join(os.path.dirname(__file__), "dl3.man"))

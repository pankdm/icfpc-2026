import sys; sys.path.insert(0,'tools')
import littleman as lm
p=lm.Program()
# CTRL room top-left: 7x7 interior 5x5 (room for tight loop + divert + count logic)
p.room(0,0,7,7)
# RELAY room bottom-right small: 4x4 interior 2x2
p.room(9,8,4,4)   # cols9-12 rows8-11
# I room top-right
p.input_room(9,0)   # cols9-11 rows0-2
# O room: left of CTRL
p.output_room(-4,2) # cols -4..-2 rows2-4
# Ring FEED pipe: CTRL right wall (col6) -> serpentine down -> into RELAY.
# Ring RETURN pipe: RELAY -> back up -> CTRL bottom/left.
# feed: from (7,3) east/serpentine to relay top (row7 area)
p.pipe([(7,3),(8,3),(8,7)])              # feed: 3 cells into relay top (10? ) -- rough
# return: relay left (col9) -> up -> CTRL bottom wall
p.pipe([(8,9),(7,9),(7,8),(1,8),(1,7)])  # return path under CTRL back to bottom wall col1
# input pipe: I bottom (row2) -> down into CTRL top? I is top-right, route to CTRL top wall col5
p.pipe([(10,3),(10,5),(5,5)])            # rough
# output pipe: CTRL left wall -> O
p.pipe([(-1,3),(-2,3)])
w,h,box=p.footprint()
print(p.render())
print("FOOTPRINT",w,'x',h,'box',box)

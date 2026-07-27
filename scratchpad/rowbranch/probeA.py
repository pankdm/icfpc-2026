import sys
sys.path.insert(0, '/Users/dmitrykorolev/projects/icfpc-2026-main/tools')
from littleman import Program

p = Program()
p.room(0, 0, 13, 8)
# y=1 : POSITIVE target row  ('>' catcher at corridor col 2)
p.put(2,1,'>'); p.text(5,1,'1sH')
# y=2 : block entry row: @ r ... v   (turn south = to_west first cell)
p.put(4,2,'@'); p.put(5,2,'r'); p.put(7,2,'v')
# y=3 : THE BRANCH ROW - man heads west, X at col2 dispatches N/S, zero falls west to col1
p.put(7,3,'<'); p.put(2,3,'X'); p.put(1,3,'v')
# y=4 : ZERO target row  ('>' catcher at corridor col 1)
p.put(1,4,'>'); p.text(3,4,'2sH')
# y=5 : NEGATIVE target row ('>' catcher at corridor col 2)
p.put(2,5,'>'); p.text(3,5,'3sH')
p.input_room(16,0)
p.pipe([(15,1),(13,1)])
p.output_room(4,10)
p.pipe([(5,8),(5,9)])
print(p.render())
p.save('/Users/dmitrykorolev/projects/icfpc-2026-main/scratchpad/rowbranch/probeA.man')

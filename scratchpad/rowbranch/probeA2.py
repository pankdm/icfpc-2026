import sys
sys.path.insert(0, '/Users/dmitrykorolev/projects/icfpc-2026-main/tools')
from littleman import Program
p = Program()
p.room(0,0,21,8)
# row1: NEG target, WEST-running block: '<' catcher in east corridor col 17
p.put(17,1,'<'); p.text(15,1,'3sH',d='W')     # 3 at 15, s at 14, H at 13
# row2: START block, EAST-running: @ r ... X at east corridor col 17, 'v' at col 18
p.put(3,2,'@'); p.put(4,2,'r'); p.put(17,2,'X'); p.put(18,2,'v')
# row3: POS target, WEST-running
p.put(17,3,'<'); p.text(15,3,'1sH',d='W')
# row4: ZERO target, WEST-running, entered one column further east
p.put(18,4,'<'); p.text(16,4,'2sH',d='W')
p.input_room(24,5); p.pipe([(23,6),(21,6)])
p.output_room(13,10); p.pipe([(14,8),(14,9)])
print(p.render())
p.save('/Users/dmitrykorolev/projects/icfpc-2026-main/scratchpad/rowbranch/probeA2.man')

import sys
sys.path.insert(0,'/Users/dmitrykorolev/projects/icfpc-2026-main/tools')
from littleman import Program
p=Program(); p.room(0,0,15,6)
p.put(2,2,'@'); p.put(4,2,'Y')
p.put(8,1,'r'); p.text(9,1,'1sH')
p.put(8,3,'r'); p.text(9,3,'2sH')
p.input_room(18,0); p.pipe([(17,1),(15,1)])
p.output_room(8,8); p.pipe([(9,6),(9,7)])
print(p.render()); p.save('/Users/dmitrykorolev/projects/icfpc-2026-main/scratchpad/rowbranch/probeC.man')

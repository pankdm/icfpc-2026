import sys
sys.path.insert(0,'/Users/dmitrykorolev/projects/icfpc-2026-main/tools')
from littleman import Program
p=Program(); p.room(0,0,25,9)
p.put(4,4,'@'); p.put(5,4,'r'); p.put(20,4,'v')      # entry row, heads east
p.put(20,5,'<'); p.put(15,5,'b'); p.put(14,5,'x')    # branch row, heads west; x tests bit0
p.put(14,4,']'); p.put(14,3,'x')                     # bit0=1 -> north leg, tests bit1
p.put(14,6,']'); p.put(14,7,'x')                     # bit0=0 -> south leg, tests bit1
p.text(15,3,'3sH');  p.text(13,3,'1sH',d='W')        # north: bit1=1 -> east ; bit1=0 -> west
p.text(13,7,'2sH',d='W'); p.text(15,7,'0sH')         # south: bit1=1 -> west ; bit1=0 -> east
p.input_room(28,0); p.pipe([(27,1),(25,1)])
p.output_room(5,11); p.pipe([(6,9),(6,10)])
print(p.render()); p.save('/Users/dmitrykorolev/projects/icfpc-2026-main/scratchpad/rowbranch/probeB.man')

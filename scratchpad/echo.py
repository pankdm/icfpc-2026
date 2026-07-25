import sys; sys.path.insert(0,'tools')
import littleman as lm
p = lm.Program()
top=6
p.room(0,top,10,6)   # CTRL cols0-9 rows6-11
cIN=4; cOUT=1
p.input_room(cIN-1, top-5);  p.pipe([(cIN, top-2),(cIN, top-1)])
p.output_room(cOUT-1, top-5); p.pipe([(cOUT, top-1),(cOUT, top-2)])
p.man(1,7); p.put(1,7,'@'); p.put(cIN,7,'r'); p.put(5,7,'v')
p.put(5,8,'<'); p.put(1,8,'v')
p.put(1,9,'>'); p.put(cIN,9,'r'); p.put(7,9,'v')       # read seq discard
p.put(7,10,'<'); p.put(cIN,10,'r'); p.put(2,10,'s'); p.put(1,10,'^')  # read val, send at col2->OUT@col1
open('scratchpad/echo.man','w').write(p.render()+"\n")
print(p.render())

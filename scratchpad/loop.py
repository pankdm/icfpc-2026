import sys; sys.path.insert(0,'tools')
import littleman as lm
p=lm.Program()
# room 7x6: outer cols0-6 rows0-5, interior cols1-5 rows1-4
p.room(0,0,7,6)
# input room above, pipe into top wall at col2
p.input_room(1,-4)              # I at (2,-3)
p.pipe([(2,-2),(2,-1)])         # down into (2,0) top border
# output room to the right, pipe from right wall row3 to O
p.output_room(9,2)              # O at (10,3)
p.pipe([(6,3),(8,3)])           # from (6,0-border? col6 is right wall) -> O
# man: @ (1,1) E; loop r,s then wrap
p.put(1,1,'@')
p.put(2,1,'r')   # receive from input (nearest incoming = top pipe)
p.put(3,1,'s')   # send to output (nearest outgoing = right pipe row3)
p.put(4,1,'v')
p.put(4,2,'<')
p.put(2,2,'^')
print(p.render()); print("FP",p.footprint())
open('scratchpad/loop.man','w').write(p.render())

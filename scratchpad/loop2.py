import sys; sys.path.insert(0,'tools')
import littleman as lm
p=lm.Program()
# CTRL room outer (0,0) 7x6 : interior cols1-5 rows1-4, walls col0/6 row0/5
p.room(0,0,7,6)
# I room ABOVE with a 2-cell pipe gap. CTRL top border row0. pipe cells rows -1,-2. I bottom border row-3.
p.input_room(1,-5)             # I room rows -5..-3, I at (2,-4)
p.pipe([(2,-2),(2,-1)])        # 2 pipe cells outside CTRL top (row-2,-1), enter (2,0) border
# O room RIGHT with 2-cell gap. CTRL right border col6. pipe cells col7,8. O left border col9.
p.output_room(9,2)             # O room cols9-11 rows2-4, O at (10,3)
p.pipe([(7,3),(8,3)])          # 2 pipe cells outside CTRL right, into (9,3)=O left border
# man tight loop inside CTRL (interior cols1-5 rows1-4)
p.put(1,1,'@')  # start E
p.put(2,1,'r')  # recv from input (top pipe nearest)
p.put(3,1,'s')  # send to output (right pipe nearest)
p.put(4,1,'v')
p.put(4,2,'<')
p.put(2,2,'^')
print(p.render()); print("FP",p.footprint())
open('scratchpad/loop2.man','w').write(p.render())

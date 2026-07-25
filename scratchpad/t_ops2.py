import sys; sys.path.insert(0,'tools')
import littleman as lm
p = lm.Program()
p.input_room(0,0); p.output_room(4,0)
p.room(0,5,26,6)
p.pipe([(1,3),(1,4)]); p.pipe([(5,4),(5,3)])
# read k; compute 1<<k -> output. A=1,B=k,{ 
# read k->A ; M->B=k ; 1->A=1 ; { -> A=1<<k
p.text(1,6,"@rM1{v")
p.put(6,7,"<"); p.text(5,7,"s"); p.text(2,7,"H")
for c in range(3,6): p.put(c,7," ")
open('scratchpad/t_ops2.man','w').write(p.render()+"\n")
print(p.render())

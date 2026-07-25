import sys; sys.path.insert(0,'tools')
import littleman as lm
p = lm.Program()
p.input_room(0,0); p.output_room(4,0)
p.room(0,5,26,6)   # interior cols1-24 rows6-9
p.pipe([(1,3),(1,4)])   # IN -> (1,6)
p.pipe([(5,4),(5,3)])   # OUT from (5,6)
# read x; compute x&15 -> out ; x>>2 -> out ; divmod(x,6): q -> out, r-> out
# row6 (E): @ r M `15` W & then send. Need to route send to OUT at col5.
# Let's do sequence writing outputs by turning to a send lane.
# Simpler: do one op, send, repeat. Use serpentine.
prog = "@rM`15`W&"   # A=x&15, x saved? no. We'll just do one thing per run.
p.text(1,6,prog)
# after &, A = x&15. turn down to send: put v after
# place: at end col of prog, go down then west to (5,7) then up? OUT pipe is at (5,6) col5.
# Let's send from (5,7)->? OUT attach is (5,6) top? Actually OUT pipe end forward neighbor must be room border (5,5). So attach at (5,6). man does s adjacent... man in room at (5,7) nearest outgoing = OUT. 
# route from end of prog (col 10,row6) down to row7 then west to col5 row7, s.
p.text(10,6,"v")
p.text(5,7,"s")  # need man to reach (5,7) heading... put path
# path row7 from col10 west to col5
for c in range(6,10): p.put(c,7," ")
p.put(10,7,"<")
p.text(2,7,"H")  # halt after
open('scratchpad/t_ops.man','w').write(p.render()+"\n")
print(p.render())

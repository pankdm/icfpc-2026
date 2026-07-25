import sys, os
sys.path.insert(0, 'tools')
import littleman as lm
p = lm.Program()
# CTRL room
top=6
r = p.room(0, top, 14, 6)   # x0=0,y0=6,w=14,h=6 ; interior rows 7-10, cols 1-12
# self-loop pipe: out at col 4 (up), over to col 6, down at col 6 (in)
p.pipe([(4, top-1), (4, top-3), (6, top-3), (6, top-1)])
# man: A=5, send into self-loop, then read back into A, halt (can't output easily; just check load+run)
p.man(1,7)
p.text(1,7,"@ 5 s")   # @, space, 5->A, space, s (send). nearest outgoing = self-loop
p.text(1,8,"H   r")   # on next row after turning... need path. keep simple: 
# Actually just: @5s then turn down then r then H
open('scratchpad/t_selfloop.man','w').write(p.render()+"\n")
print(p.render())

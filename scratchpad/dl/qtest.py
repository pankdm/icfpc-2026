import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
from littleman import Program

# THE QUESTION test: one input pipe, one output pipe. Man walks EAST doing
# r/s at SUCCESSIVE separated columns. If reads pull successive FIFO values
# regardless of column -> position-independent (YES).

p = Program()
# compute room interior row = y=6, interior cols 1.. (room top-left at (0,5))
room = p.room(0, 5, 20, 4)      # outer cols 0..19, rows 5..8; interior cols1..18 rows6..7
# man path along interior row y=6, starting col1 facing east (default)
# r at 2, s at 3 ; r at 6, s at 7 ; r at 10, s at 11 ; r at 14, s at 15 ; v at 16
p.man(1, 6)
p.put(2, 6, 'r'); p.put(3, 6, 's')
p.put(6, 6, 'r'); p.put(7, 6, 's')
p.put(10, 6, 'r'); p.put(11, 6, 's')
p.put(14, 6, 'r'); p.put(15, 6, 's')
p.put(16, 6, 'v')   # turn south into wall -> crash (free after settle)

# input room I above, single pipe down into room top (attach at col 1)
p.input_room(0, 0)              # I at (1,1); room rows0..2
p.pipe([(1, 3), (1, 4)])       # I bottom (1,2) -> down, end (1,4) forward into top wall (1,5)

# output room O to the right/below; single pipe from room to O
p.output_room(0, 11)           # O at (1,12); room rows11..13
# output pipe: from compute room bottom (attach somewhere) down to O top
# start backward neighbour on compute room border, end forward neighbour on O top
p.pipe([(1, 9), (1, 10)])      # compute bottom wall (1,8); pipe start (1,9) down to (1,10)->O top (1,11)

print(p.render())
p.save(os.path.join(os.path.dirname(__file__), 'qtest.man'))

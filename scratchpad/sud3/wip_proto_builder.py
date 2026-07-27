import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys; sys.path.insert(0,_REPO + '/tools')
import littleman as lm
from layout import Layout

L = Layout()
# ================= CONTROLLER: bit = 1<<(v-1), send twice to storage =================
L.room(0,0,9,15)                      # cols0..8 rows0..14
L.put(1,1,'@')                        # start heads east
L.put(2,1,'v')                        # feeder: south (loop re-entry from west)
for y,ch in [(2,'r'),(3,'M'),(4,'1'),(5,'W'),(6,'-'),(7,'M'),(8,'1'),(9,'{'),(10,'s'),(11,'s')]:
    L.put(2,y,ch)
L.put(2,12,'>'); L.put(6,12,'^'); L.put(6,1,'<')     # loop back to feeder
# ================= STORAGE room + bit pipe =================
L.room(0,17,9,15)                     # rows17..31
L.pipe([(2,15),(2,16)])               # bit pipe ctrl->storage (south)
Sx=4
L.put(3,18,'@')                       # storage man start heads east into feeder
L.put(Sx,18,'v')                      # feeder south (loop re-entry)
for y,ch in [(19,'r'),(20,'&'),(21,'X')]:
    L.put(Sx,y,ch)
for y,ch in [(22,'r'),(23,'|'),(24,'M'),(25,'1'),(26,'s')]:   # OK path
    L.put(Sx,y,ch)
L.put(Sx,27,'>'); L.put(7,27,'^'); L.put(7,18,'<')            # loop back
# DUP path (west from X)
L.put(3,21,'0'); L.put(2,21,'s'); L.put(1,21,'H')
# ================= I/O =================
L.input_room(1,-5)                    # I at (2,-4), bottom border row-3
L.pipe([(2,-2),(2,-1)])               # input pipe -> controller top (2,0)
L.output_room(3,34)                   # O room rows34..36, O at (4,35), top border row34
L.pipe([(4,32),(4,33)])               # storage bottom -> O top
print(L.render())
print("FOOT", L.footprint())
L.save(_REPO + '/scratchpad/proto.man')

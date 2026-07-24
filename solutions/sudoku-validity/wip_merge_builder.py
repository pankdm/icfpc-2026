import sys; sys.path.insert(0,'/Users/visenbaev/icfpc26/tools')
import littleman as lm
from layout import Layout, auto_pipe
L=Layout(); occ=set()
def apipe(a,b):
    global occ
    p=auto_pipe(L,a,b,occupied=occ); occ|=set(map(tuple,p)); return p
def man_storage(x0,y0):
    L.room(x0,y0,9,13); fx=x0+2
    L.put(x0+1,y0+1,'@'); L.put(fx,y0+1,'v')
    for dy,ch in [(2,'r'),(3,'&'),(4,'s'),(5,'r'),(6,'|'),(7,'M')]:
        L.put(fx,y0+dy,ch)
    L.put(fx,y0+8,'>'); L.put(x0+6,y0+8,'^'); L.put(x0+6,y0+1,'<')
    return fx

# ===== DRIVER: read v, bit=1<<(v-1); bit->LO(col2)x2 ; 0->HI(col13,14)x2 =====
L.room(0,0,22,15)
L.put(1,1,'@'); L.put(2,1,'v')
for y,ch in [(2,'r'),(3,'M'),(4,'1'),(5,'W'),(6,'-'),(7,'M'),(8,'1'),(9,'{'),(10,'s'),(11,'s')]:
    L.put(2,y,ch)
L.put(2,12,'>'); L.put(11,12,'0'); L.put(12,12,'s'); L.put(13,12,'s')
L.put(14,12,'^'); L.put(14,1,'<')                 # up col14, west row1 -> feeder(2,1)

# ===== men =====
man_storage(0,20)      # LO, feeder col2, dup out bottom (2,32)
man_storage(10,20)     # HI, feeder col12, dup out bottom (12,32)

# ===== merger: R,M,R,| ,X ; ok->1 ; dup->0,H =====
L.room(0,36,18,13); mfx=8
L.put(1,37,'@'); L.put(mfx,37,'v')
for dy,ch in [(2,'R'),(3,'M'),(4,'R'),(5,'|'),(6,'X')]:
    L.put(mfx,37+dy,ch)
L.put(mfx,44,'1'); L.put(mfx,45,'s')              # ok path -> output
L.put(mfx,46,'>'); L.put(15,46,'^'); L.put(15,37,'<')   # loop back
L.put(mfx-1,43,'0'); L.put(mfx-2,43,'s'); L.put(mfx-3,43,'H')   # dup path (west from X@row43)

# ===== IO + pipes =====
L.input_room(1,-5)
apipe((2,-3),(2,0))            # input->driver
apipe((2,14),(2,20))          # driver->LO
apipe((12,14),(12,20))        # driver->HI
apipe((2,32),(2,36))          # LO dup->merger
apipe((12,32),(12,36))        # HI dup->merger
L.output_room(7,52)
apipe((8,48),(8,52))          # merger->O
print(L.render())
print("FOOT",L.footprint())
L.save('/private/tmp/claude-501/-Users-visenbaev-icfpc26/45d36e33-5a95-458c-9599-9b3faeeb9c09/scratchpad/merge.man')

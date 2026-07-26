import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0,_REPO + '/scratchpad')
from router import Grid
BIAS=10001
g=Grid()
g.room(0,5,18,44)                                   # P interior x1..16 y6..47
g.p.input_room(6,0); g.p.pipe([(7,3),(7,4)])
g.p.room(30,20,6,6)
g.p.pipe([(18,22),(29,22)]); g.p.pipe([(29,23),(18,23)])
g.p.man(31,22)
for (x,y,c) in [(32,22,'>'),(33,22,'r'),(34,22,'v'),(32,23,'^'),(33,23,'s'),(34,23,'<')]: g.p.put(x,y,c)
g.p.output_room(3,51); g.p.pipe([(4,49),(4,50)])
g.commit_program_cells()
INC={'input':(7,4),'recv':(18,23)}; OUT={'send':(18,22),'out':(4,49)}
rs=[]
def P(x,y,ch):
    g.put(x,y,ch)
    if ch in 'rs': rs.append((x,y,ch))
def RUN(x,y,s):
    for i,c in enumerate(s): P(x+i,y,c)

# READ + marker
P(1,6,'@'); P(2,6,'>'); P(3,6,'v'); P(3,7,'r'); P(3,8,'b'); P(3,9,'v'); P(3,10,'a')
RUN(4,10,'rM'); RUN(6,10,'`10001`'); P(13,10,'+'); P(14,10,'s'); P(15,10,'^'); P(15,9,'<'); P(14,9,'m')
for x in range(4,14): g.straight.add((x,9))
P(3,11,'1'); P(3,12,'N')
P(13,11,'s')                                         # SEND marker

# INIT vertical col16
P(16,12,'v')
for i,c in enumerate('`30000`'): P(16,13+i,c)
P(16,20,'M')                                         # exit S(16,21)

# FINDMIN  (4-cell feeder stack; each loopback its own row from W)
P(12,13,'v'); P(12,14,'v'); P(12,15,'v'); P(12,16,'v')   # noupd1->13 noupd2->14 upd->15 INIT->16 (all from W)
P(12,17,'r'); P(12,18,'X')                           # markertest S: data W(11,18); marker E(13,18)
P(11,18,'s'); P(10,18,'-'); P(9,18,'X')              # resend; A=v-min; cmp W
P(9,19,'+'); P(9,20,'M')                             # UPD exit S(9,21)
# cmp exits: v>min N(9,17)=noupd1; v<min S(9,19)=UPD; v==min W(8,18)=noupd2

# RM (findmin has-data) near ring
RUN(13,24,'1N'); P(15,24,'s')

# EMIT  (4-cell feeder stack)
P(12,26,'v'); P(12,27,'v'); P(12,28,'v'); P(12,29,'v')   # R1->26 R2->27 OUTPUT->28 RM->29 (from W)
P(12,30,'r'); P(12,31,'X')                           # markertest S: data W(11,31); marker E(13,31)
P(11,31,'-'); P(10,31,'X')                           # cmp W: v>t N(10,30); v<t S(10,32); v==t W(9,31)=EMIT-OUT
P(10,30,'+'); P(10,29,'s')                           # R1 exit N(10,28)
P(10,32,'+'); P(10,33,'s')                           # R2 exit S(10,34)

# RM2 (emit marker) near ring
RUN(13,34,'1N'); P(15,34,'s')

# MARKER/empty (bottom-left, clear)
P(1,40,'>'); RUN(2,40,'`30000`'); P(9,40,'-'); P(10,40,'X')   # X E: has-data S(10,41); empty E(11,40)
# EMIT-OUT
P(1,37,'>'); P(2,37,'+'); P(3,37,'M'); RUN(4,37,'`10001`'); P(11,37,'W'); P(12,37,'-')   # exit E(13,37)
# OUTPUT-S near bottom
P(5,44,'s'); P(6,44,'+'); P(7,44,'M')                # exit E(8,44)

# ROUTES
_n=[0]
def R(*a,b=None):
    _n[0]+=1
    try: return g.route(*a,bound=b)
    except SystemExit as e:
        print(f"--- FAIL route #{_n[0]}: {a}")
        for yy in range(12,21):
            row=''.join((g.g.get((xx,yy)) or ('+' if (xx,yy) in g.straight else '.')) for xx in range(6,15))
            print(f"  y{yy} x6: {row}")
        sys.exit(1)
R((3,12),'S',(13,11),'E',b=(2,11,14,13))     #1 READ-marker -> SEND
R((13,11),'E',(16,12),'E',b=(12,9,17,13))    #2 SEND -> INIT MI (W)
R((9,18),'N',(12,13),'S')                    #3 noupd1 -> stack13 (N)
R((9,18),'W',(12,14),'E')                    #4 noupd2 -> stack14 (W)
R((9,20),'S',(12,15),'W')                    #5 upd -> stack15 (E)
R((16,20),'S',(12,16),'E')                   #6 INIT -> stack16 (W)
R((12,18),'E',(1,40),'S')                    #7 FM-marker -> MARKER
R((10,41),'S',(13,24),'E')                   #8 has-data -> RM
R((11,40),'E',(2,6),'N')                     #9 empty -> READ
R((10,29),'N',(12,26),'E')                   #10 R1 -> stack26 (W)
R((10,34),'S',(12,27),'E')                   #11 R2 -> stack27 (W)
R((8,44),'E',(12,28),'E')                    #12 OUTPUT-S -> stack28 (W)
R((15,24),'E',(12,29),'E')                   #13 RM -> stack29 (W)
R((12,31),'E',(13,34),'E')                   #14 EMIT-marker -> RM2
R((15,34),'E',(16,12),'S')                   #15 RM2 -> INIT MI (N)
R((10,31),'W',(1,37),'S')                    #16 EMIT-OUT
R((13,37),'E',(5,44),'E')                    #17 EMIT-OUT -> OUTPUT-S

def near(cell,c):
    x,y=cell;best=None;bd=1e9
    for n,(px,py) in c.items():
        d=abs(x-px)+abs(y-py)
        if d<bd:bd=d;best=n
    return best,bd
for (x,y,ch) in rs:
    n,d=near((x,y),INC if ch=='r' else OUT); print(f"  {ch}@({x},{y})->{n}(d={d})")
g.p.save(_REPO + '/scratchpad/sortG.man')
print(g.p.render()); print('fp',g.p.footprint())

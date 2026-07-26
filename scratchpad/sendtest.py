"""4-cell H-tree SEND test: each leaf sends [mode,val]; cell does r r M (store val in B).
Cells placed outside decoder on the nearer wall side. Verify correct cell gets value."""
import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
from layout import Layout

WV=[8]; WH=[8]; R0=16; XV=[14]; XH0=18; RG=2
def band_row(low): return R0 + (WV[0] if low&1 else -WV[0])
def leaf_col(high): return XH0 + (-WH[0] if high&1 else WH[0])
def mouth(a):
    low=a&1; high=(a>>1)&1
    return leaf_col(high), band_row(low)+RG

L=Layout()
dtop=R0-WV[0]-3; dbot=max(mouth(a)[1] for a in range(4))+8
dleft=0; dright=XH0+WH[0]+6
L.room(dleft,dtop,dright-dleft+1,dbot-dtop+1)
L.input_room(-5,R0-1); L.pipe([(-2,R0),(-1,R0)])
# parse (fixed 3-token for this test): @ > r M r b r  -> A=val,B=mode,BP=addr
L.put(1,R0,'@');L.put(2,R0,'>');L.put(3,R0,'r');L.put(4,R0,'M');L.put(5,R0,'r');L.put(6,R0,'b');L.put(7,R0,'r')
CJ=XV[0]-2; L.put(CJ,R0,'>')

def node_v(level,col,row):
    L.put(col,row,'x')
    for bit in (1,0):
        sign=+1 if bit==1 else -1
        L.put(col,row+sign,']')
        corner=row+sign*WV[level]
        L.put(col,corner,'>')
        L.put(XH0,corner,'v'); node_h(0,XH0,corner+1)
def node_h(level,col,row):
    L.put(col,row,'x')
    for bit in (1,0):
        sign=-1 if bit==1 else +1
        corner=col+sign*WH[level]
        L.put(corner,row,'v')
        leaf(corner,row+1)
def leaf(col,row):
    L.put(col,row,'W');L.put(col,row+1,'s');L.put(col,row+2,'W');L.put(col,row+3,'s')
    L.put(col,row+4,'v')
node_v(0,XV[0],R0)
# return rail
railrow=dbot-1
for a in range(4):
    c,_=mouth(a); L.put(c,railrow,'<')
L.put(2,railrow,'^')  # up col2 to (2,R0)? need col2 clear; (2,R0)='>' already
# but loop must re-enter at r(mode) col3. (2,R0)='>' -> east -> col3 r. good.

# cells: ALL on EAST at DISTINCT rows (test same-row-leaf ambiguity).
# assign each addr a distinct east-wall attach row.
attach_row={0:band_row(0), 2:band_row(0)+3, 1:band_row(1), 3:band_row(1)+3}
cellrooms={}
for a in range(4):
    row=attach_row[a]
    cx=dright+3
    L.room(cx,row-1,7,3)
    L.put(cx+1,row,'@');L.put(cx+2,row,'>');L.put(cx+3,row,'r');L.put(cx+4,row,'r');L.put(cx+5,row,'M')
    L.pipe([(dright+1,row),(dright+2,row)])
    cellrooms[a]=(cx+1,row)
print(L.render())
print('FOOT',L.footprint())
print('mouths',{a:mouth(a) for a in range(4)})
print('cellrooms',cellrooms)
L.save(_REPO + '/scratchpad/sendtest.man')

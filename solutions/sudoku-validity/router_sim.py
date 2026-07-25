"""Simulate the serpentine router HEIGHT for a given op stream + column map, to
compare controller-layout compactness of the 1-ring vs 3-ring designs.

Router model: man snakes E/W across columns [XL..XR]. Each pipe-op must land on its
pipe's column; if the target is 'behind' the heading, wrap to next row. Non-pipe ops
placed at current cell advancing 1. Count rows used = controller height.
"""
import importlib.util, sys
sys.path.insert(0,'/Users/visenbaev/icfpc26/tools')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def sim_height(prog, target_of, XL, XR):
    x, y, d = XL, 0, 'E'
    def wrap():
        nonlocal x, y, d
        if d=='E': x=XR; y+=1; x=XR-1; d='W'   # v at XR,y-1 then < ; land XR-1
        else: x=XL; y+=1; x=XL+1; d='E'
    for op in prog:
        T = target_of(op)
        if T is not None:
            guard=0
            while x!=T:
                guard+=1; assert guard<10000
                if d=='E':
                    if T>x: x+=1
                    else: wrap()
                else:
                    if T<x: x-=1
                    else: wrap()
        else:
            if d=='E' and x>XR: wrap()
            if d=='W' and x<XL: wrap()
        # place op at x, advance
        if d=='E':
            x+=1
            if x>XR: wrap()
        else:
            x-=1
            if x<XL: wrap()
    return y+1

# ---- 1-ring ----
m1 = load('/Users/visenbaev/icfpc26/solutions/sudoku-validity/ctrl_onering.py','m1')
p1 = m1.build_dispatch()
cols1 = dict(rIN=2, rS=4, sS=6, sD=8)  # I, ret, feed, dispatch (all south)
def t1(op):
    k = op if isinstance(op,str) else op[0]
    return cols1.get(k, None)
for W in (10,12,14,16,20):
    print('1-ring W',W,'height', sim_height(p1, t1, 1, W-2), 'ops', len(p1))

# ---- 3-ring (ctrl_opstream) in dispatch form ----
m3 = load('/Users/visenbaev/icfpc26/solutions/sudoku-validity/ctrl_opstream.py','m3')
p3raw = m3.controller()
# convert: OUT sinks -> 'sD'; ring ops sIDX/rIDX/sVR/rVR/sT/rT/rIN
SINKS3 = {'rowLo','rowHi','colLo','colHi','boxLo','boxHi'}
p3 = []
for op in p3raw:
    if isinstance(op,str) and op in SINKS3: p3.append('sD')
    else: p3.append(op)
# assign columns: rIN, and each ring's r/s share a column (opposite-wall same col not
# used here; use distinct cols per r/s). Actually give each ring ONE column (r and s
# both there is impossible on one wall). Give r and s of a ring adjacent columns.
cols3 = dict(rIN=2, sIDX=4, rIDX=5, sVR=7, rVR=8, sT=10, rT=11, sD=13)
def t3(op):
    k = op if isinstance(op,str) else op[0]
    return cols3.get(k, None)
def npipe(prog, tof):
    return sum(1 for op in prog if tof(op) is not None)
print('3-ring ops', len(p3raw), 'pipe-ops', npipe(p3, t3))
print('1-ring ops', len(p1), 'pipe-ops', npipe(p1, t1))
for W in (16,18,20,24):
    print('3-ring W',W,'height', sim_height(p3, t3, 1, W-2))

"""Build solutions/sudoku-validity/multi.man — compact multi-man validator.

Topology (data flows DOWNWARD):
  CONTROLLER (1 man, 1 scratch ring; emits 6 values/round down ONE dispatch pipe)
     -> DISPATCHER (scratch-free: read value, send TWICE to man-k)
        -> 6 STORAGE men (mask permanently in B; loop  r & s r | M)
           -> MERGER (R-reads 6 dups, ORs; dup>0 -> out 0 + H ; else out 1)
              -> O

All 4 controller pipes are on its SOUTH wall (cI input, cR ring-return, cF ring-feed,
cD dispatch-out). With every pipe on one wall, "nearest pipe" is column-only: an op
placed exactly at its pipe's column is nearest that pipe at any row. The controller
op-stream is laid as a boustrophedon serpentine gliding each pipe-op to its column.
"""
import sys, importlib.util
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout, auto_pipe, place_pipe, DIRS

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m
ctrl = load('/Users/visenbaev/icfpc26/solutions/sudoku-validity/ctrl_onering.py','ctrl')

def glyph_of(op):
    k = op if isinstance(op, str) else op[0]
    if k == 'rIN': return 'r'          # recv_nearest at col I (input)
    if k == 'rS':  return 'R'          # recv_any: during compute only the ring is ready
    if k in ('sS','sD'): return 's'
    if k == 'c': return str(op[1])
    if k in ('M','W','+','-','*','&','|','{','/'): return k
    raise ValueError(f'no glyph for {op}')

# ---------------------------------------------------------------------------
# Serpentine layout of the controller op-stream. Returns dict cells, extents,
# man-start, loopback endpoint, and the 4 south-wall attach columns.
# ---------------------------------------------------------------------------
def lay_controller(prog, cols, XL=1, W=12):
    """cols=dict(I=,R=,F=,D=) relative columns (interior). Serpentine within [XL..XR].
    Reserves row1 (top rail) + col W-2 (right riser) for the loop-back; feeder @/v/>
    at top-left. Returns cells + dims; all pipe-ops land on their south-wall column."""
    XR = W-3   # reserve col W-2 as the loop-back riser
    RISER = W-2
    cells = {}
    def put(x,y,g):
        if g==' ':
            cells.setdefault((x,y),' '); return
        if (x,y) in cells and cells[(x,y)] not in (' ',g):
            raise SystemExit(f'ctrl collision {(x,y)} {cells[(x,y)]} vs {g}')
        cells[(x,y)] = g
    def target(op):
        k = op if isinstance(op,str) else op[0]
        # rS uses R (recv_any) -> column-FREE; only rIN/sS/sD are column-disciplined.
        return {'rIN':cols['I'],'sS':cols['F'],'sD':cols['D']}.get(k)
    # placeable op columns: [XL .. XR-1] heading E ; [XL+1 .. XR] heading W.
    # Turn columns XR (E-row end) and XL (W-row end) hold only turn glyphs.
    # Feeder re-entry: @ (XL,1) -> 'v'(XL+1,1) [loop merge] -> '>'(XL+1,2) -> row2 E.
    put(XL,1,'@'); put(XL+1,1,'v'); put(XL+1,2,'>')
    x,y,d = XL+2,2,'E'
    def adv():
        nonlocal x
        x += 1 if d=='E' else -1
    def wrap():
        nonlocal x,y,d
        if d=='E':
            while x<XR: put(x,y,' '); x+=1
            put(XR,y,'v'); y+=1; put(XR,y,'<'); x=XR-1; d='W'
        else:
            while x>XL: put(x,y,' '); x-=1
            put(XL,y,'v'); y+=1; put(XL,y,'>'); x=XL+1; d='E'
    def can_place():
        return (d=='E' and x<=XR-1) or (d=='W' and x>=XL+1)
    for op in prog:
        T = target(op)
        if T is not None:
            g=0
            while x!=T:
                g+=1; assert g<10000, 'route stuck'
                if d=='E':
                    if x<T and T<=XR-1: put(x,y,' '); x+=1
                    else: wrap()
                else:
                    if x>T and T>=XL+1: put(x,y,' '); x-=1
                    else: wrap()
        if not can_place(): wrap()
        put(x,y,glyph_of(op)); adv()
    endx,endy,endd = x,y,d
    maxrow = max(yy for (_,yy) in cells)
    # ---- loop-back: end -> down to lane -> east to RISER -> up to row1 -> west to merge 'v'(XL+1,1)
    lane = maxrow + 1
    put(endx, endy, 'v')
    for yy in range(endy+1, lane): put(endx, yy, ' ')
    # along lane east to RISER
    put(endx, lane, '>')
    for xx in range(endx+1, RISER): put(xx, lane, ' ')
    put(RISER, lane, '^')
    for yy in range(lane-1, 1, -1): put(RISER, yy, ' ')
    put(RISER, 1, '<')
    for xx in range(RISER-1, XL+1, -1): put(xx, 1, ' ')   # west along row1 to merge (XL+1,1)='v'
    maxrow = max(yy for (_,yy) in cells)
    return dict(cells=cells, endx=endx, endy=endy, endd=endd, maxrow=maxrow, XL=XL, XR=XR, W=W)

# ---------------------------------------------------------------------------
def place_controller(L, prog, cols, W):
    lay = lay_controller(prog, cols, XL=1, W=W)
    Hroom = lay['maxrow'] + 2
    L.room(0, 0, W, Hroom)
    for (x,y),g in lay['cells'].items():
        if g==' ': continue
        L.put(x, y, g)
    return Hroom   # south wall row = Hroom-1

def relay(L, x, y, recv='R'):
    """4x2 relay man at (x,y): @ > R v / ^ s <  (recv value, send it on)."""
    L.put(x,y,'@'); L.put(x+1,y,'>'); L.put(x+2,y,recv); L.put(x+3,y,'v')
    L.put(x+1,y+1,'^'); L.put(x+2,y+1,'s'); L.put(x+3,y+1,'<')

def vpipe(L, col, y_srcwall, y_dstwall):
    """Straight vertical pipe between two room-wall rows on `col`."""
    if y_dstwall > y_srcwall:            # going down
        L.pipe([(col, y_srcwall+1), (col, y_dstwall-1)])
    else:                                # going up
        L.pipe([(col, y_srcwall-1), (col, y_dstwall+1)])

def stage1():
    """Controller + ring relay + I room; dispatch routed straight to O."""
    prog = ctrl.build_dispatch()
    L = Layout()
    W = 15
    cols = dict(I=2, R=5, F=7, D=10)
    Hroom = place_controller(L, prog, cols, W)
    sw = Hroom-1
    # I room directly below col2, straight pipe up
    iwall = sw+4
    L.input_room(cols['I']-1, iwall)            # I at (col2, iwall+1); top border row iwall
    vpipe(L, cols['I'], iwall, sw)              # I top (2,iwall) -> controller (2,sw)
    # relay below cols5(return)/7(feed)
    rwall = sw+3
    L.room(4, rwall, 6, 4)                       # cols4-9 rows rwall..rwall+3
    relay(L, 5, rwall+1)                         # @ > R v / ^ s <  at row rwall+1/+2
    vpipe(L, cols['F'], sw, rwall)              # feed: controller(7,sw)-> relay top(7,rwall)
    vpipe(L, cols['R'], rwall, sw)              # return: relay top(5,rwall)-> controller(5,sw)
    # dispatch -> O (straight down)
    owall = sw+8
    L.output_room(cols['D']-1, owall)
    vpipe(L, cols['D'], sw, owall)
    print(L.render())
    print('FOOT', L.footprint())
    L.save('/private/tmp/claude-501/-Users-visenbaev-icfpc26/45d36e33-5a95-458c-9599-9b3faeeb9c09/scratchpad/stage1.man')

def build_dispatcher(L, x0, y0, W, mcols):
    """Scratch-free dispatcher: R (read value) then s s (send twice) per man column.
    Room (x0,y0,W,4). North wall gets the dispatch input pipe; south wall sends to men
    at absolute columns mcols. Returns south-wall row."""
    L.room(x0, y0, W, 4)
    tr, st = y0+1, y0+2                       # toprail row, station row
    riser = x0+W-2
    L.put(x0+1, tr, '@'); L.put(x0+2, tr, 'v'); L.put(x0+2, st, '>')
    # stations on row st
    for f in mcols:
        L.put(f-1, st, 'R'); L.put(f, st, 's'); L.put(f+1, st, 's')
    # loop back: from last station glide E to riser, ^ up, < west along toprail to merge
    L.put(riser, st, '^'); L.put(riser, tr, '<')
    return y0+3

def man_storage(L, f, y0):
    """Storage man, feeder col f, room (f-2,y0,5,10). Mask lives in B; loop r & s r | M.
    bit enters north (f,y0); dup exits south (f,y0+9)."""
    L.room(f-2, y0, 5, 10)
    L.put(f-1, y0+1, '@'); L.put(f, y0+1, 'v'); L.put(f+1, y0+1, '<')
    for dy,ch in [(2,'r'),(3,'&'),(4,'s'),(5,'r'),(6,'|'),(7,'M')]:
        L.put(f, y0+dy, ch)
    L.put(f, y0+8, '>'); L.put(f+1, y0+8, '^')

def build_merger(L, x0, y0, W):
    """FLAT merger spanning W wide (receives 6 dup pipes on north wall). A horizontal
    OR row does R (M R |)*5 = OR of 6 dups (R=recv_any, position-free), then X:
      A==0 (ok, straight E)  -> 1 ; s->O ; loop back
      A>0  (dup, CW=South)   -> 0 ; s->O ; H
    Output 's' -> O on the south wall (col = ocol, returned). Room is 7 tall."""
    H = 7
    L.room(x0, y0, W, H)
    tr, st = y0+1, y0+2
    L.put(x0+1, tr, '@'); L.put(x0+2, tr, 'v'); L.put(x0+2, st, '>')
    ops = ['R','M'] + ['R','|','M']*4 + ['R','|']
    x = x0+3
    for ch in ops:
        L.put(x, st, ch); x += 1
    L.put(x, st, 'X'); xc = x
    # ok (straight E): 1 ; s(->O) ; loop back to merge via riser
    L.put(xc+1, st, '1'); L.put(xc+2, st, 's'); ocol = xc+2
    riser = xc+4
    L.put(riser, st, '^'); L.put(riser, tr, '<')     # loop east->riser->up->west along toprail
    # dup (CW South): 0 ; s(->O) ; H
    L.put(xc, st+1, '0'); L.put(xc, st+2, 's'); L.put(xc, st+3, 'H')
    return H, y0+H-1, ocol

def build_full():
    prog = ctrl.build_dispatch()
    L = Layout()
    W = 16
    cols = dict(I=2, R=5, F=7, D=10)
    Hroom = place_controller(L, prog, cols, W)
    sw = Hroom-1
    # I room + relay in band A
    iwall = sw+4
    L.input_room(cols['I']-1, iwall); vpipe(L, cols['I'], iwall, sw)
    rwall = sw+3
    L.room(4, rwall, 6, 4); relay(L, 5, rwall+1)
    vpipe(L, cols['F'], sw, rwall); vpipe(L, cols['R'], rwall, sw)
    # dispatcher
    mcols = [4,10,16,22,28,34]
    DW = mcols[-1]+4                    # room wide enough for riser
    DY = sw+8
    dsw = build_dispatcher(L, 0, DY, DW, mcols)     # north wall = DY
    vpipe(L, cols['D'], sw, DY)                      # dispatch pipe controller->dispatcher
    # men
    MY = dsw+3
    for f in mcols:
        man_storage(L, f, MY); vpipe(L, f, dsw, MY)   # bit pipe dispatcher->man
    men_sw = MY+9
    # merger (wide enough to receive all 6 dup pipes on its north wall)
    MGY = men_sw+3
    mh, msw, ocol = build_merger(L, 0, MGY, DW)
    for f in mcols:
        vpipe(L, f, men_sw, MGY)                       # dup pipes men->merger
    # O below merger, fed from merger output col
    OY = msw+3
    L.output_room(ocol-1, OY); vpipe(L, ocol, msw, OY)
    print(L.render())
    print('FOOT', L.footprint())
    L.save('/Users/visenbaev/icfpc26/solutions/sudoku-validity/multi.man')
    return L

if __name__ == '__main__':
    build_full()

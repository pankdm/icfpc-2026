import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# Prototype: 4-cell value tape. Loader reads 4 input values, distributes v_i to
# storage_i. Head walks left->right, reads each v_i and sends to O. Output should
# equal the 4 input values in order -> proves load + walking-read mechanism.

N = 4
GAP = 6  # storage columns spaced GAP apart

def build():
    p = lm.Program(); placed = {}
    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]} vs {ch}")
        placed[(x, y)] = ch; p.put(x, y, ch)
    def room(x,y,w,h,g="+-|"):
        r=p.room(x,y,w,h,g)
        # record room cells (overwrite ok; rooms are pre-validated shapes)
        for i in range(w):
            placed[(x+i,y)]=p.get(x+i,y); placed[(x+i,y+h-1)]=p.get(x+i,y+h-1)
        for j in range(h):
            placed[(x,y+j)]=p.get(x,y+j); placed[(x+w-1,y+j)]=p.get(x+w-1,y+j)
        return r

    read_cols = [2 + GAP*i for i in range(N)]   # 2,8,14,20

    # ---- LOADER room (top), interior row LROW ----
    LX0 = 0; LX1 = read_cols[-1] + 3
    LY = 0
    room(LX0, LY, LX1-LX0+1, 3)
    LROW = LY+1
    p.man(LX0+1, LROW)                    # @ at (1,LROW), initial dir = East
    for c in read_cols:
        C(c, LROW, 'r')                  # read next input value into A
        C(c+1, LROW, 's')                # send down to storage at this col
    C(LX1-1, LROW, 'H')                  # halt (never crash a loader)

    # ---- STORAGE rooms (middle), 5 wide x 4 tall, r/w column at c ----
    SY = 6
    for c in read_cols:
        X = c-2
        room(X, SY, 5, 4)
        C(X+1, SY+1, '@'); C(X+2, SY+1, 'r'); C(X+3, SY+1, 'v')
        C(X+1, SY+2, '>'); C(X+2, SY+2, 's'); C(X+3, SY+2, '<')

    # ---- HEAD room (bottom), interior row HROW ----
    HY = 12
    HX0 = 0; HX1 = read_cols[-1] + 4
    room(HX0, HY, HX1-HX0+1, 3)
    HROW = HY+1
    p.man(HX0+1, HROW)                    # @ initial dir East
    for c in read_cols:
        C(c, HROW, 'r')                  # read v_i
        C(c+1, HROW, 's')                # send to O

    # ---- I room -> loader (input pipe), 2-cell gap on the west ----
    p.input_room(-5, LROW-1)             # I cols -5..-3, interior (-4,LROW)
    p.pipe([(-2, LROW), (-1, LROW)])     # start bk-nb (-3)=I border; end fwd-nb (0)=loader border

    # ---- loader -> storage down pipes (rows 3,4,5) ----
    for c in read_cols:
        p.pipe([(c, LY+3), (c, SY-1)])   # (c,3)->(c,5); bk-nb (c,2) loader; fwd-nb (c,6) storage

    # ---- storage -> head down pipes (rows 10,11) ----
    for c in read_cols:
        p.pipe([(c, SY+4), (c, HY-1)])   # (c,10)->(c,11); bk-nb (c,9) storage; fwd-nb (c,12) head

    # ---- head -> O (output) ----
    p.output_room(HX1+3, HROW-1)         # O to the right, 2-cell gap
    p.pipe([(HX1+1, HROW), (HX1+2, HROW)])

    return p, placed

if __name__ == '__main__':
    p,_ = build()
    txt = p.render()
    print(txt)
    print('footprint', p.footprint())
    p.save(_REPO + '/scratchpad/ss_proto.man')

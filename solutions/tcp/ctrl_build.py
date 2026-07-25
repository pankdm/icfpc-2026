"""Lay the validated op_stream as geometry -> tcp-ram.man.
Controller: tall room; 6 pipes on TOP wall (column discipline):
 INPUT(in)=4  CMD(out)=10  WF(out)=16  WR(in)=22  FF(out)=28  FR(in)=34.
Blocks laid as E-rows; each pipe op ends its row; branches via v+X; gotos routed
on col1 risers / a west return column.
"""
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
from layout import Layout, route
from driver_mod import build_driver
from storage_mod import build_storage
from op_stream import program, LOADW, STOREW, LOADF, STOREF

def rte(L, pts):
    clean = [pts[0]]
    for p in pts[1:]:
        if p != clean[-1]:
            clean.append(p)
    if len(clean) >= 2:
        route(L, clean)

cIN, cCMD, cWF, cWR, cFF, cFR = 4, 10, 16, 22, 28, 34
PIPECOL = {'r': cIN, 'sCMD': cCMD, 'sWF': cWF, 'rWR': cWR, 'sFF': cFF, 'rFR': cFR}
PIPECH = {'r': 'r', 'sCMD': 's', 'sWF': 's', 'rWR': 'r', 'sFF': 's', 'rFR': 'r'}
Ctop = 30
CWID = 42

def build():
    L = Layout()
    cmd_pt, o_attach, _ = build_driver(L, 4, 70, Ctop + 4)
    Cbot = Ctop + 160
    L.room(0, Ctop, CWID + 1, Cbot - Ctop + 1)
    # input room above cIN
    L.input_room(cIN - 1, Ctop - 4)
    L.pipe([(cIN, Ctop - 2), (cIN, Ctop - 1)])
    # cmd pipe top wall cCMD -> driver
    dx, dy = cmd_pt
    L.pipe([(cCMD, Ctop - 1), (cCMD, Ctop - 8), (dx - 1, Ctop - 8), (dx - 1, dy)])
    # storage men above-right; wire pipes with distinct cols/rows (no crossings)
    Wy, Fy = Ctop - 14, Ctop - 30
    W_in, W_out = build_storage(L, 52, Wy)     # W_in=(52,Wy) west, W_out=(62,Wy) east
    F_in, F_out = build_storage(L, 52, Fy)
    # WF: ctrl top cWF -> up col16 -> row Wr1 -> col50 -> W_in.  each pipe its own vert col & row.
    L.pipe([(cWF, Ctop - 1), (cWF, Wy), (W_in[0] - 1, Wy)])                       # 16 up, east to W west
    L.pipe([(W_out[0] + 1, Wy), (W_out[0] + 2, Wy), (W_out[0] + 2, Ctop - 4), (cWR, Ctop - 4), (cWR, Ctop - 1)])
    L.pipe([(cFF, Ctop - 1), (cFF, Fy), (F_in[0] - 1, Fy)])                       # 28 up, east to F west
    L.pipe([(F_out[0] + 1, Fy), (F_out[0] + 3, Fy), (F_out[0] + 3, Ctop - 2), (cFR, Ctop - 2), (cFR, Ctop - 1)])
    # O
    ox, oy = o_attach
    L.output_room(ox - 1, oy + 3)
    L.pipe([(ox, oy + 1), (ox, oy + 2)])

    # ---- lay op-stream ----
    P = program()
    order = ['INIT', 'MAIN', 'CONT', 'DRAIN', 'BODY', 'HALT']
    head = {}
    pending = []   # (kind, from_xy, targets/label)
    y = Ctop + 2
    RETC = CWID - 2    # west?? we use col1 heads; risers use col2

    def down(fx, fy, ty):
        route(L, [(fx, fy), (fx, fy + 1), (2, fy + 1), (2, ty)])
        L.put(1, ty, '>')

    def expand(tokens):
        out = []
        for t in tokens:
            out.append(t)
        return out

    for lab in order:
        toks = P[lab]
        head[lab] = y
        L.put(1, y, '@' if lab == 'INIT' else '>')
        if lab == 'INIT':
            L.put(2, y, '>')
        x = 2
        buf_x = x
        cur_y = y
        def newrow(cur_y, endx):
            ny = cur_y + 2
            route(L, [(endx, cur_y), (endx, cur_y + 1), (2, cur_y + 1), (2, ny)])
            L.put(1, ny, '>')
            return ny, 2
        i = 0
        # process tokens, splitting rows on pipe ops / control
        xx = 3 if lab == 'INIT' else 2
        yy = y
        for t in toks:
            if isinstance(t, tuple) and t[0] == 'lit':
                L.put(xx, yy, '`'); xx += 1
                for ch in str(t[1]): L.put(xx, yy, ch); xx += 1
                L.put(xx, yy, '`'); xx += 1
            elif isinstance(t, tuple) and t[0] == 'goto':
                pending.append(('goto', (xx, yy), t[1]))
                break
            elif isinstance(t, tuple) and t[0] == 'br':
                # v + X at (xx,yy),(xx,yy+1); route 3 exits
                L.put(xx, yy, 'v'); L.put(xx, yy + 1, 'X')
                pending.append(('br', (xx, yy + 1), (t[1], t[2], t[3])))
                break
            elif t == 'H':
                L.put(xx, yy, 'H'); break
            elif t.startswith('c') and t[1:].isdigit():
                L.put(xx, yy, t[1:]); xx += 1
            elif t in PIPECOL:
                col = PIPECOL[t]
                if xx > col:   # need a fresh row (can't go back)
                    yy, xx = newrow(yy, xx)
                while xx < col: xx += 1
                L.put(col, yy, PIPECH[t]); xx = col + 1
                # end row after a pipe op
                yy, xx = newrow(yy, xx)
            else:
                L.put(xx, yy, t); xx += 1
        y = yy + 4   # gap before next block
    # wire pending gotos/branches, each on its own highway column near the east
    hw = CWID - 2
    def goto_route(fx, fy, ty, col):
        # from (fx,fy): down 1, east to col, vertical to ty, west to head '>'
        rte(L, [(fx, fy), (fx, fy + 1), (col, fy + 1), (col, ty), (1, ty)])
    for kind, frm, tgt in pending:
        if kind == 'goto':
            fx, fy = frm
            goto_route(fx, fy, head[tgt], hw); hw -= 2
        else:  # br from X at (xX,yX) heading S: CW(>0)=W, straight(==0)=S, CCW(<0)=E
            gt, eq, lt = tgt
            xX, yX = frm
            goto_route(xX - 1, yX, head[gt], hw); hw -= 2       # gt: CW->W exit
            goto_route(xX, yX + 1, head[eq], hw); hw -= 2       # eq: straight S exit
            goto_route(xX + 1, yX, head[lt], hw); hw -= 2       # lt: CCW->E exit
    return L

if __name__ == '__main__':
    L = build()
    L.save('/Users/visenbaev/icfpc26/scratchpad/tcp_ram.man')
    print('saved. foot', L.footprint())

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

cIN, cCMD, cWF, cWR, cFF, cFR, cLF, cLR = 4, 10, 16, 22, 28, 34, 40, 46
PIPECOL = {'r': cIN, 'sCMD': cCMD, 'sWF': cWF, 'rWR': cWR, 'sFF': cFF, 'rFR': cFR, 'sLF': cLF, 'rLR': cLR}
PIPECH = {'r': 'r', 'sCMD': 's', 'sWF': 's', 'rWR': 'r', 'sFF': 's', 'rFR': 'r', 'sLF': 's', 'rLR': 'r'}
Ctop = 30
CWID = 68

def build_const15(L, cx, sy):
    """Self-serving const-15 man: loop r `15` s (its backtick is isolated here).
    IN (trigger) and OUT (reply 15) attach the BOTTOM wall at cols cLF, cLR."""
    L.room(cx, sy - 1, 12, 4)                 # interior rows sy, sy+1 ; bottom wall sy+2
    L.put(cx + 1, sy, '@'); L.put(cx + 2, sy, '>'); L.put(cx + 3, sy, 'r')
    L.put(cx + 4, sy, '`'); L.put(cx + 5, sy, '1'); L.put(cx + 6, sy, '5'); L.put(cx + 7, sy, '`')
    L.put(cx + 8, sy, 's'); L.put(cx + 9, sy, 'v')
    L.put(cx + 2, sy + 1, '^'); L.put(cx + 9, sy + 1, '<')

def build():
    L = Layout()
    cmd_pt, o_attach, _ = build_driver(L, 4, 80, Ctop + 4)
    Cbot = Ctop + 160
    L.room(0, Ctop, CWID + 1, Cbot - Ctop + 1)
    # input room above cIN
    L.input_room(cIN - 1, Ctop - 5)
    L.pipe([(cIN, Ctop - 2), (cIN, Ctop - 1)])
    # cmd pipe top wall cCMD -> up above storage men -> down a lane 5 cols off the
    # driver wall -> short east stub into the driver (avoid wall-adjacency spurious attach)
    dx, dy = cmd_pt
    lane = dx - 5
    L.pipe([(cCMD, Ctop - 1), (cCMD, Ctop - 9), (lane, Ctop - 9), (lane, dy), (dx - 1, dy)])
    # storage men just above the controller; BOTH pipes attach the man's BOTTOM wall
    # -> all 4 storage pipes are short straight verticals in distinct columns (no crossings).
    Wsy = Ctop - 7                          # man interior rows Wsy..Wsy+3; bottom wall Wsy+4=Ctop-3
    build_storage(L, cWF - 2, Wsy)          # W-man cols 14..24 ; in@cWF=16 out@cWR=22 on bottom wall
    build_storage(L, cFF - 2, Wsy)          # F-man cols 26..36 ; in@cFF=28 out@cFR=34
    # WF: ctrl top col16 UP into W-man bottom
    L.pipe([(cWF, Ctop - 1), (cWF, Ctop - 2)])
    # WR: W-man bottom col22 DOWN into ctrl top
    L.pipe([(cWR, Ctop - 2), (cWR, Ctop - 1)])
    L.pipe([(cFF, Ctop - 1), (cFF, Ctop - 2)])
    L.pipe([(cFR, Ctop - 2), (cFR, Ctop - 1)])
    # const-15 man (bottom-wall pipes at cLF/cLR)
    build_const15(L, 38, Ctop - 5)
    L.pipe([(cLF, Ctop - 1), (cLF, Ctop - 2)])
    L.pipe([(cLR, Ctop - 2), (cLR, Ctop - 1)])
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

    def expand(tokens):
        out = []
        for t in tokens:
            if isinstance(t, tuple) and t[0] == 'lit':
                out += ['c0', 'sLF', 'rLR']      # LOAD15: trigger const15, recv 15 (A=15, B kept)
            else:
                out.append(t)
        return out

    for lab in order:
        toks = expand(P[lab])
        head[lab] = y
        L.put(1, y, '@' if lab == 'INIT' else '>')
        if lab == 'INIT':
            L.put(2, y, '>')
        x = 2
        buf_x = x
        cur_y = y
        def newrow(cur_y, endx):
            ny = cur_y + 2
            # down, west to col1, south onto the '>' head (arrive heading E into ops)
            rte(L, [(endx, cur_y), (endx, cur_y + 1), (1, cur_y + 1), (1, ny)])
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
            elif isinstance(t, tuple) and t[0] == 'br2':
                # v + d at (xx,yy),(xx,yy+1); d: BP>0->CW(W), else straight(S). 2 exits.
                L.put(xx, yy, 'v'); L.put(xx, yy + 1, 'd')
                pending.append(('br2', (xx, yy + 1), (t[1], t[2])))
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
    hw = 66
    def goto_route(fx, fy, ty, col):
        # from (fx,fy): down 1, east to highway col, vertical to just ABOVE the head,
        # west to col1, then SOUTH onto the head '>' (never traverse the op row).
        rte(L, [(fx, fy), (fx, fy + 1), (col, fy + 1), (col, ty - 1), (1, ty - 1), (1, ty)])
    for kind, frm, tgt in pending:
        if kind == 'goto':
            fx, fy = frm
            goto_route(fx, fy, head[tgt], hw); hw -= 2
        else:  # br2: d at (xX,yX) heading S: BP>0->CW(W)=cw, else straight(S)=straight
            cw, straight = tgt
            xX, yX = frm
            goto_route(xX - 1, yX, head[cw], hw); hw -= 2        # CW -> W exit
            goto_route(xX, yX + 1, head[straight], hw); hw -= 2  # straight -> S exit
    return L

if __name__ == '__main__':
    L = build()
    L.save('/Users/visenbaev/icfpc26/scratchpad/tcp_ram.man')
    print('saved. foot', L.footprint())

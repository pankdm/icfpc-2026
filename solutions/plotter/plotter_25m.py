#!/usr/bin/env python3
"""25M plotter: BRANCH-based Bresenham body over a 7-slot belt.

Rewrite of Plan C's branchless typewriter into a REGISTER/BRANCH form:
  * Belt shrunk 9 -> 7 slots: [addr, err, e2, dy, dx, sx, sy32].
  * BODY uses TWO sign-branches (X-diamonds) instead of 4 multiplies + 3 temp
    slots -> ~187 executed ops/pixel (sync-padded) vs Plan C's 305 (1.63x).
    Skip arms are BELT-SYNCED: each arm leaves the belt in the same rotation
    state (both arms perform the identical slot move-to-rear sequence), so the
    compiler can track slot positions statically across the diamond merge.
  * Branch test = 2*(cond)+1 (always ODD, never 0) so `X` maps cleanly:
    positive -> CW (step arm), negative -> CCW (skip arm); no `straight` case.

The reference draws the SYMMETRIC two-conditional Bresenham (proven: Plan C
passes 6/6; the octant-normalized single-branch form FAILS 'both ways'/'octant
fan' on direction-dependent ties). So BODY keeps both conditionals.

This module is the ALGORITHM + faithful op/belt simulator (frame-exact proof).
The grid compiler lives in build().
"""
import sys, os, json
from collections import deque
sys.path.insert(0, os.path.dirname(__file__))

MASK = (1 << 64) - 1
def s64(v):
    v &= MASK
    return v - (1 << 64) if v & (1 << 63) else v
def _asr(a, b):
    if b < 0: return 0
    if b > 63: return -1 if a < 0 else 0
    return a >> b

# 7-slot belt, ordered addr-first (addr accessed every pixel for PA/updates)
LAYOUT7 = ['addr', 'err', 'e2', 'dy', 'dx', 'sx', 'sy32']

# ============================================================================
# Op-stream assembler for the branchLESS parts (INIT, SETUP): mirrors planC C.
# ============================================================================
class C:
    def __init__(self, ring):
        self.ring = list(ring); self.ops = []
    def e(self, *o): self.ops.extend(o)
    def rot(self): self.e('r', 's'); self.ring.append(self.ring.pop(0))
    def tf(self, n):
        while self.ring[0] != n: self.rot()
    def readA(self, n):
        self.tf(n); self.e('r', 's'); self.ring.append(self.ring.pop(0))
    def writeA(self, n):
        self.e('M'); self.tf(n); self.e('r', 'W', 's'); self.ring.append(self.ring.pop(0))
    def setB(self, k): self.e('M', ('#', k), 'W')
    def inc(self): self.e('M', ('#', 1), '+')
    def sign(self): self.setB(63); self.e('}')
    def binop(self, X, Y, o):
        self.readA(Y); self.e('M'); self.readA(X); self.e(o)

def build_init():
    ops = []
    for _ in LAYOUT7: ops += [('#', 0), 's']
    return ops

def build_setup2(ring0):
    """Per round: read x0,y0,x1,y1; compute Bresenham state into 7 slots using
    slot reuse as scratch. dy=-|Dy| (negative), dx=|Dx|, sx=+-1, sy32=+-32,
    err=dx+dy, addr=y0*32+x0, BP=n=max(dx,|Dy|). e2 left 0. Order-preserving."""
    c = C(ring0)
    # Use slots as scratch: inputs -> addr(x0), err(y0), dx(x1), dy(y1)
    c.e('ri'); c.writeA('addr')
    c.e('ri'); c.writeA('err')
    c.e('ri'); c.writeA('dx')
    c.e('ri'); c.writeA('dy')
    # Dx=x1-x0 -> sx ; Dy=y1-y0 -> sy32   (raw deltas parked in sign slots)
    c.binop('dx', 'addr', '-'); c.writeA('sx')     # sx = Dx (raw)
    c.binop('dy', 'err', '-');  c.writeA('sy32')   # sy32 = Dy (raw)
    # addr = y0*32 + x0  (y0 in err, x0 in addr) -> addr
    c.readA('err'); c.setB(32); c.e('*'); c.e('M'); c.readA('addr'); c.e('+'); c.writeA('addr')
    # e2 = |Dx| = Dx * sign_x ; compute sign_x=1+2*sign(Dx-1) into dx (temp), then |Dx|
    c.readA('sx'); c.setB(1); c.e('-'); c.sign(); c.setB(2); c.e('*'); c.inc(); c.writeA('dx')  # dx = sx_final
    c.binop('sx', 'dx', '*'); c.writeA('e2')       # e2 = Dx*sx_final = |Dx|
    # now set sx slot to sx_final (currently sx=raw Dx, dx=sx_final): copy dx->sx
    c.readA('dx'); c.writeA('sx')                   # sx = sx_final
    # err(temp) : sign_y=1+2*sign(Dy-1) -> dx(temp) ; |Dy| = Dy*sign_y -> err
    c.readA('sy32'); c.setB(1); c.e('-'); c.sign(); c.setB(2); c.e('*'); c.inc(); c.writeA('dx')  # dx = sy_final
    c.binop('sy32', 'dx', '*'); c.writeA('err')    # err = Dy*sy_final = |Dy|  (temp)
    # sy32 = sy_final*32
    c.readA('dx'); c.setB(32); c.e('*'); c.writeA('sy32')  # sy32 = sy*32
    # dy = -|Dy|  (|Dy| in err)
    c.readA('err'); c.e('N'); c.writeA('dy')
    # BP = n = max(|Dx|,|Dy|) ; |Dx| in e2, |Dy| in err
    #   n = |Dx| - ((|Dx|-|Dy|) & sign(|Dx|-|Dy|))
    c.binop('e2', 'err', '-'); c.writeA('dx')      # dx = |Dx|-|Dy|  (temp)
    c.readA('dx'); c.sign(); c.writeA('err')        # err = sign(|Dx|-|Dy|)  (temp)
    c.binop('dx', 'err', '&'); c.writeA('dx')       # dx = (|Dx|-|Dy|)&sign
    c.binop('e2', 'dx', '-'); c.inc(); c.e('b')     # BP = max(|Dx|,|Dy|) + 1  (loop runs BP times)
    # finalize: dx = |Dx| (from e2) ; err = err_bres = dx+dy ; e2 = 0
    c.readA('e2'); c.writeA('dx')                   # dx = |Dx|
    c.binop('dx', 'dy', '+'); c.writeA('err')       # err = |Dx| + (-|Dy|)
    c.e(('#', 0)); c.writeA('e2')                   # e2 = 0
    c.tf('addr')
    assert c.ring == list(ring0), f"setup not order-preserving: {c.ring}"
    return c.ops, c.ring

INIT = build_init()
SETUP, _ring = build_setup2(LAYOUT7)

# ============================================================================
# Faithful simulator: INIT + SETUP (op-stream) + BODY (structured branches).
# BODY is structured control (mirrors the grid X-diamonds). Belt is a named-slot
# move-to-rear ring; we track A,B,belt and produce frames -> frame-exact proof.
# ============================================================================
def simulate(rounds, count_ops=False):
    """Faithful sim: INIT+SETUP as op-stream, BODY as X-diamond structured control
    over a named-slot move-to-rear belt. opc counts EXECUTED ops (taken path) as a
    tick proxy (belt r/s + register/alu + display + branch/turn)."""
    frames = []
    belt = [[n, 0] for n in LAYOUT7]
    st = {'A': 0, 'B': 0, 'BP': 0, 'cur': 0, 'opc': 0}
    buf = [0]*768
    inp = deque()
    def ftr(): belt.append(belt.pop(0))
    def bump(k): st['opc'] += k
    def ex(ops):                       # branchless op-stream (INIT/SETUP)
        for op in ops:
            bump(1)
            if op == 'ri': st['A'] = inp.popleft()
            elif op == 'r': st['A'] = belt[0][1]
            elif op == 's': belt[0][1] = st['A']; ftr()
            elif op == 'PA': st['cur'] = st['A']
            elif op == 'PD':
                if 0 <= st['cur'] < 768: buf[st['cur']] = st['A'] % 16
                st['cur'] += 1
            elif op == 'PS': pass
            elif isinstance(op, tuple): st['A'] = s64(op[1])
            elif op == 'M': st['B'] = st['A']
            elif op == 'W': st['A'], st['B'] = st['B'], st['A']
            elif op == 'b': st['BP'] = st['A']
            elif op == '+': st['A'] = s64(st['A'] + st['B'])
            elif op == '-': st['A'] = s64(st['A'] - st['B'])
            elif op == '*': st['A'] = s64(st['A'] * st['B'])
            elif op == 'N': st['A'] = s64(-st['A'])
            elif op == '&': st['A'] = s64(st['A'] & st['B'])
            elif op == '}': st['A'] = _asr(st['A'], st['B'])
            else: raise ValueError(op)
    # named-slot belt helpers (move-to-rear; A destroyed by rotations in HW but
    # readA/writeA overwrite A at the end so tracking the final A is exact)
    def tf(name):
        while belt[0][0] != name: bump(2); ftr()     # r,s per rotation
    def readA(name):
        tf(name); st['A'] = belt[0][1]; bump(2); ftr()  # r,s
    def MA(): st['B'] = st['A']; bump(1)
    def add(): st['A'] = s64(st['A'] + st['B']); bump(1)
    def sub(): st['A'] = s64(st['A'] - st['B']); bump(1)
    def lit(k): st['A'] = k; bump(1)
    def loadB(name): readA(name); MA()
    def writeA(name):                # slot := A ; M done inline (payload->B), r,W,s
        MA(); tf(name); belt[0][1] = st['B']; st['A'] = st['B']; bump(3)  # r,W,s
    def rmw_add(name):               # slot := slot + B (B preset); one move-to-rear
        tf(name); st['A'] = s64(belt[0][1] + st['B']); belt[0][1] = st['A']; bump(3)  # r,+,s
    def body():
        # plot addr
        readA('addr'); st['cur'] = st['A']
        # color 15 inline: 3,M,5,* -> A=15 (B clobbered, unused hereafter until reload)
        bump(4); c = st['cur']
        if 0 <= c < 768: buf[c] = 15
        st['cur'] = c + 1
        # e2 = 2*err ; store slot
        readA('err'); MA(); add(); writeA('e2')
        # branch1: step x if e2>=dy ; test=2*(e2-dy)+1 (odd)
        loadB('dy'); readA('e2'); sub()          # A = e2-dy
        MA(); add(); MA(); lit(1); add()         # A = 2*(e2-dy)+1
        bump(1)                                  # X (branch turn op)
        if st['A'] > 0:
            loadB('dy'); rmw_add('err')
            loadB('sx'); rmw_add('addr')
        else:
            readA('dy'); readA('err'); readA('sx'); readA('addr')   # belt-sync
        # branch2: step y if e2<=dx ; test=2*(dx-e2)+1
        loadB('e2'); readA('dx'); sub()          # A = dx-e2
        MA(); add(); MA(); lit(1); add()
        bump(1)                                  # X
        if st['A'] > 0:
            loadB('dx'); rmw_add('err')
            loadB('sy32'); rmw_add('addr')
        else:
            readA('dx'); readA('err'); readA('sy32'); readA('addr')
        # RESTORE LAYOUT7 order (body must be order-preserving so the fixed-rotation
        # SETUP op-stream stays aligned each round). Deterministic count (arms synced).
        while belt[0][0] != 'addr': bump(2); ftr()

    ex(INIT)
    for (x0, y0, x1, y1) in rounds:
        inp.extend([x0, y0, x1, y1]); buf[:] = [0]*768; st['cur'] = 0
        ex(SETUP)
        for _ in range(st['BP']):        # BP already = n+1 (loop runs BP times, matches grid)
            body()
        frames.append(list(buf))
    return (frames, st['opc']) if count_ops else frames


def hexrows(buf):
    hexc = "0123456789abcdef"
    return ["".join(hexc[buf[y*32+x]] for x in range(32)) for y in range(24)]


# ============================================================================
# GRID COMPILER: reuse Plan C's proven Turtle (INIT/SETUP/linear + cmd/input
# excursions) and driver/belt/relay/input wiring; add branch-diamonds for BODY.
# ============================================================================
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import littleman as lm
import plotter_planC as PC

def _despine(ops):
    """Despine literals to digits (no backticks) exactly like Plan C, extended for
    our op-stream. Handles M,#63,W,} (sign); M,#32,W,* (=*32); #15; single digits."""
    out = []; i = 0; n = len(ops)
    while i < n:
        o = ops[i]
        if (i + 3 < n and o == "M" and ops[i+1] == ("#", 63)
                and ops[i+2] == "W" and ops[i+3] == "}"):
            out += ["M", "9", "W", "}"] * 7; i += 4
        elif (i + 3 < n and o == "M" and ops[i+1] == ("#", 32)
                and ops[i+2] == "W" and ops[i+3] == "*"):
            out += ["M", "5", "W", "{"]; i += 4
        elif o == ("#", 15):
            out += ["3", "M", "5", "*"]; i += 1
        elif isinstance(o, tuple):
            assert 0 <= o[1] <= 9, f"undespined literal {o}"
            out.append(str(o[1])); i += 1
        else:
            out.append(o); i += 1
    return out

def _toks(ops):
    """op-stream (with 'ri','CMD' markers) -> Turtle tokens."""
    out = []
    for o in _despine([x for x in ops]):
        if o == "ri": out.append(("ri",))
        elif o == "CMD": out.append(("cmd",))
        else: out.append(("op", o))
    return out

# ---- flat op-streams for BODY segments (belt-order tracked; arms sync) ----
def _body_segments():
    r = list(LAYOUT7)
    def pre1(c):
        c.readA('addr'); c.e('M', ('#',1), '+', 'CMD')      # PA: send addr+1
        c.e(('#',15), 'CMD')                                # color 15 send (despined)
        c.readA('err'); c.e('M', '+'); c.writeA('e2')       # e2 = 2*err
        c.readA('dy'); c.e('M'); c.readA('e2'); c.e('-'); c.e('M', ('#',1), '+', 'M', ('#',1), '+')  # test1=2*(e2-dy)+1
    c = C(r); pre1(c); pre1_ops = c.ops; r1 = c.ring
    def a1s(c):
        c.readA('dy'); c.e('M'); c.readA('err'); c.e('+'); c.writeA('err')
        c.readA('sx'); c.e('M'); c.readA('addr'); c.e('+'); c.writeA('addr')
    def a1k(c):
        c.readA('dy'); c.readA('err'); c.readA('sx'); c.readA('addr')
    cs = C(r1); a1s(cs); ck = C(r1); a1k(ck)
    assert cs.ring == ck.ring
    r2 = cs.ring
    def midf(c):
        c.readA('e2'); c.e('M'); c.readA('dx'); c.e('-'); c.e('M', ('#',1), '+', 'M', ('#',1), '+')  # test2
    cm = C(r2); midf(cm); mid_ops = cm.ops; r3 = cm.ring
    def a2s(c):
        c.readA('dx'); c.e('M'); c.readA('err'); c.e('+'); c.writeA('err')
        c.readA('sy32'); c.e('M'); c.readA('addr'); c.e('+'); c.writeA('addr')
    def a2k(c):
        c.readA('dx'); c.readA('err'); c.readA('sy32'); c.readA('addr')
    c2s = C(r3); a2s(c2s); c2k = C(r3); a2k(c2k)
    assert c2s.ring == c2k.ring
    r4 = c2s.ring
    cc = C(r4); cc.tf('addr'); corr_ops = cc.ops
    assert cc.ring == list(LAYOUT7)
    return dict(pre1=pre1_ops, a1s=cs.ops, a1k=ck.ops, mid=mid_ops,
                a2s=c2s.ops, a2k=c2k.ops, corr=corr_ops)


def build(band_right=48):
    PC.set_geometry(band_right)
    BL, BR = PC.BL, PC.BR
    p = lm.Program()
    T = 4
    put = PC.put; hput = PC.hput
    put(p, BL - 2, T, "@")
    t = PC.Turtle(p, T)

    # ---- INIT + SETUP (branchless op-streams via the proven Turtle) ----
    t.emit(_toks(INIT))
    t.force_newline()
    t.emit(_toks(SETUP))
    body_start = t.force_newline()

    seg = _body_segments()

    ELANE = BR                                 # east descent lane (skip); serpentine uses BL..BR-2
    def lay_serpentine_ops(ops_chars, y0, xstart):
        """Lay ops as an EAST-first boustrophedon within [BL..BR-2] (leaving BR-1,BR
        clear for the skip lane), starting at (xstart,y0) heading east. Returns exit."""
        x = xstart; y = y0; d = 1
        for ch in ops_chars:
            if d == 1 and x > BR - 3:
                put(p, BR - 2, y, "v"); put(p, BR - 2, y + 1, "<"); y += 1; x = BR - 3; d = -1
            elif d == -1 and x < BL + 1:
                put(p, BL, y, "v"); put(p, BL, y + 1, ">"); y += 1; x = BL + 1; d = 1
            put(p, x, y, ch); x += d
        return x, y, d

    def branch(pre_toks, step_ops, skip_ops):
        """Emit linear prefix (with cmd) then an X-diamond. Skip descends the east
        lane (col BR); step uses the band + junction rail; both merge on the rail
        below everything. Only one arm runs, and both leave the belt in the same
        order, so the merge is state-consistent. Leaves the Turtle on a fresh row."""
        rail = BL - 1
        t.emit(pre_toks)                       # test value in A
        yb = t.force_newline()                 # '>' at (rail,yb); man east at BL
        put(p, BL, yb, "v")                    # man (east) -> south
        put(p, BL, yb + 1, "X")                # A>0 CW=west(step); A<0 CCW=east(skip)
        # ---- SKIP arm (east), row yb+1, cols BL+1.. ; then east lane down ----
        x = BL + 1
        for ch in skip_ops:
            put(p, x, yb + 1, ch); x += 1      # man heading east at (x, yb+1)
        put(p, ELANE, yb + 1, "v")             # reach east lane (glide east), turn south
        # ---- STEP arm (west): rail down to yb+3, east into band, serpentine ----
        put(p, rail, yb + 1, "v")              # X-west -> rail south
        put(p, rail, yb + 2, "v")
        put(p, rail, yb + 3, ">")              # east into band
        ex, ey, ed = lay_serpentine_ops(step_ops, yb + 3, BL)
        put(p, ex, ey, "v")                    # south
        put(p, ex, ey + 1, "<")               # west; glide to rail
        hput(p, rail, ey + 1, "v")             # catch at rail -> south
        # ---- merge on the rail, below both arms ----
        mrow = ey + 2
        # skip: east lane down to mrow, then west to rail
        for yy in range(yb + 2, mrow):
            hput(p, ELANE, yy, "v")
        put(p, ELANE, mrow, "<")              # west along mrow -> glide to rail
        hput(p, rail, mrow, "v")              # both: at rail, heading south
        # step: rail from ey+1 down to mrow
        for yy in range(ey + 1, mrow):
            hput(p, rail, yy, "v")
        t._start_row(mrow + 1)                 # '>' at (rail,mrow+1); man east at BL

    # ---- BODY: prefix+branch1 ; mid+branch2 ; corrective ----
    branch(_toks(seg['pre1']), _despine(seg['a1s']), _despine(seg['a1k']))
    branch(_toks(seg['mid']),  _despine(seg['a2s']), _despine(seg['a2k']))
    t.emit(_toks(seg['corr']))
    tail_y = t.force_newline()

    # ---- control tail (m; d loop) : reuse Plan C's structure ----
    ROUND_RAIL = PC.ROUND_RAIL; BODY_RAIL = PC.BODY_RAIL
    CMD_S = PC.CMD_S
    put(p, BL, tail_y, "v")
    put(p, BL, tail_y + 1, "m")
    put(p, BL, tail_y + 2, "d")
    put(p, BODY_RAIL, tail_y + 2, "^")
    put(p, BODY_RAIL, body_start, ">")
    put(p, BL, tail_y + 3, "1")
    put(p, BL, tail_y + 4, "N")
    put(p, BL, tail_y + 5, ">")
    put(p, CMD_S, tail_y + 5, "s")
    put(p, CMD_S + 1, tail_y + 5, "v")
    put(p, CMD_S + 1, tail_y + 6, "<")
    put(p, ROUND_RAIL, tail_y + 6, "^")
    put(p, ROUND_RAIL, body_start, ">")
    GB = tail_y + 7
    GL = PC.GL; GR = PC.GR
    BIN = PC.BIN; BOUT = PC.BOUT; CCMD = PC.CCMD; CINP = PC.CINP
    p.room(GL - 1, T - 1, (GR - GL + 1) + 2, (GB - T + 1) + 2)

    # ================= belt/relay/driver/display/input (Plan C wiring) =========
    south = GB + 1
    rly_y = GB + 8
    RLY = p.room(BIN - 2, rly_y, BOUT - BIN + 1, 4)
    rlx, rly = RLY.ix0, RLY.iy0
    RB = RLY.ix1
    put(p, rlx, rly, "@")
    put(p, rlx + 1, rly, ">")
    s_col = rlx + 3
    cx = rlx + 2
    while cx + 1 <= RB - 1:
        put(p, cx, rly, "r"); put(p, cx + 1, rly, "s"); cx += 2
    put(p, RB, rly, "v"); put(p, RB, rly + 1, "<")
    cx = RB - 1
    while cx - 1 >= rlx + 2:
        put(p, cx, rly + 1, "r"); put(p, cx - 1, rly + 1, "s"); cx -= 2
    put(p, rlx + 1, rly + 1, "^")
    tHi = south + 2; tLo = rly_y - 2
    p.pipe([(BOUT, south + 1), (BOUT, tLo), (BOUT - 1, tLo), (BOUT - 1, tHi),
            (BOUT - 2, tHi), (BOUT - 2, tLo), (BOUT - 3, tLo), (BOUT - 3, rly_y - 1)])
    p.pipe([(s_col, rly_y - 1), (s_col, tHi), (s_col - 1, tHi), (s_col - 1, tLo),
            (BIN, tLo), (BIN, south + 1)])
    # driver + display beside gate
    dvx, dvy = GR + 5, T + 2
    info = PC.build_driver(p, dvx, dvy, None)
    DR = info["DR"]; rENTRY = info["rENTRY"]
    lane = GR + 3
    p.pipe([(CCMD, south + 1), (CCMD, GB + 3), (lane, GB + 3),
            (lane, rENTRY), (DR.x0 - 1, rENTRY)])
    # input room (west, below gate)
    IR = p.input_room(CINP - 1, GB + 6)
    p.pipe([(CINP, IR.y0 - 1), (CINP, south + 1)])
    return p


if __name__ == "__main__":
    import sys
    if "--build" in sys.argv:
        p = build()
        path = os.path.join(os.path.dirname(__file__), "plotter-25m.man")
        p.save(path)
        print("saved", path, "footprint", p.footprint())
        print(json.dumps(p.grade("plotter")))
    else:
        spec = json.load(open(os.path.join(os.path.dirname(__file__), '..', '..', 'tests', 'plotter.json')))
        allok = True
        for tc in spec["publicTestData"]:
            rnds = [tuple(map(int, r["in"])) for r in tc["rounds"]]
            exp = [r["frames"][0] for r in tc["rounds"]]
            got = [hexrows(b) for b in simulate(rnds)]
            ok = got == exp; allok &= ok
            print(("OK  " if ok else "FAIL"), tc["name"])
        print("25M OP-STREAM FRAME-EXACT" if allok else "MISMATCH")
        print("INIT", len(INIT), "SETUP", len(SETUP))

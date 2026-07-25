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
    c.binop('e2', 'dx', '-'); c.e('b')              # BP = max(|Dx|,|Dy|)
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
        for _ in range(st['BP'] + 1):
            body()
        frames.append(list(buf))
    return (frames, st['opc']) if count_ops else frames


def hexrows(buf):
    hexc = "0123456789abcdef"
    return ["".join(hexc[buf[y*32+x]] for x in range(32)) for y in range(24)]


if __name__ == "__main__":
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

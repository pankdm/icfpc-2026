#!/usr/bin/env python3
"""Plan C op-stream: REGISTER-aware / short-belt Bresenham for the plotter.

Phase 1 (this file, branchless): shrink the persistent FIFO belt from 15 slots
to the 9 slots the inner loop actually touches, and ORDER them to the fixed
access sequence so the belt makes ~1 revolution per access-run instead of
backtracking (86-88% rotation tax -> ~half).  Setup is rewritten to compute the
Bresenham state using ONLY those 9 slots as scratch (inputs x0..y1 and temps
t/t2 reuse not-yet-final slots), so the belt never has to grow to 15.

Belt is order-preserving across INIT / SETUP / BODY so the round loop stays
synchronised (asserted in simulate()).  Op tokens map 1:1 to littleman chars
exactly as in dsl.py.
"""
import sys, os
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

# ---- 9-slot belt, ordered to the body access sequence (analyze_belt best) ----
LAYOUT9 = ['addr', 'err', 'e2', 'dy', 'cx', 'dx', 'cy', 'sx', 'sy32']

class C:
    """Symbolic-belt assembler mirroring littleman primitives.  The belt is a
    move-to-rear self-organising list; readA/writeA rotate forward (tf) to reach
    a slot, matching how the man physically cycles the FIFO."""
    def __init__(self, ring):
        self.ring = list(ring)
        self.ops = []
    def e(self, *o): self.ops.extend(o)
    def rot(self): self.e('r', 's'); self.ring.append(self.ring.pop(0))
    def tf(self, n):
        while self.ring[0] != n: self.rot()
    def readA(self, n):                       # A := slot(n)  (nondestructive)
        self.tf(n); self.e('r', 's'); self.ring.append(self.ring.pop(0))
    def writeA(self, n):                      # slot(n) := A  (clobbers B)
        self.e('M'); self.tf(n); self.e('r', 'W', 's'); self.ring.append(self.ring.pop(0))
    def setB(self, k): self.e('M', ('#', k), 'W')
    def inc(self): self.e('M', ('#', 1), '+')
    def sign(self): self.setB(63); self.e('}')          # A := A >>a 63  (0 or -1)
    def binop(self, X, Y, o):                 # A := slot(X) <o> slot(Y)
        self.readA(Y); self.e('M'); self.readA(X); self.e(o)

# ------------------------------- INIT ---------------------------------------
def build_init():
    """Fill the empty belt with 9 zero slots (LAYOUT9 order)."""
    ops = []
    for _ in LAYOUT9: ops += [('#', 0), 's']
    return ops

# ------------------------------- SETUP --------------------------------------
def build_setup(ring0):
    """Per round: read x0,y0,x1,y1; compute Bresenham state into the 9 slots
    using slot reuse (see liveness schedule below); BP := n = max(|dx|,|dy|).
    Order-preserving: ends with ring == ring0.  Leaves addr at belt front.

    Slot reuse (physical slot -> transient meaning):
      addr<-x0, err<-y0, dx<-x1, dy<-y1                 (inputs)
      cx<-Dx, cy<-Dy                                    (deltas)
      sx<-sx, e2<-sy                                    (signs)
      dx<-|Dx|, cx<-|Dy|, dy<- -|Dy|, sy32<-sy*32
      addr<-y0*32+x0, err<-dx+dy, BP<-max(dx,|Dy|)
    """
    c = C(ring0)
    # inputs
    c.e('ri'); c.writeA('addr')   # x0 -> addr
    c.e('ri'); c.writeA('err')    # y0 -> err
    c.e('ri'); c.writeA('dx')     # x1 -> dx
    c.e('ri'); c.writeA('dy')     # y1 -> dy
    # Dx = x1 - x0 -> cx ;  Dy = y1 - y0 -> cy
    c.binop('dx', 'addr', '-'); c.writeA('cx')       # cx = Dx
    c.binop('dy', 'err', '-');  c.writeA('cy')       # cy = Dy
    # sx = 1 + 2*(sign(Dx-1))  (=1 if Dx>0 else -1) -> sx
    c.readA('cx'); c.setB(1); c.e('-'); c.sign(); c.setB(2); c.e('*'); c.inc(); c.writeA('sx')
    # sy likewise -> e2
    c.readA('cy'); c.setB(1); c.e('-'); c.sign(); c.setB(2); c.e('*'); c.inc(); c.writeA('e2')
    # dx = Dx*sx = |Dx| -> dx
    c.binop('cx', 'sx', '*'); c.writeA('dx')
    # |Dy| = Dy*sy -> cx   (reuse; Dx no longer needed)
    c.binop('cy', 'e2', '*'); c.writeA('cx')
    # dy = -|Dy| -> dy   (keep |Dy| in cx for max)
    c.readA('cx'); c.e('N'); c.writeA('dy')
    # sy32 = sy*32 -> sy32
    c.readA('e2'); c.setB(32); c.e('*'); c.writeA('sy32')
    # addr = y0*32 + x0   (y0 in err, x0 in addr)
    c.readA('err'); c.setB(32); c.e('*'); c.e('M'); c.readA('addr'); c.e('+'); c.writeA('addr')
    # err = dx + dy
    c.binop('dx', 'dy', '+'); c.writeA('err')
    # n = max(dx, |Dy|)  via  dx - ((dx-|Dy|) & sign(dx-|Dy|))
    c.binop('dx', 'cx', '-'); c.writeA('e2')         # e2 = dx-|Dy|  (temp, ok to clobber)
    c.readA('e2'); c.sign(); c.writeA('cy')          # cy = sign(dx-|Dy|)
    c.binop('e2', 'cy', '&'); c.writeA('cx')         # cx = (dx-|Dy|)&sign
    c.binop('dx', 'cx', '-'); c.e('b')               # BP = max(dx,|Dy|)
    c.tf('addr')
    assert c.ring == list(ring0), f"setup not order-preserving: {c.ring}"
    return c.ops, c.ring

# ------------------------------- BODY ---------------------------------------
def build_body(ring0):
    """One pixel (branchless multiply form, identical math to dsl.build_body but
    over the reordered 9-slot belt).  Order-preserving."""
    c = C(ring0)
    c.readA('addr'); c.e('PA'); c.e(('#', 15), 'PD')            # plot addr, color 15
    c.readA('err'); c.e('M', '+'); c.writeA('e2')               # e2 = 2*err
    c.binop('e2', 'dy', '-'); c.sign(); c.inc(); c.writeA('cx') # cx = (e2>=dy)
    c.binop('dx', 'e2', '-'); c.sign(); c.inc(); c.writeA('cy') # cy = (e2<=dx)
    c.binop('cx', 'dy', '*'); c.e('M'); c.readA('err'); c.e('+'); c.writeA('err')
    c.binop('cy', 'dx', '*'); c.e('M'); c.readA('err'); c.e('+'); c.writeA('err')
    c.binop('cx', 'sx', '*'); c.e('M'); c.readA('addr'); c.e('+'); c.writeA('addr')
    c.binop('cy', 'sy32', '*'); c.e('M'); c.readA('addr'); c.e('+'); c.writeA('addr')
    c.tf('addr')
    assert c.ring == list(ring0), f"body not order-preserving: {c.ring}"
    return c.ops, c.ring

# ------------------------------- assemble -----------------------------------
INIT = build_init()
SETUP, _ring_after_setup = build_setup(LAYOUT9)
BODY, _ring_after_body = build_body(LAYOUT9)

# ------------------------------- simulate -----------------------------------
def simulate(rounds):
    frames = []; belt = deque(); A = B = BP = 0; buf = [0]*768; cur = 0; inp = deque()
    def ex(ops):
        nonlocal A, B, BP, cur
        for op in ops:
            if op == 'ri': A = inp.popleft()
            elif op == 'r': A = belt.popleft()
            elif op == 's': belt.append(A)
            elif op == 'PA': cur = A
            elif op == 'PD':
                if 0 <= cur < 768: buf[cur] = A % 16
                cur += 1
            elif op == 'PS': pass
            elif isinstance(op, tuple): A = s64(op[1])
            elif op == 'M': B = A
            elif op == 'W': A, B = B, A
            elif op == 'b': BP = A
            elif op == '+': A = s64(A + B)
            elif op == '-': A = s64(A - B)
            elif op == '*': A = s64(A * B)
            elif op == 'N': A = s64(-A)
            elif op == '&': A = s64(A & B)
            elif op == '}': A = _asr(A, B)
            else: raise ValueError(f"bad op {op!r}")
    ex(INIT)
    assert list(belt) == [0]*9
    for (x0, y0, x1, y1) in rounds:
        inp.extend([x0, y0, x1, y1]); buf = [0]*768; cur = 0
        ex(SETUP)
        for _ in range(BP + 1): ex(BODY)
    return frames_out(belt, buf, frames)

def frames_out(belt, buf, frames):
    frames.append(list(buf))
    return frames

def _simulate_all(rounds):
    """Return committed frames for a list of rounds (one frame per round)."""
    frames = []; belt = deque(); regs = {'A':0,'B':0,'BP':0}; inp = deque()
    state = {'buf':[0]*768, 'cur':0}
    def ex(ops):
        A = regs['A']; B = regs['B']; BP = regs['BP']; buf = state['buf']; cur = state['cur']
        for op in ops:
            if op == 'ri': A = inp.popleft()
            elif op == 'r': A = belt.popleft()
            elif op == 's': belt.append(A)
            elif op == 'PA': cur = A
            elif op == 'PD':
                if 0 <= cur < 768: buf[cur] = A % 16
                cur += 1
            elif op == 'PS': pass
            elif isinstance(op, tuple): A = s64(op[1])
            elif op == 'M': B = A
            elif op == 'W': A, B = B, A
            elif op == 'b': BP = A
            elif op == '+': A = s64(A + B)
            elif op == '-': A = s64(A - B)
            elif op == '*': A = s64(A * B)
            elif op == 'N': A = s64(-A)
            elif op == '&': A = s64(A & B)
            elif op == '}': A = _asr(A, B)
            else: raise ValueError(f"bad op {op!r}")
        regs['A'], regs['B'], regs['BP'] = A, B, BP
        state['cur'] = cur
    ex(INIT)
    for (x0, y0, x1, y1) in rounds:
        inp.extend([x0, y0, x1, y1]); state['buf'] = [0]*768; state['cur'] = 0
        ex(SETUP)
        for _ in range(regs['BP'] + 1): ex(BODY)
        frames.append(list(state['buf']))
    return frames


if __name__ == "__main__":
    import json
    from collections import Counter
    spec = json.load(open(os.path.join(os.path.dirname(__file__), '..', '..', 'tests', 'plotter.json')))
    hexc = "0123456789abcdef"
    def rows(buf): return ["".join(hexc[buf[y*32+x]] for x in range(32)) for y in range(24)]
    allok = True
    for tc in spec["publicTestData"]:
        rnds = [tuple(map(int, r["in"])) for r in tc["rounds"]]
        exp = [r["frames"][0] for r in tc["rounds"]]
        got = [rows(b) for b in _simulate_all(rnds)]
        ok = got == exp; allok &= ok
        print(f"  {'OK  ' if ok else 'FAIL'} {tc['name']}  ({len(rnds)} rounds)")
    print("PLAN C OP-STREAM FRAME-EXACT" if allok else "MISMATCH")
    def cls(ops):
        c = Counter()
        for o in ops:
            if o in ('r','s'): c['belt']+=1
            elif o == 'ri': c['input']+=1
            elif o in ('PA','PD','PS'): c['disp']+=1
            else: c['compute']+=1
        return dict(c)
    print("INIT", len(INIT), cls(INIT))
    print("SETUP", len(SETUP), cls(SETUP))
    print("BODY", len(BODY), cls(BODY), " (was 443, belt 390)")

"""Plan-B op-stream generator: fused read-modify-write on the belt + configurable
ring order + backtick sign(). Semantically identical to dsl.SETUP/BODY (verified
frame-exact by verify_gate2). Only the belt ACCESS PATTERN changes (fewer rotations).

Key primitive `add_to(n)`: assumes B holds an addend; does  tf(n); r; +; s.
This replaces the old  M; readA(n); '+'; writeA(n)  read-modify-write which paid a
forced full-loop rotation (14) to get n back to the front for the write. Fused, we
pop n, add B (survives rotation), push the new n -> cyclic order preserved, no
double rotation, no forced-14.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import dsl

# --- chosen ring order (index0 = home; front at SETUP/BODY entry & exit) ---
# Filled by the optimizer; default = original for extraction bootstrap.
LAYOUT = list(dsl.LAYOUT)
USE_BACKTICK_SIGN = True

class _C:
    def __init__(self):
        self.ring = list(LAYOUT); self.ops = []
    def e(self, *o): self.ops.extend(o)
    def rot(self): self.e('r', 's'); self.ring.append(self.ring.pop(0))
    def tf(self, n):
        while self.ring[0] != n: self.rot()
    # non-destructive read A := slot(n)
    def readA(self, n):
        self.tf(n); self.e('r', 's'); self.ring.append(self.ring.pop(0))
    # destructive write slot(n) := A (clobbers B with old n)
    def writeA(self, n):
        self.e('M'); self.tf(n); self.e('r', 'W', 's'); self.ring.append(self.ring.pop(0))
    # fused: slot(n) := slot(n) <op> B  (B holds the operand; A clobbered)
    def add_to(self, n, op='+'):
        self.tf(n); self.e('r', op, 's'); self.ring.append(self.ring.pop(0))
    def setB(self, k): self.e('M', ('#', k), 'W')
    def inc(self): self.e('M', ('#', 1), '+')
    def sign(self):
        if USE_BACKTICK_SIGN:
            self.e('M', ('#', 63), 'W', '}')     # A := A >>a 63  (backtick literal 63)
        else:
            self.setB(63); self.e('}')           # -> despined to (M9W})*7 later
    def binop(self, X, Y, o): self.readA(Y); self.e('M'); self.readA(X); self.e(o)


def build_init():
    ops = []
    for _ in LAYOUT: ops += [('#', 0), 's']
    return ops


def build_setup():
    c = _C()
    c.e('ri'); c.writeA('x0'); c.e('ri'); c.writeA('y0')
    c.e('ri'); c.writeA('x1'); c.e('ri'); c.writeA('y1')
    c.binop('x1', 'x0', '-'); c.writeA('t')
    c.binop('y1', 'y0', '-'); c.writeA('t2')
    c.readA('t');  c.setB(1); c.e('-'); c.sign(); c.setB(2); c.e('*'); c.inc(); c.writeA('sx')
    c.readA('t2'); c.setB(1); c.e('-'); c.sign(); c.setB(2); c.e('*'); c.inc(); c.writeA('cy')
    c.binop('t', 'sx', '*'); c.writeA('dx')
    c.binop('t2', 'cy', '*'); c.writeA('e2')
    c.readA('e2'); c.e('N'); c.writeA('dy')
    c.readA('cy'); c.setB(32); c.e('*'); c.writeA('sy32')
    c.readA('y0'); c.setB(32); c.e('*'); c.e('M'); c.readA('x0'); c.e('+'); c.writeA('addr')
    c.binop('dx', 'dy', '+'); c.writeA('err')
    c.binop('dx', 'e2', '-'); c.writeA('cx')
    c.readA('cx'); c.sign(); c.writeA('t')
    c.binop('cx', 't', '&'); c.writeA('t2')
    c.binop('dx', 't2', '-')                     # A = n = max(dx,|Dy|)
    c.e('M', ('#', 1), '+', 'b')                 # BP = n+1  (SETUP1)
    c.tf(LAYOUT[0])                              # return front to home
    return c.ops


def build_body():
    c = _C()
    c.readA('addr'); c.e('PA'); c.e(('#', 15), 'PD')
    c.readA('err'); c.e('M', '+'); c.writeA('e2')          # e2 = 2*err
    c.binop('e2', 'dy', '-'); c.sign(); c.inc(); c.writeA('cx')
    c.binop('dx', 'e2', '-'); c.sign(); c.inc(); c.writeA('cy')
    c.binop('cx', 'dy', '*'); c.e('M'); c.add_to('err')    # err += cx*dy
    c.binop('cy', 'dx', '*'); c.e('M'); c.add_to('err')    # err += cy*dx
    c.binop('cx', 'sx', '*'); c.e('M'); c.add_to('addr')   # addr += cx*sx
    c.binop('cy', 'sy32', '*'); c.e('M'); c.add_to('addr') # addr += cy*sy32
    c.tf(LAYOUT[0])                                        # return front to home
    return c.ops


def set_layout(order):
    global LAYOUT
    LAYOUT = list(order)

if __name__ == "__main__":
    print("LAYOUT", LAYOUT)
    print("INIT", len(build_init()), "SETUP", len(build_setup()), "BODY", len(build_body()))

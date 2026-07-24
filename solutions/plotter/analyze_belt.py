#!/usr/bin/env python3
"""Analyze belt rotation cost for the plotter body, and search for a better
slot ordering / access sequence. Instruments a logging version of dsl._C."""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(__file__))

# ---- logging compiler: records the sequence of slot accesses in body ----
class LogC:
    def __init__(self, ring):
        self.ring = list(ring)
        self.seq = []  # list of slot names accessed (readA or writeA), in order
    def readA(self, n):
        self.seq.append(n)
    def writeA(self, n):
        self.seq.append(n)
    def setB(self, k): pass
    def inc(self): pass
    def sign(self): pass
    def binop(self, X, Y, o):
        self.readA(Y); self.readA(X)

def body_access_seq():
    c = LogC([])
    # mirror dsl.build_body access pattern exactly
    c.readA('addr')            # PA + PD (display), addr read
    c.readA('err'); c.writeA('e2')
    c.binop('e2', 'dy', '-'); c.writeA('cx')
    c.binop('dx', 'e2', '-'); c.writeA('cy')
    c.binop('cx', 'dy', '*'); c.readA('err'); c.writeA('err')
    c.binop('cy', 'dx', '*'); c.readA('err'); c.writeA('err')
    c.binop('cx', 'sx', '*'); c.readA('addr'); c.writeA('addr')
    c.binop('cy', 'sy32', '*'); c.readA('addr'); c.writeA('addr')
    return c.seq

def rs_cost(order, seq):
    """Simulate move-to-rear self-organizing belt (matches dsl._C.tf+readA).
    Each access to slot t: rotate forward until t at front (index r pairs),
    then r,s and move t to rear => r;s pairs = index+1. Returns total r;s pairs."""
    ring = list(order)
    total = 0
    for t in seq:
        idx = ring.index(t)
        total += idx + 1
        ring.append(ring.pop(idx))   # move-to-rear
    return total

if __name__ == "__main__":
    seq = body_access_seq()
    print("access seq len", len(seq))
    from collections import Counter
    print("per-slot accesses:", dict(Counter(seq)))
    slots = list(dict.fromkeys(seq))  # unique in first-seen order
    print("slots used in body:", slots, "->", len(slots))

    # current LAYOUT order from dsl
    import dsl
    cur = [s for s in dsl.LAYOUT]
    print("current 15-slot cost (r;s pairs):", rs_cost(cur, seq), "=> ops", rs_cost(cur,seq)*2)

    # best reordering over the 9 body slots (belt shrunk to 9)
    best = None
    for perm in itertools.permutations(slots):
        cst = rs_cost(perm, seq)
        if best is None or cst < best[0]:
            best = (cst, perm)
    print("BEST 9-slot order cost:", best[0], "pairs =>", best[0]*2, "ops")
    print("BEST order:", best[1])

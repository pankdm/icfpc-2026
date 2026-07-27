#!/usr/bin/env python3
"""Plotter SWAR rebuild: the CTRL setup program, as a verified op stream.

The pixel kernel is swar_ops.py.  This module supplies the OTHER half: the
per-round constant computation, written as a linear list of littleman ops that
a serpentine layout can emit directly, plus a simulator that checks it against
swar_ops.consts() over all 589,824 segments.

MACHINE MODEL ASSUMED BY THE OP STREAM
  CTRL has exactly one incoming pipe (from BRAIN) and two outgoing (BRAIN =
  scratch echo, MOD = the pixel stream).  BRAIN relays x0,y0,x1,y1 and then
  echoes every scratch value back in order, so CTRL sees ONE fifo Q that starts
  as [x0,y0,x1,y1]; 'r' pops it, scratch 's' appends to it.

KERNEL CHANGE VS swar_ops.py
  swar_ops' loop is `send; P += Ic; if P > 0: P += Jc` -- a branch, which costs a
  test cell and a detour ring.  The branch is unnecessary:  P_k lives in (Jc, 0]
  and one subtraction always suffices, so

      P_{k+1} = (P_k + Ic) mod Jc            (Jc < 0, '%' takes the divisor sign)

  and, iterating, P_k = (P0 + k*Ic) mod Jc.  So CTRL never reduces at all: it
  emits the raw ramp W_k = P0 + k*Ic (`s`, `+`) and a downstream man with B = Jc
  does one `%`.  Two men, one constant each, no branch anywhere in the loop.
  check_kernel() verifies both claims exhaustively.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swar_ops import consts, pixels, reference  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# op stream emitter + simulator
# ─────────────────────────────────────────────────────────────────────────────

READ, SCRATCH, OUT, OP = "READ", "SCRATCH", "OUT", "OP"


class Emit:
    """Emits (glyphs, kind) tokens and simulates them at the same time.

    kind is one of READ ('r'), SCRATCH ('s' -> BRAIN), OUT ('s' -> MOD), OP.
    `glyphs` is an atomic run of cells (literals are >1 cell and must not be
    split across a serpentine row boundary).
    """

    def __init__(self, x0, y0, x1, y1, trace=False):
        self.toks = []
        self.A = 0
        self.B = 0
        self.BP = 0
        self.q = [("x0", x0), ("y0", y0), ("x1", x1), ("y1", y1)]
        self.sent = []          # values pushed to MOD
        self.npush = 0          # scratch pushes (BRAIN echo count)
        self.maxq = len(self.q)
        self.trace = trace

    # ---- primitive emit ----
    def _t(self, glyphs, kind):
        self.toks.append((glyphs, kind))

    def op(self, ch):
        A, B = self.A, self.B
        if ch == "M":
            self.B = A
        elif ch == "W":
            self.A, self.B = B, A
        elif ch == "b":
            self.BP = A
        elif ch == "+":
            self.A = A + B
        elif ch == "-":
            self.A = A - B
        elif ch == "*":
            self.A = A * B
        elif ch == "N":
            self.A = -A
        elif ch == "&":
            self.A = A & B
        elif ch == "|":
            self.A = A | B
        elif ch == "~":
            self.A = A ^ B
        elif ch == "{":
            self.A = (A << B) if 0 <= B <= 63 else 0
        elif ch == "}":
            self.A = (A >> B) if 0 <= B <= 63 else (0 if B < 0 else (-1 if A < 0 else 0))
        elif ch == "%":
            self.A = 0 if B == 0 else A - B * (A // B)
        elif ch in "0123456789":
            self.A = int(ch)
        else:
            raise ValueError(ch)
        self._t(ch, OP)
        return self

    def lit(self, n):
        """A = n.  Single digits are one cell; longer numbers need backticks."""
        assert n >= 0
        s = str(n)
        if len(s) == 1:
            return self.op(s)
        self.A = n
        self._t("`" + s + "`", OP)
        return self

    def push(self, name):
        """scratch-send A, remembering it under `name`."""
        self.q.append((name, self.A))
        self.npush += 1
        self.maxq = max(self.maxq, len(self.q))
        self._t("s", SCRATCH)
        return self

    def rot(self):
        n, v = self.q.pop(0)
        self._t("r", READ)
        self.q.append((n, v))
        self._t("s", SCRATCH)
        self.npush += 1
        self.A = v
        return self

    def fetch(self, name):
        """pop `name`, rotating the fifo past anything in front of it."""
        names = [n for n, _ in self.q]
        assert name in names, f"{name} not in fifo {names}"
        while self.q[0][0] != name:
            self.rot()
        n, v = self.q.pop(0)
        self.A = v
        self._t("r", READ)
        return self

    def out(self):
        """send A to MOD."""
        self.sent.append(self.A)
        self._t("s", OUT)
        return self

    # ---- convenience ----
    def use(self, name, keep=False):
        """A = `name`; with keep=True immediately re-push it for a later use.
        Keeping ONE circulating copy beats pushing N copies: every extra copy
        sits in front of every later fetch and gets rotated past."""
        self.fetch(name)
        if keep:
            self.push(name)
        return self

    def arrange(self, order):
        """Rotate until the fifo reads exactly `order`.  Called before the tail,
        so the tail can be pure `r` cells -- no scratch `s` near the MOD pipe."""
        assert sorted(n for n, _ in self.q) == sorted(order), \
            (f"{[n for n, _ in self.q]} != {order}")
        while [n for n, _ in self.q] != list(order):
            self.rot()
        return self


# ─────────────────────────────────────────────────────────────────────────────
# the setup program
# ─────────────────────────────────────────────────────────────────────────────

def setup(e):
    """Emit the whole per-round setup.  Ends with:
         A = P0, B = Ic, BP = cnt, and Jc already sent to MOD.

    Every constant is a SINGLE DIGIT: coordinates are < 32, so a sign test is
    `>> 5`, not `>> 63`, and 4096*x is `x<<6<<6`.  That removes every backtick
    literal from the grid -- multi-cell tokens are what make a serpentine layout
    (and its westward rows, which read literals reversed) fragile.
    """
    u = e.use
    # ---------------- inputs -> DX, DY, addr0 ----------------
    e.fetch("x0"); e.push("x0"); e.op("M")            # B = x0, keep x0 for addr0
    e.fetch("y0"); e.push("y0"); e.push("y0")         # y0 for addr0 and for DY
    e.fetch("x1"); e.op("-"); e.push("DX")            # DX = x1 - x0
    u("y0"); e.op("M")                                # B = y0
    e.fetch("y1"); e.op("-"); e.push("DY")            # DY = y1 - y0
    e.op("5"); e.op("M")
    u("y0"); e.op("{"); e.op("M")                     # B = 32*y0
    u("x0"); e.op("+"); e.push("addr0")               # addr0 = 32*y0 + x0

    # ---------------- gx, adx ; gy, ady ----------------
    e.op("5"); e.op("M")
    u("DX", keep=True); e.op("}"); e.op("M")          # B = gx = DX>>5 (-1 iff DX<0)
    e.push("gx")
    u("DX"); e.op("~"); e.op("-"); e.push("adx")      # adx = (DX^gx) - gx
    e.op("5"); e.op("M")
    u("DY", keep=True); e.op("}"); e.op("M")          # B = gy
    e.push("gy")
    u("DY"); e.op("~"); e.op("-"); e.push("ady")      # ady

    # ---------------- sx = +-1 and vy = +-32 ----------------
    e.op("1"); e.op("M")
    u("gx"); e.op("{"); e.op("|"); e.push("sx")
    u("gy"); e.op("{"); e.op("|"); e.push("uy")       # uy = sy
    e.op("5"); e.op("M")
    u("uy"); e.op("{"); e.push("vy")                  # vy = 32*sy

    # ---------------- D, m, |D|, L ----------------
    u("ady", keep=True); e.op("M")
    u("adx", keep=True); e.op("-"); e.push("D")       # D = adx - ady
    e.op("5"); e.op("M")
    u("D", keep=True); e.op("}"); e.push("m")         # m = -1 iff adx < ady
    u("m", keep=True); e.op("M")
    u("D", keep=True); e.op("~"); e.op("-"); e.push("dd")   # dd = |D| = L - S
    u("m", keep=True); e.op("M")
    u("D"); e.op("&"); e.op("M")                      # B = t = D & m
    u("adx", keep=True); e.op("-"); e.push("L")       # L = adx - t = max(adx,ady)

    # ---------------- sg = (L-1)>>5   (-1 exactly when L == 0) ----------------
    e.op("1"); e.op("M")
    u("L", keep=True); e.op("-"); e.push("Lm")
    e.op("5"); e.op("M")
    u("Lm"); e.op("}"); e.push("sg"); e.push("sg")

    # ---------------- qq = -4096*(|D| - sg)   (Jc's bulk, computed early so
    # that dd and one sg leave the fifo before the wide Ic block) ------------
    e.op("6"); e.op("M")
    u("dd"); e.op("{"); e.op("{"); e.push("q1")       # 4096*|D|
    u("sg"); e.op("{"); e.op("{"); e.op("M")          # B = 4096*sg
    u("q1"); e.op("-"); e.op("N"); e.push("qq")

    # ---------------- maxL, P0, cnt ----------------
    u("sg"); e.op("M")
    u("L", keep=True); e.op("-"); e.push("maxL")      # maxL = L - sg
    e.op("1"); e.op("M")
    u("maxL"); e.op("{"); e.op("N"); e.op("+")        # f0 = 1 - 2*maxL
    e.push("f0")                                      # `5` below would clobber A
    e.op("5"); e.op("M")
    u("f0"); e.op("{"); e.op("{"); e.op("M")          # B = f0 << 10
    u("addr0"); e.op("+"); e.push("P0")
    e.op("1"); e.op("M")
    u("L"); e.op("+"); e.op("b")                      # BP = cnt = L + 1

    # ---------------- Ic = Ea + ((Eb-Ea) & m) ----------------
    e.op("6"); e.op("M")
    u("ady"); e.op("{"); e.op("{"); e.op("M")         # B = 4096*ady
    u("sx", keep=True); e.op("+"); e.push("Ea"); e.push("Ea")
    e.op("6"); e.op("M")
    u("adx"); e.op("{"); e.op("{"); e.op("M")         # B = 4096*adx
    u("vy", keep=True); e.op("+")                     # Eb
    e.op("M"); u("Ea"); e.op("-"); e.op("N")          # Eb - Ea
    e.op("M"); u("m"); e.op("&"); e.op("M")           # B = (Eb-Ea) & m
    u("Ea"); e.op("+"); e.push("Ic"); e.push("Ic")

    # ---------------- Jc = (sx + vy) + qq - Ic ----------------
    u("sx"); e.op("M")
    u("vy"); e.op("+"); e.op("M")
    u("qq"); e.op("+"); e.op("M")
    u("Ic"); e.op("N"); e.op("+")

    e.arrange(["Ic", "P0"])
    e.out()                                           # Jc -> MOD (round header)
    e.fetch("Ic"); e.op("M")                          # B = Ic
    e.fetch("P0")                                     # A = P0
    return e


def run(x0, y0, x1, y1):
    e = Emit(x0, y0, x1, y1)
    setup(e)
    return e


# ─────────────────────────────────────────────────────────────────────────────
# verification
# ─────────────────────────────────────────────────────────────────────────────

def check_kernel(verbose=True):
    """The branch-free recurrence P_{k+1} = (P_k + Ic) mod Jc reproduces the
    verified branchy loop, and P_k = (P0 + k*Ic) mod Jc reproduces it too."""
    bad = 0
    for x0 in range(32):
        for y0 in range(24):
            for x1 in range(32):
                for y1 in range(24):
                    P0, Ic, Jc, cnt, _ = consts(x0, y0, x1, y1)
                    want = reference(x0, y0, x1, y1)
                    P = P0
                    got = []
                    ramp = []
                    for k in range(cnt):
                        got.append(P & 1023)
                        ramp.append((P0 + k * Ic) % Jc & 1023)
                        P = (P + Ic) % Jc
                    if got != want or ramp != want:
                        bad += 1
                        if bad < 4:
                            print("KERNEL MISMATCH", x0, y0, x1, y1)
    if verbose:
        print(f"kernel: 589824 segments, {bad} mismatches")
    return bad


def check_setup(verbose=True, sample=None):
    """Simulated setup produces exactly consts()'s (P0, Ic, Jc, cnt)."""
    bad = 0
    n = 0
    maxq = 0
    npush = None
    ntok = None
    rng = range(0, 32) if sample is None else range(0, 32, sample)
    rngy = range(0, 24) if sample is None else range(0, 24, sample)
    for x0 in rng:
        for y0 in rngy:
            for x1 in rng:
                for y1 in rngy:
                    n += 1
                    e = run(x0, y0, x1, y1)
                    # exactly what the grid does: CTRL emits the raw ramp,
                    # MOD reduces it mod Jc, ADDRM masks off the low 10 bits.
                    P0, Ic, BP, (Jc,) = e.A, e.B, e.BP, tuple(e.sent)
                    got = [((P0 + k * Ic) % Jc) & 1023 for k in range(BP)]
                    want = reference(x0, y0, x1, y1)
                    if got != want:
                        bad += 1
                        if bad < 4:
                            print("SETUP MISMATCH", (x0, y0, x1, y1),
                                  "P0,Ic,Jc,cnt", (P0, Ic, Jc, BP),
                                  "\n got ", got, "\n want", want)
                    maxq = max(maxq, e.maxq)
                    if npush is None:
                        npush, ntok = e.npush, len(e.toks)
                    else:
                        assert npush == e.npush and ntok == len(e.toks), \
                            "op stream must be input-independent"
    if verbose:
        cells = sum(len(g) for g, _ in run(3, 4, 20, 19).toks)
        print(f"setup: {n} segments, {bad} mismatches; "
              f"{ntok} ops / {cells} cells, {npush} scratch pushes, max fifo {maxq}")
    return bad


if __name__ == "__main__":
    if "--kernel" in sys.argv:
        check_kernel()
    check_setup(sample=None if "--full" in sys.argv else 3)

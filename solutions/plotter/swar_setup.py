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
        self.path = None
        self.split = self.merge = 0

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

    def relabel(self, mapping):
        """Rename fifo entries with no ops at all -- how the cheap side of the
        octant branch 'reorders' its four values."""
        self.q = [(mapping.get(n, n), v) for n, v in self.q]
        return self

    def arrange(self, order):
        """Rotate until the fifo reads exactly `order`.

        `fetch(x)` followed by `push(x)` is *identical* to a rotation, so the
        only fifo states reachable without register help are CYCLIC SHIFTS of
        the current one -- permuting needs values parked in A and B, which is
        what the octant paths do by hand.  This helper therefore only rotates,
        and asserts that the target is reachable."""
        names = [n for n, _ in self.q]
        assert sorted(names) == sorted(order), f"{names} != {order}"
        for _ in range(len(order)):
            if [n for n, _ in self.q] == list(order):
                return self
            self.rot()
        raise AssertionError(f"{names} is not a rotation of {order}")


# ─────────────────────────────────────────────────────────────────────────────
# the setup program
# ─────────────────────────────────────────────────────────────────────────────

def _schedule(pop, tgt):
    """Ops that emit `pop` (the fifo, front first) as `tgt`, using A and B as the
    only two carry slots.  Returns None when two slots are not enough."""
    A = B = None                    # None = register holds nothing live
    ops, i, j = [], 0, 0
    while j < len(tgt):
        want = tgt[j]
        if A == want:
            ops.append("s"); A = None; j += 1
        elif B == want:
            ops.append("W"); A, B = B, A
            ops.append("s"); A = None; j += 1
        elif i < len(pop):
            if A is not None:
                if B is not None:
                    return None
                ops.append("M"); B = A; A = None
            ops.append("r"); A = pop[i]; i += 1
        else:
            return None
    return ops


def converge(e, mapping, target):
    """Reorder the fifo into `target` (a list of labels), relabelling as it goes.

    Both octants call this; they differ only in `mapping`, so they end with the
    fifo reading the same labels in the same order and can share the tail."""
    inv = {lb: v for v, lb in mapping.items()}
    tgt = [inv[lb] for lb in target]
    names = [n for n, _ in e.q]
    best = None
    for k in range(len(names)):
        sched = _schedule(names[k:] + names[:k], tgt)
        if sched is not None and (best is None or len(sched) + 2 * k < best[0]):
            best = (len(sched) + 2 * k, k, sched)
    assert best, (names, tgt)
    _, k, sched = best
    for _ in range(k):
        e.rot()
    live = []                        # values fetched but not yet pushed
    for op in sched:
        if op == "r":
            n = e.q[0][0]
            e.fetch(n)
            live.append(n)
        elif op == "s":
            e.push(mapping[live.pop()])
        else:
            e.op(op)
            if op == "W" and len(live) == 2:
                live.reverse()
    return e


def setup_pre(e):
    """Everything both octants share, ending with A = ady - adx (the branch test)
    and the fifo holding exactly [adx, ady, sx, vy, addr0]."""
    u = e.use
    # inputs -> DX, DY, addr0
    e.fetch("x0"); e.push("x0"); e.op("M")            # B = x0, keep x0 for addr0
    e.fetch("y0"); e.push("y0"); e.push("y0")         # y0 for addr0 and for DY
    e.fetch("x1"); e.op("-"); e.push("DX")            # DX = x1 - x0
    u("y0"); e.op("M")
    e.fetch("y1"); e.op("-"); e.push("DY")            # DY = y1 - y0
    e.op("5"); e.op("M")
    u("y0"); e.op("{"); e.op("M")                     # B = 32*y0
    u("x0"); e.op("+"); e.push("addr0")               # addr0 = 32*y0 + x0
    # |DX|, |DY| and the two unit steps.  Coordinates are < 32, so `>>5` is a
    # sign test and every constant in this program is a single digit.
    e.op("5"); e.op("M")
    u("DX", keep=True); e.op("}"); e.op("M"); e.push("gx")
    u("DX"); e.op("~"); e.op("-"); e.push("adx")
    e.op("5"); e.op("M")
    u("DY", keep=True); e.op("}"); e.op("M"); e.push("gy")
    u("DY"); e.op("~"); e.op("-"); e.push("ady")
    e.op("1"); e.op("M")
    u("gx"); e.op("{"); e.op("|"); e.push("sx")       # sx  = +-1
    u("gy"); e.op("{"); e.op("|"); e.push("uy")
    e.op("5"); e.op("M")
    u("uy"); e.op("{"); e.push("vy")                  # vy  = +-32
    # Branch test.  `X` has THREE outcomes and a three-way merge costs cells, so
    # make the test odd -- 2*(|DY|-|DX|)+1 is never 0, and |DX| == |DY| (which
    # then lands on the y-major side) draws the same pixels either way because a
    # 45-degree line carries on every step.
    u("adx", keep=True); e.op("M")
    u("ady", keep=True); e.op("-"); e.push("T")
    e.op("1"); e.op("M")
    e.fetch("T"); e.op("{"); e.op("|")
    return e


TARGET = ("addr0", "mind", "L", "S", "majd")

MAP_X = {"adx": "L", "ady": "S", "sx": "majd", "vy": "mind", "addr0": "addr0"}
MAP_Y = {"ady": "L", "adx": "S", "vy": "majd", "sx": "mind", "addr0": "addr0"}


def setup_path_major_x(e):
    """|DX| >= |DY|."""
    return converge(e, MAP_X, TARGET)


def setup_path_major_y(e):
    """|DX| < |DY|: the two axes swap roles."""
    return converge(e, MAP_Y, TARGET)


def setup_tail(e):
    """Shared: fifo [L, S, majd, mind, addr0] -> A = P0, B = Ic, BP = cnt, Jc sent.

        Ic = 4096*S + majd        Jc = -4096*maxL + mind
        P0 = ((1 - 2*maxL) << 10) + addr0        cnt = L + 1
        maxL = L - ((L-1) >> 5)   -- max(L,1); L = 0 is the single-pixel case,
        where an unclamped Jc would be tiny and `%` would mangle P0.
    """
    u = e.use
    e.op("1"); e.op("M")
    u("L", keep=True); e.op("-"); e.push("Lm")
    e.op("5"); e.op("M")
    u("Lm"); e.op("}"); e.push("sg")
    e.op("6"); e.op("M")
    u("S"); e.op("{"); e.op("{"); e.op("M")           # B = 4096*S
    u("majd"); e.op("+"); e.push("Ic")
    e.op("1"); e.op("M")
    u("L", keep=True); e.op("+"); e.op("b")           # BP = cnt = L + 1
    u("sg"); e.op("M")
    u("L"); e.op("-"); e.push("maxL"); e.push("maxL")
    e.op("1"); e.op("M")
    u("maxL"); e.op("{"); e.op("N"); e.op("+")        # f0 = 1 - 2*maxL
    e.push("f0")
    e.op("5"); e.op("M")
    u("f0"); e.op("{"); e.op("{"); e.op("M")          # B = f0 << 10
    u("addr0"); e.op("+"); e.push("P0")
    e.op("6"); e.op("M")
    u("maxL"); e.op("{"); e.op("{"); e.op("N"); e.op("M")
    u("mind"); e.op("+")                              # Jc
    e.arrange(["Ic", "P0"])
    e.out()                                           # Jc -> MOD (round header)
    e.fetch("Ic"); e.op("M")                          # B = Ic
    e.fetch("P0")                                     # A = P0
    return e


def setup(e):
    """The whole per-round setup, taking the branch the test selects."""
    setup_pre(e)
    e.split = len(e.toks)
    if e.A < 0:
        e.path = "x"
        setup_path_major_x(e)
    else:
        e.path = "y"
        setup_path_major_y(e)
    e.merge = len(e.toks)
    setup_tail(e)
    return e


def segments():
    """(pre, path_x, path_y, tail) token lists.  The two paths are laid out side
    by side in a branch block; `tail` is emitted once and shared, which is only
    sound because both paths leave the fifo reading TARGET."""
    a = Emit(3, 4, 20, 19); setup(a)          # |DX| > |DY| -> x-major
    b = Emit(4, 3, 19, 20); setup(b)          # |DX| < |DY| -> y-major
    assert a.path == "x" and b.path == "y"
    assert a.toks[:a.split] == b.toks[:b.split]
    assert a.toks[a.merge:] == b.toks[b.merge:], "shared tail must be identical"
    return (a.toks[:a.split], a.toks[a.split:a.merge],
            b.toks[b.split:b.merge], a.toks[a.merge:])


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
    shapes = {}
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
                    key = e.path
                    if key not in shapes:
                        shapes[key] = (e.npush, len(e.toks))
                    else:
                        assert shapes[key] == (e.npush, len(e.toks)), \
                            f"{key}: op stream must be input-independent"
    if verbose:
        print(f"setup: {n} segments, {bad} mismatches; (pushes, ops) per path "
              f"{shapes}, max fifo {maxq}")
    return bad


if __name__ == "__main__":
    if "--kernel" in sys.argv:
        check_kernel()
    check_setup(sample=None if "--full" in sys.argv else 3)

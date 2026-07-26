"""Count belt ACCESSES (LA/SA) and rotations per phase, and per macro."""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lllm_build as B

CNT = collections.Counter()
ROT = [0]

_LA, _SA, _rot = B.Asm.LA, B.Asm.SA, B.Asm.rot


def LA(self, n):
    CNT['LA'] += 1
    _LA(self, n)


def SA(self, n):
    CNT['SA'] += 1
    _SA(self, n)


def rot(self):
    ROT[0] += 1
    _rot(self)


B.Asm.LA, B.Asm.SA, B.Asm.rot = LA, SA, rot


def measure(fn):
    CNT.clear(); ROT[0] = 0
    a = B.Asm()
    fn(a)
    n = 0
    for x in a.ops:
        if isinstance(x, tuple) and x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
            pass
        n += 1
    def flat(o):
        m = 0
        for x in o:
            if isinstance(x, tuple) and x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
                m += flat(x[1])
            else:
                m += 1
        return m
    return flat(a.ops), CNT['LA'], CNT['SA'], ROT[0]


for name, fn in [("fill", B.emit_fill), ("render", B.emit_render),
                 ("fetch", B.emit_fetch), ("tick", B.emit_tick),
                 ("decode", lambda a: B.emit_decode(a, 'P4', 'P7', 'P5')),
                 ("EQ", lambda a: a.EQ('P0', 'P1', 43)),
                 ("GT0", lambda a: a.GT0('P0', 'P1')),
                 ("binS", lambda a: a.binS('P0', 'P1', 'P2', '*')),
                 ("blend", lambda a: B.blend(a, 'AA', 'P4'))]:
    ops, la, sa, rot_ = measure(fn)
    acc = la + sa
    print(f"{name:8s} ops={ops:6d} LA={la:4d} SA={sa:4d} acc={acc:4d} rot={rot_:5d} "
          f"ops/acc={ops/max(acc,1):5.1f} rot/acc={rot_/max(acc,1):4.1f}")

"""Optimized controller op-stream v2. Same 6 outputs (rowHi,rowLo,colHi,colLo,
boxHi,boxLo) validated 729/729 vs reference, but fewer ops per cell.

Key wins over ctrl_onering:
  (1) precompute vbit = 1<<(v-1) ONCE, share across 3 kinds. Each kind then does
      base = vbit << (9*field) instead of re-fetching v and recomputing 1<<(9f+v-1).
      Removes 3x (fetch-v rotations + add + sub-1) -> big rotation cut.
  (2) keep rk handling cheap.
"""
import collections

M64 = (1 << 64) - 1
def w64(x):
    x &= M64
    return x - (1 << 64) if x >= (1 << 63) else x

SINKS = ('rowHi','rowLo','colHi','colLo','boxHi','boxLo')

def run(prog, inp, trace=False):
    A = B = 0
    S = collections.deque()
    IN = collections.deque(inp)
    OUT = {n: [] for n in SINKS}
    for i, op in enumerate(prog):
        k = op if isinstance(op, str) else op[0]
        if trace: print(i, op, '| A', A, 'B', B, 'S', list(S))
        if k == 'c': A = op[1]
        elif k == 'M': B = A
        elif k == 'W': A, B = B, A
        elif k == '+': A = w64(A + B)
        elif k == '-': A = w64(A - B)
        elif k == '*': A = w64(A * B)
        elif k == '&': A = w64(A & B)
        elif k == '|': A = w64(A | B)
        elif k == '{': A = w64(A << B) if 0 <= B <= 63 else 0
        elif k == '/':
            if B == 0: d = A; A = 0; B = d
            else:
                q = A // B; r = A - q * B; A = w64(q); B = w64(r)
        elif k == 'sS': S.append(A)
        elif k == 'rS': A = S.popleft()
        elif k == 'rIN': A = IN.popleft()
        elif k in OUT: OUT[k].append(A)
        else: raise Exception('badop ' + str(op))
    return OUT, list(S)

def ref(r, c, v):
    box = 3 * (r // 3) + (c // 3)
    out = {}
    for kind, idx in (('row', r), ('col', c), ('box', box)):
        field = idx % 5; rk = idx // 5
        base = 1 << (9 * field + (v - 1))
        out[kind + 'Lo'] = base * (1 - rk); out[kind + 'Hi'] = base * rk
    return out

class Emit:
    def __init__(self):
        self.p = []; self.S = []; self.A = None; self.B = None
    def op(self, *ops): self.p.extend(ops)
    def rIN(self, name): self.op('rIN'); self.A = name
    def sS(self, name=None):
        if name is not None: self.A = name
        assert self.A is not None; self.S.append(self.A); self.op('sS')
    def rS(self): assert self.S, "ring empty"; self.A = self.S.pop(0); self.op('rS')
    def M(self): self.op('M'); self.B = self.A
    def W(self): self.op('W'); self.A, self.B = self.B, self.A
    def c(self, k): self.op(('c', k)); self.A = f"={k}"
    def add(self): self.op('+'); self.A = f"({self.A}+{self.B})"
    def sub(self): self.op('-'); self.A = f"({self.A}-{self.B})"
    def mul(self): self.op('*'); self.A = f"({self.A}*{self.B})"
    def shl(self): self.op('{'); self.A = f"({self.A}<<{self.B})"
    def div(self): self.op('/'); a,b=self.A,self.B; self.A=f"({a}//{b})"; self.B=f"({a}%{b})"
    def emit_sink(self, name): assert name in SINKS; self.op(name)
    def rotate_to_front(self, name):
        g = 0
        while self.S[0] != name:
            self.rS(); self.sS(); g += 1; assert g < 30, (name, self.S)

def kind_block(e, kind):
    """Entry: A holds this kind's idx (already popped). vbit is in the ring.
    Emits kind Hi then Lo. vbit stays in ring."""
    e.M(); e.c(5); e.W(); e.div()        # A=rk, B=field
    e.A = 'rk'; e.B = 'field'
    e.sS('rk')                           # stash rk at back  (ring: ...,rk)
    e.W()                                # A=field, B=rk
    e.A = 'field'
    e.M(); e.c(9); e.mul()               # A=9*field, B=9
    e.A = '9f'
    e.M()                                # B=9field
    e.rotate_to_front('vbit')            # bring vbit to front
    e.rS(); e.sS()                       # A=vbit, re-stash vbit at back
    e.A = 'vbit'
    e.shl()                              # A = vbit<<9field = base
    e.A = 'base'
    e.M()                                # B=base
    e.rotate_to_front('rk')              # bring rk to front (consume)
    e.rS()                               # A=rk
    e.A = 'rk'
    e.mul()                              # A=base*rk=bitHi, B=base
    e.A = 'bitHi'
    e.emit_sink(kind + 'Hi')
    e.W(); e.sub()                       # A=base-bitHi=bitLo
    e.A = 'bitLo'
    e.emit_sink(kind + 'Lo')

def build():
    e = Emit()
    # read r,c,v -> ring [r,c]; v consumed into vbit
    e.rIN('r'); e.sS()
    e.rIN('c'); e.sS()
    e.rIN('v')                           # A=v
    # vbit = 1<<(v-1)
    e.M(); e.c(1); e.W(); e.sub()        # A=v-1, B=1
    e.A = 'v-1'
    e.M(); e.c(1); e.shl()               # A=1<<(v-1)=vbit, B=v-1
    e.A = 'vbit'
    e.sS()                               # ring [r,c,vbit]
    # ---- box = 3*(r//3) + c//3 ----
    e.rotate_to_front('r'); e.rS(); e.sS()   # peek r, re-stash (ring [c,vbit,r])
    e.A = 'r'
    e.M(); e.c(3); e.W(); e.div()            # A=r//3
    e.M(); e.c(3); e.mul()                   # A=3*(r//3)
    e.A = '3r3'
    e.sS()                                    # ring [c,vbit,r,3r3]
    e.rotate_to_front('c'); e.rS(); e.sS()   # peek c, re-stash (ring [vbit,r,3r3,c])
    e.A = 'c'
    e.M(); e.c(3); e.W(); e.div()            # A=c//3
    e.M()                                     # B=c//3
    e.rotate_to_front('3r3'); e.rS()         # A=3r3 (consume)
    e.A = '3r3'
    e.add()                                   # A=box
    e.A = 'box'
    e.sS()                                     # append box (ring [vbit,r,c,box] order varies)
    # process kinds
    e.rotate_to_front('r'); e.rS()            # A=r
    kind_block(e, 'row')
    e.rotate_to_front('c'); e.rS()            # A=c
    kind_block(e, 'col')
    e.rotate_to_front('box'); e.rS()          # A=box
    kind_block(e, 'box')
    # drain leftover (vbit) to keep round pure
    while e.S:
        e.rS()
    return e.p

def build_dispatch():
    prog = build()
    out = []
    for op in prog:
        if isinstance(op, str) and op in SINKS:
            out.append('sD')
        else:
            out.append(op)
    return out

def opstats(prog):
    from collections import Counter
    c = Counter()
    for op in prog:
        k = op if isinstance(op, str) else op[0]
        c[k] += 1
    return c

if __name__ == '__main__':
    prog = build()
    fails = 0; ex = []
    for r in range(9):
        for c in range(9):
            for v in range(1, 10):
                out, leftover = run(prog, [r, c, v])
                got = {k: (out[k][0] if out[k] else None) for k in out}
                want = ref(r, c, v)
                gotcmp = {kk: got[kk] for kk in want}
                if gotcmp != want or leftover:
                    fails += 1
                    if len(ex) < 6: ex.append((r, c, v, gotcmp, want, leftover))
    print('fails', fails, 'of 729')
    for e in ex: print('FAIL', e)
    print('op-count', len(prog))
    from collections import Counter
    print('stats', dict(opstats(prog)))
    rr = opstats(prog)
    print('ring ops (rS+sS):', rr['rS']+rr['sS'])
    out, _ = run(prog, [4, 5, 4])
    print('sink counts', {k: len(out[k]) for k in SINKS})

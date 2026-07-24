"""LEAN 1-RING controller op-stream for the multi-man sudoku validator.

ONE scratch ring S (FIFO) + input pipe + six send-sinks. Emits per round the six
values (rowHi,rowLo,colHi,colLo,boxHi,boxLo); each is physically SENT TWICE to
its storage man. Validated 729/729 vs the reference.

A symbolic compiler (Emit) tracks a model ring while emitting ops so all rotate
counts are compile-time constants derived from the (value-independent) ring order.
"""
import collections

M64 = (1 << 64) - 1
def w64(x):
    x &= M64
    return x - (1 << 64) if x >= (1 << 63) else x

SINKS = ('rowHi','rowLo','colHi','colLo','boxHi','boxLo')  # emit/dispatch order

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
    def sS(self): assert self.A is not None; self.S.append(self.A); self.op('sS')
    def rS(self): assert self.S, "ring empty"; self.A = self.S.pop(0); self.op('rS')
    def M(self): self.op('M'); self.B = self.A
    def W(self): self.op('W'); self.A, self.B = self.B, self.A
    def c(self, k): self.op(('c', k)); self.A = f"={k}"
    def add(self): self.op('+'); self.A = f"({self.A}+{self.B})"
    def sub(self): self.op('-'); self.A = f"({self.A}-{self.B})"
    def mul(self): self.op('*'); self.A = f"({self.A}*{self.B})"
    def shl(self): self.op('{'); self.A = f"(1<<{self.B})"
    def div(self): self.op('/'); a,b=self.A,self.B; self.A=f"({a}//{b})"; self.B=f"({a}%{b})"
    def emit_sink(self, name): assert name in SINKS; self.op(name)
    def rotate(self, n):
        for _ in range(n): self.rS(); self.sS()
    def rotate_to_front(self, name):
        g = 0
        while self.S[0] != name:
            self.rS(); self.sS(); g += 1; assert g < 30, (name, self.S)
    def rotate_to_back(self, name):
        g = 0
        while self.S[-1] != name:
            self.rS(); self.sS(); g += 1; assert g < 30, (name, self.S)

def kind_block(e, kind):
    """Entry: A holds this kind's idx (already popped). Ring = [others..., 'v'].
    Emits kind Hi then Lo. Exit ring contains the same 'others' + 'v'."""
    e.A = 'idx'
    e.M(); e.c(5); e.W(); e.div()        # A=rk, B=field
    e.A = 'rk'; e.B = 'field'
    e.sS()                               # stash rk at back
    e.W()                                # A=field, B=rk
    e.M(); e.c(9); e.mul()               # A=9*field, B=9
    e.A = '9f'
    e.M()                                # B=9field
    e.rotate_to_front('v')               # bring v to front
    e.rS(); e.sS(); e.A = 'v'            # A=v, v back to end
    e.add()                              # A = v + 9field
    e.M(); e.c(1); e.W(); e.sub()        # A = v+9field-1 = bitpos, B=1
    e.M(); e.c(1); e.shl()               # A = base, B=bitpos
    e.A = 'base'
    e.M()                                # B=base (survives the rotate; A is clobbered)
    e.rotate_to_front('rk')
    e.rS()                               # A=rk (consumed)
    e.mul()                              # A=base*rk=bitHi, B=base
    e.A = 'bitHi'
    e.emit_sink(kind + 'Hi')
    e.W(); e.sub()                       # A=base-bitHi=bitLo
    e.A = 'bitLo'
    e.emit_sink(kind + 'Lo')
    e.rotate_to_back('v')

def build():
    e = Emit()
    # read r,c,v -> ring [r,c,v]
    e.rIN('r'); e.sS(); e.rIN('c'); e.sS(); e.rIN('v'); e.sS()
    # ---- box = 3*(r//3) + c//3 ----
    e.rotate_to_front('r'); e.rS(); e.sS()      # peek r, ring restored [c,v,r]
    e.M(); e.c(3); e.W(); e.div()               # A=r//3
    e.M(); e.c(3); e.mul(); e.A = '3r3'         # A=3*(r//3), B=3
    e.sS()                                       # ring [c,v,r,3r3]
    e.rotate_to_front('c'); e.rS(); e.sS()       # peek c
    e.M(); e.c(3); e.W(); e.div()               # A=c//3
    e.M()                                        # B=c//3
    e.rotate_to_front('3r3'); e.rS()             # A=3r3 (consumed)
    e.add(); e.A = 'box'                         # A=box
    e.sS()                                        # append box to ring
    # ring now holds {r,c,v,box}; kind loop wants idx front and v last.
    e.rotate_to_back('v')
    e.rotate_to_front('r'); e.rS()               # A=r
    kind_block(e, 'row')
    e.rotate_to_front('c'); e.rS()               # A=c
    kind_block(e, 'col')
    e.rotate_to_front('box'); e.rS()             # A=box
    kind_block(e, 'box')
    # ring should be empty-ish now (only 'v' may remain). Drain to keep round pure.
    # After 3 kinds, remaining ring = ['v'] (v never consumed). Drain it.
    while e.S:
        e.rS()   # discard leftover (v)
    return e.p

def build_dispatch():
    """Same controller but each sink emit becomes a single dispatch send 'sD'
    (the dispatcher man doubles it). Values are sent in order rowHi,rowLo,colHi,
    colLo,boxHi,boxLo down ONE pipe to the dispatcher."""
    prog = build()
    out = []
    for op in prog:
        if isinstance(op, str) and op in SINKS:
            out.append('sD')          # send this value to the dispatcher (single)
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
                    if len(ex) < 4: ex.append((r, c, v, gotcmp, want, leftover))
    print('fails', fails, 'of 729')
    for e in ex: print('FAIL', e)
    print('op-count', len(prog))
    # sanity: each sink emitted exactly once per round
    out, _ = run(prog, [4, 5, 4])
    print('sink counts', {k: len(out[k]) for k in SINKS})

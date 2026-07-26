"""Faithful op-stream VM for the LLLM interpreter (two-belt model).

Tokens (list, with nested loop nodes):
  registers A,B,BP (i64). state belt (deque) via 'r'/'s'. cells belt via 'rc'/'sc'.
  input via 'ri'. display command via 'cmd' (sends A to driver stream).
  arithmetic mirrors interp/src/value.rs exactly.

Loop nodes:
  ('BPLOOP', body)         : b(BP:=A); do{ body; m(BP--); } while(BP>0)   -> runs A times (A>=1)
  ('KLOOP', cnt_slot, body): belt-counter loop; runs `cnt_slot` (state) times using X back-edge.
                             (VM: read cnt, loop that many times running body; each iter body must
                              NOT rely on BP being preserved across... actually body may use BPLOOP.)
  ('FOREVER', body)        : infinite loop (VM stops when input exhausted / settled).

We keep the VM simple: it executes the structured op-stream directly with Python control
flow for loops, but every primitive matches littleman. The assembler emits the SAME structure
for the grid compiler later.
"""
from collections import deque

MASK=(1<<64)-1
def s64(v):
    v&=MASK
    return v-(1<<64) if v&(1<<63) else v
def add(a,b): return s64(a+b)
def sub(a,b): return s64(a-b)
def mul(a,b): return s64(a*b)
def neg(a): return s64(-a)
def and_(a,b): return s64(a&b)
def or_(a,b): return s64(a|b)
def xor(a,b): return s64(a^b)
def shl(a,b): return s64((a&MASK)<<b) if 0<=b<=63 else 0
def ashr(a,b):
    if b<0: return 0
    if b>63: return -1 if a<0 else 0
    return a>>b
def divmod_(a,b):
    if b==0: return (0,a)
    q=a//b  # python floor division already floored; but must match: floored with rem sign of b
    r=a-q*b
    return (s64(q),s64(r))

class VM:
    def __init__(self, inputs, disp_w=16, disp_h=16, swap_preserve=False):
        self.A=0; self.B=0; self.BP=0
        self.state=deque()
        self.cells=deque()   # op belt (one op per cell)
        self.rbelt=deque()   # render belt (addr+1, color pairs)
        self.inp=deque(inputs)
        self.dw=disp_w; self.dh=disp_h
        self.cap=disp_w*disp_h
        self.next=[0]*self.cap
        self.cur=[0]*self.cap
        self.cursor=0
        self.frames=[]
        # driver decode state (cmd protocol: v>0 -> ADDR=v-1 then next cmd is color->DATA;
        #                       v<0 -> SWAP 0 (commit+clear))
        self.pending_addr=None
        # swap_preserve mirrors a driver that sends SWAP=1 (keep the next buffer
        # and the cursor) instead of SWAP=0 (commit and clear).  Delta rendering
        # needs it.
        self.swap_preserve=swap_preserve
        self.ticks=0
        self.out=[]   # test-only output op

    def cmd(self, v):
        # emulate the driver decoding a command value into ADDR/DATA/SWAP ops.
        v=s64(v)
        if self.pending_addr is None:
            if v>0:
                # ADDR := v-1 ; expect color next
                self.cursor=(v-1)%self.cap
                self.pending_addr=True
            else:
                # SWAP: commit; clear next unless the driver sends SWAP=1
                self.cur=self.next[:]
                self.frames.append(self.cur[:])
                if not self.swap_preserve:
                    self.next=[0]*self.cap
                    self.cursor=0
        else:
            # this is the color (DATA)
            self.next[self.cursor%self.cap]=v%16
            self.cursor=(self.cursor+1)%self.cap
            self.pending_addr=None

    def run(self, prog, max_ticks=5_000_000):
        self._exec(prog, max_ticks)

    def _exec(self, ops, max_ticks):
        for op in ops:
            self.ticks+=1
            if self.ticks>max_ticks:
                raise RuntimeError("tick cap")
            if isinstance(op, tuple):
                tag=op[0]
                if tag=='#':
                    self.A=s64(op[1])
                elif tag=='BPLOOP':
                    self.BP=self.A
                    body=op[1]
                    # do { body; BP-- } while BP>0
                    while True:
                        self._exec(body, max_ticks)
                        self.BP=s64(self.BP-1)
                        if not (self.BP>0):
                            break
                elif tag=='FOREVER':
                    body=op[1]
                    while True:
                        if self._exec(body, max_ticks)=='STOP':
                            return
                elif tag=='KLOOP':
                    # counter already in A (caller sets A := count). runs body A times via X back-edge.
                    body=op[1]
                    cnt=self.A
                    # emulate: kc=cnt; loop{ body; kc--; A=kc; X:if>0 loop }
                    while True:
                        self._exec(body, max_ticks)
                        cnt=s64(cnt-1)
                        if not (cnt>0):
                            break
                elif tag=='LOOPX':
                    # real X-sign back-edge: do{ body } while (A>0 after body). Body must leave
                    # the loop-continue value in A (>0 => loop). Mirrors: body; X-backedge.
                    body=op[1]
                    while True:
                        r=self._exec(body, max_ticks)
                        if r=='STOP': return 'STOP'
                        if not (self.A>0):
                            break
                else:
                    raise ValueError(f"bad tuple op {op}")
                continue
            # single char ops
            if op=='r':
                if not self.state:
                    self.state.append(0)
                self.A=self.state.popleft()
            elif op=='s':
                self.state.append(self.A)
            elif op=='rc':
                self.A=self.cells.popleft()
            elif op=='sc':
                self.cells.append(self.A)
            elif op=='rr':
                self.A=self.rbelt.popleft()
            elif op=='sr':
                self.rbelt.append(self.A)
            elif op=='ri':
                if not self.inp:
                    return 'STOP'  # input exhausted -> settle/stop
                self.A=s64(self.inp.popleft())
            elif op=='cmd':
                self.cmd(self.A)
            elif op=='out':
                self.out.append(self.A)
            elif op=='M': self.B=self.A
            elif op=='W': self.A,self.B=self.B,self.A
            elif op=='b': self.BP=self.A
            elif op=='m': self.BP=s64(self.BP-1)
            elif op=='+': self.A=add(self.A,self.B)
            elif op=='-': self.A=sub(self.A,self.B)
            elif op=='*': self.A=mul(self.A,self.B)
            elif op=='N': self.A=neg(self.A)
            elif op=='/':
                q,r=divmod_(self.A,self.B); self.A=q; self.B=r
            elif op=='&': self.A=and_(self.A,self.B)
            elif op=='|': self.A=or_(self.A,self.B)
            elif op=='~': self.A=xor(self.A,self.B)
            elif op=='{': self.A=shl(self.A,self.B)
            elif op=='}': self.A=ashr(self.A,self.B)
            else:
                raise ValueError(f"bad op {op!r}")
        return None

"""Token-level op-stream for the TCP controller, validated against controller_model.
Each token is a real littleman op. Simulating this exact sequence (with A/B/BP,
input queue, W/F storage men, driver/bank, X-branches, gotos) and matching model.py
means the LAYOUT is pure geometry (register logic already proven).
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
M64 = (1 << 64) - 1
def w64(x):
    x &= M64
    return x - (1 << 64) if x >= (1 << 63) else x

class Store:            # storage man holding B; [0]->reply B ; [1,val]->store
    def __init__(s): s.B = 0; s.mode = None
    def feed(s, v):
        if s.mode is None:
            if v == 0: s.mode = None; return s.B      # read: reply
            s.mode = 'w'; return None                 # write: expect val
        s.mode = None; s.B = v; return None

class Bank:
    def __init__(s): s.cell = [0]*16; s.q = []; s.out = []
    def cmd(s, mode, addr, val):
        if mode == 1: s.cell[addr & 15] = val
        else: s.out.append(s.cell[addr & 15])

# op-stream as labelled blocks. Control tokens: ('br',gt,eq,lt),('goto',L),'H'
def LOADW(): return ['c0','sWF','rWR']
def STOREW():return ['M','c1','sWF','W','sWF']
def LOADF(): return ['c0','sFF','rFR']
def STOREF():return ['M','c1','sFF','W','sFF']

def program():
    P = {}
    P['INIT'] = ['r', ('goto','MAIN')]
    P['MAIN'] = (['r','M'] + LOADW() + ['W','-',            # A=off, B=waiting
                 'M',('lit',15),'W','-','b',                # A=off-15 ; BP=A
                 ('br2','HALT','CONT')])            # BP>0 => off>=16 => HALT              # off-15>0 => off>=16 => HALT
    P['HALT'] = ['c1','N','M','c1','sCMD','c0','sCMD','W','sCMD',   # CMD_WRITE(0,-1)
                 'c0','sCMD','c0','sCMD','c0','sCMD','H']            # CMD_READ(0)
    P['CONT'] = (['M',('lit',15),'+','M'] + LOADW() + ['+',        # A=seq = (off-15)+15+waiting
                 'M',('lit',15),'W','&','M',                       # A=slot,B=slot
                 'c1','sCMD','W','sCMD','M','r','sCMD',            # CMD_WRITE(slot,val)
                 'W','M','c1','{','M'] + LOADF() + ['|'] + STOREF()# fmask|=1<<slot
                 + [('goto','DRAIN')])
    P['DRAIN'] = (LOADW() + ['M',('lit',15),'W','&','M','c1','{','M'] + LOADF() + ['&','b',
                  ('br2','BODY','MAIN')])
    P['BODY'] = (LOADW() + ['M',('lit',15),'W','&','M',           # A=w15,B=w15
                 'c0','sCMD','W','sCMD','c0','sCMD']               # CMD_READ(w15)
                 + LOADW() + ['M',('lit',15),'W','&','M','c1','{','M'] + LOADF() + ['~'] + STOREF()
                 + LOADW() + ['M','c1','+'] + STOREW()
                 + [('goto','DRAIN')])
    return P

def run_rounds(rounds):
    P = program()
    A = B = BP = 0
    W = Store(); F = Store(); bank = Bank()
    inq = []
    per = []; base = 0
    label = 'INIT'; idx = 0
    # feed input round-gated: we emulate by supplying all values but tracking output per round
    # Build flat input with round boundaries
    flat = []
    bounds = []
    for j, r in enumerate(rounds):
        vals = [int(x) for x in r['in']]
        if j == 0: flat += vals            # n,seq,val
        else: flat += vals                 # seq,val
        bounds.append(len(bank.out))       # placeholder
    ip = 0
    steps = 0
    # per-round output tracking: we know expected counts; just run to completion of input
    out_marks = []
    rounds_expected = [[int(x) for x in r['out']] for r in rounds]
    # simulate until input exhausted AND control returns to MAIN waiting for input, or HALT
    def nextlabel(lb):
        return lb
    halted = False
    guard = 0
    # We run the token machine; 'r' pulls from flat (blocks->just take next); track out length after each round's packet processed by marking when we return to MAIN top after consuming a packet.
    # Simpler: run whole stream, compare FLAT outputs.
    while not halted:
        guard += 1
        if guard > 2_000_000: raise Exception('loop guard')
        block = P[label]
        if idx >= len(block):
            # fell through end without goto -> shouldn't happen
            raise Exception('fell off '+label)
        tok = block[idx]; idx += 1
        if isinstance(tok, tuple):
            k = tok[0]
            if k == 'lit' or k == 'c':
                A = w64(int(tok[1])); continue
            if k == 'goto': label = tok[1]; idx = 0; continue
            if k == 'br':
                gt, eq, lt = tok[1], tok[2], tok[3]
                label = gt if A > 0 else (eq if A == 0 else lt); idx = 0; continue
            if k == 'br2':
                label = tok[1] if BP > 0 else tok[2]; idx = 0; continue
        else:
            if tok.startswith('c') and tok[1:].isdigit():
                A = int(tok[1:]); continue
            if tok == 'r':
                if ip >= len(flat): halted = True; break   # no more input -> stop
                A = w64(flat[ip]); ip += 1; continue
            if tok == 'b': BP = A; continue
            if tok == 'M': B = A; continue
            if tok == 'W': A, B = B, A; continue
            if tok == '&': A = w64(A & B); continue
            if tok == '|': A = w64(A | B); continue
            if tok == '~': A = w64(A ^ B); continue
            if tok == '+': A = w64(A + B); continue
            if tok == '-': A = w64(A - B); continue
            if tok == 'N': A = w64(-A); continue
            if tok == '{': A = w64(A << B) if 0 <= B <= 63 else 0; continue
            if tok == 'sWF': r = W.feed(A); continue
            if tok == 'rWR': A = w64(W.B); continue
            if tok == 'sFF': r = F.feed(A); continue
            if tok == 'rFR': A = w64(F.B); continue
            if tok == 'sCMD':
                bank.q.append(A)
                if len(bank.q) == 3: bank.cmd(bank.q[0], bank.q[1] & 15, bank.q[2]); bank.q = []
                continue
            if tok == 'H': halted = True; break
        raise Exception('bad tok '+repr(tok))
    return bank.out

if __name__ == '__main__':
    import json
    d = json.load(open(_REPO + '/scratchpad/tcp_problem.json'))
    allok = True
    for i, c in enumerate(d['publicTestData']):
        rounds = c['rounds']
        got = run_rounds(rounds)
        exp = [int(x) for r in rounds for x in r['out']]
        ok = got == exp
        allok = allok and ok
        print(f'case {i} {c["name"]:28s} {"OK" if ok else "FAIL"}')
        if not ok:
            print('   exp', exp)
            print('   got', got)
    print('ALL OK' if allok else 'FAIL')

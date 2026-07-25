"""Register-level controller flowchart for TCP, using ONLY real littleman ops
(A,B,BP registers; storage men W=waiting, F=fmask; driver commands write/read).
Validate against model.py's expected outputs BEFORE laying out geometry.

Man op semantics used:
  digit d: A=d ;  lit k: A=k ; M: B=A ; W: swap A,B ; b: BP=A ; m: BP-=1
  +,-,*,&,|,~,{ : A op= B ; X-branch on A ; d/a branch on BP
  driver.write(addr,val): cell[addr]=val ; driver.read(addr): output cell[addr]
  storeW(A)/loadW()->A ; storeF/loadF : the two fixed storage men (persist in B)
Halts on -1 (off>=16) as the final output.
"""


class Driver:
    def __init__(self):
        self.bank = [0] * 16
        self.out = []
    def write(self, addr, val):
        self.bank[addr & 15] = val
    def read(self, addr):
        self.out.append(self.bank[addr & 15])


def run_stream(packets):
    """packets: list of (seq,val). Returns (outputs, halted). Mirrors the man's
    flowchart exactly (each line is a small run of real ops)."""
    drv = Driver()
    waiting = 0          # storage man W (B register of that man)
    fmask = 0            # storage man F
    for seq, val in packets:
        # --- off = seq - waiting; if off >= 16 -> output -1, halt ---
        off = seq - waiting
        if off >= 16:
            drv.out.append(-1)
            return drv.out, True
        # --- slot = seq & 15 ; write cell[slot]=val ---
        slot = seq & 15
        drv.write(slot, val)
        # --- fmask |= (1 << slot) ---
        fmask = fmask | (1 << slot)
        # --- drain: while fmask bit (waiting&15): read, clear(xor), waiting++ ---
        while True:
            w15 = waiting & 15
            mask = 1 << w15
            if (fmask & mask) == 0:
                break
            drv.read(w15)            # output cell[w15]
            fmask = fmask ^ mask     # clear (bit is set -> xor clears)
            waiting = waiting + 1
    return drv.out, False


def run_rounds(rounds):
    drv = Driver()
    waiting = 0
    fmask = 0
    per = []
    halted = False
    for j, r in enumerate(rounds):
        if halted:
            per.append([]); continue
        vals = [int(x) for x in r['in']]
        seq, val = (vals[1], vals[2]) if j == 0 else (vals[0], vals[1])
        base = len(drv.out)
        off = seq - waiting
        if off >= 16:
            drv.out.append(-1); per.append(drv.out[base:]); halted = True; continue
        slot = seq & 15
        drv.write(slot, val)
        fmask |= (1 << slot)
        while (fmask & (1 << (waiting & 15))) != 0:
            drv.read(waiting & 15)
            fmask ^= (1 << (waiting & 15))
            waiting += 1
        per.append(drv.out[base:])
    return per


if __name__ == '__main__':
    import json
    d = json.load(open('/Users/visenbaev/icfpc26/scratchpad/tcp_problem.json'))
    allok = True
    for i, c in enumerate(d['publicTestData']):
        rounds = c['rounds']
        got = run_rounds(rounds)
        exp = [[int(x) for x in r['out']] for r in rounds]
        ok = got == exp
        allok = allok and ok
        print(f'case {i} {c["name"]:28s} {"OK" if ok else "FAIL"}')
        if not ok:
            for j in range(len(rounds)):
                if got[j] != exp[j]:
                    print(f'   round {j} in={rounds[j]["in"]} exp={exp[j]} got={got[j]}')
    print('ALL OK' if allok else 'FAIL')

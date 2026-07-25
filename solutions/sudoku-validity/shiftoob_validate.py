"""Validate the SHIFT-OOB 3-compute-man encoding.
Each compute man (row/col/box): bit = 9*idx + (v-1); idx = r/c/box.
  lane1 = 1<<bit          (shl returns 0 if bit not in 0..63  -> nonzero iff bit<64)
  lane2 = 1<<(bit-64)     (shl returns 0 if bit-64 not in 0..63 -> nonzero iff 64<=bit<=127)
Each (idx,v) lands in exactly ONE lane. 6 check men (kind x lane) hold masks; dup = lane & mask.
"""
M64 = (1 << 64) - 1
def w64(x):
    x &= M64
    return x - (1 << 64) if x >= (1 << 63) else x

def shl(a, b):                       # models `{`
    return w64((a << b)) if 0 <= b <= 63 else 0

def compute(kind, r, c, v):
    box = 3 * (r // 3) + (c // 3)
    idx = {'row': r, 'col': c, 'box': box}[kind]
    bit = 9 * idx + (v - 1)
    return shl(1, bit), shl(1, bit - 64)   # lane1, lane2

# --- register-flow op simulation of the compute man (to confirm the op stream) ---
def compute_ops(kind, r, c, v):
    """Simulate A,B ops exactly as the built man will run them."""
    A = B = 0
    box = 3 * (r // 3) + (c // 3)
    idx = {'row': r, 'col': c, 'box': box}[kind]
    # A=idx (assume distributor delivered idx)
    A = idx
    # bit = 9*idx + v - 1
    B = A                       # M : B=idx
    A = 9                       # lit 9
    A = w64(A * B)              # * : A=9*idx (B=idx)
    B = A                       # M : B=9*idx
    A = v                       # read v
    A = w64(A + B)              # + : A=v+9*idx  (B=9*idx)
    B = A                       # M : B=v+9idx
    A = 1                       # lit 1
    A, B = B, A                 # W : A=v+9idx, B=1
    A = w64(A - B)              # - : A=bit
    B = A                       # M : B=bit
    # lane1 = 1<<bit
    A = 1                       # lit 1
    A = shl(A, B)               # { : A=1<<bit
    lane1 = A
    # lane2 = 1<<(bit-64)
    A, B = B, A                 # W : A=bit, B=1<<bit
    B = A                       # M : B=bit
    A = 64                      # lit 64 (horizontal backtick)
    A, B = B, A                 # W : A=bit, B=64
    A = w64(A - B)              # - : A=bit-64
    B = A                       # M : B=bit-64
    A = 1                       # lit 1
    A = shl(A, B)               # { : A=1<<(bit-64)
    lane2 = A
    return lane1, lane2

def ref_valid(cells):
    """Reference: cells = list of (r,c,v). Return index of first duplicate or None."""
    seen = set()
    for i, (r, c, v) in enumerate(cells):
        box = 3 * (r // 3) + (c // 3)
        keys = [('r', r, v), ('c', c, v), ('b', box, v)]
        if any(k in seen for k in keys):
            return i
        seen.update(keys)
    return None

def sim_pipeline(cells):
    """Simulate the full machine: per (kind,lane) mask; return first-dup index or None."""
    masks = {(k, l): 0 for k in ('row', 'col', 'box') for l in (1, 2)}
    for i, (r, c, v) in enumerate(cells):
        dup = 0
        newmasks = {}
        for k in ('row', 'col', 'box'):
            l1, l2 = compute_ops(k, r, c, v)
            for lane, val in ((1, l1), (2, l2)):
                m = masks[(k, lane)]
                dup |= (val & m)             # check-man: dup flag = bit & mask
                newmasks[(k, lane)] = m | val
        if dup != 0:
            return i
        masks = newmasks
    return None

if __name__ == '__main__':
    # 1. per-(idx,v) exactly one lane, and op-sim == direct
    bad = 0
    for kind in ('row', 'col', 'box'):
        for r in range(9):
            for c in range(9):
                for v in range(1, 10):
                    d1, d2 = compute(kind, r, c, v)
                    o1, o2 = compute_ops(kind, r, c, v)
                    if (d1, d2) != (o1, o2): bad += 1
                    if (d1 != 0) == (d2 != 0): bad += 1     # exactly one nonzero
    print('per-cell bad:', bad, 'of', 3 * 729)

    # 2. full-pipeline dup detection vs reference on random boards + all public cases
    import json, random
    random.seed(1)
    mism = 0
    for t in range(3000):
        n = random.randint(1, 81)
        cells = [(random.randint(0, 8), random.randint(0, 8), random.randint(1, 9)) for _ in range(n)]
        if sim_pipeline(cells) != ref_valid(cells):
            mism += 1
            if mism <= 3: print('MISMATCH', cells[:6], sim_pipeline(cells), ref_valid(cells))
    print('pipeline mismatches:', mism, 'of 3000 random')

    d = json.load(open('/Users/visenbaev/icfpc26/tests/sudoku-validity.json'))
    for tc in d['publicTestData']:
        cells = [tuple(int(x) for x in rnd['in']) for rnd in tc['rounds']]
        first_dup = sim_pipeline(cells)
        # expected: outputs are 1 until the dup round (0). first '0' index:
        exp0 = next((i for i, rnd in enumerate(tc['rounds']) if rnd['out'] == ['0']), None)
        ok = (first_dup == exp0)
        print(tc['name'][:28], 'sim_dup@', first_dup, 'exp0@', exp0, 'OK' if ok else 'FAIL')

#!/usr/bin/env python3
"""Belt-native MITM subset-sum model (executable spec for ss-mitm.man).

This mirrors EXACTLY what the littleman machine will do, so it doubles as the
ground truth for the build and can be fuzzed against brute force.

Conventions (match mitm_reference.py):
  * full-mask: index i <-> bit (n-1-i).  index 0 = highest bit.
  * Larger full-mask == lexicographically-smaller chosen-INDEX set.
  * Split: h = ceil(n/2) LOW indices 0..h-1 (occupy HIGH bits),
           Rn = n//2  HIGH indices h..n-1 (occupy LOW bits).
    L (low indices) dominates lexicographic order => maximise Lpart first.

Algorithm (all FIFO / forward-read friendly):
  1. Enumerate each half's 2^k subset sums IN SORTED ORDER by iterative MERGING.
     Each entry is packed into a single i64:  packed = sum*MULT + fullpart
     (fullpart carries only that half's bits).  MULT chosen so sum < MULT... no,
     so fullpart < MULT and packed sorts by (sum, fullpart).
  2. Dedup each sorted list: collapse equal sums, keep MAX fullpart (= lex-best).
  3. Two-pointer over L ascending, H descending.  Running-max Lpart over all
     matchable L entries; its paired H entry (maxPH for the needed sum) fixes H.
  4. Reconstruct full = bestLpart | pairedHpart; emit k then chosen values in
     original-index order.  No subset -> emit single 0.
"""

MULT = 1 << 22   # > max fullpart (2^20) and > ... ; packed = sum*MULT + fullpart


def merge_enumerate(vals, idxs, n):
    """Enumerate all subset sums over the given original indices, returning a list
    of packed ints sorted ASCENDING, built by iterative merging (belt-native).
    fullpart uses global bit (n-1-i) for index i."""
    S = [0]  # single entry: sum 0, mask 0  -> packed 0
    for i in idxs:
        v = vals[i]
        bit = 1 << (n - 1 - i)
        delta = v * MULT + bit           # packed increment for adding index i
        # S' = S shifted by delta (still sorted, same order)
        # merge S and (S + delta) via a pending FIFO queue (single pass over S).
        out = []
        pending = []                     # FIFO of already-shifted values (s+delta)
        pi = 0                           # read pointer into S (as a FIFO front)
        qi = 0                           # read pointer into pending
        while pi < len(S) or qi < len(pending):
            take_s = False
            if pi < len(S) and qi < len(pending):
                take_s = S[pi] <= pending[qi]
            elif pi < len(S):
                take_s = True
            else:
                take_s = False
            if take_s:
                a = S[pi]; pi += 1
                out.append(a)
                pending.append(a + delta)   # schedule shifted copy
            else:
                out.append(pending[qi]); qi += 1
        S = out
    return S


def dedup_maxmask(sorted_packed):
    """Collapse equal-sum neighbours in an ascending-by-packed list, keeping the
    entry with the largest fullpart (== largest packed among equal sums, since
    packed = sum*MULT+fullpart).  One forward pass with 1-entry lookahead.
    Returns list of (sum, fullpart) ascending by sum, distinct sums."""
    res = []
    cur_sum = None; cur_full = None
    for p in sorted_packed:
        s = p // MULT; f = p % MULT
        if cur_sum is None:
            cur_sum, cur_full = s, f
        elif s == cur_sum:
            if f > cur_full:
                cur_full = f            # keep max fullpart
        else:
            res.append((cur_sum, cur_full))
            cur_sum, cur_full = s, f
    if cur_sum is not None:
        res.append((cur_sum, cur_full))
    return res


def solve(vals, t):
    n = len(vals)
    Rn = n // 2
    h = n - Rn
    Lidx = list(range(0, h))
    Hidx = list(range(h, n))

    Lpacked = merge_enumerate(vals, Lidx, n)
    Hpacked = merge_enumerate(vals, Hidx, n)

    Lde = dedup_maxmask(Lpacked)               # ascending sum, distinct, maxLpart
    Hde = dedup_maxmask(Hpacked)               # ascending sum, distinct, maxHpart
    Hdesc = list(reversed(Hde))                # descending sum (belt front = largest)

    # two-pointer
    i = 0; j = 0
    best_full = None
    while i < len(Lde) and j < len(Hdesc):
        sL, fL = Lde[i]
        sH, fH = Hdesc[j]
        s = sL + sH
        if s == t:
            cand = fL | fH
            if best_full is None or cand > best_full:
                best_full = cand
            i += 1
        elif s < t:
            i += 1
        else:
            j += 1

    if best_full is None:
        return [0]
    chosen = [idx for idx in range(n) if (best_full >> (n - 1 - idx)) & 1]
    return [len(chosen)] + [vals[idx] for idx in chosen]


# ------------------------------------------------------------------ tests
PUBLIC = [
    ([35598,41872,81980,98583,65116,96540,10035,60706,14417,64505], 248550),
    ([120,180,200,150,100,90,80,70,300,60], 300),
    ([59,89720,63262,24662,73570,35930,83954,41901,92098,37536,35156,701,33952,7954], 240322),
    ([62554,40915,24211,27558,54959,22322,76841,33232,83608,97109], 62554),
    ([1864,1519,695,1825,290,253,1919,302,1542,1283,1486,16687], 16687),
    ([500,500,500,300,300,700,900,500,300,700], 1000),
    ([58443,79693,37155,15450,57084,20590,29841,13454,91581,60485,36863,169,33749,20147,72090,52216,92490,97963,96043,90230], 633441),
    ([3,5,2,6], 8),
]
EXPECT = [
    [5,35598,41872,96540,10035,64505],
    [2,120,180],
    [0],
    [1,62554],
    [1,16687],
    [2,500,500],
    [11,58443,79693,15450,57084,20590,13454,91581,36863,72090,97963,90230],
    [2,3,5],
]


def brute_lexmin(vals, t):
    n = len(vals)
    best = None  # sorted index tuple, lex-min
    for mask in range(1 << n):
        s = 0
        for i in range(n):
            if (mask >> i) & 1:
                s += vals[i]
        if s == t:
            chosen = tuple(i for i in range(n) if (mask >> i) & 1)
            if best is None or chosen < best:
                best = chosen
    if best is None:
        return [0]
    return [len(best)] + [vals[i] for i in best]


if __name__ == "__main__":
    import random
    print("=== public cases ===")
    allok = True
    for (vals, t), exp in zip(PUBLIC, EXPECT):
        got = solve(vals, t)
        ok = got == exp
        allok &= ok
        print(f"n={len(vals):2d} t={t:7d} -> {'OK ' if ok else 'FAIL'} {got}")
        if not ok:
            print("     expected", exp)
    print("ALL OK" if allok else "MISMATCH")

    print("\n=== fuzz vs brute (lex-min) ===")
    random.seed(1)
    fails = 0
    for trial in range(4000):
        n = random.randint(1, 16)
        vals = [random.randint(1, 40) for _ in range(n)]
        t = random.randint(0, sum(vals) + 5)
        got = solve(vals, t)
        exp = brute_lexmin(vals, t)
        if got != exp:
            fails += 1
            if fails <= 20:
                print(f"MISMATCH n={n} vals={vals} t={t}\n  got {got}\n  exp {exp}")
    print(f"fuzz fails: {fails}/4000")

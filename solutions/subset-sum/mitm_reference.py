"""Bounded MITM reference for subset-sum (reconstructed ground truth).

Split: R = last Rn indices (LOW bits), L = first h=n-Rn indices (HIGH bits).
index i <-> bit (n-1-i).  Larger full-mask = prefers lower indices = lex-smallest.
Enumerate Lmask descending (high bits), inner Rmask descending (low bits);
first (Lmask,Rmask) with sL+sR==t wins.

Bounded: only enumerates 2^Rn (<=1024) for the table and 2^h for the outer loop.
For n<=20, Rn<=10 -> both halves <=2^10. Do NOT enumerate 2^n anywhere.
"""

def solve(vals, t, Rn=None):
    n = len(vals)
    if Rn is None:
        Rn = n // 2
    Rn = min(Rn, n)
    h = n - Rn
    # R half = indices [h .. n-1]; Rmask bit j (j in 0..Rn-1) <-> index h+ (Rn-1-j)?
    # Simpler: full mask bit (n-1-i) for index i. R occupies low Rn bits = indices
    # h..n-1 (index n-1 -> bit0). L occupies high h bits = indices 0..h-1.
    # Build R table: for Rmask in [0,2^Rn), sR = sum of R-values selected.
    # A selected R index i (h<=i<n) corresponds to full-bit (n-1-i) which is < Rn.
    def rsum(rmask):
        s = 0
        for i in range(h, n):
            if (rmask >> (n - 1 - i)) & 1:
                s += vals[i]
        return s
    def lsum(lfull):  # lfull already positioned in high bits
        s = 0
        for i in range(0, h):
            if (lfull >> (n - 1 - i)) & 1:
                s += vals[i]
        return s
    # table: list of (sR, Rmask) with sR<=t, in DESCENDING Rmask order
    table = []
    for rmask in range(2**Rn - 1, -1, -1):
        s = rsum(rmask)
        if s <= t:
            table.append((s, rmask))
    # outer L descending. Lmask over h bits, positioned <<Rn.
    for lmask in range(2**h - 1, -1, -1):
        lfull = lmask << Rn
        sL = lsum(lfull)
        if sL > t:
            continue
        need = t - sL
        for (sR, rmask) in table:      # descending Rmask
            if sR == need:
                full = lfull | rmask
                chosen = [i for i in range(n) if (full >> (n - 1 - i)) & 1]
                return chosen, table
    return None, table


def output(vals, t, Rn=None):
    chosen, table = solve(vals, t, Rn)
    if chosen is None:
        return [0]
    return [len(chosen)] + [vals[i] for i in chosen]


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

if __name__ == "__main__":
    import sys
    Rn = int(sys.argv[1]) if len(sys.argv) > 1 else None
    allok = True
    for (vals, t), exp in zip(PUBLIC, EXPECT):
        got = output(vals, t, Rn)
        ok = got == exp
        allok &= ok
        n = len(vals)
        rn = (n // 2) if Rn is None else min(Rn, n)
        print(f"n={n} Rn={rn} t={t} -> {got}  {'OK' if ok else 'FAIL exp '+str(exp)}")
    print("ALL OK" if allok else "MISMATCH")

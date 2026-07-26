#!/usr/bin/env python3
"""Exact Python model of the MITM machine to be built in the grid.

Bit convention (matches mitm_reference.py): index i <-> bit (n-1-i).
Larger integer mask == lexicographically smaller index sequence.
B half = low nb bits (last nb indices), A half = high na bits.

Machine structure modeled 1:1:
  - V[j] = vals[n-1-j] for j in 0..n-1, V[j]=0 for j in n..19
  - NIB[k][m] (k=0..4, m=0..15): sum of V[4k+j] for set bits j of m (DP-built)
  - hash table T[512], entry = TAG*2**40 + key*256 + rmask + nothing (0 = never
    used); staleness via TAG compare, no clearing between rounds
  - insert rmask ascending 0..2^nb-1, skip sum > t, overwrite on equal key
  - A enumeration: m_hi descending, m2 (nibble 2) descending; first hit wins
  - output: k then chosen values by ascending index
"""

TSIZE = 512
TMASK = TSIZE - 1

class Machine:
    def __init__(self):
        self.T = [0] * TSIZE
        self.tag = 0

    def solve_round(self, vals, t):
        n = len(vals)
        self.tag += 1
        TAG = self.tag
        V = [0] * 20
        for i in range(n):
            V[n - 1 - i] = vals[i]
        # nibble DP
        NIB = [[0] * 16 for _ in range(5)]
        for k in range(5):
            for j in range(4):
                bit = 1 << j
                for m in range(bit, bit << 1):
                    NIB[k][m] = NIB[k][m - bit] + V[4 * k + j]
        nb = 8 if n >= 8 else n
        na = n - nb
        na2 = min(na, 4)
        na1 = na - na2
        # B insert
        for rmask in range(0, 1 << nb):
            s = NIB[0][rmask & 15] + NIB[1][rmask >> 4]
            if s > t:
                continue
            packed = TAG * (1 << 40) + s * 256 + rmask
            h = s & TMASK
            while True:
                e = self.T[h]
                if (e >> 40) != TAG:
                    self.T[h] = packed
                    break
                if (e >> 8) & 0xFFFFFFFF == s:
                    self.T[h] = packed  # later rmask = higher rank
                    break
                h = (h + 1) & TMASK
        # A enumeration
        full = None
        for m_hi in range((1 << na1) - 1, -1, -1):
            sum1 = NIB[3][m_hi & 15] + NIB[4][m_hi >> 4]
            need1 = t - sum1
            if need1 < 0:
                continue
            for m2 in range((1 << na2) - 1, -1, -1):
                need = need1 - NIB[2][m2]
                if need < 0:
                    continue
                h = need & TMASK
                hit = None
                while True:
                    e = self.T[h]
                    if (e >> 40) != TAG:
                        break
                    if (e >> 8) & 0xFFFFFFFF == need:
                        hit = e & 255
                        break
                    h = (h + 1) & TMASK
                if hit is not None:
                    full = ((m_hi << 4 | m2) << 8) | hit
                    break
            if full is not None:
                break
        if full is None:
            return [0]
        out = []
        k = 0
        for j in range(19, -1, -1):
            if (full >> j) & 1:
                k += 1
        out.append(k)
        for j in range(n - 1, -1, -1):
            if (full >> j) & 1:
                out.append(V[j])
        return out


def brute(vals, t):
    n = len(vals)
    best = None
    for mask in range(1 << n):
        s = sum(vals[i] for i in range(n) if (mask >> i) & 1)
        if s == t:
            seq = tuple(i for i in range(n) if (mask >> i) & 1)
            if best is None or seq < best:
                best = seq
    if best is None:
        return [0]
    return [len(best)] + [vals[i] for i in best]


if __name__ == "__main__":
    import json, random, sys
    # public cases
    d = json.load(open(__file__.rsplit("/", 2)[0] + "/../tests/subset-sum.json"))
    ok = True
    for c in d["publicTestData"]:
        m = Machine()
        for r in c["rounds"]:
            xs = [int(x) for x in r["in"]]
            n = xs[0]
            vals, t = xs[1:1 + n], xs[1 + n]
            got = [str(x) for x in m.solve_round(vals, t)]
            good = got == r["out"]
            ok &= good
            print(c["name"], "OK" if good else f"FAIL got {got} want {r['out']}")
    # fuzz vs brute force, small n, multiple rounds per machine (tag reuse)
    rng = random.Random(12345)
    fails = 0
    for trial in range(500):
        m = Machine()
        rounds = rng.randint(1, 4)
        for _ in range(rounds):
            n = rng.randint(1, 12)
            style = rng.random()
            if style < 0.4:
                vals = [rng.randint(1, 30) for _ in range(n)]  # dense collisions
            elif style < 0.7:
                vals = [rng.randint(1, 99999) for _ in range(n)]
            else:
                v = rng.randint(1, 500)
                vals = [rng.choice([v, v, 2 * v, rng.randint(1, 50)]) for _ in range(n)]
            total = sum(vals)
            r = rng.random()
            if r < 0.15:
                t = rng.randint(1, max(1, total))
            elif r < 0.3:
                t = total  # everything
            elif r < 0.45:
                t = rng.choice(vals)  # single element likely
            elif r < 0.6:
                k = rng.randint(1, n)
                t = sum(rng.sample(vals, k))  # guaranteed solvable
            else:
                t = rng.randint(1, 2 * total + 5)  # often unsolvable
            got = m.solve_round(vals, t)
            want = brute(vals, t)
            if got != want:
                fails += 1
                print("FUZZ FAIL", vals, t, "got", got, "want", want)
                if fails > 5:
                    sys.exit(1)
    print("fuzz fails:", fails, "| public:", "ALL OK" if ok else "MISMATCH")
    sys.exit(0 if ok and fails == 0 else 1)

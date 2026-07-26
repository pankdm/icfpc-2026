#!/usr/bin/env python3
"""Grid-exact Python model of the nb=7 MITM machine (mirrors build_mitm.py).

Differences vs mitm_machine_model.py (the nb=8 draft): the split_ram belts
cap a bank's block size at ~32-40 cells, so a 1024-cell RAM is not buildable.
This design fits everything in the proven configs:
  - cell RAM 256/8: the hash table T[256] only (<=128 inserts, load <= 50%)
  - scalar RAM 128/4: loop vars + NIB banks + V
  - nb = 7 (B half = last 7 indices, 128 masks), na = n-7 in 3..13
  - packed entry = TAG<<32 | s<<7 | rmask   (s < 2^21, rmask < 2^7)
  - staleness: entry < TAG<<32  <=> stale (tags only grow)

Scalar map (mirrored by the builder):
  0 H  1 E  2 NEED  3 TB  4 M2  5 MHI  6 NEED1  7 M  8 S  9 T
  10 TAG  11 N  12 NA  13 I  14 J  15 K  16 FULL  17 TMP
  18 BB  19 VB  20 WID  21 BANKI  22 BIT  23 SUM1  24 RMASK
  25 M2S  26 MHIS  27 ADDR
  NIB0@28[16] NIB1@44[8] AB0@52[16] AB1@68[16] AB2@84[16] AB3@100[2]
  V@102[20]  (V[j] = vals[n-1-j])

Banks (base, vbase, width): (28,0,4) (44,4,3) (52,7,4) (68,11,4)
(84,15,4) (100,19,1).  A mask bits: m2 = bits 7-10 (AB0),
mhi = bits 11-19 (AB1 low, AB2 mid, AB3 bit 19).
FULL = MHI<<11 | M2<<7 | RMASK.
"""

TSIZE = 256
TMASK = 255
BANKS = [(28, 0, 4), (44, 4, 3), (52, 7, 4), (68, 11, 4), (84, 15, 4), (100, 19, 1)]
VBASE = 102


class Machine:
    def __init__(self):
        self.T = [0] * TSIZE       # cell RAM
        self.s = [0] * 128         # scalar RAM

    def solve_round(self, vals, t):
        s = self.s
        n = len(vals)
        assert n >= 7
        s[11] = n
        s[10] += 1
        s[3] = s[10] << 32         # TB
        s[12] = n - 7              # NA
        for i in range(n):
            s[VBASE + n - 1 - i] = vals[i]
        s[9] = t
        # bank DP
        for base, vbase, wid in BANKS:
            s[base] = 0
            for j in range(wid):
                bit = 1 << j
                for m in range(bit, 2 * bit):
                    s[base + m] = s[base + m - bit] + s[VBASE + vbase + j]
        # INSERT: rmask ascending 0..127
        for m in range(128):
            sm = s[28 + (m & 15)] + s[44 + (m >> 4)]
            if sm - t > 0:
                continue
            packed = s[3] + (sm << 7) + m
            h = sm & TMASK
            while True:
                e = self.T[h]
                if s[3] - e > 0:            # stale -> claim
                    self.T[h] = packed
                    break
                if sm - ((e - s[3]) >> 7) == 0:   # same key -> overwrite
                    self.T[h] = packed
                    break
                h = (h + 1) & TMASK
        # A setup
        na = s[12]
        if na - 4 > 0:
            m2s, mhis = 15, (1 << (na - 4)) - 1
        else:
            m2s, mhis = (1 << na) - 1, 0
        # A enumeration: mhi desc, m2 desc, first hit wins
        full = None
        mhi = mhis
        while mhi >= 0 and full is None:
            sum1 = s[68 + (mhi & 15)] + s[84 + ((mhi >> 4) & 15)] + s[100 + (mhi >> 8)]
            need1 = t - sum1
            if need1 >= 0:
                m2 = m2s
                while m2 >= 0:
                    need = need1 - s[52 + m2]
                    if need >= 0:
                        h = need & TMASK
                        while True:
                            e = self.T[h]
                            if s[3] - e > 0:          # stale -> miss
                                break
                            if need - ((e - s[3]) >> 7) == 0:
                                rmask = e - s[3] - (need << 7)
                                full = (mhi << 11) + (m2 << 7) + rmask
                                break
                            h = (h + 1) & TMASK
                        if full is not None:
                            break
                    m2 -= 1
            mhi -= 1
        if full is None:
            return [0]
        # output
        k = 0
        for j in range(n - 1, -1, -1):
            if (full >> j) & 1:
                k += 1
        out = [k]
        for j in range(n - 1, -1, -1):
            if (full >> j) & 1:
                out.append(s[VBASE + j])
        return out


def brute(vals, t):
    n = len(vals)
    best = None
    for mask in range(1 << n):
        if sum(vals[i] for i in range(n) if (mask >> i) & 1) == t:
            seq = tuple(i for i in range(n) if (mask >> i) & 1)
            if best is None or seq < best:
                best = seq
    if best is None:
        return [0]
    return [len(best)] + [vals[i] for i in best]


if __name__ == "__main__":
    import json, os, random, sys
    here = os.path.dirname(os.path.abspath(__file__))
    d = json.load(open(os.path.join(here, "..", "..", "tests", "subset-sum.json")))
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
    rng = random.Random(4242)
    fails = 0
    for trial in range(600):
        m = Machine()
        for _ in range(rng.randint(1, 4)):
            n = rng.randint(8, 15)
            style = rng.random()
            if style < 0.4:
                vals = [rng.randint(1, 30) for _ in range(n)]
            elif style < 0.7:
                vals = [rng.randint(1, 99999) for _ in range(n)]
            else:
                v = rng.randint(1, 500)
                vals = [rng.choice([v, v, 2 * v, rng.randint(1, 50)]) for _ in range(n)]
            total = sum(vals)
            r = rng.random()
            if r < 0.2:
                t = rng.randint(1, max(1, total))
            elif r < 0.35:
                t = total
            elif r < 0.5:
                t = rng.choice(vals)
            elif r < 0.7:
                t = sum(rng.sample(vals, rng.randint(1, n)))
            else:
                t = rng.randint(1, 2 * total + 5)
            got = m.solve_round(vals, t)
            want = brute(vals, t)
            if got != want:
                fails += 1
                print("FUZZ FAIL", vals, t, "got", got, "want", want)
                if fails > 5:
                    sys.exit(1)
    # a few large-n spot checks
    for trial in range(10):
        m = Machine()
        n = rng.choice([18, 19, 20])
        vals = [rng.randint(1, 99999) for _ in range(n)]
        t = sum(rng.sample(vals, rng.randint(3, 12))) if trial % 2 == 0 else rng.randint(1, sum(vals))
        got = m.solve_round(vals, t)
        want = brute(vals, t)
        if got != want:
            fails += 1
            print("BIG FAIL", n, vals, t, got, want)
    print("fuzz fails:", fails, "| public:", "ALL OK" if ok else "MISMATCH")
    sys.exit(0 if ok and fails == 0 else 1)

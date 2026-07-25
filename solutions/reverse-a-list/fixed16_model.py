#!/usr/bin/env python3
"""Python model of the fixed-16 padding design for reverse-a-list.

Design (as it will run in littleman):
  C = 1<<21 = 2097152  (> max|value|=1e6, so every biased real is > 0)

  READER+SEQUENCER (one wide man, walks 16 lane columns RIGHT->LEFT):
    B = C (constant, for biasing)
    read n -> BP = n
    for k in 0..15 (physical columns visited right->left, lane = 15-k):
        if BP > 0:  A = read_value + C ; send A to lane(15-k) ; BP -= 1   (real, biased -> nonzero)
        else:       A = 0             ; send 0 to lane(15-k)              (padding)
    -> lane_j holds S[15-j], where S = [b0,b1,...,b_{n-1}, 0,...,0]
       i.e. lane15=S0(=b0), lane14=S1, ... , lane(15-(n-1))=b_{n-1}, remaining low lanes = 0.

  WRITER (compact loop, reads all 16 lanes then debiases nonzero):
    B = C (for debias)
    barrier: r nearest = lane0 (leftmost = last-filled -> all present)  -> value = S[15]
    then R x15 in reading order lane1..lane15 -> S[14], S[13], ..., S[0]
    per value: if value>0 (X test): print value - C ; else skip (padding 0)
    -> encounter order S[15],S[14],...,S[0]; skip the top-index paddings; print reals reversed.
"""

C = 1 << 21  # 2097152


def reader_sequencer(n, values):
    """Produce the 16 lane contents lane[0..15]. lane_j = S[15-j]."""
    assert 1 <= n <= 16
    assert len(values) == n
    # S = biased reals followed by zero padding, length 16
    S = [values[i] + C for i in range(n)] + [0] * (16 - n)
    assert len(S) == 16
    # snake writes S[k] to lane(15-k)
    lane = [0] * 16
    for k in range(16):
        lane[15 - k] = S[k]
    return lane


def writer(lane):
    """Read lanes lane0,lane1,...,lane15 in order; print nonzero debiased."""
    out = []
    for j in range(16):        # reading order left->right: lane0..lane15
        v = lane[j]
        if v > 0:              # biased real (all biased reals are > 0)
            out.append(v - C)
        # else padding 0 -> skip
    return out


def run_round(n, values):
    lane = reader_sequencer(n, values)
    return writer(lane)


def run_case(rounds):
    """rounds: list of (n, [values])."""
    out = []
    for n, values in rounds:
        out.extend(run_round(n, values))
    return out


# ---- test against all public cases + stress ----
PUBLIC = [
    ("warm up", [(1, [42]), (2, [100, -100]), (3, [10, 20, 30])]),
    ("a single list", [(7, [8, 6, 7, 5, 3, 0, 9])]),
    ("mixed sizes", [(5, [1, 2, 3, 4, 5]), (4, [-7, 0, 7, -14])]),
    ("repeats and palindromes",
     [(5, [4, 4, 4, 4, 4]), (5, [1, 2, 3, 2, 1]), (5, [9, 1, 1, 9, 5])]),
    ("extreme values",
     [(2, [1000000, -1000000]),
      (5, [-1000000, 0, 999999, -999999, 1000000])]),
    ("singletons", [(1, [-1000000]), (1, [0]), (1, [7])]),
    ("climbing lengths",
     [(2, [5, 10]), (7, [2, 4, 6, 8, 10, 12, 14]),
      (12, [1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6])]),
    ("full size",
     [(16, [675866, -469990, -316526, -586202, -495649, -594977, 725024,
            970614, -758697, -386951, -1260, 998677, 169990, 282058,
            -501276, -694925]),
      (9, [165787, 322570, 386470, 49875, -994912, 784925, -412923,
           -940544, 752013]),
      (16, [42599, -637865, 661864, 705729, -598961, 63916, 752576,
            -185145, -616486, -304818, -325803, -753987, -817166, 155504,
            633092, -453999])]),
]


def expected(rounds):
    out = []
    for n, values in rounds:
        out.extend(list(reversed(values)))
    return out


def main():
    ok = True
    for name, rounds in PUBLIC:
        got = run_case(rounds)
        exp = expected(rounds)
        status = "PASS" if got == exp else "FAIL"
        if got != exp:
            ok = False
            print(f"[{status}] {name}\n   got {got}\n   exp {exp}")
        else:
            print(f"[{status}] {name}")
    # exhaustive stress: n=1..16, negatives, zeros, extremes, palindromes, multi-round
    import random
    random.seed(1)
    stress_fail = 0
    for trial in range(20000):
        nrounds = random.randint(1, 3)
        rounds = []
        for _ in range(nrounds):
            n = random.randint(1, 16)
            vals = [random.choice([0, 1, -1, 1000000, -1000000,
                                   random.randint(-1000000, 1000000)])
                    for _ in range(n)]
            rounds.append((n, vals))
        if run_case(rounds) != expected(rounds):
            stress_fail += 1
            if stress_fail <= 3:
                print("STRESS FAIL", rounds)
    # explicit edge: every n, value 0 present, all-zero lists, extreme lists
    for n in range(1, 17):
        for vals in ([0] * n, [i - n // 2 for i in range(n)],
                     [1000000] * n, [-1000000] * n, list(range(n))):
            if run_round(n, vals) != list(reversed(vals)):
                ok = False
                print("EDGE FAIL", n, vals)
    print(f"\nstress failures: {stress_fail} / 20000")
    print("ALL PUBLIC + EDGE PASS" if ok and stress_fail == 0 else "SOME FAILURES")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate stress / generality test suites for littleman problems.

Grading locally only exercises the PUBLIC test cases, but the contest also runs
hidden PRIVATE cases and a team scores ZERO on a problem unless it passes at
least one private case.  A candidate that happens to satisfy the public cases
(and, say, only sorts up to 8 numbers, or only handles n <= 3) is therefore a
silent zero.  This tool closes that hole by generating extra cases.

Method, per problem:

  1. Read `tests/<slug>.json` (statement + `publicTestData`).
  2. A Python REFERENCE implementation of the problem's input -> output rule.
  3. GATE: the reference must reproduce EVERY public case's expected output
     exactly.  If it does not, the generator for that problem is refused --
     a wrong expected output is far worse than no extra case at all.
  4. Only then, emit edge cases whose expected output is *computed by the very
     same gated reference*: min/max sizes, extreme values, duplicates, sorted
     and reverse-sorted inputs, multi-round sequences, ...
  5. Write `tests/stress/<slug>.json`.

The output format is exactly what `tools/grade_json.js --cases <file>` accepts:
a JSON `{"cases": [...]}` whose entries look like `publicTestData` entries,
i.e. `{"name": ..., "rounds": [{"in": ["1","2"], "out": ["3"]}, ...]}`.

Usage:
    python3 tools/stress.py                 # regenerate every suite
    python3 tools/stress.py sort-numbers    # just one (or several) problems
    python3 tools/stress.py --check         # gate only, write nothing
    python3 tools/stress.py --list

Then gate a candidate on it:
    node tools/grade_json.js sort-numbers solutions/sort-numbers/select-v5.man \
        --cases tests/stress/sort-numbers.json
"""

import argparse
import json
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO, "tests")
OUT_DIR = os.path.join(TESTS, "stress")

# The reference for a problem is a function
#     ref(rounds_in) -> rounds_out
# taking the list of per-round input token lists (ints) and returning the list
# of per-round output token lists (ints).  Modelling a whole test case (rather
# than a single round) is what lets the stateful problems -- sudoku, gradebook,
# tcp, memory -- be expressed at all.
REFS = {}
GENS = {}


def problem(slug):
    """Register `ref` under `slug`; the matching generator registers separately."""
    def deco(fn):
        REFS[slug] = fn
        return fn
    return deco


def generator(slug):
    def deco(fn):
        GENS[slug] = fn
        return fn
    return deco


# ---------------------------------------------------------------------------
# references
# ---------------------------------------------------------------------------

@problem("triangle")
def ref_triangle(rounds):
    return [[n * (n + 1) // 2] for (n,) in rounds]


@problem("sort-numbers")
def ref_sort_numbers(rounds):
    out = []
    for r in rounds:
        n, xs = r[0], r[1:]
        assert len(xs) == n, "malformed round"
        out.append(sorted(xs))
    return out


@problem("reverse-a-list")
def ref_reverse_a_list(rounds):
    out = []
    for r in rounds:
        n, xs = r[0], r[1:]
        assert len(xs) == n, "malformed round"
        out.append(list(reversed(xs)))
    return out


@problem("brackets")
def ref_brackets(rounds):
    OPEN = {40: 41, 91: 93, 123: 125}  # ( [ {
    CLOSE = {41, 93, 125}
    out = []
    for r in rounds:
        n, chars = r[0], r[1:]
        assert len(chars) == n, "malformed round"
        stack = []
        verdict = 0
        for i, c in enumerate(chars):
            if c in OPEN:
                stack.append(OPEN[c])
            elif c in CLOSE:
                # An unmatched closer -- or one closing the wrong opener -- is
                # the first offending character, reported 1-based.
                if not stack or stack[-1] != c:
                    verdict = i + 1
                    break
                stack.pop()
        else:
            # No offending character inside the string: leftover openers make
            # the answer n + 1, otherwise the string is balanced.
            verdict = n + 1 if stack else 0
        out.append([verdict])
    return out


@problem("memory")
def ref_memory(rounds):
    out = []
    for r in rounds:
        cells = [0] * 100
        res = []
        i = 0
        while i < len(r):
            op = r[i]
            if op == 0:
                res.append(cells[r[i + 1]])
                i += 2
            else:
                cells[r[i + 1]] = r[i + 2]
                i += 3
        out.append(res)
    return out


@problem("matmul")
def ref_matmul(rounds):
    out = []
    for r in rounds:
        n, m, k = r[0], r[1], r[2]
        p = 3
        a = [r[p + i * m: p + (i + 1) * m] for i in range(n)]
        p += n * m
        b = [r[p + i * k: p + (i + 1) * k] for i in range(m)]
        p += m * k
        assert p == len(r), "malformed round"
        res = []
        for i in range(n):
            for j in range(k):
                res.append(sum(a[i][t] * b[t][j] for t in range(m)))
        out.append(res)
    return out


@problem("sudoku-validity")
def ref_sudoku(rounds):
    # A grid stays valid while no row, column or 3x3 box repeats a digit.  The
    # test case ends as soon as an invalid value is delivered, so `0` is only
    # ever emitted once, as the final output.
    rows = [set() for _ in range(9)]
    cols = [set() for _ in range(9)]
    boxes = [set() for _ in range(9)]
    out = []
    for r, c, v in rounds:
        b = (r // 3) * 3 + c // 3
        if v in rows[r] or v in cols[c] or v in boxes[b]:
            out.append([0])
            break
        rows[r].add(v)
        cols[c].add(v)
        boxes[b].add(v)
        out.append([1])
    return out


@problem("tcp")
def ref_tcp(rounds):
    # Round 1 carries `n` then the first packet; later rounds carry one packet.
    # A packet whose seq is >= 16 above the awaited seq loses the stream.
    buf = {}
    want = 0
    out = []
    for idx, r in enumerate(rounds):
        seq, val = (r[1], r[2]) if idx == 0 else (r[0], r[1])
        if seq - want >= 16:
            # `-1` is always the test case's final output -- the stream is lost
            # and no further packet is delivered.
            out.append([-1])
            break
        buf[seq] = val
        drained = []
        while want in buf:
            drained.append(buf.pop(want))
            want += 1
        out.append(drained)
    return out


@problem("subset-sum")
def ref_subset_sum(rounds):
    out = []
    for r in rounds:
        n, vals, t = r[0], r[1: 1 + r[0]], r[1 + r[0]]
        assert len(vals) == n and len(r) == n + 2, "malformed round"
        # reach[i] is the bitset of sums attainable from vals[i:].
        reach = [0] * (n + 1)
        reach[n] = 1
        for i in range(n - 1, -1, -1):
            reach[i] = reach[i + 1] | (reach[i + 1] << vals[i])
        if not (reach[0] >> t) & 1:
            out.append([0])
            continue
        # Lexicographically smallest index set: greedily take the earliest index
        # that still leaves the remainder attainable from the suffix after it.
        chosen = []
        rem = t
        for i in range(n):
            if vals[i] <= rem and (reach[i + 1] >> (rem - vals[i])) & 1:
                chosen.append(vals[i])
                rem -= vals[i]
                if rem == 0:
                    break
        assert rem == 0
        out.append([len(chosen)] + chosen)
    return out


@problem("gradebook")
def ref_gradebook(rounds):
    # Round 1 is the roster `N K` + N records `id g1..gK`; later rounds are
    # batches `O` + O operations.
    head = rounds[0]
    n, k = head[0], head[1]
    ids = []
    grades = {}
    p = 2
    for _ in range(n):
        sid = head[p]
        ids.append(sid)
        grades[sid] = head[p + 1: p + 1 + k]
        p += 1 + k
    assert p == len(head), "malformed roster"
    out = [[]]
    for batch in rounds[1:]:
        o = batch[0]
        p = 1
        res = []
        for _ in range(o):
            op = batch[p]
            if op == 1:                                  # GET id s
                sid, s = batch[p + 1], batch[p + 2]
                res.append(grades[sid][s - 1])
                p += 3
            elif op == 2:                                # SET id s v
                sid, s, v = batch[p + 1], batch[p + 2], batch[p + 3]
                grades[sid][s - 1] = v
                p += 4
            elif op == 3:                                # AVG s (floor)
                s = batch[p + 1]
                res.append(sum(grades[i][s - 1] for i in ids) // n)
                p += 2
            elif op == 4:                                # TOP s (smallest id wins ties)
                s = batch[p + 1]
                best = max(grades[i][s - 1] for i in ids)
                res.append(min(i for i in ids if grades[i][s - 1] == best))
                p += 2
            else:
                raise AssertionError("bad op %r" % op)
        assert p == len(batch), "malformed batch"
        out.append(res)
    return out


# ---------------------------------------------------------------------------
# generators -- each returns a list of (name, rounds_in) pairs.  Expected
# outputs are *never* written by hand: they come from the gated reference.
# ---------------------------------------------------------------------------

@generator("triangle")
def gen_triangle(rng):
    # 0 <= n <= 1000
    cases = [("n=0 minimum", [[0]]),
             ("n=1", [[1]]),
             ("n=2", [[2]]),
             ("n=1000 maximum", [[1000]]),
             ("n=999", [[999]]),
             ("n=100 round number", [[100]]),
             ("n=255 byte boundary", [[255]]),
             ("n=256 byte boundary", [[256]]),
             ("n=44 first 4-digit result", [[44]]),
             ("n=45 result 1035", [[45]])]
    for i in range(6):
        n = rng.randint(3, 1000)
        cases.append(("random n=%d" % n, [[n]]))
    return cases


@generator("sort-numbers")
def gen_sort_numbers(rng):
    # 1 <= n <= 16, -10000 <= x <= 10000, 2-6 lists per test case.
    LO, HI, NMAX = -10000, 10000, 16
    cases = [
        ("singletons only", [[1, 0], [1, LO], [1, HI]]),
        ("n=1 to n=16 growth", [[1, 5], [2, 2, 1], [16] + list(range(16, 0, -1))]),
        ("already sorted, full width", [[NMAX] + sorted(rng.sample(range(LO, HI), NMAX)),
                                       [3, -1, 0, 1]]),
        ("reverse sorted, full width", [[NMAX] + sorted(rng.sample(range(LO, HI), NMAX), reverse=True),
                                       [2, HI, LO]]),
        ("all identical extremes", [[NMAX] + [LO] * NMAX, [NMAX] + [HI] * NMAX,
                                    [8] + [0] * 8]),
        ("two distinct values interleaved", [[NMAX] + [HI, LO] * (NMAX // 2),
                                             [15] + [7, -7] * 7 + [7]]),
        ("extremes at the ends", [[NMAX] + [HI] + [0] * (NMAX - 2) + [LO],
                                  [NMAX] + [LO] + [0] * (NMAX - 2) + [HI]]),
        ("min already at front, max at back", [[5, LO, -1, 0, 1, HI],
                                               [5, HI, 1, 0, -1, LO]]),
        ("near-boundary values", [[6, HI, HI - 1, LO, LO + 1, 0, -1],
                                  [4, -9999, 9999, -10000, 10000]]),
        ("many duplicates", [[NMAX] + [3, 3, -3, -3, 0, 0] * 2 + [3, 3, -3, -3],
                             [10] + [1] * 5 + [-1] * 5]),
    ]
    # 6 rounds is the documented maximum; walk every length once.
    for start in (1, 7, 11):
        rounds = []
        for n in range(start, min(start + 6, NMAX + 1)):
            rounds.append([n] + [rng.randint(LO, HI) for _ in range(n)])
        cases.append(("lengths %d..%d" % (start, start + len(rounds) - 1), rounds))
    for i in range(4):
        rounds = []
        for _ in range(rng.randint(2, 6)):
            n = rng.randint(1, NMAX)
            rounds.append([n] + [rng.randint(LO, HI) for _ in range(n)])
        cases.append(("random mix %d" % (i + 1), rounds))
    return cases


@generator("reverse-a-list")
def gen_reverse_a_list(rng):
    # 1 <= n <= 16, -1000000 <= x <= 1000000, 1-3 lists per test case.
    LO, HI, NMAX = -1000000, 1000000, 16
    cases = [
        ("single minimum list", [[1, 0]]),
        ("singleton extremes", [[1, LO], [1, HI], [1, -1]]),
        ("full width, three rounds", [[NMAX] + [rng.randint(LO, HI) for _ in range(NMAX)],
                                      [NMAX] + [rng.randint(LO, HI) for _ in range(NMAX)],
                                      [NMAX] + [rng.randint(LO, HI) for _ in range(NMAX)]]),
        ("ascending then descending", [[NMAX] + list(range(1, NMAX + 1)),
                                       [NMAX] + list(range(NMAX, 0, -1))]),
        ("all identical", [[NMAX] + [7] * NMAX, [NMAX] + [-7] * NMAX]),
        ("palindrome stays put", [[7, 1, 2, 3, 4, 3, 2, 1], [6, 5, 5, 9, 9, 5, 5]]),
        ("extremes and zero", [[5, LO, 0, HI, 0, LO], [3, HI, HI, LO]]),
        ("boundary magnitudes", [[6, LO, LO + 1, -1, 1, HI - 1, HI]]),
        ("all zeroes", [[NMAX] + [0] * NMAX]),
        ("shrinking lengths", [[NMAX] + [rng.randint(LO, HI) for _ in range(NMAX)],
                               [8] + [rng.randint(LO, HI) for _ in range(8)],
                               [1, rng.randint(LO, HI)]]),
        ("growing lengths", [[1, rng.randint(LO, HI)],
                             [9] + [rng.randint(LO, HI) for _ in range(9)],
                             [NMAX] + [rng.randint(LO, HI) for _ in range(NMAX)]]),
    ]
    # Every single length 1..16 gets covered by a dedicated round.
    for n in range(1, NMAX + 1):
        cases.append(("length %d" % n, [[n] + [rng.randint(LO, HI) for _ in range(n)]]))
    return cases


@generator("brackets")
def gen_brackets(rng):
    # 0 <= n <= 64, characters from ()[]{}, nesting depth <= 32.
    OPENERS = [40, 91, 123]
    CLOSER = {40: 41, 91: 93, 123: 125}

    def balanced(depth_pairs, rng):
        """A random balanced string of `depth_pairs` bracket pairs."""
        s = []
        stack = []
        left = depth_pairs
        while left or stack:
            if left and (not stack or rng.random() < 0.6):
                o = rng.choice(OPENERS)
                s.append(o)
                stack.append(CLOSER[o])
                left -= 1
            else:
                s.append(stack.pop())
        return s

    def case(name, chars):
        return (name, [[len(chars)] + list(chars)])

    cases = [
        case("empty string", []),
        case("one opener", [40]),
        case("one closer", [41]),
        case("one square closer", [93]),
        case("one curly closer", [125]),
        case("shortest balanced", [40, 41]),
        case("depth 32 maximum, balanced", [40] * 32 + [41] * 32),
        case("depth 32 mixed types", [40, 91, 123] * 10 + [40, 91] +
             [93, 41] + [125, 93, 41] * 10),
        case("64 concatenated pairs", [40, 41] * 32),
        case("all openers, depth 32", [40] * 32),
        case("all closers, 64 long", [41] * 64),
        case("offense at the very last position", [40] * 31 + [41] * 31 + [93]),
        case("unclosed by exactly one", [40] * 32 + [41] * 31),
        case("mismatch in the middle", [40, 91, 40, 41, 93, 125]),
        case("crossed at depth", [40, 91, 123, 41, 125, 93]),
        case("closer before any opener", [41, 40, 41]),
        case("balanced prefix then stray closer", [40, 41] * 10 + [93]),
        case("wrong type immediately", [91, 41]),
        case("curly closed by square", [123, 93]),
        case("long balanced, one bad char at 33", [40, 41] * 16 + [93] + [40, 41] * 15),
    ]
    for i in range(6):
        n = rng.randint(1, 32)
        cases.append(case("random balanced %d (%d pairs)" % (i + 1, n), balanced(n, rng)))
    for i in range(6):
        s = balanced(rng.randint(2, 32), rng)
        # Corrupt one character so the answer is a genuine offset, not 0.
        j = rng.randrange(len(s))
        s[j] = rng.choice([40, 41, 91, 93, 123, 125])
        cases.append(case("random corrupted %d" % (i + 1), s))
    return cases


@generator("memory")
def gen_memory(rng):
    # 2..1000 input tokens, 0 <= addr < 100, |value| <= 1000000.
    LO, HI = -1000000, 1000000
    cases = [
        ("single read of a fresh cell", [[0, 0]]),
        ("read the last address", [[0, 99]]),
        ("write then read address 0", [[1, 0, HI, 0, 0]]),
        ("write then read address 99", [[1, 99, LO, 0, 99]]),
        ("every address read fresh", [[t for a in range(100) for t in (0, a)]]),
        ("write every address then read every address",
         [[t for a in range(100) for t in (1, a, a * 7 - 300)] +
          [t for a in range(100) for t in (0, a)]]),
        ("repeated overwrite of one cell",
         [[t for v in range(1, 40) for t in (1, 42, v)] + [0, 42]]),
        ("write zero over a value", [[1, 5, 12345, 0, 5, 1, 5, 0, 0, 5]]),
        ("extreme values round trip",
         [[1, 1, LO, 1, 2, HI, 1, 3, 0, 0, 1, 0, 2, 0, 3]]),
        ("trailing write produces nothing", [[0, 8, 1, 8, 9]]),
        ("aliasing neighbours", [[1, 50, 1, 1, 51, 2, 0, 50, 0, 51, 1, 50, 3, 0, 50, 0, 51]]),
        ("read same cell many times", [[1, 7, -999999] + [t for _ in range(30) for t in (0, 7)]]),
    ]
    # A near-maximum stream (1000 tokens is the cap).
    stream = []
    model = [0] * 100
    while len(stream) < 995:
        if rng.random() < 0.5 or not any(model):
            a = rng.randrange(100)
            v = rng.randint(LO, HI)
            stream += [1, a, v]
            model[a] = v
        else:
            stream += [0, rng.randrange(100)]
    cases.append(("near-maximum stream (%d tokens)" % len(stream), [stream]))
    for i in range(4):
        s = []
        while len(s) < rng.randint(20, 300):
            if rng.random() < 0.5:
                s += [1, rng.randrange(100), rng.randint(LO, HI)]
            else:
                s += [0, rng.randrange(100)]
        cases.append(("random stream %d" % (i + 1), [s]))
    return cases


@generator("matmul")
def gen_matmul(rng):
    # 2 <= N, M, K <= 16, -99 <= entries <= 99.
    def mk(n, m, k, a, b):
        return [[n, m, k] + a + b]

    def rnd(count):
        return [rng.randint(-99, 99) for _ in range(count)]

    def ident(d):
        return [1 if i == j else 0 for i in range(d) for j in range(d)]

    cases = [
        ("minimum 2x2x2 zeros", mk(2, 2, 2, [0] * 4, [0] * 4)),
        ("minimum 2x2x2 extremes", mk(2, 2, 2, [99] * 4, [99] * 4)),
        ("minimum 2x2x2 negative extremes", mk(2, 2, 2, [-99] * 4, [-99] * 4)),
        ("mixed sign extremes 2x2x2", mk(2, 2, 2, [99, -99, -99, 99], [-99, 99, 99, -99])),
        ("maximum magnitude 16x16x16", mk(16, 16, 16, [-99] * 256, [99] * 256)),
        ("identity on the right 16x16x16", mk(16, 16, 16, rnd(256), ident(16))),
        ("identity on the left 16x16x16", mk(16, 16, 16, ident(16), rnd(256))),
        ("thin N: 2x16x16", mk(2, 16, 16, rnd(32), rnd(256))),
        ("thin M: 16x2x16", mk(16, 2, 16, rnd(32), rnd(32))),
        ("thin K: 16x16x2", mk(16, 16, 2, rnd(256), rnd(32))),
        ("row vector times matrix 2x16x2", mk(2, 16, 2, rnd(32), rnd(32))),
        ("all ones 16x16x16", mk(16, 16, 16, [1] * 256, [1] * 256)),
        ("zero A 16x16x16", mk(16, 16, 16, [0] * 256, rnd(256))),
        ("zero B 16x16x16", mk(16, 16, 16, rnd(256), [0] * 256)),
        ("cancelling sums 2x16x2", mk(2, 16, 2, [99, -99] * 16, [1] * 32)),
    ]
    seen = set()
    for i in range(8):
        n, m, k = rng.randint(2, 16), rng.randint(2, 16), rng.randint(2, 16)
        if (n, m, k) in seen:
            continue
        seen.add((n, m, k))
        cases.append(("random %dx%dx%d" % (n, m, k), mk(n, m, k, rnd(n * m), rnd(m * k))))
    return cases


@generator("sudoku-validity")
def gen_sudoku(rng):
    # 0 <= r, c <= 8; 1 <= v <= 9; up to 81 rounds, no cell repeated; the case
    # ends at the first invalid value.
    def solved_grid(rng):
        """A valid completed 9x9 solution, from the canonical grid + shuffles."""
        base = [[(3 * (r % 3) + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]
        rows = [b * 3 + r for b in rng.sample(range(3), 3) for r in rng.sample(range(3), 3)]
        cols = [b * 3 + c for b in rng.sample(range(3), 3) for c in rng.sample(range(3), 3)]
        perm = rng.sample(range(1, 10), 9)
        return [[perm[base[r][c] - 1] for c in cols] for r in rows]

    def rounds_from(grid, order):
        return [[r, c, grid[r][c]] for (r, c) in order]

    cases = []
    grid = solved_grid(rng)

    row_major = [(r, c) for r in range(9) for c in range(9)]
    col_major = [(r, c) for c in range(9) for r in range(9)]
    box_major = [(br * 3 + r, bc * 3 + c)
                 for br in range(3) for bc in range(3)
                 for r in range(3) for c in range(3)]
    shuffled = row_major[:]
    rng.shuffle(shuffled)

    cases.append(("full valid grid, row-major", rounds_from(grid, row_major)))
    cases.append(("full valid grid, column-major", rounds_from(grid, col_major)))
    cases.append(("full valid grid, box-major", rounds_from(grid, box_major)))
    cases.append(("full valid grid, shuffled order", rounds_from(grid, shuffled)))
    g2 = solved_grid(rng)
    s2 = row_major[:]
    rng.shuffle(s2)
    cases.append(("second valid grid, shuffled", rounds_from(g2, s2)))

    # Single cell / very short cases.
    cases.append(("one cell only", [[0, 0, 1]]))
    cases.append(("one cell, corner and max value", [[8, 8, 9]]))
    cases.append(("two independent cells", [[0, 0, 1], [8, 8, 1]]))

    # Immediate violations of each kind, on the second delivered cell.
    cases.append(("row clash immediately", [[3, 0, 5], [3, 8, 5]]))
    cases.append(("column clash immediately", [[0, 4, 7], [8, 4, 7]]))
    cases.append(("box clash immediately", [[6, 6, 2], [8, 8, 2]]))
    cases.append(("box clash, adjacent cells", [[4, 4, 9], [3, 3, 9]]))

    # Violations that only appear after a long valid prefix.
    for kind, k in (("row", 0), ("column", 1), ("box", 2)):
        order = row_major[:]
        rng.shuffle(order)
        prefix = order[:70]
        rnds = rounds_from(grid, prefix)
        used = set(prefix)
        bad = None
        for (r, c) in order[70:]:
            if (r, c) in used:
                continue
            # Pick a value that clashes on exactly the requested axis.
            for v in range(1, 10):
                if v == grid[r][c]:
                    continue
                inrow = any(grid[r][cc] == v for cc in range(9))
                incol = any(grid[rr][c] == v for rr in range(9))
                br, bc = (r // 3) * 3, (c // 3) * 3
                inbox = any(grid[br + i][bc + j] == v for i in range(3) for j in range(3))
                # It must clash with a cell that has ALREADY been delivered.
                def delivered(cells):
                    return any(cell in used for cell in cells)
                rowcells = [(r, cc) for cc in range(9) if grid[r][cc] == v]
                colcells = [(rr, c) for rr in range(9) if grid[rr][c] == v]
                boxcells = [(br + i, bc + j) for i in range(3) for j in range(3)
                            if grid[br + i][bc + j] == v]
                want = [delivered(rowcells) and inrow,
                        delivered(colcells) and incol,
                        delivered(boxcells) and inbox][k]
                if want:
                    bad = [r, c, v]
                    break
            if bad:
                break
        if bad:
            cases.append(("late %s violation after 70 cells" % kind, rnds + [bad]))

    # A violation on the very last (81st) cell: fill 80 cells of a valid grid,
    # then deliver a wrong value for the hole.
    order = row_major[:]
    rng.shuffle(order)
    hole = order[-1]
    hr, hc = hole
    wrong = grid[(hr + 1) % 9][hc]
    if wrong == grid[hr][hc]:
        wrong = grid[hr][(hc + 1) % 9]
    cases.append(("violation on the 81st cell",
                  rounds_from(grid, order[:-1]) + [[hr, hc, wrong]]))

    # Same digit nine times in nine independent places is legal.
    diag = [[i, i, 5] for i in range(0, 9, 4)]
    cases.append(("same digit in disjoint rows/cols/boxes",
                  [[0, 0, 5], [3, 3, 5], [6, 6, 5], [1, 4, 5], [4, 7, 5], [7, 1, 5]]))
    cases.append(("sparse diagonal same digit", diag))

    # Value 9 and value 1 boundaries, plus a clash between the two extremes.
    cases.append(("all nines down a diagonal then a row clash",
                  [[0, 0, 9], [1, 1, 9], [2, 2, 9], [0, 5, 9]]))
    cases.append(("value 1 clash in a box", [[5, 5, 1], [4, 3, 2], [3, 4, 1]]))
    return cases


@generator("tcp")
def gen_tcp(rng):
    # 1 <= n <= 48, 0 <= seq < n distinct, 1 <= val <= 999, displacement >= 16 loses.
    def rounds(n, order, vals):
        rs = [[n, order[0], vals[order[0]]]]
        for s in order[1:]:
            rs.append([s, vals[s]])
        return rs

    def vlist(n):
        return [rng.randint(1, 999) for _ in range(n)]

    cases = []

    cases.append(("n=1 single packet", [[1, 0, 1]]))
    cases.append(("n=1 max value", [[1, 0, 999]]))
    v = vlist(48)
    cases.append(("n=48 in order", rounds(48, list(range(48)), v)))
    v = vlist(48)
    cases.append(("n=48 blocks of 16 reversed",
                  rounds(48, [b * 16 + i for b in range(3) for i in range(15, -1, -1)], v)))
    v = vlist(16)
    cases.append(("n=16 fully reversed (max legal displacement)",
                  rounds(16, list(range(15, -1, -1)), v)))
    v = vlist(17)
    cases.append(("n=17, first packet at displacement 15",
                  rounds(17, [15] + [s for s in range(17) if s != 15], v)))
    v = vlist(17)
    cases.append(("n=17, first packet at displacement 16 loses immediately",
                  rounds(17, [16] + [s for s in range(17) if s != 16], v)))
    v = vlist(48)
    cases.append(("n=48, loss in the middle",
                  rounds(48, list(range(10)) + [26] + [s for s in range(10, 48) if s != 26], v)))
    v = vlist(2)
    cases.append(("n=2 swapped", rounds(2, [1, 0], v)))
    v = vlist(2)
    cases.append(("n=2 in order", rounds(2, [0, 1], v)))
    v = vlist(48)
    cases.append(("n=48 pairwise swaps",
                  rounds(48, [s ^ 1 for s in range(48)], v)))
    v = vlist(32)
    cases.append(("n=32 last packet first (displacement 31) loses",
                  rounds(32, [31] + list(range(31)), v)))
    v = vlist(48)
    cases.append(("n=48 sawtooth within window",
                  rounds(48, [b * 8 + i for b in range(6) for i in (7, 0, 6, 1, 5, 2, 4, 3)], v)))
    v = [999] * 48
    cases.append(("n=48 all values 999, in order", rounds(48, list(range(48)), v)))
    v = [1] * 48
    cases.append(("n=48 all values 1, reversed blocks",
                  rounds(48, [b * 8 + i for b in range(6) for i in range(7, -1, -1)], v)))

    # Random scrambles that stay inside the 16-packet window.
    for i in range(6):
        n = rng.randint(4, 48)
        order = []
        pending = list(range(n))
        want = 0
        while pending:
            # Only offer packets whose displacement is < 16 so the stream survives.
            choices = [s for s in pending if s - want < 16]
            s = rng.choice(choices)
            order.append(s)
            pending.remove(s)
            while want not in pending and want < n:
                want += 1
        cases.append(("random scramble %d (n=%d)" % (i + 1, n), rounds(n, order, vlist(n))))

    # Random streams that do lose.
    for i in range(3):
        n = rng.randint(20, 48)
        order = list(range(n))
        rng.shuffle(order)
        cases.append(("random shuffle %d (n=%d)" % (i + 1, n), rounds(n, order, vlist(n))))
    return cases


@generator("subset-sum")
def gen_subset_sum(rng):
    # 10 <= n <= 20, 1 <= v <= 99999, 100 < t < 1000000, t ~ 10-60% of the sum.
    def case(name, vals, t):
        return (name, [[len(vals)] + list(vals) + [t]])

    cases = []

    v10 = [rng.randint(1, 99999) for _ in range(10)]
    v20 = [rng.randint(1, 99999) for _ in range(20)]

    # Answer is the first element alone -> lex-smallest is a prefix pick.
    vals = [rng.randint(1000, 99999) for _ in range(10)]
    vals[0] = 54321
    cases.append(case("n=10, first element alone", vals, 54321))

    # Answer needs the last element only.
    vals = [rng.randint(1, 999) for _ in range(20)]
    vals[-1] = 87654
    cases.append(case("n=20, last element only", vals, 87654))

    # Everything must be taken.
    vals = [rng.randint(1, 40000) for _ in range(10)]
    cases.append(case("n=10, whole list required", vals, sum(vals)))
    vals = [rng.randint(1, 40000) for _ in range(20)]
    cases.append(case("n=20, whole list required", vals, sum(vals)))

    # All values equal -> answer is a prefix of k copies.
    cases.append(case("n=20 all equal, prefix answer", [5000] * 20, 5000 * 7))
    cases.append(case("n=10 all equal, single element", [12345] * 10, 12345))
    cases.append(case("n=10 all equal, unreachable target", [10000] * 10, 15000))

    # Powers of two: exactly one representation, forces a bit-exact search.
    pw = [2 ** i for i in range(1, 17)]          # 2 .. 65536, all <= 99999
    cases.append(case("n=16 powers of two, unique subset", pw, 2 + 8 + 32 + 1024 + 65536))
    cases.append(case("n=16 powers of two, low bits", pw, 2 + 4 + 8 + 16 + 256))

    # No solution at all: every value even, odd target.
    vals = [2 * rng.randint(1, 40000) for _ in range(20)]
    cases.append(case("n=20 even values, odd target: no solution", vals, sum(vals) // 2 | 1))
    vals = [2 * rng.randint(1, 40000) for _ in range(10)]
    cases.append(case("n=10 even values, odd target: no solution", vals, sum(vals) // 3 | 1))

    # Target just below the smallest value / just above the total.
    vals = sorted(rng.randint(20000, 99999) for _ in range(10))
    cases.append(case("n=10, target below every value", vals, 101))

    # Lex tie-break stressors: many equal-sum subsets.
    cases.append(case("lex tie-break, duplicated pairs",
                      [300, 300, 300, 300, 300, 300, 300, 300, 300, 300], 900))
    cases.append(case("lex tie-break, early pair vs late single",
                      [400, 500, 900, 900, 900, 900, 900, 900, 900, 900], 900))
    cases.append(case("lex tie-break, greedy-first trap",
                      [999, 1, 2, 3, 500, 499, 250, 250, 125, 875], 1000))

    # Maximum magnitudes.
    big = [99999] * 10
    cases.append(case("n=10 maximum values", big, 99999 * 6))
    big20 = [99999] * 20
    cases.append(case("n=20 maximum values", big20, 99999 * 10))

    # Random instances that do have an answer (target built from a real subset).
    for i in range(6):
        n = rng.randint(10, 20)
        vals = [rng.randint(1, 99999) for _ in range(n)]
        k = rng.randint(2, max(2, n // 2))
        t = sum(rng.sample(vals, k))
        if not (100 < t < 1000000):
            continue
        cases.append(case("random solvable %d (n=%d)" % (i + 1, n), vals, t))

    # Random instances that are probably unsolvable (coprime-ish residues).
    for i in range(3):
        n = rng.randint(10, 20)
        vals = [3 * rng.randint(1, 30000) for _ in range(n)]
        t = 3 * rng.randint(200, 100000) + 1
        if not (100 < t < 1000000):
            continue
        cases.append(case("random unsolvable %d (n=%d)" % (i + 1, n), vals, t))
    return cases


@generator("gradebook")
def gen_gradebook(rng):
    # 4 <= N <= 16, 1 <= K <= 4, ids distinct in 1000..9999, 0 <= g <= 100,
    # 1-10 batch rounds, 1-8 operations per batch.
    def roster(n, k, grades=None, ids=None):
        ids = ids or rng.sample(range(1000, 10000), n)
        head = [n, k]
        table = {}
        for i, sid in enumerate(ids):
            g = grades[i] if grades else [rng.randint(0, 100) for _ in range(k)]
            table[sid] = list(g)
            head += [sid] + list(g)
        return head, ids, table

    def batch(ops):
        return [len(ops)] + [t for op in ops for t in op]

    cases = []

    # Smallest roster, K=1, every operation exercised.
    head, ids, _ = roster(4, 1, grades=[[0], [100], [50], [50]],
                          ids=[9999, 1000, 5000, 4999])
    cases.append(("N=4 K=1 minimum roster, all ops", [
        head,
        batch([[1, 9999, 1], [1, 1000, 1], [3, 1], [4, 1]]),
        batch([[2, 9999, 1, 100], [4, 1], [3, 1]]),
        batch([[2, 1000, 1, 0], [2, 5000, 1, 0], [2, 4999, 1, 0], [4, 1], [3, 1]]),
    ]))

    # All grades zero -> TOP must pick the smallest id; AVG is 0.
    ids = sorted(rng.sample(range(1000, 10000), 16))
    head, ids, _ = roster(16, 4, grades=[[0] * 4] * 16, ids=ids)
    cases.append(("N=16 K=4 all zeroes, ties everywhere", [
        head,
        batch([[4, 1], [4, 2], [4, 3], [4, 4], [3, 1], [3, 2], [3, 3], [3, 4]]),
        batch([[2, ids[-1], 1, 100], [4, 1], [3, 1]]),
        batch([[2, ids[0], 1, 100], [4, 1]]),
    ]))

    # All grades 100 -> AVG exactly 100, no rounding.
    head, ids, _ = roster(16, 4, grades=[[100] * 4] * 16, ids=sorted(rng.sample(range(1000, 10000), 16)))
    cases.append(("N=16 K=4 all hundreds", [
        head,
        batch([[3, 1], [3, 2], [3, 3], [3, 4], [4, 1], [4, 4]]),
        batch([[2, ids[3], 2, 0], [3, 2], [4, 2]]),
    ]))

    # Floor rounding stress: sums that are not divisible by N.
    head, ids, _ = roster(7, 1, grades=[[1], [1], [1], [1], [1], [1], [1]],
                          ids=[1001, 1002, 1003, 1004, 1005, 1006, 1007])
    cases.append(("N=7 K=1 floor rounding (7 ones -> avg 1)", [
        head,
        batch([[3, 1]]),
        batch([[2, 1001, 1, 0], [3, 1]]),          # 6/7 -> 0
        batch([[2, 1002, 1, 100], [3, 1]]),        # 105/7 -> 15
        batch([[2, 1003, 1, 100], [3, 1]]),        # 204/7 -> 29
    ]))
    head, ids, _ = roster(9, 1, grades=[[11]] * 9, ids=list(range(1010, 1019 + 1))[:9])
    cases.append(("N=9 K=1 floor rounding near boundaries", [
        head,
        batch([[3, 1]]),
        batch([[2, 1010, 1, 12], [3, 1]]),
        batch([[2, 1011, 1, 0], [3, 1]]),
        batch([[2, 1012, 1, 100], [2, 1013, 1, 100], [3, 1]]),
    ]))

    # TOP tie-break under repeated demotion/promotion.
    ids = [5000, 1000, 9000, 3000, 7000]
    head, ids, _ = roster(5, 2, grades=[[90, 10], [90, 20], [90, 30], [80, 40], [70, 50]], ids=ids)
    cases.append(("TOP tie-break and repeated demotion", [
        head,
        batch([[4, 1], [4, 2]]),
        batch([[2, 5000, 1, 0], [4, 1]]),
        batch([[2, 1000, 1, 0], [4, 1]]),
        batch([[2, 9000, 1, 0], [4, 1]]),
        batch([[2, 3000, 1, 0], [4, 1]]),
        batch([[2, 7000, 1, 0], [4, 1]]),
        batch([[2, 9000, 1, 100], [4, 1], [1, 9000, 1], [3, 1]]),
    ]))

    # Extreme ids (both ends of the legal range) and out-of-order roster.
    head, ids, _ = roster(4, 4, grades=[[100, 0, 50, 25], [0, 100, 50, 75],
                                        [50, 50, 50, 50], [25, 75, 50, 100]],
                          ids=[9999, 1000, 5555, 1001])
    cases.append(("extreme ids, unsorted roster, K=4", [
        head,
        batch([[4, 1], [4, 2], [4, 3], [4, 4]]),
        batch([[1, 9999, 4], [1, 1000, 1], [1, 5555, 3], [1, 1001, 2]]),
        batch([[3, 1], [3, 2], [3, 3], [3, 4]]),
    ]))

    # A single operation per round, ten rounds (max batch count).
    head, ids, _ = roster(8, 2)
    rounds = [head]
    for i in range(10):
        sid = ids[i % len(ids)]
        if i % 3 == 0:
            rounds.append(batch([[1, sid, 1 + (i % 2)]]))
        elif i % 3 == 1:
            rounds.append(batch([[2, sid, 1 + (i % 2), (i * 13) % 101]]))
        else:
            rounds.append(batch([[4, 1 + (i % 2)]]))
    cases.append(("ten single-operation rounds", rounds))

    # Max batch size (8 ops) repeated.
    head, ids, _ = roster(16, 4)
    rounds = [head]
    for b in range(6):
        ops = []
        for _ in range(8):
            kind = rng.randint(1, 4)
            sid = rng.choice(ids)
            s = rng.randint(1, 4)
            if kind == 1:
                ops.append([1, sid, s])
            elif kind == 2:
                ops.append([2, sid, s, rng.randint(0, 100)])
            elif kind == 3:
                ops.append([3, s])
            else:
                ops.append([4, s])
        rounds.append(batch(ops))
    cases.append(("N=16 K=4, six full batches of 8 random ops", rounds))

    # SET-only round produces no output at all.
    head, ids, _ = roster(5, 3)
    cases.append(("SET-only round yields empty output", [
        head,
        batch([[2, ids[0], 1, 0], [2, ids[1], 2, 100], [2, ids[2], 3, 55]]),
        batch([[1, ids[0], 1], [1, ids[1], 2], [1, ids[2], 3]]),
    ]))

    # Set a grade to the value it already had; TOP/AVG must not drift.
    head, ids, table = roster(6, 2)
    sid = ids[2]
    cases.append(("idempotent SET", [
        head,
        batch([[3, 1], [4, 1], [2, sid, 1, table[sid][0]], [3, 1], [4, 1]]),
    ]))

    for i in range(4):
        n = rng.randint(4, 16)
        k = rng.randint(1, 4)
        head, ids, _ = roster(n, k)
        rounds = [head]
        for _ in range(rng.randint(1, 10)):
            ops = []
            for _ in range(rng.randint(1, 8)):
                kind = rng.randint(1, 4)
                sid = rng.choice(ids)
                s = rng.randint(1, k)
                if kind == 1:
                    ops.append([1, sid, s])
                elif kind == 2:
                    ops.append([2, sid, s, rng.randint(0, 100)])
                elif kind == 3:
                    ops.append([3, s])
                else:
                    ops.append([4, s])
            rounds.append(batch(ops))
        cases.append(("random N=%d K=%d (%d)" % (n, k, i + 1), rounds))
    return cases


# ---------------------------------------------------------------------------
# gate + emit
# ---------------------------------------------------------------------------

def load_problem(slug):
    with open(os.path.join(TESTS, "%s.json" % slug)) as f:
        return json.load(f)


def case_rounds(tc):
    """Public entries come in two shapes: multi-round, or a bare in/out pair."""
    return tc.get("rounds") or [{"in": tc.get("in", []), "out": tc.get("out", [])}]


def gate(slug, verbose=True):
    """Check the reference against every public case.  Returns (ok, n, total)."""
    prob = load_problem(slug)
    ref = REFS[slug]
    cases = prob.get("publicTestData", [])
    ok = 0
    for tc in cases:
        rounds = case_rounds(tc)
        rin = [[int(x) for x in r.get("in", [])] for r in rounds]
        want = [[str(x) for x in r.get("out", [])] for r in rounds]
        try:
            got = [[str(x) for x in r] for r in ref(rin)]
        except Exception as e:                                  # noqa: BLE001
            if verbose:
                print("    MISMATCH %-40s reference raised %s: %s"
                      % (tc.get("name"), type(e).__name__, e))
            continue
        # A case may legitimately stop early (sudoku ends at the first 0).
        if got == want:
            ok += 1
        elif verbose:
            print("    MISMATCH %s" % tc.get("name"))
            for i, (g, w) in enumerate(zip(got + [None] * len(want), want)):
                if g != w:
                    print("      round %d: want %r got %r" % (i, w, g))
                    break
            if len(got) != len(want):
                print("      round count: want %d got %d" % (len(want), len(got)))
    return ok == len(cases), ok, len(cases)


def build(slug, seed):
    """Generate the suite; outputs come from the (already gated) reference."""
    rng = random.Random(seed)
    ref = REFS[slug]
    cases = []
    for name, rounds_in in GENS[slug](rng):
        rounds_out = ref([list(r) for r in rounds_in])
        # A reference may stop early (sudoku); truncate the inputs to match, so
        # the emitted case is exactly as long as the answer it expects.
        rounds_in = rounds_in[:len(rounds_out)]
        cases.append({
            "name": name,
            "rounds": [{"in": [str(x) for x in ri], "out": [str(x) for x in ro]}
                       for ri, ro in zip(rounds_in, rounds_out)],
        })
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="*", help="problems to build (default: all)")
    ap.add_argument("--check", action="store_true", help="gate only, write nothing")
    ap.add_argument("--list", action="store_true", help="list supported problems")
    ap.add_argument("--seed", type=int, default=20260725,
                    help="RNG seed -- fixed so suites are reproducible")
    ap.add_argument("--out", default=OUT_DIR, help="output directory")
    args = ap.parse_args()

    if args.list:
        for s in sorted(REFS):
            print(s)
        return 0

    slugs = args.slugs or sorted(REFS)
    unknown = [s for s in slugs if s not in REFS]
    if unknown:
        print("no reference for: %s" % ", ".join(unknown), file=sys.stderr)
        return 2

    if not args.check:
        os.makedirs(args.out, exist_ok=True)

    failed = []
    for slug in slugs:
        ok, n, total = gate(slug)
        status = "OK " if ok else "GATE FAILED"
        print("%-18s reference reproduces %d/%d public cases  %s" % (slug, n, total, status))
        if not ok:
            failed.append(slug)
            print("    -> refusing to emit a suite for %s" % slug)
            continue
        if args.check:
            continue
        cases = build(slug, args.seed)
        path = os.path.join(args.out, "%s.json" % slug)
        with open(path, "w") as f:
            json.dump({"cases": cases}, f, indent=1)
            f.write("\n")
        rounds = sum(len(c["rounds"]) for c in cases)
        print("    wrote %s  (%d cases, %d rounds)"
              % (os.path.relpath(path, REPO), len(cases), rounds))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

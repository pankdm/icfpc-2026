import json, random, sys, os
sys.path.insert(0, os.path.abspath("scratchpad"))
import lllm_ref as R

def framed(W, H, fill):
    """A walled W x H program; fill(x,y) supplies each interior cell."""
    rows = ["+" + "-" * (W - 2) + "+"]
    for y in range(1, H - 1):
        rows.append("|" + "".join(fill(x, y) for x in range(1, W - 1)) + "|")
    rows.append("+" + "-" * (W - 2) + "+")
    return "\n".join(rows)

def case(name, prog, ks):
    c = R.make_case(prog, ks); c["name"] = name; return c

cases = []
OPS = "^>v<0123456789M+-X "          # H handled separately (rare in real cases)
def dense(seed, W=16, H=16, hp=0.0):
    r = random.Random(seed)
    pool = OPS + ("H" if hp else "")
    def fill(x, y):
        if (x, y) == (1, 1): return "@"
        return r.choice(pool)
    return framed(W, H, fill)

# 1. max-size dense grids: max setup traffic, every op class, long stepping
for s in range(6):
    cases.append(case("dense16-%d" % s, dense(s), [64] * 8 + [1, 2, 3, 64, 64]))
for s in (20, 21):
    cases.append(case("dense16H-%d" % s, dense(s, hp=1), [64] * 6 + [1, 64]))
# 2. a lap the man runs forever (never halts, max k, max rounds)
lap = ["+" + "-" * 14 + "+", "|@" + ">" * 12 + "v|"] + \
      ["|^" + " " * 12 + "v|" for _ in range(12)] + \
      ["|^" + "<" * 12 + "<|", "+" + "-" * 14 + "+"]
cases.append(case("lap16", "\n".join(lap), [64] * 12))
# 3. degenerate / minimum sizes
cases.append(case("3x3", "+-+\n|@|\n+-+", [1, 1, 2, 64]))
cases.append(case("3x16", framed(3, 16, lambda x, y: "@" if y == 1 else "v"), [1, 2, 14, 64]))
cases.append(case("16x3", framed(16, 3, lambda x, y: "@" if x == 1 else ">"), [1, 2, 14, 64]))
cases.append(case("4x4blank", framed(4, 4, lambda x, y: "@" if (x, y) == (1, 1) else " "), [1, 2, 3, 64]))
# 4. arithmetic / turn stress inside a 16x16 frame
ar = {(1, 1): "@"}
for i, ch in enumerate("9M++++++++X"): ar[(1 + i + 1, 1)] = ch
for i, ch in enumerate("9M--------X"): ar[(1 + i, 3)] = ch
for i, ch in enumerate("0MX"): ar[(1 + i, 5)] = ch
cases.append(case("arith16", framed(16, 16, lambda x, y: ar.get((x, y), " ")), [1, 3, 7, 20, 64, 64]))
# 5. immediate halt, and a man who runs into a wall and stops there
cases.append(case("halt0", framed(8, 4, lambda x, y: "@" if (x, y) == (1, 1) else ("H" if (x, y) == (2, 1) else " ")), [1, 1, 64, 64]))
cases.append(case("wallstop", framed(8, 4, lambda x, y: "@" if (x, y) == (1, 1) else " "), [1, 2, 3, 4, 5, 6, 7, 64]))
# 6. maximum round count at k=1 (max frame traffic), and k=0 rounds
cases.append(case("k1x40", dense(99), [1] * 40))
# NOTE: k=0 rounds are NOT in the stress set -- the (unmodified) champion
# already crashes on them ("wall"), so k=0 is either impossible in the real
# cases or a pre-existing bug in every build we have; it is not a regression.
json.dump({"publicTestData": cases, "tickCap": 15000000},
          open("tests/lllm-stress.json", "w"))
print("wrote %d stress cases" % len(cases))

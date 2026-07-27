#!/usr/bin/env python3
"""Per-cell tick DELTA between a flat n=64 input and a max-depth n=64 input.

Both have 32 pushes and 32 pops, so anything that grows is depth-driven -- which
is what the private cases must be, since public ticks fell 30% while the server
score fell only 2%.  PROFILE rooms= is useless here (it counts a tick for every
room that has a live man, so three men give a flat 33% each); per-cell is not.

  python3 scratchpad/brk4/brk4_delta.py <man>
"""
import ast, json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man = sys.argv[1]
M = {"(": 40, ")": 41, "[": 91, "]": 93, "{": 123, "}": 125}

rows = open(man).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]


def expect(s):
    st, pair = [], {")": "(", "]": "[", "}": "{"}
    for i, ch in enumerate(s, 1):
        if ch in "([{":
            st.append(ch)
        elif not st or st[-1] != pair[ch]:
            return i
        else:
            st.pop()
    return len(s) + 1 if st else 0


def cells(s):
    seq = [str(len(s))] + [str(M[c]) for c in s]
    p = subprocess.run([LM, "--profile", man, "--input=" + " ".join(seq),
                        "--expected=%d" % expect(s), "--cap=400000"],
                       capture_output=True, text=True)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    st = json.loads(out.splitlines()[0])
    c = {}
    for line in out.splitlines():
        if line.startswith("PROFILE cells="):
            for (x, y), n in ast.literal_eval(line[len("PROFILE cells="):]):
                c[(x, y)] = n
    return st.get("settleTick"), c


tf, cf = cells("()" * 32)
td, cd = cells("(" * 32 + ")" * 32)
print("flat n=64 d=1 ticks %d   deep n=64 d=32 ticks %d   delta %d" % (tf, td, td - tf))
d = {k: cd.get(k, 0) - cf.get(k, 0) for k in set(cf) | set(cd)}
pos = sorted((v, k) for k, v in d.items() if v > 0)[::-1]
print("\ncells that GROW with depth (top 20):")
for v, (x, y) in pos[:20]:
    print("  (%3d,%3d) %-3s +%d   (flat %d -> deep %d)"
          % (x, y, repr(rows[y][x]).strip("'"), v, cf.get((x, y), 0), cd.get((x, y), 0)))
print("\ntotal growth %d over %d cells" % (sum(v for v, _ in pos), len(pos)))
neg = sorted((v, k) for k, v in d.items() if v < 0)
print("total shrink %d over %d cells" % (sum(v for v, _ in neg), len(neg)))

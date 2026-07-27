#!/usr/bin/env python3
"""Which room dominates at DEPTH vs at LENGTH -- i.e. what do private cases hit?

MEASURED elsewhere: public ticks fell 30% while the server score fell 2%, so the
private cases are heavier and improve less.  They cannot be seen, but the spec
bounds them: n <= 64, depth <= 32.  So build public-shaped inputs that scale the
two axes independently and profile per room.

  python3 scratchpad/brk4/brk4_shape.py <man>
"""
import json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
man = sys.argv[1]

OPEN = {"(": 40, "[": 91, "{": 123}
CLOSE = {")": 41, "]": 93, "}": 125}


def enc(s):
    m = dict(OPEN); m.update(CLOSE)
    return [str(len(s))] + [str(m[ch]) for ch in s]


CASES = {
    "public-shape  n=6  d=1": "()[]{}",
    "flat max      n=64 d=1": "()" * 32,
    "deep max      n=64 d=32": "(" * 32 + ")" * 32,
    "deep mixed    n=64 d=32": "([{" * 10 + "(" * 2 + ")" * 2 + "}])" * 10,
    "deep  n=48 d=24": "[" * 24 + "]" * 24,
    "deep  n=32 d=16": "{" * 16 + "}" * 16,
    "deep  n=16 d=8": "(" * 8 + ")" * 8,
    "late mismatch n=64": "(" * 31 + "[" + ")" * 32,
    "early mismatch n=64": "(]" + "()" * 31,
}


def expect(s):
    """0 if balanced, else the 1-based index of the first offending char, or n+1
    if openers are left unclosed (matches the public cases exactly)."""
    st = []
    pair = {")": "(", "]": "[", "}": "{"}
    for i, ch in enumerate(s, 1):
        if ch in OPEN:
            st.append(ch)
        else:
            if not st or st[-1] != pair[ch]:
                return i
            st.pop()
    return len(s) + 1 if st else 0


def prof(seq, exp):
    p = subprocess.run([LM, "--profile", man, "--input=" + " ".join(seq),
                        "--expected=%d" % exp, "--cap=400000"],
                       capture_output=True, text=True)
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    st = json.loads(out.splitlines()[0])
    rooms = {}
    for line in out.splitlines():
        if line.startswith("PROFILE rooms="):
            rooms = dict(eval(line[len("PROFILE rooms="):]))
    return st.get("settleTick"), rooms


base = None
for name, s in CASES.items():
    seq = enc(s)
    t, rooms = prof(seq, expect(s))
    tot = sum(rooms.values()) or 1
    top = sorted(rooms.items(), key=lambda kv: -kv[1])[:5]
    share = "  ".join("r%d %4.1f%%" % (k, 100.0 * v / tot) for k, v in top)
    print("%-26s ticks %6s | %s" % (name, t, share))

#!/usr/bin/env python3
"""Marginal tick cost per op for a memory build: settleTick vs op count/shape."""
import json
import subprocess
import sys

MAN = sys.argv[1] if len(sys.argv) > 1 else "solutions/memory/direct-straight.man"
LM = "interp/target/release/lm"


def model(t):
    mem, out, i = [0] * 100, [], 0
    while i < len(t):
        if t[i] == 0:
            out.append(mem[t[i + 1]]); i += 2
        else:
            mem[t[i + 1]] = t[i + 2]; i += 3
    return out


def run(t):
    exp = model(t)
    r = subprocess.run(
        [LM, "--grade", MAN, "--input=" + " ".join(map(str, t)),
         "--expected=" + " ".join(map(str, exp)), "--cap=400000"],
        capture_output=True, text=True, timeout=300)
    try:
        return json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        return {"status": "ERR", "settleTick": -1}


def series(name, mk, ns):
    prev = None
    for n in ns:
        r = run(mk(n))
        st = r.get("settleTick", -1)
        d = "" if prev is None else "  d=%+.2f/op" % ((st - prev[1]) / (n - prev[0]))
        print("  %-22s n=%3d  %-6s tick=%5s%s" % (name, n, r["status"], st, d))
        prev = (n, st)


NS = [1, 2, 5, 10, 20, 40, 80]
series("reads same addr", lambda n: [0, 7] * n, NS)
series("reads spread addr", lambda n: sum(([0, (i * 37) % 100] for i in range(n)), []), NS)
series("reads same block", lambda n: sum(([0, i % 25] for i in range(n)), []), NS)
series("writes spread", lambda n: sum(([1, (i * 37) % 100, i + 1] for i in range(n)), []), NS)
series("w+r spread", lambda n: sum(([1, (i * 37) % 100, i + 1, 0, (i * 37) % 100] for i in range(n)), []), NS)

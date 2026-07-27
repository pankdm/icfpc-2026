#!/usr/bin/env python3
"""When does each structure finish initialising?  Binary-search over --inspect."""
import json
import subprocess
import sys

MAN = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mem_patch.man"
INP = sys.argv[2] if len(sys.argv) > 2 else "0 3"


def men(t):
    r = subprocess.run(["interp/target/release/lm", MAN, "--input=" + INP,
                        "--inspect=%d" % t, "--cap=%d" % (t + 2)],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        return None
    rs = d.get("runners") or d.get("men") or []
    return {tuple(x.get("pos") or (x.get("x"), x.get("y")))
            for x in rs if not x.get("halted")}


def first_tick(pos, lo=0, hi=400):
    while lo < hi:
        mid = (lo + hi) // 2
        s = men(mid)
        if s is None:
            return None
        if pos in s:
            hi = mid
        else:
            lo = mid + 1
    return lo


targets = {
    "cell 0  block0 (12,19)": (12, 19),
    "cell 12 block0 (12,43)": (12, 43),
    "cell 24 block0 (12,67)": (12, 67),
    "cell 24 block3 (69,67)": (69, 67),
    "dispatch R first (3,72)": (3, 72),
    "dispatch R last  (60,76)": (60, 76),
}
for name, p in targets.items():
    print("  %-26s first occupied at tick %s" % (name, first_tick(p)))

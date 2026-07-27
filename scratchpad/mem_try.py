#!/usr/bin/env python3
"""Fast diagnostic run of a .man on the memory public cases (short cap)."""
import json
import subprocess
import sys

MAN = sys.argv[1]
CAP = sys.argv[2] if len(sys.argv) > 2 else "4000"
d = json.load(open("tests/memory.json"))
tot = 0
for i, c in enumerate(d["publicTestData"]):
    r = subprocess.run(
        ["interp/target/release/lm", "--grade", MAN,
         "--input=" + " ".join(c["in"]), "--expected=" + " ".join(c["out"]),
         "--cap=" + CAP], capture_output=True, text=True, timeout=120)
    try:
        j = json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        j = {"status": "ERR", "raw": (r.stdout + r.stderr)[:200]}
    print("  %d %-32s %-10s tick=%s %s" % (
        i, c["name"], j.get("status"), j.get("settleTick"),
        j.get("reason", "") or j.get("raw", "")))

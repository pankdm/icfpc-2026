#!/usr/bin/env python3
"""Turn an existing per-problem fuzz generator into a stress-case JSON that
sw_gradelib.Gate can use, so the sweep on a slug without tests/stress/<slug>.json
is still gated on more than the public cases.

  python3 sw_mkstress.py memory [nrandom]   -> scratchpad/sweep/stress_memory.json

Each stream is its OWN single-round case: the memory belt is initialised once at
program start, so packing several streams into one run as multiple rounds would
not re-initialise it and would report bogus failures (rewind/fuzz.py's own note).
"""
import json, os, sys

REPO = "/Users/visenbaev/icfpc26"
HERE = os.path.dirname(os.path.abspath(__file__))

slug = sys.argv[1] if len(sys.argv) > 1 else "memory"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 60

if slug == "memory":
    sys.path.insert(0, os.path.join(REPO, "scratchpad", "rewind"))
    import fuzz
    cases = []
    for name, stream in fuzz.streams(n):
        out = fuzz.reference(stream)
        cases.append({"name": name,
                      "rounds": [{"in": [str(v) for v in stream],
                                  "out": [str(v) for v in out]}]})
else:
    raise SystemExit("no generator wired for " + slug)

path = os.path.join(HERE, "stress_%s.json" % slug)
json.dump({"cases": cases}, open(path, "w"))
print("wrote", path, len(cases), "cases")

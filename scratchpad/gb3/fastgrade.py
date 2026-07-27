#!/usr/bin/env python3
"""fastgrade.py — screen a candidate on the two dominant gradebook cases only.

grade_fast.py runs all seven public cases; N=16 K=4 alone is 47% of the tick total, so a
two-case screen is 3.5x cheaper and rejects almost everything a full grade would.  Callers
re-run the full grade on survivors.

usage: fastgrade.py <file.man>   -> prints "<passed> <total> <sumTicks>" or "FAIL"
"""
import sys, os, json, subprocess
REPO = "/Users/visenbaev/icfpc26"
os.chdir(REPO)
SEL = ("N=16", "mixed batch")
_d = json.load(open("tests/gradebook.json"))
CASES = [c for c in _d["publicTestData"] if any(s in c["name"] for s in SEL)]


def run(man):
    tot = 0
    for c in CASES:
        rs = c["rounds"]
        inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
        exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
        p = subprocess.run(["interp/target/release/lm", "--grade", man,
                            "--input=" + inp, "--expected=" + exp, "--cap=200000"],
                           capture_output=True, text=True)
        try:
            o = json.loads(p.stdout.strip().split("\n")[-1])
        except Exception:
            return None
        if o.get("status") != "pass":
            return None
        tot += o.get("settleTick") or 0
    return tot


if __name__ == "__main__":
    r = run(sys.argv[1])
    print("FAIL" if r is None else r)

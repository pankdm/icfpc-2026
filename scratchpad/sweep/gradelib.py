#!/usr/bin/env python3
"""Generic slug-parameterised grading gate (public cases, Rust engine).

Set the slug via the SWEEP_SLUG env var.  Returns box*avgTicks over the public
cases, or None if any case fails.
"""
import json
import os
import subprocess

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
SLUG = os.environ.get("SWEEP_SLUG", "matmul")
CAP = int(os.environ.get("SWEEP_CAP", "400000"))


def _cases_of(obj):
    return obj.get("publicTestData") or obj.get("cases") or []


PUBLIC = _cases_of(json.load(open(os.path.join(REPO, "tests", SLUG + ".json"))))


def _io(c):
    rs = c.get("rounds") or [c]
    return (" / ".join(" ".join(r.get("in") or []) for r in rs),
            " / ".join(" ".join(r.get("out") or []) for r in rs))


def score(man):
    box = None
    total = 0
    for c in PUBLIC:
        inp, exp = _io(c)
        p = subprocess.run([LM, "--grade", man, "--input=" + inp,
                            "--expected=" + exp, f"--cap={CAP}"],
                           capture_output=True, text=True)
        try:
            d = json.loads(p.stdout.strip())
        except Exception:
            return None
        if d.get("status") != "pass":
            return None
        box = d["footprint"]
        total += d["settleTick"]
    if box is None or not PUBLIC:
        return None
    return box * (total / len(PUBLIC))

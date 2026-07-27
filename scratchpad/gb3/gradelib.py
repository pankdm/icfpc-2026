#!/usr/bin/env python3
"""gradelib.py — Rust-engine grading gate for gradebook, PUBLIC + both stress suites.

A grid search gated on the 7 public cases alone finds moves that pass locally and break
generality: the first block-shift run reached 44.0M on public while failing 4/22 and 5/47
stress cases.  Private cases are ~2-3x the public count, so a public-only gate is not a
gate at all.

`score()` runs the 7 public cases first (cheap reject for the overwhelming majority of
proposals) and only then the 69 stress cases; any failure anywhere returns None.  The
returned score is box * avgTicks over the PUBLIC cases, which is what the server scores.
"""
import json, os, subprocess

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
PUBLIC_CAP = 60000      # max real public settle is 38.5k
STRESS_CAP = 300000     # "N=16 K=4 all zeroes" alone settles at 59k


def _cases_of(obj):
    return obj.get("publicTestData") or obj.get("cases") or []


PUBLIC = _cases_of(json.load(open(os.path.join(REPO, "tests/gradebook.json"))))
STRESS = (_cases_of(json.load(open(os.path.join(REPO, "tests/stress/gradebook.json"))))
          + _cases_of(json.load(open(os.path.join(REPO, "tests/stress/gradebook-align.json")))))


def _io(c):
    rs = c.get("rounds") or [c]
    return (" / ".join(" ".join(r.get("in") or []) for r in rs),
            " / ".join(" ".join(r.get("out") or []) for r in rs))


def _run(man, cases, cap):
    total = 0
    for c in cases:
        inp, exp = _io(c)
        p = subprocess.run([LM, "--grade", man, "--input=" + inp, "--expected=" + exp,
                            f"--cap={cap}"], capture_output=True, text=True)
        try:
            o = json.loads(p.stdout.strip().split("\n")[-1])
        except Exception:
            return None
        if o.get("status") != "pass":
            return None
        total += o.get("settleTick") or 0
    return total


def footprint(path):
    rows = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
    ys = [i for i, r in enumerate(rows) if r.strip()]
    if not ys:
        return 0
    w = max(len(r) for r in rows)
    xs = [x for x in range(w) if any(len(r) > x and r[x] != " " for r in rows)]
    return max(xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1) ** 2


def score(man):
    """box * avgTicks over the public cases, or None if any public/stress case fails."""
    pub = _run(man, PUBLIC, PUBLIC_CAP)
    if pub is None:
        return None
    if _run(man, STRESS, STRESS_CAP) is None:
        return None
    return footprint(man) * pub / len(PUBLIC)

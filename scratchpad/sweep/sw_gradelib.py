#!/usr/bin/env python3
"""Generic Rust-engine grading gate: PUBLIC cases plus every stress suite we have
for the slug.  Same contract as scratchpad/gb3/gradelib.py, parameterised.

A public-only gate is not a gate: private cases are ~2-3x the public count, and on
gradebook the first block-shift run reached 44.0M on public while failing 4/22 and
5/47 stress cases.  score() runs public first (cheap reject) and only then stress;
any failure anywhere returns None.
"""
import json, os, subprocess

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")

# extra stress suites that do not follow tests/stress/<slug>.json
EXTRA = {
    "sort-numbers": ["tests/sort-stress.json"],
    "sudoku-validity": ["scratchpad/sweep/stress_sudoku-validity.json"],
    "tcp": ["scratchpad/sweep/stress_tcp.json"],
    "memory": ["scratchpad/sweep/stress_memory.json"],
    "gradebook": ["tests/stress/gradebook-align.json",
                  "tests/stress/gradebook-parity.json",
                  "tests/stress/gradebook-fuzz.json"],
}


def _cases_of(obj):
    return obj.get("publicTestData") or obj.get("cases") or []


def load(slug):
    pub = _cases_of(json.load(open(os.path.join(REPO, "tests", slug + ".json"))))
    stress = []
    paths = [os.path.join("tests", "stress", slug + ".json")] + EXTRA.get(slug, [])
    for rel in paths:
        p = os.path.join(REPO, rel)
        if os.path.exists(p):
            stress += _cases_of(json.load(open(p)))
    return pub, stress


def _io(c):
    rs = c.get("rounds") or [c]
    return (" / ".join(" ".join(r.get("in") or []) for r in rs),
            " / ".join(" ".join(r.get("out") or []) for r in rs))


def _run(man, cases, cap):
    total = 0
    for c in cases:
        inp, exp = _io(c)
        p = subprocess.run([LM, "--grade", man, "--input=" + inp, "--expected=" + exp,
                            "--cap=%d" % cap], capture_output=True, text=True)
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


class Gate:
    def __init__(self, slug, pub_cap=None, stress_cap=None):
        self.slug = slug
        self.pub, self.stress = load(slug)
        assert self.pub, "no public cases for " + slug
        self.pub_cap = pub_cap or 5_000_000
        self.stress_cap = stress_cap or (self.pub_cap * 5)

    def score(self, man, with_stress=True):
        """Full gate by default.  with_stress=False is ONLY for the search phase on
        problems whose stress set is too slow to run per proposal (memory: >115s a
        proposal); the finalist must still be run through the full gate before it
        is submitted, or the search has no gate at all."""
        pub = _run(man, self.pub, self.pub_cap)
        if pub is None:
            return None
        if with_stress and self.stress and _run(man, self.stress, self.stress_cap) is None:
            return None
        return footprint(man) * pub / len(self.pub)

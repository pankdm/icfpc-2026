#!/usr/bin/env python3
"""Simulation test for the merged DISP room (classifier + ring lookup)."""
import random
from roomsim import run

DISP = [
    #0123456789012345678901234
    "v@<<s<<<<<<              ",
    ">`17`Mr  X^              ",
    " >`31`+^ -               ",
    "vX~`92`M+X+b >> mdrMs>rv ",
    ">rb          ^^sr<   ^sXv",
    "     ^W                s<",
]

ESC = 29


def pipe_for(x, y, kind):
    if kind == "in":
        return "in" if (x, y) in ((6, 1), (1, 4)) else "ring"
    return "out" if (x, y) == (4, 0) else "ring"


def test():
    for r in DISP:
        assert len(r) == 25, (len(r), r)
    N = 34
    entries = [1000 + i for i in range(1, N + 1)]
    ringq = entries + [-1]
    stream, want = [], []
    random.seed(7)
    for _ in range(400):
        c = random.random()
        if c < 0.1:
            stream.append(0); want.append(0)
        elif c < 0.35:
            v = random.randint(1, 16)
            stream.append(v); want.append(1000 + v)
        elif c < 0.55:
            k = random.randint(17, N)
            stream += [ESC, k]; want.append(1000 + k)
        else:
            v = random.choice([v for v in range(18, 92) if v != ESC])
            stream.append(v); want.append(v + 31)
    q = {"in": list(stream), "ring": list(ringq), "out": []}
    res = run(DISP, (1, 0), "E", q, pipe_for, max_steps=8000000)
    assert res["reason"] == "starved", (res["reason"], res["pos"], res["A"], res["B"])
    assert q["out"] == want, (q["out"][:10], want[:10])
    assert q["ring"] == ringq, q["ring"][:6]
    print("DISP OK:", len(want), "outputs; ring canonical")


if __name__ == "__main__":
    test()

#!/usr/bin/env python3
"""Simulation tests for D1 and L1 grids."""
import random
from roomsim import run, Fatal

D1 = [
    #012345678901234567
    "v@<<<<<<<<<<<<<<<<",
    ">`17`M  r X`1`Ns^ ",
    "  >WM`32`v-       ",
    " vX~`92`M+X+s^    ",
    " >rs  ^sN<        ",
]

L1 = [
    #01234567890123456789012
    "v   s-N<               ",
    ">`1`Mr X@v             ",
    "       b         >sv   ",
    "       v   > mdrs^ >rv ",
    "       >   ^sr<    ^sXv",
    "^        <        s   <",
]
# row3: v7; rot1: >11, m13, d14; hit: r15 s16 ^17; restore: >19 r20 v21
# row4: >7; rot1: ^11 s12 r13 <14; restore: ^19 s20 X21 v22
# row5: ^0; sentinel s18; <22


def test_d1():
    ESC = 29
    cases = []
    # (input symbols, expected tags)
    cases.append(([0], [-1]))
    for v in (1, 5, 13, 16):
        cases.append(([v], [v]))
    for v in (18, 28, 30, 91):
        cases.append(([v], [-(v + 32)]))
    for k in (17, 40, 91):
        cases.append(([ESC, k], [k]))
    # mixed stream
    stream, want = [], []
    random.seed(1)
    for _ in range(200):
        c = random.choice(cases)
        stream += c[0]
        want += c[1]
    queues = {"in": list(stream), "out": []}
    res = run(D1, (0, 1), "E", queues, lambda x, y, k: "in" if k == "in" else "out",
              max_steps=200000)
    assert res["reason"] == "starved", res
    assert queues["out"] == want, (queues["out"][:20], want[:20])
    print("D1 OK:", len(want), "tags")


def test_l1():
    # ring with N entries
    N = 8
    entries = [100 + i for i in range(1, N + 1)]  # ring[g] = 100+g
    ringq = entries + [-1]          # P1->L1 pipe preloaded, E1 first, sentinel last

    def pipe_for(x, y, kind):
        if kind == "in":
            return "in" if (x, y) == (5, 1) else "ring"
        # sends: out only at (4,0) and (18,2)
        return "out" if (x, y) in ((4, 0), (18, 2)) else "ring"

    tags, want = [], []
    random.seed(2)
    for _ in range(300):
        if random.random() < 0.5:
            t = -random.randint(1, 120)
            tags.append(t)
            want.append(-t - 1)
        else:
            g = random.randint(1, N)
            tags.append(g)
            want.append(100 + g)
    queues = {"in": list(tags), "ring": list(ringq), "out": []}
    res = run(L1, (0, 1), "E", queues, pipe_for, max_steps=2000000)
    assert res["reason"] == "starved", (res["reason"], res["pos"], res["A"], res["B"])
    assert queues["out"] == want, (queues["out"][:20], want[:20])
    # ring must be restored to canonical order
    assert queues["ring"] == ringq, queues["ring"]
    print("L1 OK:", len(want), "outputs; ring restored")


if __name__ == "__main__":
    test_d1()
    test_l1()

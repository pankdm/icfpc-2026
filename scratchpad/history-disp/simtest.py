#!/usr/bin/env python3
"""Standalone semantic test for a DISP grid, independent of the full layout.

Ports are given as local attach coordinates (lx, ly) in interior coordinates,
where a west attach is lx = -2, a north attach ly = -2, a south attach
ly = H + 1 and an east attach lx = W + 1 (one cell outside the wall, which is
what the interpreter measures to).  Nearest-pipe selection replicates
interp/src/lib.rs: (manhattan, attach_y, attach_x).
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "history-ring"))
from roomsim import run   # noqa: E402

ESC = 29
DIRECT = 16          # symbols 1..16 are direct dictionary slots
RESERVED = 17        # bare 17 crashes the dispatcher by design


def make_pipe_for(ports):
    """ports: list of (queue, kind, (lx, ly)); kind in {'in', 'out'}."""
    def pipe_for(x, y, kind):
        cands = [(q, a) for q, k, a in ports if k == kind]
        best = min(cands, key=lambda qa: (abs(qa[1][0] - x) + abs(qa[1][1] - y),
                                          qa[1][1], qa[1][0]))
        return best[0]
    return pipe_for


def check(rows, ports, start, direction="E", entries=44, trials=1500, seed=7,
          zeros=False, direct=None, reserved=None, esc=None):
    """zeros: also feed the 0 year-marker symbol, which the champion's
    dispatcher forwards untouched (the no-YEAR vertical builds never emit it)."""
    DIRECT_ = DIRECT if direct is None else direct
    RESERVED_ = RESERVED if reserved is None else reserved
    ESC_ = ESC if esc is None else esc
    w = max(len(r) for r in rows)
    rows = [r.ljust(w) for r in rows]
    ring0 = [1000 + i for i in range(1, entries + 1)] + [0]
    stream, want = [], []
    rnd = random.Random(seed)
    for _ in range(trials):
        c = rnd.random()
        if zeros and c < 0.10:
            stream.append(0)
            want.append(0)
        elif c < 0.40:
            v = rnd.randint(1, DIRECT_)
            stream.append(v)
            want.append(1000 + v)
        elif c < 0.70:
            k = rnd.randint(DIRECT_ + 1, entries)
            stream += [ESC_, k]
            want.append(1000 + k)
        else:
            v = rnd.choice([v for v in range(RESERVED_ + 1, 92)
                            if v != ESC_])
            stream.append(v)
            want.append(v + 31)
    queues = {"stream": list(stream), "ring": list(ring0), "unpack": []}
    res = run(rows, start, direction, queues, make_pipe_for(ports),
              max_steps=4_000_000)
    if res["reason"] != "starved":
        return f"ended {res['reason']} at {res['pos']} A={res['A']} B={res['B']}"
    if queues["unpack"] != want:
        n = next(i for i, (a, b) in enumerate(zip(queues["unpack"] + [None],
                                                  want + [None])) if a != b)
        return (f"output diverged at {n}: got {queues['unpack'][n:n+4]} "
                f"want {want[n:n+4]} (after {n} correct)")
    if queues["ring"] != ring0:
        return f"ring not canonical: {queues['ring'][:6]} vs {ring0[:6]}"
    return None

#!/usr/bin/env python3
"""Check the five-row, 30-column fold of History Lesson's ring dispatcher."""
import random

from roomsim import run


DISP_FOLDED = [
    "v@<<s<<<<<<<<              <",
    ">`17`Mr  X^                 ",
    " >`31`+^ -                  ",
    "vX~`92`M+X+b >> mdrMs>rv    ",
    ">rb          ^^sr<   ^sX sW^",
]

ESC = 29


def pipe_for(x, y, kind):
    if kind == "in":
        return "in" if (x, y) in ((6, 1), (1, 4)) else "ring"
    return "out" if (x, y) == (4, 0) else "ring"


def test():
    assert all(len(row) == 28 for row in DISP_FOLDED)
    count = 38
    entries = [1000 + i for i in range(1, count + 1)]
    canonical_ring = entries + [-1]
    stream, expected = [], []
    random.seed(81)
    for _ in range(400):
        choice = random.random()
        if choice < 0.1:
            stream.append(0)
            expected.append(0)
        elif choice < 0.35:
            value = random.randint(1, 16)
            stream.append(value)
            expected.append(1000 + value)
        elif choice < 0.55:
            position = random.randint(17, count)
            stream.extend([ESC, position])
            expected.append(1000 + position)
        else:
            value = random.choice(
                [value for value in range(18, 92) if value != ESC]
            )
            stream.append(value)
            expected.append(value + 31)

    queues = {
        "in": stream,
        "ring": list(canonical_ring),
        "out": [],
    }
    result = run(
        DISP_FOLDED,
        (1, 0),
        "E",
        queues,
        pipe_for,
        max_steps=9_000_000,
    )
    assert result["reason"] == "starved", result
    assert queues["out"] == expected
    assert queues["ring"] == canonical_ring
    print("folded DISP OK: 400 outputs; ring canonical")


if __name__ == "__main__":
    test()

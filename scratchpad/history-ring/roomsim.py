#!/usr/bin/env python3
"""Tiny exact-ish simulator for a single room's man, for layout iteration.

Grid: list of strings (content only, no borders).  Off-grid = wall = fatal.
Pipes: pipe_for(x, y, kind) -> queue name; queues: dict name -> list.
r pops from the front of its queue (error if empty and no feeder callback);
s appends A.  Blocked-forever situations aren't modeled (queues are scripted).

Literal rule: stepping on '`' enters literal mode; digits accumulate in walk
order; the closing '`' loads the value into A.  Digit cells outside literal
mode set A directly.  This matches the oracle for the patterns we use.
"""

DIRS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
CW = {"E": "S", "S": "W", "W": "N", "N": "E"}
CCW = {v: k for k, v in CW.items()}


class Fatal(Exception):
    pass


def parse_literals(grid):
    """Faithful to interp: per-row consecutive backtick pairs (digits/spaces
    between, else error); per-column pairs only when span is digits/spaces.
    Returns (lit_content set, lit_close dict ((x,y),dir)->value)."""
    content, close = set(), {}
    h = len(grid)
    w = max(len(r) for r in grid)

    def at(x, y):
        row = grid[y]
        return row[x] if x < len(row) else " "

    for y in range(h):
        ticks = [x for x in range(w) if at(x, y) == "`"]
        for i in range(0, len(ticks) - 1, 2):
            a, b = ticks[i], ticks[i + 1]
            digits = ""
            for x in range(a + 1, b):
                c = at(x, y)
                content.add((x, y))
                if c == " ":
                    continue
                assert c.isdigit(), f"bad literal cell {c!r} at ({x},{y})"
                digits += c
            if digits:
                close[((b, y), "E")] = int(digits)
                close[((a, y), "W")] = int(digits[::-1])
    for x in range(w):
        ticks = [y for y in range(h) if at(x, y) == "`"]
        i = 0
        while i + 1 < len(ticks):
            a, b = ticks[i], ticks[i + 1]
            digits, ok = "", True
            for y in range(a + 1, b):
                c = at(x, y)
                if c == " ":
                    continue
                if c.isdigit():
                    digits += c
                else:
                    ok = False
                    break
            if not ok:
                i += 1
                continue
            for y in range(a + 1, b):
                content.add((x, y))
            if digits:
                close[((x, b), "S")] = int(digits)
                close[((x, a), "N")] = int(digits[::-1])
            i += 2
    return content, close


def run(grid, start, direction, queues, pipe_for, max_steps=100000, trace=False):
    x, y = start
    d = direction
    A = B = BP = 0
    lit_content, lit_close = parse_literals(grid)
    steps = 0
    log = []
    while steps < max_steps:
        steps += 1
        if y < 0 or y >= len(grid) or x < 0 or x >= len(grid[y]):
            raise Fatal(f"wall at ({x},{y}) dir {d} A={A} B={B} BP={BP}")
        ch = grid[y][x]
        if trace:
            log.append((x, y, ch, A, B, BP))
        if (x, y) in lit_content:
            pass
        elif ch == "`":
            if ((x, y), d) in lit_close:
                A = lit_close[((x, y), d)]
        elif ch.isdigit():
            A = int(ch)
        elif ch in " .@":
            pass
        elif ch == ">":
            d = "E"
        elif ch == "<":
            d = "W"
        elif ch == "^":
            d = "N"
        elif ch in "vV":
            d = "S"
        elif ch == "M":
            B = A
        elif ch == "W":
            A, B = B, A
        elif ch == "b":
            BP = A
        elif ch == "m":
            BP -= 1
        elif ch == "+":
            A = A + B
        elif ch == "-":
            A = A - B
        elif ch == "*":
            A = A * B
        elif ch == "N":
            A = -A
        elif ch == "~":
            A = A ^ B
        elif ch == "/":
            if B == 0:
                A, B = 0, A
            else:
                q, r = divmod(A, B)
                A, B = q, r
        elif ch == "%":
            A = (A % B) if B else 0
        elif ch == "X":
            if A > 0:
                d = CW[d]
            elif A < 0:
                d = CCW[d]
        elif ch == "d":
            if BP > 0:
                d = CW[d]
        elif ch == "a":
            if BP > 0:
                d = CCW[d]
        elif ch == "s":
            q = pipe_for(x, y, "out")
            queues[q].append(A)
        elif ch == "r":
            q = pipe_for(x, y, "in")
            if not queues[q]:
                return dict(reason="starved", pos=(x, y), steps=steps,
                            A=A, B=B, BP=BP, log=log)
            A = queues[q].pop(0)
        elif ch == "H":
            return dict(reason="halt", pos=(x, y), steps=steps,
                        A=A, B=B, BP=BP, log=log)
        else:
            raise Fatal(f"bad op {ch!r} at ({x},{y})")
        dx, dy = DIRS[d]
        x, y = x + dx, y + dy
    return dict(reason="steps", pos=(x, y), steps=steps, A=A, B=B, BP=BP, log=log)

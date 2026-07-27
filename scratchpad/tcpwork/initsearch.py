#!/usr/bin/env python3
"""What values of B can the checker's init reach in N cells?

The 2-wide checker's init man walks `@` -> '^' -> a straight run of N free cells
in column R -> the ok-return turn -> U. Those N cells are the ONLY place the
window constant can be built: everything above them is either the ok-return
corridor (an op there re-runs on every accepted packet) or the drain ring.

N is fixed by the layout: it equals the number of overflow rows, because the
init cells sit alongside the overflow gadget between the ok-turn row and the
`@` row. Overflow is `1 N s` = 3, so N = 3.

This brute-forces every N-cell program over the real op set and reports the
reachable B, which is what caps the window constant K.
"""
import itertools

DIGITS = '0123456789'
OPS = list(DIGITS) + ['M', 'W', '+', '-', '*', '%', '/', 'N', '&', '|', '~', '{', '}']


def run(prog):
    a, b = 0, 0
    for op in prog:
        try:
            if op in DIGITS:
                a = int(op)
            elif op == 'M':
                b = a
            elif op == 'W':
                a, b = b, a
            elif op == '+':
                a = a + b
            elif op == '-':
                a = a - b
            elif op == '*':
                a = a * b
            elif op == '%':
                a = 0 if b == 0 else a % b if b > 0 else -((-a) % (-b))
            elif op == '/':
                if b == 0:
                    a, b = 0, a
                else:
                    q = a // b
                    a, b = q, a - q * b
            elif op == 'N':
                a = -a
            elif op == '&':
                a = a & b
            elif op == '|':
                a = a | b
            elif op == '~':
                a = a ^ b
            elif op == '{':
                a = a << b if 0 <= b <= 63 else 0
            elif op == '}':
                a = a >> b if b >= 0 else 0
        except Exception:
            return None
        if abs(a) > 10 ** 12 or abs(b) > 10 ** 12:
            return None
    return b


for n in (2, 3, 4):
    reach = set()
    best = {}
    for prog in itertools.product(OPS, repeat=n):
        b = run(prog)
        if b is not None and 0 < b <= 64:
            reach.add(b)
            best.setdefault(b, ''.join(prog))
    print(f'{n} cells: max B = {max(reach)}   B=16 reachable? '
          + (f"YES via {best[16]}" if 16 in reach else 'no'))

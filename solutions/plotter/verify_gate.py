#!/usr/bin/env python3
"""Verify the GATE stream logic (BP+1 patch, m/d body loop, cmd translation +
driver decode) produces the SAME frames as dsl.simulate, independent of layout."""
import sys, os, json
from collections import deque
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import dsl
import littleman as lm

MASK = (1 << 64) - 1
def s64(v):
    v &= MASK
    return v - (1 << 64) if v & (1 << 63) else v
def _asr(a, b):
    if b < 0: return 0
    if b > 63: return -1 if a < 0 else 0
    return a >> b

# ---- SETUP' : insert inc (M,1,+) before the single 'b' so BP = n+1 ----
def setup_prime():
    ops = list(dsl.SETUP)
    i = ops.index('b')
    return ops[:i] + ['M', ('#', 1), '+'] + ops[i:]

SETUP1 = setup_prime()


def _lshift(a, b):
    if b < 0 or b > 63: return 0
    return s64(a << b)


def run_gate_ops(init, setup, body, rounds):
    """Executes the gate op-stream given (possibly de-spined) op lists."""
    belt = deque(); A = B = BP = 0
    cmd = deque()
    frames = []; buf = [0] * 768; cur = 0
    inp = deque()

    def ex(ops):
        nonlocal A, B, BP, cur
        for op in ops:
            if op == 'ri': A = inp.popleft()
            elif op == 'r': A = belt.popleft()
            elif op == 's': belt.append(A)
            elif op == 'PA': cmd.append(s64(A + 1))
            elif op == 'PD': cmd.append(A)
            elif isinstance(op, tuple): A = s64(op[1])
            elif isinstance(op, str) and len(op) == 1 and op.isdigit(): A = int(op)
            elif op == 'M': B = A
            elif op == 'W': A, B = B, A
            elif op == 'b': BP = A
            elif op == 'm': BP = s64(BP - 1)
            elif op == '+': A = s64(A + B)
            elif op == '-': A = s64(A - B)
            elif op == '*': A = s64(A * B)
            elif op == 'N': A = s64(-A)
            elif op == '&': A = s64(A & B)
            elif op == '}': A = _asr(A, B)
            elif op == '{': A = _lshift(A, B)
            else: raise ValueError("bad op %r" % (op,))

    def drive():
        nonlocal cur, buf
        while cmd:
            v = cmd.popleft()
            if v < 0:
                frames.append(list(buf)); buf = [0] * 768; cur = 0
            else:
                cur = v - 1
                c = cmd.popleft()
                if 0 <= cur < 768: buf[cur] = c % 16
                cur += 1

    ex(init)
    for r in rounds:
        inp.extend(r)
        ex(setup)
        while True:
            ex(body)
            BP = s64(BP - 1)
            if BP > 0:
                continue
            break
        cmd.append(-1)
        drive()
    return frames


def run_gate(rounds):
    return run_gate_ops(dsl.INIT, SETUP1, dsl.BODY, rounds)


if __name__ == "__main__":
    spec = json.load(open(os.path.join(lm.REPO, "tests", "plotter.json")))
    hexc = "0123456789abcdef"
    def rows(buf): return ["".join(hexc[buf[y*32+x]] for x in range(32)) for y in range(24)]
    allok = True
    for tc in spec["publicTestData"]:
        rnds = [tuple(map(int, r["in"])) for r in tc["rounds"]]
        exp = [r["frames"][0] for r in tc["rounds"]]
        got = [rows(b) for b in run_gate(rnds)]
        ok = got == exp; allok &= ok
        print(f"  {'OK  ' if ok else 'FAIL'} {tc['name']}")
    print("GATE STREAM LOGIC MATCHES dsl.simulate" if allok else "MISMATCH")

#!/usr/bin/env python3
"""Register-flow sim of the TWO-MAN rewind choreography (CONTROL + MEMORY, 100-belt).

CONTROL room (B = prev persists, BP = op):
  r  A=op ; b BP=op ; r A=addr
  -  A=addr-prev=delta, B=prev      ('-' writes A only)
  s  send delta
  +  A=delta+prev=addr              (addr recovered)
  M  B=addr ; 1 A=1 ; + A=addr+1 ; M B=addr+1 = new prev
  d  BP>0 (write): r A=value ; s ; 1 ; s      -> sends value, then op=1
     BP==0 (read):  0 ; s ; 0 ; s             -> sends dummy 0, then op=0

MEMORY room (stateless; belt + engine):
  r A=delta ; M B=delta ; `100` A=100 ; W A=delta,B=100 ; % A=delta%100=rot in [0,99]
  b BP=rot
  r A=value ; M B=value
  r A=op
  engine: relay `rot` belt values head->tail (A,B untouched)
  X on A: op>0 write / op==0 read
    read : r A=head ; S  (output A + reinject A at tail)
    write: r A=head(discard) ; W A=value,B=head ; s (append value at tail)

Belt invariant: the value at the belt head is memory cell `prev` (mod 100),
prev starts 0 and the belt starts as 100 zeros -> head is cell 0.
"""
import json, random, sys
from collections import deque

BELT = 100

def run_choreo(tokens):
    tokens = [int(t) for t in tokens]
    belt = deque([0] * BELT)
    prev = 0                 # CONTROL's B
    out = []
    i = 0
    while i < len(tokens):
        # ---- CONTROL ----
        op = tokens[i]; i += 1
        A = op
        BP = op                      # b
        addr = tokens[i]; i += 1
        A = addr
        A = A - prev                 # -    A=delta, B=prev
        delta = A
        A = A + prev                 # +    A=addr
        assert A == addr
        B = A                        # M
        A = 1
        A = A + B                    # +    A=addr+1
        prev = A                     # M    new prev
        if BP > 0:                   # d
            value = tokens[i]; i += 1
            msg = (delta, value, 1)
        else:
            msg = (delta, 0, 0)
        # ---- MEMORY ----
        d, val, o = msg
        A = d
        B = A                        # M
        A = 100                      # `100`
        A, B = B, A                  # W  -> A=d, B=100
        A = A % B if B else 0        # %  python % is floored -> matches
        rot = A
        assert 0 <= rot < 100, rot
        BP = rot                     # b
        A = val; B = A               # r ; M
        A = o                        # r
        for _ in range(rot):         # engine
            belt.append(belt.popleft())
        if A > 0:                    # X : write
            belt.popleft()           # r (discard old)
            A, B = B, A              # W  -> A=value
            belt.append(A)           # s
        else:                        # read
            A = belt.popleft()       # r
            out.append(A)            # S -> output
            belt.append(A)           # S -> reinject
    return out

def run_ref(tokens):
    tokens = [int(t) for t in tokens]
    mem = [0] * 100
    out = []
    i = 0
    while i < len(tokens):
        op = tokens[i]; addr = tokens[i + 1]; i += 2
        if op == 1:
            mem[addr] = tokens[i]; i += 1
        else:
            out.append(mem[addr])
    return out

def main():
    cases = json.load(open('/Users/visenbaev/icfpc26/tests/memory.json'))['publicTestData']
    for c in cases:
        got = run_choreo(c['in'])
        want = [int(x) for x in c['out']]
        assert got == want, (c['name'], got[:20], want[:20])
    print(f'public: {len(cases)}/{len(cases)} OK')

    rng = random.Random(7)
    rots = []
    for trial in range(5000):
        toks = []
        n_ops = rng.randint(1, 60)
        prev_addr = None
        for _ in range(n_ops):
            op = rng.randint(0, 1)
            style = rng.random()
            if style < 0.2 and prev_addr is not None:
                addr = prev_addr
            elif style < 0.35:
                addr = rng.choice([0, 99])
            else:
                addr = rng.randint(0, 99)
            prev_addr = addr
            toks += [op, addr]
            if op == 1:
                toks.append(rng.choice([0, rng.randint(-10**18, 10**18)]))
        got, want = run_choreo(toks), run_ref(toks)
        assert got == want, (trial, toks[:30], got[:10], want[:10])
    print('fuzz: 5000/5000 OK (same-addr, addr 0/99, zero + huge writes, read-before-write)')

    # rotation statistics on the big public case + uniform model
    big = max(cases, key=lambda c: len(c['in']))
    toks = [int(t) for t in big['in']]
    prev = 0; i = 0; rs = []
    while i < len(toks):
        op = toks[i]; addr = toks[i+1]; i += 2
        rs.append((addr - prev) % 100); prev = addr + 1
        if op == 1: i += 1
    print(f'big case: {len(rs)} ops, avg rot {sum(rs)/len(rs):.1f}, max {max(rs)}')

if __name__ == '__main__':
    main()

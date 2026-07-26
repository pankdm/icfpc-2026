#!/usr/bin/env python3
"""DUAL-HEAD belt, BELT=128 / HALF=64 -- simulated at the level of actual CELLS.

Every quantity below is computed with exactly the ops the .man will execute, on
exactly the values it will hold, so that a pass here means the arithmetic is
right (it does NOT prove the timing/order is right -- only the oracle can).

WHY 128 AND NOT 100.  CONTROL has A, B and a WRITE-ONLY BP, and needs `prev`,
`delta` and a divisor live simultaneously -- one register short.  With a
power-of-two belt the head selector falls out of BP alone:

    `b` BP=delta ; `]` x6  -> BP = delta>>6 ; `x` branches on its low bit

so B = prev is never touched and no helper room is needed.  With BELT=100 the
`%100`/`/50` would clobber B, which costs an extra room + 2 pipes.  Measured
price of 128 over 100: mean r 28.24 -> 35.61 on the public cases.

PREV IS NEVER REDUCED.  prev grows by 2..66 per op forever, so delta goes large
and NEGATIVE.  That is safe because every decode below is floored (`/` floors,
`%` takes the divisor's sign, `]` is arithmetic), so rem/a/which come out
non-negative for negative delta with no branch and no special case.

ENGINE DECODE (identical in both rooms; room B just adds its head offset 64):
    d    = delta + K                 K = 0 in room A, 64 in room B
    rem  = d mod 8                   `/` by 8  -> A = d>>3, B = rem
    a    = (d>>3) mod 8              `/` by 8  -> A = d>>6, B = a
    which= (d>>6) mod 2              `%` by 2
    relays before the tap = 8*a + rem + 1        (the +1 is unconditional)
    which == 0  ->  THIS room taps;  which == 1  ->  this room plain-relays
"""
import json, random
from collections import deque

BELT, HALF = 128, 64


def engine_decode(delta, K):
    """Exactly the cells `M 8 W / W b <ring1> W M 8 W / W b <ring8> W M 2 W %`."""
    d = delta + K
    hi, rem = divmod(d, 8)          # `/` by 8 : A = d>>3, B = d mod 8
    hi2, a = divmod(hi, 8)          # `/` by 8 : A = d>>6, B = (d>>3) mod 8
    which = hi2 % 2                 # `%` by 2
    return which, 8 * a + rem


def run_dual(tokens):
    tokens = [int(t) for t in tokens]
    belt = deque([0] * BELT)        # belt[0] at A's dest, belt[64] at B's dest
    prev = 1                        # prev = P + 1, and P starts at 0
    out, i = [], 0
    while i < len(tokens):
        op, a = tokens[i], tokens[i + 1]
        i += 2
        value = 0
        if op == 1:
            value = tokens[i]; i += 1

        delta = a - prev                        # CONTROL: `-`
        whichA, qA = engine_decode(delta, 0)    # room A
        whichB, qB = engine_decode(delta, HALF) # room B
        assert qA == qB, (delta, qA, qB)        # both rooms relay the same count
        assert whichA + whichB == 1, (delta, whichA, whichB)   # exactly one taps

        r = qA + 1                              # rings + the unconditional relay
        belt.rotate(-r)
        idx = 0 if whichA == 0 else HALF        # the tapping room's own dest
        if op == 1:
            belt[idx] = value
        else:
            out.append(belt[idx])
        belt.rotate(-1)                         # the tap is itself a relay

        # CONTROL's `b`, `]`x6, `x` extracts exactly room A's selector bit, and
        # bit==0 means room A tapped (so the head advanced to a+1), bit==1 means
        # room B tapped (head is 64 behind, so a+1+64).
        bit = (delta >> 6) & 1                  # CONTROL: `b`, `]`x6, `x`
        assert bit == whichA, (delta, bit, whichA)
        prev = a + 2 + HALF * bit               # `+` with literal 2 or 66
    return out


def run_ref(tokens):
    tokens = [int(t) for t in tokens]
    mem, out, i = [0] * 100, [], 0
    while i < len(tokens):
        op, a = tokens[i], tokens[i + 1]
        i += 2
        if op == 1:
            mem[a] = tokens[i]; i += 1
        else:
            out.append(mem[a])
    return out


def main():
    cases = json.load(open('/Users/visenbaev/icfpc26/tests/memory.json'))['publicTestData']
    for c in cases:
        got, want = run_dual(c['in']), [int(x) for x in c['out']]
        assert got == want, (c['name'], got[:8], want[:8])
    print('public: %d/%d OK' % (len(cases), len(cases)))

    rng = random.Random(7)
    worst = 0
    for trial in range(20000):
        toks, p = [], None
        for _ in range(rng.randint(1, 80)):
            op, st = rng.randint(0, 1), rng.random()
            if st < 0.25 and p is not None: a = p
            elif st < 0.4: a = rng.choice([0, 99])
            else: a = rng.randrange(100)
            p = a
            toks += [op, a]
            if op == 1:
                toks.append(rng.choice([0, rng.randint(-10 ** 18, 10 ** 18)]))
        assert run_dual(toks) == run_ref(toks), trial
        worst = max(worst, len(toks))
    print('fuzz: 20000/20000 OK')

    # how big does the unreduced `prev` get, and what does the ring cost?
    tot = n = mx = 0
    for c in cases:
        toks, prev, i = [int(t) for t in c['in']], 1, 0
        while i < len(toks):
            op, a = toks[i], toks[i + 1]; i += 2
            if op == 1: i += 1
            delta = a - prev
            _, q = engine_decode(delta, 0)
            tot += q + 1; n += 1; mx = max(mx, q + 1)
            prev = a + 2 + HALF * ((delta >> 6) & 1)
        mx = max(mx, abs(prev))
    print('mean relays/op %.2f  (rings do 8a+rem, then 1 unconditional)' % (tot / n))
    print('largest |prev| reached on public cases: %d  (i64 has room to spare)' % mx)


if __name__ == '__main__':
    main()

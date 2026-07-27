#!/usr/bin/env python3
"""Randomised tcp arrival-order suite.

The public cases fix a handful of arrival orders. Private cases are ~2-3x the
public count and will hit orders these do not, so this generates many legal
streams and checks each against a reference model of the spec:

  - n packets, seq 0..n-1 distinct, 1 <= val <= 999
  - a packet delivered with offset (seq - next_expected) >= 16 means the
    receiver emits -1 and stops
  - otherwise values come out in seq order as the window advances

usage: randsuite.py <file.man> [trials] [seed]
"""
import json, random, subprocess, sys

ROOT = '/Users/visenbaev/icfpc26'
LM = ROOT + '/interp/target/release/lm'


def model(pkts):
    """Reference: returns the expected output list for this arrival order."""
    out, buf, want = [], {}, 0
    for seq, val in pkts:
        if seq - want >= 16:
            out.append(-1)
            return out, True
        buf[seq] = val
        while want in buf:
            out.append(buf.pop(want))
            want += 1
    return out, False


def gen(rng, n):
    """A legal arrival order: a permutation of 0..n-1 with bounded displacement."""
    pkts = [(s, rng.randint(1, 999)) for s in range(n)]
    order = list(range(n))
    for _ in range(rng.randint(0, n)):
        i = rng.randrange(n)
        j = min(n - 1, i + rng.randint(0, 20))
        order[i], order[j] = order[j], order[i]
    return [pkts[i] for i in order]


def main():
    man = sys.argv[1]
    trials = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 12345)
    bad = 0
    for t in range(trials):
        n = rng.choice([1, 2, 3, 5, 8, 16, 17, 31, 32, 47, 48])
        pkts = gen(rng, n)
        exp, halted = model(pkts)
        rounds = [f'{n}'] + [f'{s} {v}' for s, v in pkts]
        inp = '/'.join(rounds)
        # outputs are gated per round; the harness compares the flat stream
        outs = ['' for _ in rounds]
        k = 0
        cum, buf, want = [], {}, 0
        for i, (s, v) in enumerate(pkts):
            got = []
            if s - want >= 16:
                got = [-1]
            else:
                buf[s] = v
                while want in buf:
                    got.append(buf.pop(want)); want += 1
            outs[i + 1] = ' '.join(str(x) for x in got)
            if got and got[-1] == -1:
                break
        exps = '/'.join(outs[:len(rounds)])
        p = subprocess.run([LM, man, '--grade', f'--input={inp}',
                            f'--expected={exps}', '--cap=200000'],
                           capture_output=True, text=True, timeout=300)
        try:
            d = json.loads(p.stdout)
        except Exception:
            print(f'trial {t} n={n}: unparseable'); bad += 1; continue
        if d.get('status') != 'pass':
            bad += 1
            if bad <= 5:
                print(f'trial {t} n={n} FAIL {d.get("status")} {str(d.get("reason"))[:40]}'
                      f'  order={[s for s, _ in pkts][:12]}')
    print(f'{trials - bad}/{trials} passed')


main()

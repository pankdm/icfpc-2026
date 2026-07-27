#!/usr/bin/env python3
"""Generality stress for tcp: n=1, n=48 in-order / reverse / random, loss variants.

Builds rounds exactly like the real judge: round 1 = "n seq val", later rounds
= "seq val"; expected output per round = the values drained by that packet, in
seq order; a packet with seq >= head+16 makes the round output -1 and ends the
case.
"""
import json, os, random, subprocess, sys
REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp/target/release/lm")


def make_case(name, n, order, vals=None):
    """order: list of seq values, the arrival order (a permutation prefix of 0..n-1)."""
    if vals is None:
        vals = [(i * 37) % 999 + 1 for i in range(n)]
    head, have, rounds = 0, {}, []
    for k, seq in enumerate(order):
        inp = ([str(n)] if k == 0 else []) + [str(seq), str(vals[seq])]
        if seq - head >= 16:
            rounds.append({"in": inp, "out": ["-1"]})
            break
        have[seq] = vals[seq]
        out = []
        while head in have:
            out.append(str(have.pop(head)))
            head += 1
        rounds.append({"in": inp, "out": out})
    return {"name": name, "rounds": rounds}


def cases():
    cs = [make_case("n=1", 1, [0])]
    cs.append(make_case("n=2 reverse", 2, [1, 0]))
    cs.append(make_case("n=48 in-order", 48, list(range(48))))
    # reverse in blocks of 16 (the max legal displacement)
    order = []
    for b in range(0, 48, 16):
        order += list(range(b + 15, b - 1, -1))
    cs.append(make_case("n=48 block-reversed", 48, order))
    # sawtooth: always 15 ahead then fill
    order = []
    for b in range(0, 48, 16):
        blk = list(range(b, b + 16))
        random.Random(7 + b).shuffle(blk)
        order += blk
    cs.append(make_case("n=48 shuffled blocks", 48, order))
    cs.append(make_case("immediate loss", 20, [16]))
    cs.append(make_case("loss at 16 after fill", 20, list(range(1, 16)) + [16]))
    cs.append(make_case("loss aliasing head", 32, [15, 31]))   # 31-0 = 31 >= 16
    cs.append(make_case("n=16 max window", 16, [15] + list(range(15))))
    cs.append(make_case("n=48 single lag", 48, [1, 0] + list(range(2, 48))))
    # tightest overflow race: the bogus seq's slot aliases the slot the sweeper is
    # parked on, so it IS stored and drained -- `-1`+`H` must win.
    cs.append(make_case("alias head=1", 20, [0, 17]))
    cs.append(make_case("alias head=8", 32, list(range(8)) + [24]))
    cs.append(make_case("alias mid-burst", 40, list(range(15, -1, -1)) + [32]))
    return cs


def main():
    man = sys.argv[1]
    bad = 0
    for tc in cases():
        rs = tc["rounds"]
        inp = " / ".join(" ".join(r["in"]) for r in rs)
        exp = " / ".join(" ".join(r["out"]) for r in rs)
        p = subprocess.run([LM, "--grade", man, f"--input={inp}", f"--expected={exp}",
                            "--cap=5000000"], capture_output=True, text=True, timeout=600)
        try:
            v = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            v = {"status": "engine-error", "reason": (p.stderr or p.stdout)[:200]}
        ok = v.get("status") == "pass"
        bad += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {tc['name']:<24} {v.get('settleTick')}  {v.get('reason','')}")
    print("FAILURES:", bad)


main()

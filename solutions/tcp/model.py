#!/usr/bin/env python3
"""Ring-buffer reference model for the tcp (packet reassembly) problem.

Physical slot = seq & 15 (collision-free direct index over the 16-wide live
window [waiting, waiting+15]). fmask = 16-bit filled-flags. bank = 16 values.

Per packet:
  1. read seq,val; off = seq - waiting; if off>=16 -> output -1 and HALT.
  2. slot = seq & 15; bank[slot]=val; fmask |= (1<<slot).
  3. DRAIN: while fmask bit (waiting&15) set: output bank[waiting&15];
     clear bit; waiting++.
"""


def run_stream(packets):
    """packets: list of (seq, val). Returns (outputs, halted)."""
    waiting = 0
    fmask = 0
    bank = [0] * 16
    out = []
    for seq, val in packets:
        off = seq - waiting
        if off >= 16:
            out.append(-1)
            return out, True
        slot = seq & 15
        bank[slot] = val
        fmask |= (1 << slot)
        while fmask & (1 << (waiting & 15)):
            out.append(bank[waiting & 15])
            fmask &= ~(1 << (waiting & 15))
            waiting += 1
    return out, False


def run_rounds(rounds):
    """rounds as in the spec: round 0 in=[n,seq,val], later in=[seq,val].
    Returns per-round output lists (to compare against each round's out)."""
    waiting = 0
    fmask = 0
    bank = [0] * 16
    per_round = []
    halted = False
    for j, r in enumerate(rounds):
        if halted:
            per_round.append([])
            continue
        vals = [int(x) for x in r['in']]
        if j == 0:
            n, seq, val = vals
        else:
            seq, val = vals
        ro = []
        off = seq - waiting
        if off >= 16:
            ro.append(-1)
            per_round.append(ro)
            halted = True
            continue
        slot = seq & 15
        bank[slot] = val
        fmask |= (1 << slot)
        while fmask & (1 << (waiting & 15)):
            ro.append(bank[waiting & 15])
            fmask &= ~(1 << (waiting & 15))
            waiting += 1
        per_round.append(ro)
    return per_round


if __name__ == '__main__':
    import json
    import sys
    d = json.load(open('scratchpad/tcp_problem.json'))
    ok = True
    for i, c in enumerate(d['publicTestData']):
        rounds = c['rounds']
        got = run_rounds(rounds)
        # flatten expected + got for whole-stream comparison
        exp_flat = [int(x) for r in rounds for x in r['out']]
        got_flat = [x for ro in got for x in ro]
        # also per-round check
        per_ok = all([int(x) for x in rounds[j]['out']] == got[j] for j in range(len(rounds)))
        status = 'OK' if (exp_flat == got_flat and per_ok) else 'FAIL'
        if status == 'FAIL':
            ok = False
        print(f'case {i} {c["name"]:30s} {status}')
        if status == 'FAIL':
            print('  expected flat:', exp_flat)
            print('  got flat     :', got_flat)
            for j in range(len(rounds)):
                e = [int(x) for x in rounds[j]['out']]
                if e != got[j]:
                    print(f'    round {j} in={rounds[j]["in"]} exp={e} got={got[j]}')
    sys.exit(0 if ok else 1)

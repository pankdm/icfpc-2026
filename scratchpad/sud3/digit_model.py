#!/usr/bin/env python3
"""Model for a DIGIT-INDEXED sudoku auditor, and its per-cell cost under the real ISA.

Current architecture (ringfree4) is GROUP-indexed: 27 group masks of 9 bits, so a cell
(r,c,v) touches three groups that live in three different men, and the per-cell protocol
to reach them costs ~44 compute ops on the critical man (85 ticks/cell measured).

Digit-indexed layout instead: one 27-bit word PER DIGIT
    bits  0.. 8  rows that already contain this digit
    bits  9..17  columns that already contain this digit
    bits 18..26  boxes that already contain this digit
A cell (r,c,v) then touches EXACTLY ONE word (digit v), and all three checks are a single
AND against a 3-bit mask. 27 bits/digit means two digits fit in one 63-bit register, so
five keepers hold all nine digits.

The ISA constraint that shapes everything (verified in interpreter/machine.py and
interp/src/lib.rs): `b` `m` `q` `]` WRITE the backpack and only `d`/`a`/`x` read it, as a
branch — there is no BP->A move. So a man has two usable registers, and a man holding
state in B has only A free. A keeper can therefore test (A &= B) and set (A |= B; M) but
cannot build its own mask: masks must arrive over a pipe, prebuilt.

Run: python3 solutions/sudoku-validity/digit_model.py
"""
import json
import os
import sys

REPO = os.path.abspath(__file__).split('/solutions/')[0]


def box_of(r, c):
    return 3 * (r // 3) + c // 3


def audit(cells, digits_per_keeper=2):
    """Replay one test case. Returns (outputs, keeper_touch_counts)."""
    state = [0] * 9                      # per digit: 27-bit word
    outputs, touches = [], [0] * ((9 + digits_per_keeper - 1) // digits_per_keeper)
    for r, c, v in cells:
        d = v - 1
        mask = (1 << r) | (1 << (9 + c)) | (1 << (18 + box_of(r, c)))
        touches[d // digits_per_keeper] += 1
        if state[d] & mask:              # duplicate in row, column or box
            outputs.append(0)
            break                        # the case ends on the first 0
        state[d] |= mask
        outputs.append(1)
    return outputs, touches


# Per-cell critical path, in ticks, for the two architectures. Each entry is
# (stage, ticks, why) — stages that run on different men in the same tick are merged.
DIGIT_PATH = [
    ("reader: r, c, v", 3, "three blocking receives, one value per tick"),
    ("reader: pack + broadcast", 3, "S sends one word to the three mask lanes"),
    ("pipe hop", 1, "minimum 2-cell pipe"),
    ("mask lanes (parallel)", 8, "walk a 9-lane jump table to the literal for 2^r / 2^(9+c) / 2^(18+b);"
                                 " avg 4 lanes + literal load. Sidesteps the 2-register squeeze"),
    ("pipe hop", 1, ""),
    ("keeper test+set", 6, "tester: r,&,send verdict | setter: r,|,M — one delivery each"),
    ("pipe hop", 1, ""),
    ("merger -> O", 4, "OR three verdicts, emit"),
    ("out-pipe + round gate", 3, "output must land before the next cell is released"),
]


def main():
    spec = json.load(open(os.path.join(REPO, "tests", "sudoku-validity.json")))
    print("=== correctness of the digit-indexed rule on the public cases ===")
    all_ok = True
    for tc in spec["publicTestData"]:
        rounds = tc.get("rounds") or [tc]
        cells = [tuple(int(x) for x in rnd["in"]) for rnd in rounds]
        expected = [int(rnd["out"][0]) for rnd in rounds if rnd.get("out")]
        got, touches = audit(cells)
        ok = got == expected[:len(got)] and len(got) == len(expected)
        all_ok &= ok
        print(f"  {('OK ' if ok else 'FAIL')} {tc['name'][:34]:36} {len(cells):>3} cells  "
              f"-> {len(got)} outputs, ends {got[-1] if got else '-'}")
        if not ok:
            print(f"       expected {expected[:12]}\n       got      {got[:12]}")
    print(f"\n  digit-indexed rule reproduces every public case: {all_ok}")

    total = sum(t for _, t, _ in DIGIT_PATH)
    print(f"\n=== projected per-cell critical path (digit-indexed) ===")
    for stage, ticks, why in DIGIT_PATH:
        print(f"  {ticks:>3}  {stage:26} {why}")
    print(f"  {total:>3}  TOTAL per cell")

    # measured baseline, from sim/xray.js on ringfree4-tuned, dominant case 0 (81 cells)
    cur_ticks_per_cell = 6900 / 81
    cur_score = 7_125_678
    cur_box, cur_avg = 1764, 4040
    new_avg = cur_avg * total / cur_ticks_per_cell
    print(f"\n=== what that is worth ===")
    print(f"  now:  {cur_ticks_per_cell:.0f} ticks/cell, box {cur_box} -> {cur_score:,}")
    for box, label in ((1764, "same box"), (1156, "34x34"), (900, "30x30"), (676, "26x26")):
        print(f"  new:  {total} ticks/cell, box {box:>4} ({label:8}) -> {box * new_avg:>12,.0f}")
    print(f"\n  leader 1,355,571 | us 7,230,636 (rank 28/64)")
    print("  NOTE: men count barely drops (reader + 3 mask lanes + 5 keeper pairs + merger),")
    print("  and each man needs its own room, so the box will NOT shrink the way I first said.")


if __name__ == "__main__":
    main()

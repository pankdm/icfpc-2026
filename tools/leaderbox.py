"""leaderbox.py — recover a rival's BOX and TICKS from their score alone, by factoring.

`score = max(w,h)^2 * avgTicks` and `avgTicks = total_ticks / cases`, so

    score * cases = box * total_ticks

with `box` a perfect square and `total_ticks` an integer. Factor `score * cases`, enumerate
its square divisors, and any candidate box must be among them. Very often EXACTLY ONE square
divisor lands in a plausible side range (30..1500), which pins the rival's grid size and
their tick count with no guessing at all.

VALIDATION. Run against our own LLM submission it recovers box 540,225 = 735^2 and
avgTicks 11,026,620.5, matching `tools/submissions.py` exactly.

WHY IT MATTERS. The board shows one number, so a 30x gap looks like one undifferentiated
wall. Split it and the gap becomes a work item. Measured 2026-07-27:

    problem            leader box   leader ticks     our box    our ticks   box gap  tick gap
    LLM                  193x193       5,509,238     735x735   11,026,620    14.5x      2.0x
    Subset Sum            67x67           45,984     449x449      117,382    44.9x      2.6x
    Matrix Multiply       32x32            8,125      61x61        13,959     3.6x      1.7x
    Grade Book            39x39           17,142      64x64        39,731     2.7x      2.3x
    Snake                 53x53            7,875      74x74        11,574     1.9x      1.5x
    Packet Reassembly     24x24              367      24x24          812     1.0x      2.2x

Read that column: **every tick gap is 1.5-2.6x and every box gap is bigger.** Nobody is
beating us on cleverness-per-tick; they are beating us on GEOMETRY. On Packet Reassembly the
boxes are already identical and the whole 2.2x is ticks. On LLM the leader fits 193 rows where
our compiled-CFG ribbon needs 735 -- and we have 194 basic blocks, i.e. they spend ONE ROW PER
BLOCK with no wrap rows and no 3-row branch groups.

CAVEATS.
  * The board ROUNDS in its display. Use the raw float from the standings API (this tool does);
    factoring the rounded integer is meaningless -- 205213603601 is squarefree, while the true
    205213603601.35712 x 28 = 5,745,980,900,838 = 2 * 3 * 193^2 * 829 * 31013.
  * Only trust a result when exactly ONE square divisor is in range; otherwise it is ambiguous
    and this tool prints all candidates rather than picking one.
  * `cases` must be the case count the score was averaged over (casesTotal from standings).

    python3 tools/leaderbox.py [--slug X] [--all] [--min-side N] [--max-side N]
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

TEAM = "Snakes, Monkeys, and Two Smoking Lambdas"


def factor(n):
    f = {}
    m, d = n, 2
    while d * d <= m:
        while m % d == 0:
            f[d] = f.get(d, 0) + 1
            m //= d
        d += 1 if d == 2 else 2
    if m > 1:
        f[m] = f.get(m, 0) + 1
    return f


def square_divisors(n, lo, hi):
    divs = [1]
    for p, e in factor(n).items():
        divs = [x * p ** k for x in divs for k in range(e + 1)]
    return sorted({d for d in divs
                   if math.isqrt(d) ** 2 == d and lo <= math.isqrt(d) <= hi})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default=None, help="one problem (default: all we trail)")
    ap.add_argument("--all", action="store_true", help="include ambiguous results")
    ap.add_argument("--min-side", type=int, default=20)
    ap.add_argument("--max-side", type=int, default=2000)
    args = ap.parse_args()

    print(f"{'problem':20s} {'leader':>10} {'leader ticks':>15} {'ours':>10} "
          f"{'our ticks':>14} {'box':>7} {'ticks':>7}")
    print("-" * 92)
    for problem in lib.list_problems():
        if problem.get("status") != "graded":
            continue
        if args.slug and problem["slug"] != args.slug:
            continue
        rows = lib.problem_standings(problem["id"]).get("rows", [])
        full = [r for r in rows
                if r.get("score") and r.get("casesPassed") == r.get("casesTotal")]
        if not full:
            continue
        full.sort(key=lambda r: r["score"])
        leader = full[0]
        ours = next((r for r in full if TEAM in (r.get("teamName") or "")), None)
        cases = leader.get("casesTotal") or 1

        cands = square_divisors(round(leader["score"] * cases),
                                args.min_side, args.max_side)
        if len(cands) != 1:
            if args.all:
                sides = ", ".join(str(math.isqrt(c)) for c in cands) or "none"
                print(f"{problem['name'][:20]:20s} AMBIGUOUS — candidate sides: {sides}")
            continue
        box = cands[0]
        side = math.isqrt(box)
        lt = leader["score"] / box

        if ours is leader or not ours:
            print(f"{problem['name'][:20]:20s} {f'{side}x{side}':>10} {lt:>15,.0f}"
                  f"{'  (we lead)':>33}")
            continue

        ocands = square_divisors(round(ours["score"] * cases),
                                 args.min_side, args.max_side)
        obox = ocands[0] if len(ocands) == 1 else None
        if obox is None:
            print(f"{problem['name'][:20]:20s} {f'{side}x{side}':>10} {lt:>15,.0f}"
                  f"{'  (our box ambiguous — read it off the .man)':>46}")
            continue
        oside = math.isqrt(obox)
        ot = ours["score"] / obox
        print(f"{problem['name'][:20]:20s} {f'{side}x{side}':>10} {lt:>15,.0f} "
              f"{f'{oside}x{oside}':>10} {ot:>14,.0f} {obox / box:>6.1f}x {ot / lt:>6.1f}x")

    print()
    print("A tick gap near 1 with a large box gap means the rival is not out-computing us —")
    print("they are out-PACKING us, and the work is geometry, not algorithms.")


if __name__ == "__main__":
    main()

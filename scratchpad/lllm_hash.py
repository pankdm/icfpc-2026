"""Search a two-stage perfect hash that also separates '|' (124) as its own slot.

Adding `|` to the character table lets the left/right border cells of an LLLM
program go through the ordinary interior decode, so `mid_row` becomes one
uniform loop over W cells instead of border/interior/border -- two fewer static
copies of `emit_border_cell`, i.e. eight fewer narrow-band (cold) ops.

Both multipliers have to be a product of single digits, because the placer may
only ever be handed a one-digit ('#', k): a multi-digit constant is despined
into `d M d *`, which clobbers B.
"""
CHARS = {32: 0, 64: 0, 94: 1, 62: 2, 118: 3, 60: 4, 88: 5, 77: 6,
         43: 7, 45: 8, 72: 9, 124: 10}
DIGITS = list(range(48, 58))

PROD = sorted({a * b for a in range(1, 10) for b in range(1, 10)} |
              {a * b * c for a in range(1, 10) for b in range(1, 10)
               for c in range(1, 10)})


def factor(k):
    """cheapest chain of single-digit multipliers giving k, or None."""
    for a in range(2, 10):
        if k == a:
            return [a]
    for a in range(2, 10):
        if k % a == 0 and 2 <= k // a <= 9:
            return [k // a, a]
    for a in range(2, 10):
        if k % a == 0:
            rest = factor(k // a)
            if rest and len(rest) <= 2:
                return [a] + rest
    return None


def main():
    best = []
    for m1 in PROD:
        if factor(m1) is None and m1 != 1:
            continue
        for s1 in range(0, 9):
            stage1 = {}
            for asc in list(CHARS) + DIGITS:
                stage1[asc] = (asc * m1) >> s1
            for m2 in PROD:
                if factor(m2) is None and m2 != 1:
                    continue
                for s2 in range(0, 9):
                    slots = {}
                    ok = True
                    for asc, cl in CHARS.items():
                        h = ((stage1[asc] * m2) >> s2) & 15
                        if h in slots and slots[h] != cl:
                            ok = False
                            break
                        slots[h] = cl
                    if not ok:
                        continue
                    for asc in DIGITS:
                        h = ((stage1[asc] * m2) >> s2) & 15
                        if slots.get(h, 11) != 11:
                            ok = False
                            break
                        slots[h] = 11
                    if not ok:
                        continue
                    cost = (len(factor(m1) or []) + len(factor(m2) or []))
                    best.append((cost, len(set(slots)), m1, s1, m2, s2))
    best.sort()
    for row in best[:15]:
        print(row, 'f1', factor(row[2]), 'f2', factor(row[4]))
    print("total solutions:", len(best))


if __name__ == '__main__':
    main()
